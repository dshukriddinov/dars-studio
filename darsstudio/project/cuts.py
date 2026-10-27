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


RETAKE_MAX_WORDS = 10      # tashlab ketilgan urinish uzunligi (so'z)
RETAKE_MAX_S = 12.0
PHRASE_GAP_MS = 500        # shundan uzun pauza — yangi ibora boshi
CORRECTION_CUES = ("adashdim", "adashibman", "adashdik", "kechirasiz", "uzr", "qaytadan")
CORRECTION_PAIRS = (("noto'g'ri", "aytdim"), ("xato", "aytdim"), ("noto'g'ri", "aytdik"))
FILLERS = ("demak", "xo'sh", "ya'ni", "endi", "mana")
CORRECTION_LOOKBACK_S = 30.0


def _key(text: str) -> str:
    return uz_text.normalize(text).strip(".,;:?!-…")


def _alike(a: str, b: str) -> bool:
    import difflib
    return a == b or (min(len(a), len(b)) >= 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.7)


def _restart_match(k: list[str], i: int, j: int) -> bool:
    """Qayta boshlash: ikki so'z aynan bir xil, yoki uchta so'z o'xshash. ("O'zbekiston Respublikasida… bu
    O'zbekiston Respublikasining…" — bitta to'liq gap, kesilmasligi kerak.)"""
    if k[j] == k[i] and k[j + 1] == k[i + 1]:
        return True
    return j + 2 < len(k) and i + 2 < j and all(_alike(k[j + d], k[i + d]) for d in range(3))


def _ends_sentence(w: Word) -> bool:
    return w.text.rstrip()[-1:] in ".?!"


def _mid_frame(a_ms: int, b_ms: int, fps: Fraction, up: bool) -> int:
    f = Fraction(a_ms + b_ms, 2000) * fps
    return math.ceil(f) if up else math.floor(f)


def retake_cuts(words: Sequence[Word], fps: Fraction) -> list[CutProposal]:
    """Gapni qayta aytish (TZ: inson tasdiqlaydi):
    1) qayta boshlash — ibora boshidagi >= 2 so'z RETAKE_MAX_WORDS ichida pauzadan keyin qayta aytilgan, birinchi
       urinish gap oxiriga yetmagan: birinchi urinish boshidan oxirgi urinish boshigacha kesiladi (zanjir);
    2) tuzatish iborasi ("yo'q, adashdim…"): xato gap boshidan (tuzatilgan gap bilan so'zma-so'z moslab topiladi)
       to'g'ri gap boshigacha. Kesish chegaralari so'zlar orasidagi bo'shliq o'rtasida."""
    ws = sorted(words, key=lambda w: w.start_ms)
    k = [_key(w.text) for w in ws]
    n = len(ws)

    def phrase_start(i: int) -> bool:
        return i == 0 or _ends_sentence(ws[i - 1]) or ws[i].start_ms - ws[i - 1].end_ms >= PHRASE_GAP_MS

    def cut(i: int, j: int) -> CutProposal | None:
        lo = ws[i - 1].end_ms if i else ws[i].start_ms
        cs, ce = _mid_frame(lo, ws[i].start_ms, fps, True), _mid_frame(ws[j - 1].end_ms, ws[j].start_ms, fps, False)
        return CutProposal(start=cs, end=ce, reason="takror") if ce > cs else None

    out: list[CutProposal] = []
    # 1) qayta boshlash
    i = 0
    while i < n - 2:
        last = None
        cur = i
        while phrase_start(cur):
            nxt = next((j for j in range(cur + 2, min(n - 1, cur + RETAKE_MAX_WORDS + 1))
                        if phrase_start(j) and _restart_match(k, cur, j)
                        and ws[j].start_ms - ws[cur].start_ms <= RETAKE_MAX_S * 1000
                        and not any(_ends_sentence(ws[m]) for m in range(cur, j))), None)
            if nxt is None:
                break
            last, cur = nxt, nxt
        if last is not None and (cp := cut(i, last)):
            out.append(cp)
            i = last
        i += 1
    # 2) tuzatish iborasi
    for q in range(n):
        hit = k[q] in CORRECTION_CUES or any(k[q] == a and q + 1 < n and k[q + 1] == b for a, b in CORRECTION_PAIRS)
        if not hit:
            continue
        cs = q - 1 if q and k[q - 1] in ("yo'q", "yoq") else q
        ce = q
        while ce + 1 < n and not _ends_sentence(ws[ce]) and ce - q < 4:  # "…shu yerda." ibora oxiri
            ce += 1
        after = list(range(ce + 1, min(n, ce + 9)))
        before = [m for m in range(cs) if ws[cs].start_ms - ws[m].start_ms <= CORRECTION_LOOKBACK_S * 1000]
        # to'g'ri gapdagi birinchi so'z juftligi xato gapdagi (eng yaqin) juftlikka mos keladi
        match = next(((a, b) for b in after if b + 1 < n for a in reversed(before)
                      if a + 1 < cs and _alike(k[a], k[b]) and _alike(k[a + 1], k[b + 1])), None)
        err0, fix0 = match if match else (cs - 1, ce + 1)   # moslik yo'q: tuzatishdan oldingi gap
        start = err0
        while start > 0 and not _ends_sentence(ws[start - 1]) and ws[err0].start_ms - ws[start - 1].start_ms < 20000:
            start -= 1
        end = ce + 1
        for m in range(ce + 1, fix0):                    # "saylov, demak, bu uchta…" — oxirgi to'ldiruvchidan keyin
            if k[m] in FILLERS:
                end = m + 1
        if end < n and (x := cut(start, end)):
            out.append(x)
    out.sort(key=lambda x: x.start)
    merged: list[CutProposal] = []
    for c in out:
        if merged and c.start <= merged[-1].end:
            merged[-1] = merged[-1].model_copy(update={"end": max(merged[-1].end, c.end)})
        else:
            merged.append(c)
    return merged


def filler_cuts(fillers: Sequence[Any], fps: Fraction, keep_s: float = KEEP_PAUSE_S) -> list[CutProposal]:
    """O'ylab turish tovushlari (audio/fillers.py) -> kesish: tovush to'liq, atrofidagi jimlik bilan (bo'shliq chetida
    keep_s/2 qoladi), so'zlarga tegmaydi (bo'shliq chetidan 30 ms ichkarida)."""
    out = []
    half = int(keep_s * 500)
    for f in fillers:
        g0, g1 = f.gap[0] + 30, f.gap[1] - 30
        s, e = max(g0, min(f.start_ms, f.gap[0] + half)), min(g1, max(f.end_ms, f.gap[1] - half))
        cs, ce = math.ceil(Fraction(s, 1000) * fps), math.floor(Fraction(e, 1000) * fps)
        if ce > cs:
            out.append(CutProposal(start=cs, end=ce, reason="to'ldiruvchi"))
    return out


def union(cuts: Sequence[CutProposal]) -> list[CutProposal]:
    """Ustma-ust tushgan takliflarni birlashtiradi (sabab: pauzadan boshqasi ustun — u kesishning asosiy sababi)."""
    out: list[CutProposal] = []
    for c in sorted(cuts, key=lambda x: x.start):
        if out and c.start <= out[-1].end:
            last = out[-1]
            reason = last.reason if last.reason != "pause" else c.reason
            out[-1] = last.model_copy(update={"end": max(last.end, c.end), "reason": reason})
        else:
            out.append(c)
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
