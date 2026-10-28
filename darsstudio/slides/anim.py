"""Slayd animatsiyasi qadamlari: javob o'qituvchi aytganda chiqadi (topshiriqni tushuntirayotganda ko'rinmaydi).

Vaqt: har bosishda chiqadigan matn (Slide.anim) slayd oralig'idagi nutqdan tartib bilan qidiriladi; topilgan so'z
boshida bosish (montajchi uslubi: "it's | present simple"). Slaydning o'z matnidagi ibora ("TRUE OR FALSE" sarlavhasi)
o'qilganda javob chiqmaydi. Topilmagan bosish kechroq qo'yiladi (keyingi topilgandan yoki slayd oxiridan oldin) —
xato bo'lsa ham javob erta ko'rinmaydi.
"""

import math
import re
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path

from rapidfuzz import fuzz

from darsstudio.asr import uz_text
from darsstudio.project.model import AnimStep, Slide, SlideSpan, Word

LEAD_MS = 100          # bosish so'z boshidan biroz oldin (paydo bo'lish effekti so'z bilan tugaydi)
MIN_GAP_MS = 500       # ketma-ket bosishlar orasida kamida
LATE_STEP_MS = 1500    # topilmagan bosishlar oralig'i (keyingi topilgandan yoki slayd oxiridan orqaga)


def _tokens(text: str) -> list[str]:
    toks = re.findall(r"[^\W_]+(?:[ʼ'][^\W_]+)?", uz_text.normalize(text))
    return [t for t in toks if len(t) > 1 or t.isdigit()]


STOP = set("the a an is are am was were be it its itʼs he she they we you i me my our your his her their of to in on "
           "at for and or but with by as do does so this that these those there what which who va bu u ular bilan "
           "uchun ham endi demak".split())


def _alike(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 4 and fuzz.ratio(a, b) >= 80)   # "continuous" ~ "continues"


def _find(target: list[str], ks: list[str], start: int, static: str) -> int | None:
    """target ibora ks[start:] da tartib bilan uchragan birinchi joy (ibora birinchi mos so'zi indeksi)."""
    # mazmunli so'zlar bo'yicha ("He is the CEO" -> "ceo"): yordamchi so'zlar savol gapida ham bor
    content = [t for t in target if t not in STOP] or target
    need = len(content) if len(content) <= 2 else math.ceil(0.6 * len(content))
    for i in range(start, len(ks)):
        if not any(_alike(ks[i], t) for t in content[:2]):
            continue
        hits, q, first = 0, i, None
        for t in content:
            m = next((x for x in range(q, min(len(ks), q + 7)) if _alike(ks[x], t)), None)
            if m is not None:
                hits, q, first = hits + 1, m + 1, m if first is None else first
        if hits < need or first is None:
            continue
        # javob iborasi chetidan slaydning o'z matni davom etsa ("true or false", "simple or continuous") —
        # o'qituvchi topshiriq matnini o'qiyapti, javobni emas
        edges = [" ".join(ks[a:a + 2]) for a in (first - 1, q - 1) if a >= 0 and a + 2 <= len(ks)]
        if any(f" {g} " in f" {static} " for g in edges):
            continue
        return first
    return None


