"""Pauzalarni kesish takliflari (FR-09, TZ 9.5). Pauza = ketma-ket so'zlar orasidagi bo'shliq ∩ VAD nutqsiz
oraliq, uzunligi >= min_pause. Kesiladigan qism: pauza o'rtasidan keep_pause qoldirib (har tomonda yarmi).
Kesish nuqtalari kadr chegarasiga (ichkariga) tekislanadi, shuning uchun so'z ichiga hech qachon tushmaydi."""

import bisect
import math
from collections.abc import Sequence
from fractions import Fraction
from typing import Any

from darsstudio.asr import uz_text
from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import CutProposal, LayoutSpan, Project, Word

MIN_PAUSE_S = 1.2
KEEP_PAUSE_S = 0.35
# Dars boshi/oxiri: salomlashishdan oldingi ("boshlasangiz bo'ladi") va xayrlashishdan keyingi qism kesiladi
GREETINGS = ("assalomu", "assalom", "salom", "hurmatli", "aziz", "qadrli")
FAREWELLS = ("ko'rishguncha", "ko'rishgunimizcha", "xayr", "salomat", "rahmat")
EVENT_MIN_PROB = 0.6     # yo'tal/aksa ehtimoli (PANNs); pastrog'i ko'pincha oddiy nafas
EVENT_MIN_GAP_MS = 300
WORD_CUT_REASONS = ("bosh", "oxir", "takror")   # so'zni ataylab kesadigan sabablar (TZ 8.2 istisno)
TRIM_SEARCH_S = 60      # signal dars boshidagi/oxiridagi shuncha soniya ichida izlanadi
TRIM_PAD_S = (0.3, 0.6)  # salomdan oldin / xayrdan keyin qoldiriladigan bo'shliq


def trim_cuts(words: Sequence[Word], fps: Fraction, total: int) -> list[CutProposal]:
    """Bosh (birinchi salomlashish so'zigacha) va oxir (oxirgi xayrlashish so'zidan keyin) kesishlari."""
    if not words:
        return []
    norm = [uz_text.normalize(w.text) for w in words]
    greet, bye = tuple(map(uz_text.normalize, GREETINGS)), tuple(map(uz_text.normalize, FAREWELLS))
    total_ms = int(Fraction(total) / fps * 1000)
    out = []
    head = next((i for i, n in enumerate(norm) if n.startswith(greet) and words[i].start_ms < TRIM_SEARCH_S * 1000),
                None)
    if head:  # 0 — salomdan oldin hech narsa yo'q
        end = math.floor(Fraction(max(0, words[head].start_ms - int(TRIM_PAD_S[0] * 1000)), 1000) * fps)
        if end > 0:
            out.append(CutProposal(start=0, end=end, reason="bosh", status="tasdiqlangan"))
    tail = next((i for i in range(len(norm) - 1, -1, -1) if norm[i].startswith(bye)
                 and words[i].end_ms > total_ms - TRIM_SEARCH_S * 1000), None)
    if tail is not None:
        start = math.ceil(Fraction(words[tail].end_ms + int(TRIM_PAD_S[1] * 1000), 1000) * fps)
        if start < total:
            out.append(CutProposal(start=start, end=total, reason="oxir", status="tasdiqlangan"))
    return out


def event_cuts(events: Sequence[dict[str, Any]], words: Sequence[Word], fps: Fraction, total: int,
               min_prob: float = EVENT_MIN_PROB, keep_s: float = KEEP_PAUSE_S) -> list[CutProposal]:
    """Yo'tal/aksa kabi hodisalar (audio/events.py) -> kesish takliflari. Kesish hodisa joylashgan so'zlar orasidagi
    bo'shliqni (har tomonda keep_s/2 qoldirib) qamraydi; bo'shliq so'zlarga tegmaydi (TZ 8.2). Hodisa so'z ustida
    bo'lsa (bo'shliq < EVENT_MIN_GAP_MS) — taklif yo'q (kesish nutqni buzadi)."""
    ws = sorted(words, key=lambda w: w.start_ms)
    starts = [w.start_ms for w in ws]
    out: list[CutProposal] = []
    for e in events:
        if e["prob"] < min_prob:
            continue
        c = (e["start_ms"] + e["end_ms"]) // 2
        i = bisect.bisect_right(starts, c)                     # ws[i-1] — markazdan oldin boshlangan so'z
        lo = ws[i - 1].end_ms if i else 0
        hi = ws[i].start_ms if i < len(ws) else int(Fraction(total) / fps * 1000)
        if hi - lo < EVENT_MIN_GAP_MS or c < lo:
            continue
        half = int(keep_s * 500)
        cs, ce = math.ceil(Fraction(lo + half, 1000) * fps), math.floor(Fraction(hi - half, 1000) * fps)
        if ce - cs >= 1 and not any(cs < o.end and o.start < ce for o in out):
            out.append(CutProposal(start=cs, end=min(ce, total), reason=e["kind"]))
    return out


def stutter_cuts(words: Sequence[Word], fps: Fraction, max_gap_ms: int = 700) -> list[CutProposal]:
    """Ketma-ket takrorlangan so'z ("yaʼni yaʼni"): birinchisi kesiladi (oldingi so'z oxiridan ikkinchisi boshigacha).
    Matn bo'yicha — aniqlik past (ma'ruzada atamalar ataylab takrorlanadi), faqat taklif."""
    ws = sorted(words, key=lambda w: w.start_ms)
    norm = [uz_text.normalize(w.text) for w in ws]
    out = []
    for i in range(1, len(ws)):
        a, b = ws[i - 1], ws[i]
        # yolg'on takrorlar (sinov videosi): nol uzunlikli so'z — CTC tekislash artefakti; ".uch" — kasr (93.3);
        # "rais, rais o'rinbosari" — tinish belgisidan keyingi takror ro'yxat
        artefact = (min(a.end_ms - a.start_ms, b.end_ms - b.start_ms) < 60 or b.text.startswith(".")
                    or a.text.rstrip()[-1:] in ",.;:")
        if norm[i] == norm[i - 1] and len(norm[i]) > 1 and b.start_ms - a.end_ms <= max_gap_ms and not artefact:
            lo = ws[i - 2].end_ms if i >= 2 else ws[i - 1].start_ms
            cs, ce = math.ceil(Fraction(lo, 1000) * fps), math.floor(Fraction(ws[i].start_ms, 1000) * fps)
            if ce > cs:
                out.append(CutProposal(start=cs, end=ce, reason="takror"))
    return out


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
        if c.status != "tasdiqlangan" or c.reason in WORD_CUT_REASONS:  # so'zlarni ataylab kesadi
            continue
        cs_ms, ce_ms = Fraction(c.start) / fps * 1000, Fraction(c.end) / fps * 1000
        if any(w.start_ms < ce_ms and cs_ms < w.end_ms for w in words):
            bad.append(c)
    return bad


def timemap(p: Project) -> TimeMap:
    """Faqat tasdiqlangan kesishlar bo'yicha TimeMap (barcha chiqish vaqtlari shundan)."""
    return TimeMap.from_cuts(p.total_frames, [(c.start, c.end) for c in p.cuts if c.status == "tasdiqlangan"],
                             p.fps_frac)
