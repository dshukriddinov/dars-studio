"""Rejalashtiruvchi (FR-20, D-04): navbatdagi vazifalarni resurs qoidasi va bog'liqliklar bo'yicha alohida jarayonlarda
ishga tushiradi; progress navbat bazasiga yoziladi; to'xtatish — jarayon daraxti o'ldiriladi; xatoda 1 marta qayta
urinish (VRAM yetishmasa — boshqa GPU vazifalar tugashini kutib)."""

import json
import logging
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

from darsstudio.jobs.queue_db import Job, Queue
from darsstudio.jobs.resources import fits

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 2  # birinchi urinish + 1 avtomatik qayta urinish
VRAM_ERRORS = ("out of memory", "CUDA_ERROR_OUT_OF_MEMORY", "cudaErrorMemoryAllocation")


def kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = parent.children(recursive=True) + [parent]
    for p in procs:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=10)


class Scheduler:
    def __init__(self, queue: Queue, log_dir: Path, on_update: Callable[[Job], None] | None = None) -> None:
        self.q = queue
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.on_update = on_update
        self.procs: dict[int, subprocess.Popen[str]] = {}
        self._lock = threading.Lock()
        self.q.requeue_interrupted()

    # --- ishga tushirish ---
    def _deps_state(self, job: Job) -> str:
        sts = [self.q.get(d).status for d in job.depends_on]
        if any(s in ("xato", "toʻxtatildi") for s in sts):
            return "failed"
        return "ready" if all(s == "tayyor" for s in sts) else "wait"

    def tick(self) -> list[int]:
        """Bitta qadam: tugaganlarni yig'ish, yangilarini qabul qoidasi bo'yicha boshlash. Boshlanganlar id'lari."""
        self._reap()
        started = []
        with self._lock:
            running = [j for j in self.q.list(statuses=("ishlanmoqda",))]
            for job in self.q.list(statuses=("navbatda",)):
                dep = self._deps_state(job)
                if dep == "failed":
                    self.q.update(job.id, status="xato", error="bog'liq vazifa bajarilmadi", finished=time.time())
                    self._notify(job.id)
                    continue
                if dep == "wait":
                    continue
                gpu_busy = any(r.resources.vram_mb for r in running)
                if job.wait_gpu_idle and gpu_busy:
                    continue
                if not fits(job.resources, [r.resources for r in running]):
                    continue
                self._start(job)
                running.append(self.q.get(job.id))
                started.append(job.id)
        return started

    def _start(self, job: Job) -> None:
        log_path = self.log_dir / f"job_{job.id}.log"
        args = {**job.args, "project": job.project}
        proc = subprocess.Popen([sys.executable, "-m", "darsstudio.jobs.worker", job.type, json.dumps(args)],
                                stdout=subprocess.PIPE, stderr=open(log_path, "a", encoding="utf-8"),  # noqa: SIM115
                                encoding="utf-8", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.procs[job.id] = proc
        self.q.update(job.id, status="ishlanmoqda", pid=proc.pid, started=time.time(), log_path=str(log_path),
                      attempts=job.attempts + 1, message="", error=None)
        threading.Thread(target=self._pump, args=(job.id, proc), daemon=True).start()
        self._notify(job.id)

    def _pump(self, job_id: int, proc: "subprocess.Popen[str]") -> None:
        assert proc.stdout is not None
        last = 0.0
        for line in proc.stdout:
            kind, _, rest = line.rstrip("\n").partition(" ")
            if kind == "PROGRESS":
                p = float(rest)
                if p - last >= 0.01 or p >= 1:
                    last = p
                    self.q.update(job_id, progress=p)
                    self._notify(job_id)
            elif kind == "LOG":
                self.q.update(job_id, message=rest[:500])
                self._notify(job_id)
            elif kind == "RESULT":
                self.q.update(job_id, result=rest)

    def _reap(self) -> None:
        for job_id, proc in list(self.procs.items()):
            rc = proc.poll()
            if rc is None:
                continue
            del self.procs[job_id]
            time.sleep(0.05)  # _pump oxirgi qatorlarni yozib ulgursin
            job = self.q.get(job_id)
            if job.status == "toʻxtatildi":
                continue
            if rc == 0 and job.result is not None:
                self.q.update(job_id, status="tayyor", progress=1.0, finished=time.time(), error=None)
            else:
                err = Path(job.log_path).read_text(encoding="utf-8", errors="replace")[-2000:] if job.log_path else ""
                vram = any(e in err for e in VRAM_ERRORS)
                if job.attempts < MAX_ATTEMPTS:
                    self.q.update(job_id, status="navbatda", wait_gpu_idle=int(vram), error=err[-500:],
                                  message="qayta urinish" + (" (GPU bo'shashini kutib)" if vram else ""))
                else:
                    self.q.update(job_id, status="xato", error=err[-1500:], finished=time.time())
            self._notify(job_id)

    # --- boshqaruv ---
    def stop(self, job_id: int) -> None:
        job = self.q.get(job_id)
        proc = self.procs.pop(job_id, None)
        if job.status in ("navbatda", "ishlanmoqda"):
            self.q.update(job_id, status="toʻxtatildi", finished=time.time())
        if proc is not None:
            kill_tree(proc.pid)
        elif job.pid:
            kill_tree(job.pid)
        self._notify(job_id)

    def resume(self, job_id: int) -> None:
        """To'xtatilgan/xato vazifani qayta navbatga (vazifalar checkpoint'dan davom etadi)."""
        self.q.update(job_id, status="navbatda", attempts=0, wait_gpu_idle=0, finished=None)
        self._notify(job_id)

    def _notify(self, job_id: int) -> None:
        if self.on_update:
            try:
                self.on_update(self.q.get(job_id))
            except Exception:  # bildirishnoma xatosi navbatni to'xtatmasin
                log.exception("on_update")

    def run(self, stop: threading.Event, interval: float = 0.5) -> None:
        while not stop.is_set():
            self.tick()
            stop.wait(interval)
        for jid in list(self.procs):
            self.stop(jid)

    def idle(self) -> bool:
        self._reap()
        return not self.procs and not self.q.list(statuses=("navbatda",))


def enqueue_prepare(q: Queue, project: str, asr: dict[str, Any] | None = None, eye: bool = True,
                    proxy: bool = False) -> list[int]:
    """"Tekshiruvgacha tayyorlash" zanjiri: (slaydlar ‖ audio -> ASR ‖ Eye Contact) -> sinxron -> kesish takliflari."""
    from darsstudio.jobs.tasks import lesson_lang, resources_for
    from darsstudio.project.store import ProjectStore
    # til — VRAM e'loni uchun (inglizcha dars Whisper large-v3 bilan, ~3.6 GB)
    a = {"lang": lesson_lang(ProjectStore(Path(project)).load().meta), **(asr or {})}
    ids = {}
    ids["slides"] = q.add("slides", project, {}, resources_for("slides", {}))
    ids["audio"] = q.add("audio", project, {}, resources_for("audio", {}))
    ids["asr"] = q.add("asr", project, a, resources_for("asr", a), [ids["audio"]])
    if eye:
        ids["eyecontact"] = q.add("eyecontact", project, {}, resources_for("eyecontact", {}))
    if proxy:
        ids["proxy"] = q.add("proxy", project, {}, resources_for("proxy", {}))
    ids["sync"] = q.add("sync", project, {}, resources_for("sync", {}), [ids["asr"], ids["slides"]])
    ids["cuts"] = q.add("cuts", project, {}, resources_for("cuts", {}), [ids["sync"], ids["audio"]])
    return list(ids.values())
