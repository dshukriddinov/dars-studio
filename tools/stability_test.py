"""Barqarorlik sinovi (AC-11, NFR-04/05): N loyiha navbat orqali to'liq siklda (tayyorlash -> eksport render);
birinchi loyihaning render vazifasi o'rtasida worker jarayoni o'ldiriladi (TerminateProcess) va qayta navbatga
qo'yiladi — tayyor chunk'lardan davom etishi, crash va progress yo'qolishi bo'lmasligi tekshiriladi.

    python tools/stability_test.py VIDEO SLAYDLAR [--n 3] [--workdir DIR] [--kill-at 0.4]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import psutil

from darsstudio.jobs.queue_db import Queue
from darsstudio.jobs.scheduler import Scheduler, enqueue_prepare
from darsstudio.jobs.tasks import resources_for
from darsstudio.project import importer


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("slides")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--workdir", default="workdir/stability")
    ap.add_argument("--kill-at", type=float, default=0.4)
    ap.add_argument("--no-eye", action="store_true")
    a = ap.parse_args()
    wd = Path(a.workdir).resolve()
    wd.mkdir(parents=True, exist_ok=True)
    q = Queue(wd / "queue.db")
    s = Scheduler(q, wd / "logs")
    tag = time.strftime("%H%M%S")
    renders = []
    t0 = time.time()
    for i in range(a.n):
        st = importer.import_project(Path(a.video), Path(a.slides), "demo", wd, name=f"s{tag}_{i}", make_proxy=False)
        prep = enqueue_prepare(q, str(st.root), eye=not a.no_eye)
        cuts_job = prep[-1]
        args = {"out": str(st.root / "exports" / "stability.mp4"), "profile": "web"}
        renders.append(q.add("render", str(st.root), args, resources_for("render", args),
                             [cuts_job] + ([prep[3]] if not a.no_eye else [])))
    killed = False
    peak_ram = 0.0
    while not s.idle():
        s.tick()
        peak_ram = max(peak_ram, sum(p.memory_info().rss for p in psutil.process_iter(["name"])
                                     if (p.info["name"] or "").lower().startswith("python")) / 2**30)
        j = q.get(renders[0])
        if not killed and j.status == "ishlanmoqda" and j.progress >= a.kill_at and j.pid:
            print(f"[{time.time() - t0:6.0f} s] render #{j.id} {j.progress:.0%} da worker o'ldirilmoqda", flush=True)
            for c in psutil.Process(j.pid).children(recursive=True) + [psutil.Process(j.pid)]:
                c.kill()
            killed = True
        time.sleep(0.5)
    jobs = q.list()
    bad = [(j.id, j.type, j.status, (j.error or "")[-200:]) for j in jobs if j.status != "tayyor"]
    out = {"projects": a.n, "jobs": len(jobs), "not_ok": bad, "killed": killed,
           "render_attempts": q.get(renders[0]).attempts, "wall_s": round(time.time() - t0),
           "python_ram_peak_gb": round(peak_ram, 1)}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if not bad and killed else 1


if __name__ == "__main__":
    sys.exit(main())
