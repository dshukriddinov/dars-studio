"""Buyruqlar (undo/redo, TZ FR-14, D-10). Har o'zgarish = loyiha maydon(lar)ining eski va yangi qiymati.

Buyruq JSON'ga to'liq seriyalanadi, shuning uchun tarix diskda saqlanadi va dastur qayta ochilganda ham undo ishlaydi.
Maydon yo'li nuqta bilan: "slide_spans", "key.tolerance", "cuts.3.status".
Domen amallari (chegarani surish, kesishni tasdiqlash ...) shu `Change` lar ro'yxatini quradi.
"""

import json
from collections.abc import Sequence
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
        if store.history_file.is_file():
            h = json.loads(store.history_file.read_text(encoding="utf-8"))
            self.undo_stack = [Command.model_validate(c) for c in h.get("undo", [])]
            self.redo_stack = [Command.model_validate(c) for c in h.get("redo", [])]

    def _persist(self) -> None:
        atomic_write_json(self.store.history_file, {
            "undo": [c.model_dump(mode="json") for c in self.undo_stack[-HISTORY_LIMIT:]],
            "redo": [c.model_dump(mode="json") for c in self.redo_stack[-HISTORY_LIMIT:]],
        })
        self.store.save(self.project)

    def execute(self, cmd: Command) -> Project:
        self.project = _apply(self.project, cmd.changes, "new")
        self.undo_stack = [*self.undo_stack, cmd][-HISTORY_LIMIT:]
        self.redo_stack = []
        self._persist()
        return self.project

    def do(self, label: str, values: dict[str, Any]) -> Project:
        return self.execute(make(self.project, label, values))

    def undo(self) -> Command | None:
        if not self.undo_stack:
            return None
        cmd = self.undo_stack[-1]
        self.project = _apply(self.project, list(reversed(cmd.changes)), "old")
        self.undo_stack.pop()
        self.redo_stack.append(cmd)
        self._persist()
        return cmd

    def redo(self) -> Command | None:
        if not self.redo_stack:
            return None
        cmd = self.redo_stack[-1]
        self.project = _apply(self.project, cmd.changes, "new")
        self.redo_stack.pop()
        self.undo_stack.append(cmd)
        self._persist()
        return cmd
