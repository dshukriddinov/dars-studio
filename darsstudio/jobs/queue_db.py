"""Global navbat (FR-20, D-10): SQLite `queue.db` (WAL). Holatlar: navbatda, ishlanmoqda, tayyor, xato, toʻxtatildi."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from darsstudio.jobs.resources import Resources

Status = Literal["navbatda", "ishlanmoqda", "tayyor", "xato", "toʻxtatildi"]
ACTIVE: tuple[Status, ...] = ("navbatda", "ishlanmoqda")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  project TEXT NOT NULL,
  args TEXT NOT NULL DEFAULT '{}',
  resources TEXT NOT NULL DEFAULT '{}',
  depends_on TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'navbatda',
  progress REAL NOT NULL DEFAULT 0,
  message TEXT NOT NULL DEFAULT '',
  attempts INTEGER NOT NULL DEFAULT 0,
  wait_gpu_idle INTEGER NOT NULL DEFAULT 0,
  pid INTEGER,
  log_path TEXT,
  result TEXT,
  error TEXT,
  created REAL NOT NULL,
  started REAL,
  finished REAL
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
"""


class Job(BaseModel):
    id: int
    type: str
    project: str
    args: dict[str, Any]
    resources: Resources
    depends_on: list[int]
    status: Status
    progress: float
    message: str
    attempts: int
    wait_gpu_idle: bool
    pid: int | None
    log_path: str | None
    result: dict[str, Any] | None
    error: str | None
    created: float
    started: float | None
    finished: float | None


class Queue:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _job(r: sqlite3.Row) -> Job:
        d = dict(r)
        for k in ("args", "resources", "depends_on"):
            d[k] = json.loads(d[k])
        d["result"] = json.loads(d["result"]) if d["result"] else None
        d["wait_gpu_idle"] = bool(d["wait_gpu_idle"])
        return Job.model_validate(d)

    def add(self, type_: str, project: str, args: dict[str, Any] | None = None, resources: Resources | None = None,
            depends_on: list[int] | None = None) -> int:
        with self._conn() as c:
            cur = c.execute("INSERT INTO jobs(type, project, args, resources, depends_on, created) "
                            "VALUES (?,?,?,?,?,?)",
                            (type_, project, json.dumps(args or {}, ensure_ascii=False),
                             (resources or Resources()).model_dump_json(), json.dumps(depends_on or []), time.time()))
            return int(cur.lastrowid or 0)

    def get(self, job_id: int) -> Job:
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if r is None:
            raise KeyError(job_id)
        return self._job(r)

    def list(self, project: str | None = None, statuses: tuple[str, ...] | None = None) -> list[Job]:
        q, a = "SELECT * FROM jobs WHERE 1=1", []
        if project:
            q += " AND project=?"
            a.append(project)
        if statuses:
            q += f" AND status IN ({','.join('?' * len(statuses))})"
            a += list(statuses)
        with self._conn() as c:
            return [self._job(r) for r in c.execute(q + " ORDER BY id", a).fetchall()]

    def update(self, job_id: int, **kw: Any) -> None:
        for k in ("result",):
            if k in kw and kw[k] is not None and not isinstance(kw[k], str):
                kw[k] = json.dumps(kw[k], ensure_ascii=False)
        sets = ", ".join(f"{k}=?" for k in kw)
        with self._conn() as c:
            c.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*kw.values(), job_id))

    def requeue_interrupted(self) -> int:
        """Dastur/kompyuter qayta ishga tushganda: 'ishlanmoqda' qolganlar navbatga qaytadi (checkpoint'dan davom)."""
        with self._conn() as c:
            return c.execute("UPDATE jobs SET status='navbatda', pid=NULL WHERE status='ishlanmoqda'").rowcount
