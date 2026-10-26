"""Loyiha bosqichlarini birlashtiruvchi yuqori daraja (CLI va keyin API/navbat uchun bitta joy)."""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from darsstudio.audio import mix
from darsstudio.export import srt
from darsstudio.media.probe import MediaError, ProbeResult
from darsstudio.project import cuts
from darsstudio.project.commands import CommandStack
from darsstudio.project.model import Word
from darsstudio.render import eyepatch, overlays, prepare, renderer, templates

log = logging.getLogger(__name__)


def words(stack: CommandStack) -> list[Word]:
    f = stack.store.cache("asr") / "words.json"
    return [Word(**w) for w in json.loads(f.read_text(encoding="utf-8"))] if f.is_file() else []


def prepare_audio(stack: CommandStack, atten_db: float = 15.0) -> dict[str, Any]:
    """FR-04: 48 kHz + 16 kHz WAV (video 0-kadriga tekislangan), VAD, loudness o'lchovi, denoise."""
    from darsstudio.audio import denoise, extract, loudness, vad
    pr = prepare.work_probe(stack.project)
    d = stack.store.cache("audio")
    a48, a16 = extract.extract_all(pr, d)
    sp = vad.detect(extract.read_pcm(a16))
    (d / "vad.json").write_text(json.dumps([[s.start_ms, s.end_ms] for s in sp]), encoding="utf-8")
    m = loudness.measure(a48)
    method = denoise.denoise(a48, d / "denoised_48k.wav", atten_db)
    info = {**m.__dict__, "denoise": method, "speech_segments": len(sp)}
    (d / "loudness.json").write_text(json.dumps(info), encoding="utf-8")
    return info

def propose_cuts(stack: CommandStack, min_pause_s: float = cuts.MIN_PAUSE_S, keep_pause_s: float = cuts.KEEP_PAUSE_S,
                 prefer_fullscreen: bool = False, approve_all: bool = False) -> int:
    """FR-09: VAD + so'z bo'shliqlari bo'yicha takliflar (eski "taklif"lar almashtiriladi, qarorlar saqlanadi)."""
    from darsstudio.audio.vad import silences
    store, p = stack.store, stack.project
    vf = store.cache("audio") / "vad.json"
    if not vf.is_file():
        raise MediaError("Avval audio tayyorlang: python -m darsstudio.cli audio LOYIHA")
    speech = json.loads(vf.read_text(encoding="utf-8"))
    from darsstudio.audio.vad import Speech
    total_ms = int(p.total_frames / p.fps_frac * 1000)
    sil = silences([Speech(s, e) for s, e in speech], total_ms)
    new = cuts.propose(words(stack), sil, p.fps_frac, p.total_frames, min_pause_s, keep_pause_s, p.layout_spans,
                       prefer_fullscreen)
    decided = [c for c in p.cuts if c.status != "taklif"]
    keep = decided + [c for c in new if not any(c.start < d.end and d.start < c.end for d in decided)]
    if approve_all:
        keep = [c.model_copy(update={"status": "tasdiqlangan"}) if c.status == "taklif" else c for c in keep]
    keep.sort(key=lambda c: c.start)
    stack.do("pauza takliflari", {"cuts": [c.model_dump(mode="json") for c in keep]})
    return len(new)


def run_eye_contact(stack: CommandStack, pr: ProbeResult,
                    on_progress: Callable[[int, int], None] | None = None) -> Path:
    out = stack.store.cache("eyepatch")
    lid = float(stack.project.eye_contact.get("lid_open", 0.5))
    if not eyepatch.is_valid(out, Path(pr.path), lid):
        meta = eyepatch.run_eye_contact(Path(pr.path), out, lid, on_progress)
        ec = {**stack.project.eye_contact, "status": "tayyor", "dir": str(out), "source_id": meta["source_id"],
              "cfg_key": meta["cfg_key"]}
        stack.do("Eye Contact patchlari", {"eye_contact": ec})
    return out


def render_project(stack: CommandStack, out: Path, *, template: str | None = None, profile: str = "web",
                   preset: str = "p7", chunk_sec: int = 60, start: int = 0, frames: int | None = None,
                   eye: bool = True, on_progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """FR-16: tayyor loyihani render qiladi (kesishlar, ko'z patchlari, tozalangan audio, lower-third) + SRT."""
    p = stack.project
    tpl = templates.load(template or p.template_id)
    pr = prepare.work_probe(p)
    pngs = prepare.ensure_slides(stack)
    warped = prepare.ensure_warped(stack, tpl, pngs)
    prepare.ensure_key(stack, pr)
    prepare.ensure_placement(stack, pr, tpl)
    p = stack.project
    if not p.slide_spans:
        raise MediaError("Slayd vaqtlari yo'q: `sync` yoki `render --slides-csv` bilan bering.")
    ws = words(stack)
    bad = cuts.check_no_word_cut(p.cuts, ws, p.fps_frac)
    if bad:
        raise MediaError(f"{len(bad)} ta tasdiqlangan kesish so'z ichiga tushadi (masalan {bad[0].start}-kadr). "
                         "Ularni rad eting yoki suring.")
    tm = cuts.timemap(p)
    extra = renderer.RenderInputs(timemap=tm, lower_third=overlays.lower_third(p.meta, tpl.canvas),
                                  lower_third_s=tpl.lower_third.duration_s)
    den = stack.store.cache("audio") / "denoised_48k.wav"
    audio_info: dict[str, Any] = {}
    if den.is_file():
        fa = stack.store.cache("render") / "final_audio.wav"
        m = mix.final_audio(den, tm, fa)
        extra.audio_wav = fa
        audio_info = {"integrated": m.integrated, "true_peak": m.true_peak}
    elif len(tm.ranges) > 1:
        raise MediaError("Kesishlar bor, lekin audio tayyorlanmagan: python -m darsstudio.cli audio LOYIHA")
    ep = stack.store.cache("eyepatch")
    if eye and eyepatch.is_valid(ep, Path(pr.path), float(p.eye_contact.get("lid_open", 0.5))):
        extra.eyepatch_dir = ep
    opts = renderer.RenderOptions(profile=profile, preset=preset, chunk_sec=chunk_sec, start=start, frames=frames,
                                  on_progress=on_progress)
    rep = renderer.render(p, pr, tpl, warped, pngs, p.slide_spans, p.layout_spans, out, stack.store.cache("render"),
                          opts, extra)
    srt_path = None
    if ws and start == 0 and frames is None:
        srt_path = out.with_suffix(".srt")
        srt_path.write_text(srt.to_srt(srt.build_cues(ws, tm)), encoding="utf-8")
    return {"report": rep.__dict__, "audio": audio_info, "srt": str(srt_path) if srt_path else None,
            "eye_contact": extra.eyepatch_dir is not None, "cuts": len(tm.ranges) - 1, "out_frames": tm.out_total}
