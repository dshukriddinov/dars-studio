"""Vazifa turlari: worker ichida bajariladigan funksiya + resurs e'loni (FR-20). Funksiya: (args, emit) -> natija.
args da doim `project` (loyiha papkasi) bor."""

import contextlib
import json
import time
from pathlib import Path
from typing import Any

from darsstudio import paths
from darsstudio.jobs.resources import Resources


def _stack(args: dict[str, Any]) -> Any:
    from darsstudio.project.commands import CommandStack
    from darsstudio.project.store import ProjectStore
    return CommandStack(ProjectStore(Path(args["project"])))


def t_slides(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio.render import prepare, templates
    st = _stack(args)
    pngs = prepare.ensure_slides(st)
    prepare.ensure_warped(st, templates.load(st.project.template_id), pngs)
    return {"slides": len(pngs)}


def t_audio(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio import pipeline
    return pipeline.prepare_audio(_stack(args), float(args.get("atten_db", 15.0)))


def t_asr(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio.asr import glossary
    from darsstudio.asr.run import task
    st = _stack(args)
    terms = glossary.load(paths.ROOT / "glossary.json", st.store.root / "glossary.json")
    return task({"wav16k": str(st.store.cache("audio") / "asr_16k.wav"), "engine": args.get("engine", DEFAULT_ASR),
                 "align": args.get("align", DEFAULT_ALIGN), "hotwords": glossary.hotwords(terms) if terms else None,
                 "out_dir": str(st.store.cache("asr"))}, emit)


def t_eyecontact(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio import pipeline
    from darsstudio.render import prepare
    st = _stack(args)
    out = pipeline.run_eye_contact(st, prepare.work_probe(st.project), lambda d, t: emit.progress(d / max(t, 1)))
    return {"dir": str(out)}


def t_sync(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio.sync.run import sync_project
    out = sync_project(_stack(args))
    return {"mode": out["mode"], "suspicious": len(out["suspicious"])}


def t_cuts(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio import pipeline
    return {"proposals": pipeline.propose_cuts(_stack(args))}


def t_proxy(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio.media import proxy
    from darsstudio.render import prepare
    st = _stack(args)
    out = proxy.make_proxy(prepare.work_probe(st.project), st.store.cache("media") / "proxy_540p.mp4")
    return {"proxy": str(out)}


def t_render(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    from darsstudio import pipeline
    st = _stack(args)
    from darsstudio.project.cuts import timemap
    from darsstudio.project.store import atomic_write_json
    out = Path(args["out"])
    # butun dars ko'rinishi (Batafsil tahrir 3-ekrani): render boshlangandagi holat yoziladi
    meta = {"key": final_key(st.store.root), "keep": [list(r) for r in timemap(st.project).ranges]}
    final = bool(args.get("final"))
    # ko'rish nusxasi: intro/outro va SRT'siz (asl kadr bilan 1:1 moslanadi), yengil kodlash
    r = pipeline.render_project(st, out, profile=args.get("profile", "web"), preset="p1" if final else "p7",
                                start=int(args.get("start", 0)), frames=args.get("frames"),
                                bumpers_on=not final, subtitles=not final,
                                on_progress=lambda d, t: emit.progress(d / max(t, 1)))
    if final:
        atomic_write_json(out.with_suffix(".json"), meta)
        for old in out.parent.glob("final_*.*"):   # eski ko'rinishlar (~100 MB); ochiq bo'lsa keyingi safar
            if old.stem != out.stem:
                with contextlib.suppress(OSError):
                    old.unlink()
    return r


def final_key(project_root: Path) -> str:
    """Tayyor ko'rinishga ta'sir qiladigan holat (project.json) xeshi: o'zgarsa ko'rinish eskirgan."""
    import hashlib
    return hashlib.sha1((project_root / "project.json").read_bytes()).hexdigest()[:12]


def t_export(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    """To'liq eksport (FR-16..19): MP4 (intro/outro bilan) + jadvallar + QA [+ SRT] [+ Premiere paketi]."""
    from darsstudio import pipeline
    st = _stack(args)
    r = pipeline.export_project(st, args.get("profile", "web"), bool(args.get("premiere")),
                                on_progress=lambda d, t: emit.progress(d / max(t, 1)),
                                subtitles=bool(args.get("subtitles")))
    return {k: r[k] for k in ("version", "path", "qa", "premiere")}


def t_sleep(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    """Test va diagnostika: N soniya, progress bilan; fail=True — xato, marker fayl — resume tekshiruvi."""
    n = float(args.get("seconds", 1))
    mark = Path(args["marker"]) if args.get("marker") else None
    start = float(mark.read_text()) if mark and mark.is_file() else 0.0
    steps = 20
    for i in range(int(start * steps), steps):
        time.sleep(n / steps)
        emit.progress((i + 1) / steps)
        if mark:
            mark.write_text(str((i + 1) / steps))
    if args.get("fail"):
        raise RuntimeError(args.get("fail_message", "sinov xatosi"))
    return {"slept": n, "resumed_from": start}


DEFAULT_ASR = "rubaistt-v2-medium-ct2"
DEFAULT_ALIGN = "sarahai-uzbek-stt-3"


def model_vram(*names: str) -> int:
    try:
        data = json.loads((paths.models_dir() / "manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 4000
    v = {m["name"]: m.get("vram_mb") or 3000 for m in data["models"]}
    return int(max((v.get(n, 3000) for n in names if n), default=3000) * 1.1)


TASKS: dict[str, tuple[str, Resources]] = {
    "slides": ("t_slides", Resources(pptx=1, cpu_heavy=1)),
    "audio": ("t_audio", Resources(cpu_heavy=1)),
    "asr": ("t_asr", Resources(vram_mb=4500)),
    "eyecontact": ("t_eyecontact", Resources(vram_mb=1100, cpu_heavy=1)),
    "sync": ("t_sync", Resources()),
    "cuts": ("t_cuts", Resources()),
    "proxy": ("t_proxy", Resources(nvenc=1)),
    "render": ("t_render", Resources(vram_mb=3200, nvenc=1)),
    "export": ("t_export", Resources(vram_mb=3200, nvenc=1, pptx=1)),
    "sleep": ("t_sleep", Resources()),
}


def resources_for(task: str, args: dict[str, Any]) -> Resources:
    if "resources" in args:
        return Resources.model_validate(args["resources"])
    r = TASKS[task][1]
    if task == "asr":
        return r.model_copy(update={"vram_mb": model_vram(args.get("engine", DEFAULT_ASR),
                                                          args.get("align", DEFAULT_ALIGN))})
    return r
