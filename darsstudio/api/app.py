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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from darsstudio import doctor, paths
from darsstudio.jobs.queue_db import Job, Queue
from darsstudio.jobs.scheduler import Scheduler, enqueue_prepare
from darsstudio.jobs.tasks import TASKS, final_key, resources_for
from darsstudio.media.probe import MediaError
from darsstudio.project import importer
from darsstudio.project.commands import CommandStack
from darsstudio.project.store import ProjectStore

LOW_CONF, MAX_LOW_WORDS = 0.25, 50
NAME_RE = re.compile(r"^[\w\-. ]{1,100}$", re.UNICODE)


class ImportReq(BaseModel):
    video: str
    more_videos: list[str] = []      # davomi (dars bir nechta faylda yozilgan bo'lsa), tartib bilan
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


def reveal_cmd(f: Path) -> str:
    """Explorer faqat /select,"yo'l" ko'rinishini tushunadi. Ro'yxat argumenti bo'sh joyli yo'lni butunlay
    qo'shtirnoqqa olardi ("/select,D:/ai montaj/...") va Explorer boshqa papkani (Hujjatlar) ochardi."""
    return f'explorer /select,"{f}"'


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
        # eng oxirgi yaratilgani ro'yxat boshida (papka st_ctime: Windows'da yaratilgan vaqt, qayta yozilmaydi)
        dirs = [d for d in wd.iterdir() if d.is_dir() and (d / "project.json").is_file()]
        for d in sorted(dirs, key=lambda d: d.stat().st_ctime, reverse=True):
            s = ProjectStore(d)
            if s.exists():
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
        videos = [Path(r.video), *(Path(v) for v in r.more_videos if v.strip())]
        s = await asyncio.to_thread(importer.import_project, videos, Path(r.slides), r.template, wd,
                                    name=r.name, meta=r.meta, slide_log=Path(r.slide_log) if r.slide_log else None,
                                    copy=r.copy_sources, make_proxy=False)
        jobs = enqueue_prepare(queue, str(s.root), proxy=True) if r.prepare else []
        return {"name": s.root.name, "jobs": jobs}

    class PartReq(BaseModel):
        video: str

    @app.post("/api/projects/{name}/parts")
    async def add_part(name: str, r: PartReq) -> dict[str, Any]:
        """Davomini qo'shish: qismlar ulanadi, tahlil (audio, ASR, Eye Contact, sinxron, kesish) qayta navbatga."""
        s = store(name)
        if any(j.status in ("navbatda", "ishlanmoqda") for j in queue.list(project=str(s.root))):
            raise HTTPException(409, "Loyihada vazifalar ishlayapti: tugashini kuting, keyin davomini qo'shing.")
        await asyncio.to_thread(importer.append_part, s, Path(r.video))
        return {"jobs": enqueue_prepare(queue, str(s.root), proxy=True), **project_view(stack(name))}

    class RevealReq(BaseModel):
        file: str

    @app.post("/api/projects/{name}/reveal")
    def reveal(name: str, r: RevealReq) -> dict[str, bool]:
        """Eksport faylini Windows Explorer'da belgilab ochadi (faqat loyiha papkasi ichidagi fayl)."""
        import subprocess
        root = store(name).root.resolve()
        f = (root / r.file).resolve()
        if not str(f).startswith(str(root)) or not f.exists():
            raise HTTPException(404, "Fayl topilmadi.")
        subprocess.Popen(reveal_cmd(f), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"ok": True}

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
    def slide_png(name: str, index: int, state: int | None = None) -> FileResponse:
        """state — animatsiya holati (bajarilgan bosishlar soni); yakuniy holat yoki qadam yo'q — NNN.png."""
        if state is not None and (store(name).cache("slides") / "4k" / f"{index:03d}_{state}.png").is_file():
            return cached_file(name, "slides", "4k", f"{index:03d}_{state}.png")
        return cached_file(name, "slides", "4k", f"{index:03d}.png")

    @app.get("/api/projects/{name}/waveform")
    def waveform(name: str) -> Response:
        """Timeline uchun audio to'lqin: har kadrga RMS (0..255, uint8), keshlanadi (cache/audio/rms.u8)."""
        import numpy as np

        from darsstudio.audio.extract import read_pcm
        s = store(name)
        d = s.cache("audio")
        out = d / "rms.u8"
        src = next((f for f in (d / "denoised_48k.wav", d / "src_48k.wav") if f.is_file()), None)
        if src is None:
            raise HTTPException(404, "Audio hali tayyor emas.")
        if not out.is_file() or out.stat().st_mtime < src.stat().st_mtime:
            fps = float(s.load().fps_frac)
            x = read_pcm(src, 16000).astype(np.float64) ** 2
            hop = 16000 / fps
            n = int(len(x) / hop)
            idx = (np.arange(n + 1) * hop).astype(np.int64)
            peaks = np.sqrt(np.add.reduceat(x[: idx[-1]], idx[:-1]) / np.diff(idx)) if n else np.zeros(0)
            ref = float(np.percentile(peaks, 99.5)) if n else 1.0
            out.write_bytes((np.clip(peaks / max(ref, 1e-4), 0, 1) * 255).astype(np.uint8).tobytes())
        return Response(out.read_bytes(), media_type="application/octet-stream")

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
            low = sorted((w for w in json.loads(wf.read_text(encoding="utf-8")) if w["conf"] < LOW_CONF),
                         key=lambda w: w["conf"])[:MAX_LOW_WORDS]   # ro'yxat shovqin bilan to'lib ketmasin
            for w in low:
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

    @app.get("/api/projects/{name}/frame/{frame}")
    def frame_image(name: str, frame: int, mode: str = "orig", width: int = 960) -> Any:
        """Kalibrlash uchun kadr (JPEG): orig | keyed (shaxmat fonda) | matte. Keyer CPU'da (server CUDA yuklamaydi)."""
        import cv2
        import numpy as np
        import torch
        from fastapi.responses import Response

        from darsstudio.media.frames import planes
        from darsstudio.render import prepare
        from darsstudio.render.keyer import Keyer, to_rgb, ycbcr
        p = store(name).load()
        if not 0 <= frame < p.total_frames:
            raise HTTPException(400, "Kadr raqami loyiha chegarasidan tashqarida.")
        pr = prepare.work_probe(p)
        w, h = pr.video.width, pr.video.height
        y, u, v = planes(prepare.read_frame(pr, frame), w, h)
        t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).unsqueeze(0)  # noqa: E731
        if mode == "orig":
            img = to_rgb(*ycbcr(t(y), t(u), t(v), pr.full_range))[0].permute(1, 2, 0).numpy()
        else:
            r = Keyer(p.key, w, h, pr.full_range, torch.device("cpu"))(t(y), t(u), t(v))
            a = r.alpha[0].permute(1, 2, 0).numpy()
            if mode == "matte":
                img = a.repeat(3, 2)
            else:
                checker = ((np.indices((h, w)).sum(0) // 32) % 2 * 0.3 + 0.35)[..., None].repeat(3, 2)
                img = r.rgb[0].permute(1, 2, 0).numpy() + checker * (1 - a)
        out = (np.clip(img, 0, 1) * 255).astype(np.uint8)[..., ::-1]
        if width and width < w:
            out = cv2.resize(out, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 88])
        return Response(buf.tobytes(), media_type="image/jpeg")

    @app.post("/api/projects/{name}/key/suggest")
    def key_suggest(name: str, frame: int) -> dict[str, Any]:
        from darsstudio.render import prepare
        st = stack(name)
        prepare.ensure_key(st, prepare.work_probe(st.project), frame=frame)
        return project_view(st)

    @app.post("/api/projects/{name}/preview")
    def preview(name: str, start_s: float, duration_s: float = 10.0) -> dict[str, Any]:
        """"Haqiqiy ko'rinish" (FR-15): oraliq render navbatga (alohida jarayon); natija /files orqali."""
        from darsstudio.project.cuts import timemap
        s = store(name)
        p = s.load()
        fps = float(p.fps_frac)
        # start_s — asl video vaqti; render esa chiqish (kesishlardan keyingi) kadrlarida
        tm = timemap(p)
        src = min(max(0, int(start_s * fps)), p.total_frames - 1)
        g = next((a for a, _ in tm.map_span(src, p.total_frames)), max(0, tm.out_total - 1))
        out = s.root / "cache" / "preview" / f"preview_{g}_{int(duration_s * 1000)}.mp4"
        args = {"out": str(out), "start": g, "frames": max(1, int(duration_s * fps)), "profile": "web"}
        return {"id": queue.add("render", str(s.root), args, resources_for("render", args)),
                "file": str(out.relative_to(s.root)).replace("\\", "/")}

    @app.post("/api/projects/{name}/slides-file")
    def replace_slides_file(name: str, r: dict[str, str]) -> dict[str, Any]:
        """Taqdimotni almashtirish; keyin slaydlar va sinxron vazifalari navbatga (nutq qayta ishlanmaydi)."""
        from darsstudio.project.importer import replace_slides
        st = stack(name)
        replace_slides(st, Path(r.get("path", "")))
        root = str(st.store.root)
        sl = queue.add("slides", root, {}, resources_for("slides", {}))
        queue.add("sync", root, {}, resources_for("sync", {}), [sl])
        return project_view(st)

    @app.post("/api/projects/{name}/relayout")
    def relayout_scenes(name: str) -> dict[str, Any]:
        """Sahnalarni slaydlarga moslash (qo'lda o'zgartirilganlari saqlanadi)."""
        from darsstudio.sync.run import relayout
        st = stack(name)
        st.do("Sahnalarni slaydlarga moslash", {"layout_spans": [s.model_dump(mode="json") for s in relayout(st)]})
        return project_view(st)

    @app.get("/api/projects/{name}/final-preview")
    def final_preview(name: str) -> dict[str, Any]:
        """Butun dars tayyor ko'rinishi (3-ekran): eng so'nggi render, uning saqlangan oraliqlari, eskirganmi."""
        s = store(name)
        d = s.root / "cache" / "preview"
        done = sorted((f for f in d.glob("final_*.mp4") if f.with_suffix(".json").is_file()),
                      key=lambda f: f.stat().st_mtime) if d.is_dir() else []
        if not done:
            return {"file": None}
        f = done[-1]
        meta = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
        return {"file": f"cache/preview/{f.name}", "keep": meta["keep"], "stale": meta["key"] != final_key(s.root)}

    @app.post("/api/projects/{name}/final-preview")
    def final_preview_start(name: str) -> dict[str, Any]:
        s = store(name)
        out = s.root / "cache" / "preview" / f"final_{final_key(s.root)}.mp4"
        args = {"out": str(out), "profile": "korish", "final": True}
        return {"id": queue.add("render", str(s.root), args, resources_for("render", args))}

    @app.get("/api/projects/{name}/files/{path:path}")
    def project_file(name: str, path: str) -> FileResponse:
        """Loyiha ichidagi eksport/preview fayllari (yo'l loyiha papkasidan chiqmaydi)."""
        s = store(name)
        f = (s.root / path).resolve()
        if not str(f).startswith(str(s.root.resolve())) or not f.is_file() or f.name == "project.json":
            raise HTTPException(404, "Fayl topilmadi.")
        return FileResponse(f)

    @app.get("/api/projects/{name}/exports")
    def exports(name: str) -> list[dict[str, Any]]:
        s = store(name)
        out = []
        for f in sorted(s.root.glob("exports/**/*.mp4")):
            qa = f.with_name("qa.json")
            m = re.fullmatch(r"v(\d+)", f.parent.name)
            out.append({"file": str(f.relative_to(s.root)).replace("\\", "/"),
                        "size_mb": round(f.stat().st_size / 2**20, 1), "version": int(m.group(1)) if m else 0,
                        "mtime": int(f.stat().st_mtime),
                        "qa": json.loads(qa.read_text(encoding="utf-8")) if qa.is_file() else None})
        return out

    @app.get("/api/templates")
    def list_templates() -> list[str]:
        from darsstudio.render import templates
        return sorted(d.name for d in templates.templates_dir().iterdir() if (d / "template.json").is_file())

    @app.get("/api/templates/{tid}")
    def get_template(tid: str) -> dict[str, Any]:
        from darsstudio.render import templates
        if not NAME_RE.match(tid):
            raise HTTPException(400, "Noto'g'ri shablon nomi.")
        return templates.load(tid).model_dump(mode="json", exclude={"dir"})

    @app.get("/api/templates/{tid}/background")
    def template_bg(tid: str) -> FileResponse:
        from darsstudio.render import templates
        if not NAME_RE.match(tid):
            raise HTTPException(400, "Noto'g'ri shablon nomi.")
        t = templates.load(tid)
        return FileResponse(t.asset(t.background))

    class TemplatePatch(BaseModel):
        screen_quad: list[list[float]] | None = None
        teacher_anchor: list[int] | None = None

    @app.put("/api/templates/{tid}")
    def put_template(tid: str, r: TemplatePatch) -> dict[str, Any]:
        from darsstudio.render import templates
        if not NAME_RE.match(tid):
            raise HTTPException(400, "Noto'g'ri shablon nomi.")
        t = templates.load(tid)
        upd: dict[str, Any] = {}
        if r.screen_quad is not None:
            if len(r.screen_quad) != 4:
                raise HTTPException(400, "4 ta nuqta kerak: TL, TR, BR, BL.")
            upd["screen_quad"] = tuple(tuple(p) for p in r.screen_quad)
        if r.teacher_anchor is not None:
            upd["teacher_anchor"] = tuple(r.teacher_anchor)
        t = templates.Template.model_validate({**t.model_dump(), **upd})
        templates.save(t)
        return t.model_dump(mode="json", exclude={"dir"})

    class LowerThirdReq(BaseModel):
        template: str = "akademiya"
        meta: dict[str, str] = {}

    @app.post("/api/lower-third-preview")
    def lower_third_preview(r: LowerThirdReq) -> Response:
        """Lower-third ko'rinishi (fon ustida, pastki qism) — yangi loyiha formasida jonli."""
        import io

        from PIL import Image

        from darsstudio.render import overlays, templates
        if not NAME_RE.match(r.template):
            raise HTTPException(400, "Noto'g'ri shablon nomi.")
        t = templates.load(r.template)
        im = Image.open(t.asset(t.background)).convert("RGBA").resize(t.canvas)
        if t.lower_third.style == "akademiya":
            layers = overlays.lower_third_akademiya(r.meta, t.canvas) or ()
        else:
            one = overlays.lower_third(r.meta, t.canvas)
            layers = (one,) if one is not None else ()
        for layer in layers:
            im = Image.alpha_composite(im, Image.fromarray(layer))
        buf = io.BytesIO()
        im.crop((0, t.canvas[1] - 260, t.canvas[0] // 2 + 200, t.canvas[1])).convert("RGB").save(buf, "PNG")
        return Response(buf.getvalue(), media_type="image/png")

    @app.post("/api/pick-file")
    async def pick_file(kind: str = "video") -> dict[str, str]:
        """Windows fayl tanlash oynasi (tkinter, stdlib). Tanlanmasa bo'sh yo'l."""
        types = {"video": [("Video", "*.mp4 *.mov *.mxf *.mkv *.MP4 *.MOV"), ("Barchasi", "*.*")],
                 "slides": [("Slaydlar", "*.pptx *.pdf"), ("Barchasi", "*.*")]}

        def ask() -> str:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                return str(filedialog.askopenfilename(parent=root, filetypes=types.get(kind, types["video"])))
            finally:
                root.destroy()
        return {"path": (await asyncio.to_thread(ask)).replace("/", os.sep)}

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

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def api_not_found(rest: str) -> None:
        # /api ostidagi noma'lum yo'l statik UI'ga (index.html, 200) tushib qolmasin
        raise HTTPException(404, "Bunday API yo'q.")

    @app.middleware("http")
    async def no_cache_html(request: Any, call_next: Any) -> Any:
        # index.html keshlanmasin: yangilangan UI'dan keyin eski oyna eski sahifani ko'rsatardi (assets — hash nomli)
        resp = await call_next(request)
        if resp.headers.get("content-type", "").startswith("text/html"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

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
