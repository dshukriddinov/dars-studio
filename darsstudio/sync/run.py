"""Slayd sinxroni loyihaga (FR-07/08): jurnal bo'lsa beep + jurnal, aks holda AI. Natija buyruq orqali (undo bilan)."""

import json
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from darsstudio.asr import uz_text
from darsstudio.audio.extract import read_pcm
from darsstudio.media.probe import MediaError
from darsstudio.project.commands import CommandStack
from darsstudio.project.model import LayoutSpan, Slide, SlideSpan, Word
from darsstudio.slides import anim
from darsstudio.sync import ai_align, beep, slide_log

B_SCENE_WORDS = 60  # TZ FR-12: slayd matni >= 60 so'z yoki jadval -> B tavsiya


def suggest_layouts(stack: CommandStack) -> list[LayoutSpan]:
    """Sahna tavsiyasi (inson tasdiqlaydi). Shablondagi scene_policy bo'yicha:
    - words (TZ FR-12): matni >= N so'z yoki jadvalli slaydlar B, qolgani A;
    - a_then_b (montajchi uslubi): slayd almashganda a_seconds A (o'qituvchi yangi slayd bilan), keyin B; slayd qolgan
      qismi min_b_seconds dan qisqa bo'lsa A qoladi. Birinchi va oxirgi slayd A (ikkala namunada shunday)."""
    from darsstudio.render import templates
    p = stack.project
    try:
        policy = templates.load(p.template_id).scene_policy
    except MediaError:  # shablon yo'q (sinov/import holati) — TZ qoidasi
        policy = templates.ScenePolicy()
    spans: list[tuple[int, int, str]] = []
    if policy.mode == "a_then_b":
        a_fr, min_b = round(Fraction(policy.a_seconds) * p.fps_frac), round(Fraction(policy.min_b_seconds) * p.fps_frac)
        last = p.slide_spans[-1].slide if p.slide_spans else 0
        first = p.slide_spans[0].slide if p.slide_spans else 0
        for sp in p.slide_spans:
            if sp.slide in (first, last) or sp.end - sp.start - a_fr < min_b:
                spans.append((sp.start, sp.end, "A"))
            else:
                spans += [(sp.start, sp.start + a_fr, "A"), (sp.start + a_fr, sp.end, "B")]
    else:
        # TZ FR-12; chegara loyiha meta'sida sozlanadi ("b_scene_words")
        limit = int(p.meta.get("b_scene_words", B_SCENE_WORDS))
        heavy = {s.index for s in p.slides if len(s.body.split()) >= limit or " | " in s.body}
        spans = [(sp.start, sp.end, "B" if sp.slide in heavy else "A") for sp in p.slide_spans]
    out: list[LayoutSpan] = []
    for s0, s1, lay in spans:
        if out and out[-1].layout == lay:
            out[-1] = out[-1].model_copy(update={"end": s1})
        else:
            out.append(LayoutSpan(start=s0, end=s1, layout=lay, suggested=True))
    return out


def relayout(stack: CommandStack) -> list[LayoutSpan]:
    """Tavsiya sahnalari hozirgi slayd chegaralari bo'yicha qayta; inson o'zgartirgan (suggested=False) oraliqlar
    ustidan saqlanadi. Slayd chegaralari qo'lda surilgandan keyin sahna eski joyda qolmasin (DSBA9600)."""
    out = suggest_layouts(stack)
    for m in (s for s in stack.project.layout_spans if not s.suggested):
        cut: list[LayoutSpan] = []
        for s in out:
            if s.end <= m.start or s.start >= m.end:
                cut.append(s)
                continue
            if s.start < m.start:
                cut.append(s.model_copy(update={"end": m.start}))
            if s.end > m.end:
                cut.append(s.model_copy(update={"start": m.end}))
        out = sorted(cut + [m], key=lambda s: s.start)
    merged: list[LayoutSpan] = []
    for s in out:
        if merged and merged[-1].layout == s.layout and merged[-1].suggested == s.suggested:
            merged[-1] = merged[-1].model_copy(update={"end": s.end})
        else:
            merged.append(s)
    return merged


THANKS = ("rahmat", "e'tibor", "etibor", "thank", "attention")
FAREWELL_SEARCH_S = 60


def thanks_slide(spans: list[SlideSpan], slides: list[Slide], words: list[Word], fps: Fraction,
                 total: int) -> list[SlideSpan]:
    """Oxirgi slayd xayrlashuv slaydi ("E'tiboringiz uchun rahmat") bo'lsa va ko'rsatilmagan bo'lsa — ma'ruzachi
    xayrlashuv gapini boshlagan joydan oxirigacha (AI matn bo'yicha topa olmaydi: slaydda so'z yo'q)."""
    if not slides or not spans:
        return spans
    last = slides[-1]
    text = uz_text.normalize(f"{last.title} {last.body}")
    if last.index in {s.slide for s in spans} or not any(k in text for k in map(uz_text.normalize, THANKS)):
        return spans
    ws = sorted(words, key=lambda w: w.start_ms)
    bye = {uz_text.normalize(x) for x in ("rahmat", "ko'rishguncha", "ko'rishgunimizcha",
                                          "thank", "thanks", "goodbye", "bye")}
    end_ms = int(Fraction(total) / fps * 1000)
    hit = next((i for i in range(len(ws) - 1, -1, -1) if ws[i].start_ms >= end_ms - FAREWELL_SEARCH_S * 1000
                and uz_text.normalize(ws[i].text).strip(".,!") in bye), None)
    if hit is None:
        return spans
    i = hit
    while i > 0 and hit - i < 4 and ws[i - 1].text.rstrip()[-1:] not in ".?!":   # gap boshi ("e'tiboringiz…")
        i -= 1
    f = round(Fraction(ws[i].start_ms - 300, 1000) * fps)
    keep = [s for s in spans if s.start < f]
    if not keep:
        return spans
    keep[-1] = keep[-1].model_copy(update={"end": f})
    return [*keep, SlideSpan(start=f, end=total, slide=last.index, source="ai", confidence=0.9)]


def unshown_slides(spans: list[SlideSpan], n_slides: int) -> list[int]:
    return sorted(set(range(1, n_slides + 1)) - {s.slide for s in spans})


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
        spans = thanks_slide(r.spans, p.slides, words, p.fps_frac, p.total_frames)
        out = {"mode": "ai", "boundaries": [asdict(b) for b in r.boundaries],
               "suspicious": [asdict(b) for b in r.suspicious]}
    out["unshown"] = unshown_slides(spans, len(p.slides))   # gapirilmagan (ko'rsatilmagan) slaydlar — inson hal qiladi
    stack.do(f"slayd sinxroni ({out['mode']})", {"slide_spans": [s.model_dump(mode="json") for s in spans]})
    wf = store.cache("asr") / "words.json"
    if any(s.anim for s in p.slides) and wf.is_file():   # javob o'qituvchi aytganda chiqadi
        ws = [Word(**w) for w in json.loads(wf.read_text(encoding="utf-8"))]
        steps = anim.step_times(p.slides, spans, ws, p.fps_frac, p.total_frames)
        stack.do("animatsiya qadamlari", {"anim_steps": [s.model_dump(mode="json") for s in steps]})
        out["anim_steps"] = len(steps)
    stack.do("sahna tavsiyasi", {"layout_spans": [s.model_dump(mode="json") for s in suggest_layouts(stack)]})
    (store.cache("sync") / f"{out['mode']}_align.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                                    encoding="utf-8")
    return out
