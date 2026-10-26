"""Vazifani alohida jarayonda bajarish (D-04, CLAUDE.md 5-qoida): jarayon tugaganda VRAM to'liq bo'shaydi,
model yiqilsa asosiy dastur yiqilmaydi. B4 da minimal; navbat va rejalashtiruvchi — B7.

Protokol (stdout, qatorlar): `PROGRESS <0..1>`, `LOG <matn>`, `RESULT <json>`. Xato: chiqish kodi != 0, stderr.
    python -m darsstudio.jobs.worker <vazifa> <json-argumentlar>
"""

import importlib
import json
import subprocess
import sys
from collections.abc import Callable
from typing import Any

TASKS = {
    "asr_raw": "darsstudio.asr.run:task",   # WAV yo'li bilan; navbatdagi "asr" (loyiha) — jobs/tasks.py
    "vram_probe": "darsstudio.asr.run:vram_task",
}


class WorkerError(RuntimeError):
    pass


class Emit:
    def progress(self, x: float) -> None:
        print(f"PROGRESS {x:.4f}", flush=True)

    def log(self, msg: str) -> None:
        print("LOG " + msg.replace("\n", " "), flush=True)


def run_isolated(task: str, args: dict[str, Any], on_progress: Callable[[float], None] | None = None,
                 on_log: Callable[[str], None] | None = None) -> dict[str, Any]:
    proc = subprocess.Popen([sys.executable, "-m", "darsstudio.jobs.worker", task, json.dumps(args)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    result: dict[str, Any] | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        kind, _, rest = line.rstrip("\n").partition(" ")
        if kind == "PROGRESS" and on_progress:
            on_progress(float(rest))
        elif kind == "LOG" and on_log:
            on_log(rest)
        elif kind == "RESULT":
            result = json.loads(rest)
    err = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0 or result is None:
        raise WorkerError(f"'{task}' vazifasi xato bilan tugadi (kod {proc.returncode}): {err.strip()[-1500:]}")
    return result


def resolve(task: str) -> Callable[[dict[str, Any], Emit], dict[str, Any]]:
    if task in TASKS:
        mod, fn = TASKS[task].split(":")
        return getattr(importlib.import_module(mod), fn)  # type: ignore[no-any-return]
    from darsstudio.jobs import tasks
    return getattr(tasks, tasks.TASKS[task][0])  # type: ignore[no-any-return]


def main(argv: list[str]) -> int:
    from darsstudio import power
    task, args = argv[0], json.loads(argv[1])
    power.keep_awake(True)  # HW-6: vazifa davomida tizim uxlamasin (jarayon tugashi bilan bekor bo'ladi)
    out = resolve(task)(args, Emit())
    print("RESULT " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
