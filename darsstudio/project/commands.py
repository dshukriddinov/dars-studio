"""Buyruqlar (undo/redo, TZ FR-14, D-10). Har o'zgarish = loyiha maydon(lar)ining eski va yangi qiymati.

Buyruq JSON'ga to'liq seriyalanadi, shuning uchun tarix diskda saqlanadi va dastur qayta ochilganda ham undo ishlaydi.
Maydon yo'li nuqta bilan: "slide_spans", "key.tolerance", "cuts.3.status".
Domen amallari (chegarani surish, kesishni tasdiqlash ...) shu `Change` lar ro'yxatini quradi.
"""

import contextlib
import json
import os
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from darsstudio.project.model import Project
from darsstudio.project.store import ProjectStore, atomic_write_json

HISTORY_LIMIT = 500  # TZ 8.4


class Change(BaseModel):
    path: str
    old: Any
    new: Any


class Command(BaseModel):
    label: str
    changes: list[Change]


def _get(data: Any, path: str) -> Any:
    for k in path.split("."):
        data = data[int(k)] if isinstance(data, list) else data[k]
    return data


def _set(data: Any, path: str, value: Any) -> None:
    *parents, last = path.split(".")
    for k in parents:
        data = data[int(k)] if isinstance(data, list) else data[k]
    if isinstance(data, list):
        data[int(last)] = value
    else:
        data[last] = value


def make(project: Project, label: str, values: dict[str, Any]) -> Command:
    """{yo'l: yangi qiymat} dan buyruq. Qiymatlar JSON ko'rinishida (model_dump(mode="json") kabi)."""
    data = project.model_dump(mode="json")
    return Command(label=label, changes=[Change(path=p, old=_get(data, p), new=v) for p, v in values.items()])


def _apply(project: Project, changes: Sequence[Change], attr: str) -> Project:
    data = project.model_dump(mode="json")
    for c in changes:
        _set(data, c.path, getattr(c, attr))
    return Project.model_validate(data)  # invariantlar shu yerda tekshiriladi; buzilsa ValueError, holat o'zgarmaydi


class CommandStack:
    """Loyiha + tarix. Har amal: avval tarix, keyin project.json yoziladi. Ikkinchisidan oldin uzilsa, undo eski
    qiymatni (u allaqachon joriy) qayta yozadi — zararsiz."""

    def __init__(self, store: ProjectStore, project: Project | None = None) -> None:
        self.store = store
        self.project = project if project is not None else store.load()
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []
        self._load_history()

    def _load_history(self) -> None:
        if self.store.history_file.is_file():
            h = json.loads(self.store.history_file.read_text(encoding="utf-8"))
            self.undo_stack = [Command.model_validate(c) for c in h.get("undo", [])]
            self.redo_stack = [Command.model_validate(c) for c in h.get("redo", [])]

    def _reload(self) -> None:
        """Bir loyihani bir nechta jarayon (API, navbat vazifalari) o'zgartiradi: har amal diskdagi so'nggi holat
        ustiga qo'llanadi, aks holda eski nusxa boshqa jarayonning natijasini o'chirib yuboradi (lost update)."""
        if self.store.exists():
            self.project = self.store.load()
        self._load_history()

    def _persist(self) -> None:
        atomic_write_json(self.store.history_file, {
            "undo": [c.model_dump(mode="json") for c in self.undo_stack[-HISTORY_LIMIT:]],
            "redo": [c.model_dump(mode="json") for c in self.redo_stack[-HISTORY_LIMIT:]],
        })
        self.store.save(self.project)

    def execute(self, cmd: Command) -> Project:
        with project_lock(self.store.root):
            self._reload()
            self.project = _apply(self.project, cmd.changes, "new")
            self.undo_stack = [*self.undo_stack, cmd][-HISTORY_LIMIT:]
            self.redo_stack = []
            self._persist()
        return self.project

    def do(self, label: str, values: dict[str, Any]) -> Project:
        with project_lock(self.store.root):
            self._reload()
            cmd = make(self.project, label, values)   # eski qiymatlar — so'nggi holatdan
            self.project = _apply(self.project, cmd.changes, "new")
            self.undo_stack = [*self.undo_stack, cmd][-HISTORY_LIMIT:]
            self.redo_stack = []
            self._persist()
        return self.project

    def undo(self) -> Command | None:
        with project_lock(self.store.root):
            self._reload()
            if not self.undo_stack:
                return None
            cmd = self.undo_stack[-1]
            self.project = _apply(self.project, list(reversed(cmd.changes)), "old")
            self.undo_stack.pop()
            self.redo_stack.append(cmd)
            self._persist()
        return cmd

    def redo(self) -> Command | None:
        with project_lock(self.store.root):
            self._reload()
            if not self.redo_stack:
                return None
            cmd = self.redo_stack[-1]
            self.project = _apply(self.project, cmd.changes, "new")
            self.redo_stack.pop()
            self.undo_stack.append(cmd)
            self._persist()
        return cmd


STALE_LOCK_S = 60.0


@contextlib.contextmanager
def project_lock(root: Path, timeout: float = 60.0) -> Iterator[None]:
    """Jarayonlararo qulf: project.lock (O_EXCL). Jarayon o'ldirilib qolgan eski qulf (> 60 s) olib tashlanadi."""
    lock = Path(root) / "project.lock"
    t0 = time.monotonic()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > STALE_LOCK_S:
                    lock.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() - t0 > timeout:
                raise TimeoutError(f"Loyiha band (project.lock): {root}") from None
            time.sleep(0.02)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)
