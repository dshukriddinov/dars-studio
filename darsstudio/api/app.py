"""Backend API (D-09, FR-14/15/20/21/22). Faqat 127.0.0.1 ga bog'lanadi. Barcha loyiha o'zgarishlari buyruqlar orqali
(undo/redo serverda). Uzoq ishlar navbatga (alohida jarayonlar), progress WebSocket orqali.

    python -m darsstudio.api.app [--port 8765]
"""

import asyncio
import contextlib
import json
import os
import re
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from darsstudio import doctor, paths
from darsstudio.jobs.queue_db import Job, Queue
from darsstudio.jobs.scheduler import Scheduler, enqueue_prepare
from darsstudio.jobs.tasks import TASKS, resources_for
from darsstudio.media.probe import MediaError
from darsstudio.project import importer
from darsstudio.project.commands import CommandStack
from darsstudio.project.store import ProjectStore

NAME_RE = re.compile(r"^[\w\-. ]{1,100}$", re.UNICODE)


class ImportReq(BaseModel):
    video: str
    slides: str
    template: str = "demo"
    name: str | None = None
    meta: dict[str, str] = {}
    slide_log: str | None = None
    copy_sources: bool = False
    prepare: bool = True


class CommandReq(BaseModel):
    label: str
    values: dict[str, Any]


class JobReq(BaseModel):
    type: str
    args: dict[str, Any] = {}


class Hub:
    """Navbat yangilanishlarini WebSocket mijozlariga tarqatish (scheduler oqimidan asyncio'ga)."""

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[asyncio.Queue[str]] = set()

    def publish(self, job: Job) -> None:
        if self.loop is None:
            return
        msg = json.dumps({"type": "job", "job": job.model_dump(mode="json")}, ensure_ascii=False)
        for q in list(self.clients):
            self.loop.call_soon_threadsafe(q.put_nowait, msg)