def step_times(slides: Sequence[Slide], spans: Sequence[SlideSpan], words: Sequence[Word], fps: Fraction,
               total: int) -> list[AnimStep]:
    ws = sorted(words, key=lambda w: w.start_ms)
    to_f = lambda ms: max(0, min(total - 1, round(Fraction(int(ms), 1000) * fps)))  # noqa: E731
    out: list[AnimStep] = []
    for sl in slides:
        if not sl.anim:
            continue
        own = sorted((s for s in spans if s.slide == sl.index), key=lambda s: s.start)
        if not own:
            continue
        span_ms = [(int(s.start / fps * 1000), int(s.end / fps * 1000)) for s in own]
        sw = [w for w in ws if any(a <= w.start_ms < b for a, b in span_ms)]
        ks = [(_tokens(w.text) or [""])[0] for w in sw]
        body = sl.body
        for a in sl.anim:   # javob shakllari matni asosiy matnda (oxirgisi); sarlavhaga tegilmaydi ("TRUE OR FALSE")
            j = body.rfind(a)
            body = body[:j] + " " + body[j + len(a):] if a and j >= 0 else body
        static = " ".join(_tokens(f"{sl.title}\n{body}"))
        found: list[int | None] = []
        cur = 0
        for text in sl.anim:
            # "Answers: 1→e 2→h ..." — hammasi bir bosishda: o'qituvchi "now answers" deganda (yorliq bo'yicha)
            label = re.match(r"\s*([^:\n]{2,25}):", text)
            target = _tokens(label.group(1)) if label and len(_tokens(text)) > 8 else _tokens(text)
            i = _find(target, ks, cur, static) if target else None
            if i is not None:
                cur = i + 1
            found.append(sw[i].start_ms - LEAD_MS if i is not None else None)
        lo, hi = span_ms[0][0], span_ms[-1][1]
        times: list[int] = []
        for k, t in enumerate(found):
            prev = times[-1] if times else lo
            if t is None:   # kechroq: keyingi topilgan bosishdan (yoki slayd oxiridan) orqaga sanab
                nxt = next(((j, x) for j, x in enumerate(found[k + 1:], k + 1) if x is not None), None)
                end, left = (nxt[1], nxt[0] - k) if nxt else (hi, len(found) - k)
                t = max(prev + MIN_GAP_MS, end - left * LATE_STEP_MS)
            times.append(max(t, prev + MIN_GAP_MS) if times else max(t, lo))
        for k, t in enumerate(times, 1):
            out.append(AnimStep(slide=sl.index, click=k, frame=to_f(min(t, hi - 1)),
                                source="ai"))
    return out


def display_spans(slide_spans: Sequence[SlideSpan], steps: Sequence[AnimStep],
                  clicks: dict[int, int]) -> list[tuple[int, int, int]]:
    """(boshlanish kadri, slayd, holat) — holat = bajarilgan bosishlar soni. Animatsiyali slayd uchun qadam
    vaqtlari bo'lmasa — yakuniy holat (avvalgi xatti-harakat). Animatsiyasiz slaydda holat 0."""
    marks: dict[int, list[int]] = {}
    for st in steps:
        marks.setdefault(st.slide, []).append(st.frame)
    out = []
    for sp in sorted(slide_spans, key=lambda s: s.start):
        n = clicks.get(sp.slide, 0)
        fr = sorted(marks.get(sp.slide, []))[:n]
        if n == 0 or not fr:
            out.append((sp.start, sp.slide, n))
            continue
        out.append((sp.start, sp.slide, sum(f <= sp.start for f in fr)))
        out += [(f, sp.slide, k) for k, f in enumerate(fr, 1) if sp.start < f < sp.end]
    return out


def image_id(slide: int, state: int) -> int:
    """Kompozitor rasmi: animatsiyasiz slayd — o'z raqami; qadamlar 1000 dan yuqorida (slayd = id % 1000)."""
    return slide + 1000 * state


def image_table(finals: Sequence[Path], steps: dict[int, list[Path]]) -> dict[int, Path]:
    """{image_id: fayl}: animatsiyali slaydning 0..n-1 holatlari qadam rasmlari, n — yakuniy; boshqalari 0."""
    out: dict[int, Path] = {}
    for i, f in enumerate(finals, 1):
        st = steps.get(i, [])
        out[image_id(i, len(st))] = f
        for k, sf in enumerate(st):
            out[image_id(i, k)] = sf
    return out


def clicks_of(slides: Sequence[Slide], steps: dict[int, list[Path]]) -> dict[int, int]:
    """Render qilingan qadamlar soni (PowerPoint'siz render — qadam yo'q, yakuniy holat)."""
    return {s.index: min(len(s.anim), len(steps.get(s.index, []))) for s in slides if s.anim}
