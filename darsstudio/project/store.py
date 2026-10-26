"""Loyiha papkasi (TZ 8.4) va atomik saqlash. Loyiha holati faqat shu modul orqali yoziladi (CLAUDE.md, 12-qoida)."""

import json
import os
from pathlib import Path
from typing import Any

from darsstudio.project.migrations import migrate
from darsstudio.project.model import Project

CACHE_DIRS = ("media", "audio", "asr", "slides", "sync", "eyepatch", "render")


def atomic_write_text(path: Path, text: str) -> None:
    """tmp + fsync + os.replace: yarim yozilgan fayl qolmaydi (elektr o'chsa ham eski yoki yangi nusxa)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1))


class ProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @property
    def project_file(self) -> Path:
        return self.root / "project.json"

    @property
    def history_file(self) -> Path:
        return self.root / "history" / "history.json"

    def cache(self, sub: str) -> Path:
        return self.root / "cache" / sub

    def create_dirs(self) -> None:
        for d in CACHE_DIRS:
            self.cache(d).mkdir(parents=True, exist_ok=True)
        for d in ("history", "exports", "logs"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self.project_file.is_file()

    def save(self, project: Project) -> None:
        atomic_write_text(self.project_file, project.model_dump_json(indent=1))

    def load(self) -> Project:
        try:
            data = json.loads(self.project_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise FileNotFoundError(f"Loyiha topilmadi: {self.root}. Papkani tekshiring.") from None
        return Project.model_validate(migrate(data))