def create_app(workdir: Path | None = None, start_scheduler: bool = True) -> FastAPI:
    wd = Path(workdir or paths.workdir())
    wd.mkdir(parents=True, exist_ok=True)
    hub = Hub()
    queue = Queue(wd / "queue.db")
    sched = Scheduler(queue, wd / "logs", on_update=hub.publish)
    stop = threading.Event()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        hub.loop = asyncio.get_running_loop()
        th = None
        if start_scheduler:
            th = threading.Thread(target=sched.run, args=(stop,), daemon=True)
            th.start()
        yield
        stop.set()
        if th:
            th.join(30)

    app = FastAPI(title="Dars Studio", lifespan=lifespan)
    app.state.queue, app.state.scheduler, app.state.workdir = queue, sched, wd

    def store(name: str) -> ProjectStore:
        if not NAME_RE.match(name) or name in (".", ".."):
            raise HTTPException(400, "Noto'g'ri loyiha nomi.")
        s = ProjectStore(wd / name)
        if not s.exists():
            raise HTTPException(404, f"'{name}' loyihasi topilmadi.")
        return s

    def stack(name: str) -> CommandStack:
        return CommandStack(store(name))

    def project_view(st: CommandStack) -> dict[str, Any]:
        return {"project": st.project.model_dump(mode="json"), "can_undo": bool(st.undo_stack),
                "can_redo": bool(st.redo_stack),
                "undo_label": st.undo_stack[-1].label if st.undo_stack else None,
                "redo_label": st.redo_stack[-1].label if st.redo_stack else None}

    @app.exception_handler(MediaError)
    async def media_error(_: Any, e: MediaError) -> JSONResponse:
        return JSONResponse({"detail": str(e)}, status_code=400)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "workdir": str(wd)}

    @app.get("/api/doctor")
    def get_doctor() -> list[dict[str, str]]:
        return [c.__dict__ for c in doctor.run_all()]

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        out = []
        for d in sorted(wd.iterdir()):
            s = ProjectStore(d)
            if d.is_dir() and s.exists():
                p = s.load()
                jobs = queue.list(project=str(d))
                out.append({"name": d.name, "id": p.id, "fps": p.fps, "total_frames": p.total_frames,
                            "slides": len(p.slides), "meta": p.meta,
                            "jobs": {st: sum(j.status == st for j in jobs) for st in
                                     ("navbatda", "ishlanmoqda", "tayyor", "xato", "toʻxtatildi")}})
        return out

    @app.post("/api/projects")
    async def create_project(r: ImportReq) -> dict[str, Any]:
        if r.name and not NAME_RE.match(r.name):
            raise HTTPException(400, "Noto'g'ri loyiha nomi.")
        s = await asyncio.to_thread(importer.import_project, Path(r.video), Path(r.slides), r.template, wd,
                                    name=r.name, meta=r.meta, slide_log=Path(r.slide_log) if r.slide_log else None,
                                    copy=r.copy_sources, make_proxy=False)
        jobs = enqueue_prepare(queue, str(s.root), proxy=True) if r.prepare else []
        return {"name": s.root.name, "jobs": jobs}

    @app.get("/api/projects/{name}")
    def get_project(name: str) -> dict[str, Any]:
        return project_view(stack(name))

    @app.post("/api/projects/{name}/commands")
    def do_command(name: str, r: CommandReq) -> dict[str, Any]:
        st = stack(name)
        try:
            st.do(r.label, r.values)
        except (ValueError, KeyError, IndexError) as e:
            raise HTTPException(400, f"Amal bajarilmadi: {e}") from e
        return project_view(st)

    @app.post("/api/projects/{name}/undo")
    def undo(name: str) -> dict[str, Any]:
        st = stack(name)
        st.undo()
        return project_view(st)

    @app.post("/api/projects/{name}/redo")
    def redo(name: str) -> dict[str, Any]:
        st = stack(name)
        st.redo()
        return project_view(st)

    def cached_file(name: str, *parts: str) -> FileResponse:
        s = store(name)
        f = (s.root / "cache" / Path(*parts)).resolve()
        if not str(f).startswith(str(s.root.resolve())) or not f.is_file():
            raise HTTPException(404, "Fayl topilmadi.")
        return FileResponse(f)

    @app.get("/api/projects/{name}/proxy")
    def proxy(name: str) -> FileResponse:
        return cached_file(name, "media", "proxy_540p.mp4")

    @app.get("/api/projects/{name}/slides/{index}")
    def slide_png(name: str, index: int) -> FileResponse:
        return cached_file(name, "slides", "4k", f"{index:03d}.png")

    @app.get("/api/projects/{name}/words")
    def words(name: str) -> Any:
        f = store(name).cache("asr") / "words.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []

    @app.get("/api/projects/{name}/suspicious")
    def suspicious(name: str) -> list[dict[str, Any]]:
        """"Shubhali joylar" (FR-14): slayd chegaralari, framing ogohlantirishlari, past ishonchli so'zlar."""
        s = store(name)
        p = s.load()
        fps = float(p.fps_frac)
        out: list[dict[str, Any]] = []
        for f in ("ai_align.json", "log_align.json"):
            sf = s.cache("sync") / f
            if sf.is_file():
                for b in json.loads(sf.read_text(encoding="utf-8")).get("suspicious", []):
                    if isinstance(b, dict):
                        out.append({"kind": "slayd_chegarasi", "frame": b["frame"], "score": b["confidence"],
                                    "text": f"{b['prev_slide']} -> {b['slide']}: {b['reason']}"})
                    else:
                        out.append({"kind": "qisqa_slayd", "frame": b[0], "score": 0.5, "text": "1 s dan qisqa"})
        for rj in s.root.glob("exports/**/*.render.json"):
            for w in json.loads(rj.read_text(encoding="utf-8")).get("warnings", []):
                out.append({"kind": w["kind"], "frame": w["start"], "score": 0.5,
                            "text": f"{w['end'] - w['start']} kadr"})
        wf = s.cache("asr") / "words.json"
        if wf.is_file():
            for w in json.loads(wf.read_text(encoding="utf-8")):
                if w["conf"] < 0.4:
                    out.append({"kind": "past_ishonchli_soz", "frame": int(w["start_ms"] / 1000 * fps),
                                "score": w["conf"], "text": w["text"]})
        return sorted(out, key=lambda x: x["score"])

    @app.post("/api/projects/{name}/prepare")
    def prepare(name: str) -> dict[str, Any]:
        return {"jobs": enqueue_prepare(queue, str(store(name).root))}

    @app.post("/api/projects/{name}/jobs")
    def add_job(name: str, r: JobReq) -> dict[str, Any]:
        if r.type not in TASKS:
            raise HTTPException(400, f"Noma'lum vazifa: {r.type}")
        s = store(name)
        args = dict(r.args)
        if r.type == "render" and "out" not in args:
            args["out"] = str(s.root / "exports" / "render.mp4")
        return {"id": queue.add(r.type, str(s.root), args, resources_for(r.type, args))}

    @app.get("/api/jobs")
    def jobs(project: str | None = None) -> list[dict[str, Any]]:
        proj = str(store(project).root) if project else None
        return [j.model_dump(mode="json") for j in queue.list(project=proj)]

    @app.post("/api/jobs/{job_id}/stop")
    def stop_job(job_id: int) -> dict[str, Any]:
        sched.stop(job_id)
        return queue.get(job_id).model_dump(mode="json")

    @app.post("/api/jobs/{job_id}/resume")
    def resume_job(job_id: int) -> dict[str, Any]:
        sched.resume(job_id)
        return queue.get(job_id).model_dump(mode="json")

    @app.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        await sock.accept()
        q: asyncio.Queue[str] = asyncio.Queue()
        hub.clients.add(q)
        try:
            while True:
                await sock.send_text(await q.get())
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(q)

    ui = paths.ROOT / "ui" / "dist"
    if ui.is_dir():
        app.mount("/", StaticFiles(directory=ui, html=True), name="ui")
    return app


def main() -> None:
    import argparse

    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    # FR-22: ishga tushgandan keyin tarmoq talab qilinmaydi
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    uvicorn.run(create_app(), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
