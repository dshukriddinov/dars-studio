"""Pauzalarni kesish takliflari (FR-09, TZ 9.5). Pauza = ketma-ket so'zlar orasidagi bo'shliq ∩ VAD nutqsiz
oraliq, uzunligi >= min_pause. Kesiladigan qism: pauza o'rtasidan keep_pause qoldirib (har tomonda yarmi).
Kesish nuqtalari kadr chegarasiga (ichkariga) tekislanadi, shuning uchun so'z ichiga hech qachon tushmaydi."""

import math
from collections.abc import Sequence
from fractions import Fraction

from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import CutProposal, LayoutSpan, Project, Word

MIN_PAUSE_S = 1.2
KEEP_PAUSE_S = 0.35


def _intersect(a: list[tuple[int, int]], b: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        s, e = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if s < e:
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def word_gaps(words: Sequence[Word], total_ms: int) -> list[tuple[int, int]]:
    gaps, pos = [], 0
    for w in sorted(words, key=lambda w: w.start_ms):
        if w.start_ms > pos:
            gaps.append((pos, w.start_ms))
        pos = max(pos, w.end_ms)
    if pos < total_ms:
        gaps.append((pos, total_ms))
    return gaps


def propose(words: Sequence[Word], vad_silence_ms: list[tuple[int, int]], fps: Fraction, total: int,
            min_pause_s: float = MIN_PAUSE_S, keep_pause_s: float = KEEP_PAUSE_S,
            layouts: Sequence[LayoutSpan] = (), prefer_fullscreen: bool = False) -> list[CutProposal]:
    total_ms = int(Fraction(total) / fps * 1000)
    pauses = _intersect(word_gaps(words, total_ms), sorted(vad_silence_ms))
    keep_half = keep_pause_s * 1000 / 2
    out = []
    for s, e in pauses:
        if (e - s) < min_pause_s * 1000:
            continue
        cs = math.ceil(Fraction(int(s + keep_half), 1000) * fps)
        ce = math.floor(Fraction(int(e - keep_half), 1000) * fps)
        if s == 0:          # dars boshidagi jimlik: boshidan
            cs = 0
        if e >= total_ms:   # oxiridagi jimlik
            ce = total
        if ce - cs >= 1:
            out.append(CutProposal(start=cs, end=min(ce, total), reason="pause"))
    if prefer_fullscreen and layouts:
        def in_b(c: CutProposal) -> bool:
            return any(sp.layout == "B" and sp.start <= c.start and c.end <= sp.end for sp in layouts)

        out.sort(key=lambda c: (not in_b(c), c.start))
    return out


def check_no_word_cut(cuts: Sequence[CutProposal], words: Sequence[Word], fps: Fraction) -> list[CutProposal]:
    """Tasdiqlangan kesishlardan so'z ichiga tushganlari (TZ 8.2 invarianti). Bo'sh ro'yxat — hammasi to'g'ri."""
    bad = []
    for c in cuts:
        if c.status != "tasdiqlangan":
            continue
        cs_ms, ce_ms = Fraction(c.start) / fps * 1000, Fraction(c.end) / fps * 1000
        if any(w.start_ms < ce_ms and cs_ms < w.end_ms for w in words):
            bad.append(c)
    return bad


def timemap(p: Project) -> TimeMap:
    """Faqat tasdiqlangan kesishlar bo'yicha TimeMap (barcha chiqish vaqtlari shundan)."""
    return TimeMap.from_cuts(p.total_frames, [(c.start, c.end) for c in p.cuts if c.status == "tasdiqlangan"],
                             p.fps_frac)
