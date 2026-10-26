"""Slayd sinxroni loyihaga (FR-07/08): jurnal bo'lsa beep + jurnal, aks holda AI. Natija buyruq orqali (undo bilan)."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from darsstudio.audio.extract import read_pcm
from darsstudio.project.commands import CommandStack
from darsstudio.project.model import LayoutSpan, Word
from darsstudio.sync import ai_align, beep, slide_log

B_SCENE_WORDS = 60  # TZ FR-12: slayd matni >= 60 so'z yoki jadval -> B tavsiya


def suggest_layouts(stack: CommandStack) -> list[LayoutSpan]:
    """Sahna tavsiyasi: matni ko'p yoki jadvalli slaydlar B, qolgani A (inson tasdiqlaydi)."""
    p = stack.project
    # TZ FR-12 qoidasi; chegara loyiha meta'sida sozlanadi ("b_scene_words"): zich slaydli darslarda 60 da deyarli
    # hamma slayd B bo'lib qoladi (namunada 65-139 so'z) — qaror inson tomonidan
    limit = int(p.meta.get("b_scene_words", B_SCENE_WORDS))
    heavy = {s.index for s in p.slides if len(s.body.split()) >= limit or " | " in s.body}
    out: list[LayoutSpan] = []
    for sp in p.slide_spans:
        lay = "B" if sp.slide in heavy else "A"
        if out and out[-1].layout == lay:
            out[-1] = out[-1].model_copy(update={"end": sp.end})
        else:
            out.append(LayoutSpan(start=sp.start, end=sp.end, layout=lay, suggested=True))
    return out


def ensure_slide_text(stack: CommandStack) -> None:
    """AI moslashtirish slayd matnisiz ishlamaydi: importda faqat sarlavhalar o'qiladi, matn shu yerda ajratiladi."""
    p = stack.project
    src = p.asset("pptx")
    if src is None or any(s.body or s.notes for s in p.slides):
        return
    from darsstudio.slides import extract
    slides, _ = extract.extract_pptx(src.path)
    for s, old in zip(slides, p.slides, strict=False):
        s.png_4k = old.png_4k
    stack.do("slaydlar matni", {"slides": [s.model_dump(mode="json") for s in slides]})


def sync_project(stack: CommandStack, params: ai_align.Params | None = None) -> dict[str, Any]:
    ensure_slide_text(stack)
    p = stack.project
    store = stack.store
    log_asset = p.asset("slide_log")
    out: dict[str, Any]
    if log_asset is not None:
        wav = read_pcm(store.cache("audio") / "asr_16k.wav")
        b = beep.find_beep(wav)
        beep_ns, events = slide_log.read_log(Path(log_asset.path))
        spans, short = slide_log.to_spans(beep_ns, events, b.start_s, p.fps_frac, p.total_frames)
        out = {"mode": "log", "beep": asdict(b), "short": short, "suspicious": [list(s) for s in short]}
        if not b.reliable:
            out["warning"] = "beep ishonchsiz topildi (SNR past): uni qo'lda belgilang"
    else:
        words = [Word(**w) for w in json.loads((store.cache("asr") / "words.json").read_text(encoding="utf-8"))]
        r = ai_align.align(words, p.slides, p.total_frames, p.fps_frac, params)
        spans = r.spans
        out = {"mode": "ai", "boundaries": [asdict(b) for b in r.boundaries],
               "suspicious": [asdict(b) for b in r.suspicious]}
    stack.do(f"slayd sinxroni ({out['mode']})", {"slide_spans": [s.model_dump(mode="json") for s in spans]})
    stack.do("sahna tavsiyasi", {"layout_spans": [s.model_dump(mode="json") for s in suggest_layouts(stack)]})
    (store.cache("sync") / f"{out['mode']}_align.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                                    encoding="utf-8")
    return out
