"""FR-20 / B7 DoD: resurs qoidalari buzilmaydi (3 loyiha bir vaqtda), to'xtatish -> 'toʻxtatildi' va resume
checkpoint'dan, xatoda 1 marta qayta urinish, bog'liqliklar."""

import threading
import time
from pathlib import Path

from darsstudio.jobs.queue_db import Queue
from darsstudio.jobs.resources import LIMITS, VRAM_BUDGET_MB, Resources, fits
from darsstudio.jobs.scheduler import Scheduler


def test_fits_rules() -> None:
    assert fits(Resources(vram_mb=6000), [Resources(vram_mb=6000)])
    assert not fits(Resources(vram_mb=6000), [Resources(vram_mb=6000), Resources(vram_mb=1001)])
    assert not fits(Resources(nvenc=1), [Resources(nvenc=1), Resources(nvenc=1)])
    assert not fits(Resources(nvdec=1), [Resources(nvdec=1)])
    assert not fits(Resources(pptx=1), [Resources(pptx=1)])
    assert not fits(Resources(cpu_heavy=1), [Resources(cpu_heavy=1), Resources(cpu_heavy=1)])
    assert fits(Resources(exclusive=True), []) and not fits(Resources(exclusive=True), [Resources()])
    assert not fits(Resources(), [Resources(exclusive=True)])


def run_until_idle(s: Scheduler, timeout: float = 120, on_tick: object = None) -> None:
    t0 = time.time()
    while not s.idle():
        s.tick()
        if callable(on_tick):
            on_tick()
        assert time.time() - t0 < timeout, "rejalashtiruvchi tugamadi"
        time.sleep(0.05)


def test_three_projects_respect_limits(tmp_path: Path) -> None:
    q = Queue(tmp_path / "queue.db")
    s = Scheduler(q, tmp_path / "logs")
    mix = [Resources(vram_mb=6000), Resources(vram_mb=5000, nvenc=1), Resources(pptx=1, cpu_heavy=1),
           Resources(cpu_heavy=1), Resources(nvenc=1), Resources(exclusive=True)]
    for proj in ("a", "b", "c"):
        prev = None
        for i, r in enumerate(mix):
            jid = q.add("sleep", str(tmp_path / proj), {"seconds": 0.4, "resources": r.model_dump()}, r,
                        [prev] if prev and i == 3 else None)
            prev = jid
    seen_parallel = [0]

    def check() -> None:
        running = [j.resources for j in q.list(statuses=("ishlanmoqda",))]
        seen_parallel[0] = max(seen_parallel[0], len(running))
        assert sum(r.vram_mb for r in running) <= VRAM_BUDGET_MB
        for k, lim in LIMITS.items():
            assert sum(getattr(r, k) for r in running) <= lim, (k, running)
        if any(r.exclusive for r in running):
            assert len(running) == 1

    run_until_idle(s, on_tick=check)
    jobs = q.list()
    assert all(j.status == "tayyor" for j in jobs), [(j.id, j.status, j.error) for j in jobs]
    assert seen_parallel[0] >= 2  # parallellik haqiqatan bo'ldi


def test_stop_and_resume_from_checkpoint(tmp_path: Path) -> None:
    q = Queue(tmp_path / "queue.db")
    s = Scheduler(q, tmp_path / "logs")
    mark = tmp_path / "mark.txt"
    jid = q.add("sleep", str(tmp_path), {"seconds": 4, "marker": str(mark)})
    s.tick()
    t0 = time.time()
    while q.get(jid).progress < 0.25 and time.time() - t0 < 30:
        time.sleep(0.05)
    pid = q.get(jid).pid
    s.stop(jid)
    j = q.get(jid)
    assert j.status == "toʻxtatildi"
    import psutil
    assert pid is not None and not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    done_before = float(mark.read_text())
    assert 0 < done_before < 1
    s.resume(jid)
    run_until_idle(s)
    j = q.get(jid)
    assert j.status == "tayyor" and j.result is not None and j.result["resumed_from"] == done_before


def test_retry_once_then_error_and_dependency(tmp_path: Path) -> None:
    q = Queue(tmp_path / "queue.db")
    s = Scheduler(q, tmp_path / "logs")
    bad = q.add("sleep", str(tmp_path), {"seconds": 0.1, "fail": True, "fail_message": "CUDA out of memory"})
    child = q.add("sleep", str(tmp_path), {"seconds": 0.1}, depends_on=[bad])
    run_until_idle(s)
    b = q.get(bad)
    assert b.status == "xato" and b.attempts == 2 and "out of memory" in (b.error or "")
    assert q.get(child).status == "xato"


def test_interrupted_jobs_requeued(tmp_path: Path) -> None:
    q = Queue(tmp_path / "queue.db")
    jid = q.add("sleep", str(tmp_path), {"seconds": 0.1})
    q.update(jid, status="ishlanmoqda", pid=999999)
    s = Scheduler(q, tmp_path / "logs")   # dastur qayta ochildi
    assert q.get(jid).status == "navbatda"
    run_until_idle(s)
    assert q.get(jid).status == "tayyor"


def test_scheduler_thread_stop(tmp_path: Path) -> None:
    q = Queue(tmp_path / "queue.db")
    s = Scheduler(q, tmp_path / "logs")
    jid = q.add("sleep", str(tmp_path), {"seconds": 30})
    stop = threading.Event()
    th = threading.Thread(target=s.run, args=(stop, 0.1))
    th.start()
    t0 = time.time()
    while q.get(jid).status != "ishlanmoqda" and time.time() - t0 < 20:
        time.sleep(0.05)
    stop.set()
    th.join(30)
    assert q.get(jid).status == "toʻxtatildi"
