"""Pauzalarni kesish takliflari (FR-09, TZ 9.5). Pauza = ketma-ket so'zlar orasidagi bo'shliq ∩ VAD nutqsiz
oraliq, uzunligi >= min_pause. Kesiladigan qism: pauza o'rtasidan keep_pause qoldirib (har tomonda yarmi).
Kesish nuqtalari kadr chegarasiga (ichkariga) tekislanadi, shuning uchun so'z ichiga hech qachon tushmaydi."""

import bisect
import math
import re
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
WORD_CUT_REASONS = ("bosh", "oxir", "takror", "qism")   # so'zni ataylab kesadigan sabablar (TZ 8.2 istisno)
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


NUMBER_ROOTS = tuple(uz_text.normalize(x) for x in (
    "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz", "o'n", "yigirma", "o'ttiz", "qirq",
    "ellik", "oltmish", "yetmish", "sakson", "to'qson", "yuz", "ming", "million", "milliard", "trillion"))


NUMBER_RE = re.compile("^(" + "|".join(re.escape(r) for r in NUMBER_ROOTS) + ")"
                       r"(inchi|nchi|ta|tasi|tadan|i|ni|da|dan|ga|ning|lab|lik|dagi)?$")


def _is_number(w: str) -> bool:
    """Son so'zi (ildiz + son qo'shimchasi): "oltinchi", "uchta", "birinchi" — ha; "uchast" (uchastka) — yo'q."""
    return bool(NUMBER_RE.match(w))


def _alike(a: str, b: str) -> bool:
    """O'xshash so'z (ASR xatolari, qo'shimchalar). Sonlar aynan teng bo'lishi shart: "to'rtinchi" ~ "oltinchi"
    (difflib 0.7+) yilni almashtirib, haqiqiy gapni takror deb kesardi (DSBA9359, 324 s)."""
    import difflib
    if a == b:
        return True
    if _is_number(a) or _is_number(b):
        return False
    return min(len(a), len(b)) >= 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.7


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


REPEAT_MAX_S = 20.0
REPEAT_MIN_RUN = 7         # tashlab ketilgan urinish: shuncha so'z tartib bilan qayta aytilgan (6 da reja bandlari
                           # "xalq deputatlari viloyat… saylov prinsiplari / …saylov organlari" takror deb topildi)
REPEAT_MIN_SENTENCE = 3    # to'liq gap qayta aytilgan ("e'tiboringiz uchun rahmat.")


def repeat_cuts(words: Sequence[Word], fps: Fraction) -> list[CutProposal]:
    """Uzun takrorlar (DSBA9359, xulosa va xayrlashuv): 20 s ichida
    1) >= 6 so'z ketma-ket qayta aytilgan va ikkinchisi ibora boshidan — birinchi urinish tashlab ketilgan:
       uning gapi boshidan ikkinchisi boshigacha kesiladi ("Xulosa qilamiz. Byudjet daromadi… haqida, e, | Xulosa
       qiladigan bo'lsak, byudjet daromadi…" — oldidagi qisqa "xulosa qilamiz." ham, chunki ikkinchisi xuddi shu
       so'z bilan boshlanadi);
    2) >= 3 so'zli to'liq gap aynan qayta aytilgan — birinchisi kesiladi."""
    ws = sorted(words, key=lambda w: w.start_ms)
    k = [_key(w.text) for w in ws]
    n = len(ws)

    def start_of(i: int) -> bool:
        return i == 0 or _ends_sentence(ws[i - 1]) or ws[i].start_ms - ws[i - 1].end_ms >= PHRASE_GAP_MS \
            or ws[i - 1].text.rstrip()[-1:] == ","

    def run(i: int, j: int) -> int:
        t = 0
        while j + t < n and i + t < j and _alike(k[i + t], k[j + t]):
            t += 1
        return t

    def loose(i: int, j: int) -> int:
        """Tartibli moslik, 1–2 so'z qo'shilishi/tushishiga chidamli ("byudjet daromadi [bu] yalpi…")."""
        if not (_alike(k[i], k[j]) and i + 1 < j and j + 1 < n and _alike(k[i + 1], k[j + 1])):
            return 0
        hits, q = 0, i
        for b in range(j, min(n, j + 12)):
            m = next((x for x in range(q, min(j, q + 3)) if _alike(k[x], k[b])), None)
            if m is not None:
                hits, q = hits + 1, m + 1
            elif _is_number(k[b]):   # boshqa son ("2026-yilda 372 / 2028-yilda 484") — takror emas
                return 0
        return hits

    out: list[CutProposal] = []
    i = 0
    while i < n:
        hit = None
        for j in range(i + REPEAT_MIN_SENTENCE, n):
            if ws[j].start_ms - ws[i].start_ms > REPEAT_MAX_S * 1000:
                break
            if not start_of(j) or len(k[j]) < 2:
                continue
            L = run(i, j)
            # birinchi urinish tugallanmagan (i va j orasida gap oxiri yo'q): to'liq gapdagi atamalarning keyingi gapda
            # takrorlanishi — takror emas (Eshankulov: mavzu nomi kirishda va reja ichida)
            if start_of(i) and loose(i, j) >= REPEAT_MIN_RUN and not any(_ends_sentence(ws[m]) for m in range(i, j)):
                s = i   # takror ibora boshidan (gap boshidagi takrorlanmagan qism qoladi)
                # oldingi qisqa ibora ("xulosa qilamiz.") ikkinchi urinish boshidagi so'z bilan boshlansa — u ham
                p0 = _sentence_start(ws, s - 1) if s > 0 else s
                j0 = _sentence_start(ws, j)
                if s > 0 and s - p0 <= 4 and _alike(k[p0], k[j0]):
                    s, j = p0, j0
                hit = (s, j)
                break
            if L >= REPEAT_MIN_SENTENCE and start_of(i) and _ends_sentence(ws[i + L - 1]) \
                    and _ends_sentence(ws[j + L - 1]) and (i + L == j or not _ends_sentence(ws[i + L - 2])):
                hit = (i, i + L)
                break
        if hit and hit[1] < n:
            a, b = hit
            lo = ws[a - 1].end_ms if a else ws[a].start_ms
            cs, ce = _mid_frame(lo, ws[a].start_ms, fps, True), _mid_frame(ws[b - 1].end_ms, ws[b].start_ms, fps, False)
            if ce > cs:
                out.append(CutProposal(start=cs, end=ce, reason="takror"))
            i = b
        else:
            i += 1
    return out


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


START_CUE = re.compile(r"^boshl\w*(sangiz|ang|ayvering|adik)$")   # "boshlasangiz bo'ladi" (ASR: "boshlsangiz")
PART_SEARCH_S = 20


def part_join_cuts(words: Sequence[Word], parts: Sequence[Any], fps: Fraction) -> list[CutProposal]:
    """Video qismlari ulanadigan joy: oldingi qismning oxirgi so'zidan keyingi qismi va keyingi qism boshidagi
    "uch, ikki, bir, boshlasangiz bo'ladi" (yoki shunchaki jimlik) — birinchi haqiqiy so'zgacha. Sabab "qism"."""
    ws = sorted(words, key=lambda w: w.start_ms)

    def ms(f: int) -> int:
        return int(Fraction(f) / fps * 1000)

    out = []
    for prev, part in zip(parts, parts[1:], strict=False):
        b0, b1 = ms(part.start), ms(part.start + part.frames)
        before = [w for w in ws if ms(prev.start) <= w.start_ms < b0]
        inside = [w for w in ws if b0 <= w.start_ms < min(b1, b0 + PART_SEARCH_S * 1000)]
        cue = [i for i, w in enumerate(inside) if START_CUE.match(_key(w.text))]
        if cue:   # "boshlasangiz (bo'ladi)" -> undan keyingi so'z
            k = cue[-1] + 1
            if k < len(inside) and _key(inside[k].text) in (uz_text.normalize("bo'ladi"), "boladi"):
                k += 1
            nxt = inside[k] if k < len(inside) else None
        else:     # signal yo'q: qism boshidagi jimlik
            nxt = inside[0] if inside else None
        s = before[-1].end_ms + 400 if before else b0
        e = nxt.start_ms - 300 if nxt else b0
        ov = _part_overlap(before, [w for w in ws if b0 <= w.start_ms < min(b1, b0 + OVERLAP_SEARCH_S * 1000)])
        if ov:   # keyingi qismda oldingi qism oxiri qayta o'qilgan: takrorlangan (uzilgan) qism va oraliq kesiladi
            a, b = ov
            s = (a.start_ms + _prev_end(before, a)) // 2
            e = b.start_ms - 150
        cs, ce = math.ceil(Fraction(s, 1000) * fps), math.floor(Fraction(max(e, s), 1000) * fps)
        if ce > cs:
            out.append(CutProposal(start=cs, end=ce, reason="qism", status="tasdiqlangan"))
    return out


OVERLAP_SEARCH_S = 60      # keyingi qism boshidan shuncha ichida takror izlanadi
OVERLAP_TAIL_S = 120       # oldingi qism oxiridan
OVERLAP_MIN = 4            # 8 so'zlik oynada kamida shuncha o'xshash so'z (tartib bilan)


def _prev_end(ws: Sequence[Word], w: Word) -> int:
    i = ws.index(w)
    return ws[i - 1].end_ms if i else w.start_ms


def _sentence_start(ws: Sequence[Word], i: int) -> int:
    while i > 0 and not _ends_sentence(ws[i - 1]) and ws[i].start_ms - ws[i - 1].end_ms < PHRASE_GAP_MS * 2:
        i -= 1
    return i


def _part_overlap(before: Sequence[Word], after: Sequence[Word]) -> tuple[Word, Word] | None:
    """O'qituvchi keyingi qismda oldingi qism oxirini qayta o'qigan bo'lsa (yozuv uzilgan, slayd boshidan):
    (oldingi qismdagi takrorlangan gap boshi, keyingi qismdagi qayta o'qish gap boshi). Ikki so'z juftligi mos
    kelgan joydan 8 so'zlik oynada >= OVERLAP_MIN so'z tartib bilan o'xshash bo'lishi kerak."""
    if not before or not after:
        return None
    tail = [w for w in before if w.start_ms >= before[-1].start_ms - OVERLAP_TAIL_S * 1000]
    kt, ka = [_key(w.text) for w in tail], [_key(w.text) for w in after]
    for j in range(len(after) - 1):
        for i in range(len(tail) - 1):
            if not (_alike(kt[i], ka[j]) and _alike(kt[i + 1], ka[j + 1]) and len(kt[i]) >= 3):
                continue
            hits, q = 0, i
            for b in ka[j:j + 8]:                  # tartibli moslik (so'z tushib qolishiga chidamli)
                m = next((x for x in range(q, min(len(kt), q + 3)) if _alike(kt[x], b)), None)
                if m is not None:
                    hits, q = hits + 1, m + 1
            if hits >= OVERLAP_MIN:
                return tail[_sentence_start(tail, i)], after[_sentence_start(after, j)]
    return None


REREAD_CUES = re.compile(r"^(qayta(dan|tdan)|boshqa(tdan|ttan)|boshidan|yangidan|adash\w*|kechirasiz|uzr)$")
REREAD_LOOKBACK_S = 90.0
REREAD_PAUSE_MS = 1500     # signal so'zsiz: shundan uzun pauzadan keyin qayta boshlash
REREAD_HITS = (5, 7)       # 8 so'zlik oynada tartibli mos so'zlar: signal bilan / signalsiz


def _ordered_hits(k: list[str], a: int, a_end: int, j: int, n: int, strict_numbers: bool = True) -> int:
    """strict_numbers: boshqa son — takror emas (yillar). Tuzatish signali bo'lsa son farqi tuzatishning o'zi."""
    hits, q = 0, a
    for b in range(j, min(n, j + 8)):
        m = next((x for x in range(q, min(a_end, q + 3)) if _alike(k[x], k[b])), None)
        if m is not None:
            hits, q = hits + 1, m + 1
        elif strict_numbers and _is_number(k[b]):
            return 0
    return hits


def _loose_tail(k: list[str], a0: int, a1: int, b0: int, b1: int) -> int | None:
    """[b0, b1) iborasi eski matnning [a0, a1) qismiga tartib bilan mos kelsa — eski matndagi birinchi mos so'z indeksi.
    Faqat son bo'lmagan so'zlar hisoblanadi (>= 3 va >= 40%): "ikki ming," umumiy so'zlari bilan haqiqiy gap
    takror deb olinardi (DSBA9359, 610 s)."""
    hits, q, first = 0, a0, None
    for b in range(b0, b1):
        m = next((x for x in range(q, a1) if _alike(k[x], k[b])), None)
        if m is not None:
            hits, q = hits + (not _is_number(k[b])), m + 1
            first = m if first is None else first
    return first if hits >= max(3, 0.4 * (b1 - b0)) else None


def reread_cuts(words: Sequence[Word], fps: Fraction) -> list[CutProposal]:
    """Ma'ruzachi 1–3 gap orqaga qaytib qayta aytgan joy: "qaytadan", "boshqatdan", "boshidan", "adashdim…" signalidan
    keyingi 15 s ichidagi ibora boshi (oraliqda "demak", xodimlar bilan gaplashuv bo'lishi mumkin) yoki uzun
    pauzadan keyingi ibora. Undan keyingi 8 so'z oldingi 90 s dagi nutq bilan tartibli moslanadi; mos kelgan eng
    yaqin joyning gap boshidan qayta boshlash gapi boshigacha kesiladi. Signalsiz holatda moslik talabi qattiqroq."""
    ws = sorted(words, key=lambda w: w.start_ms)
    k = [_key(w.text) for w in ws]
    n = len(ws)

    def phrase(j: int) -> bool:
        return (_ends_sentence(ws[j - 1]) or ws[j - 1].text.rstrip()[-1:] == ","
                or ws[j].start_ms - ws[j - 1].end_ms >= PHRASE_GAP_MS)

    def match(j: int, end: int, need: int) -> int | None:
        lo_t = ws[j].start_ms - REREAD_LOOKBACK_S * 1000
        for a in range(end - 2, -1, -1):               # eng yaqin moslik (1–3 gap orqaga)
            if ws[a].start_ms < lo_t:
                return None
            # birinchi so'z + tartibli moslik ("bu demak, birinchi uchast saylov…" / "bu uchta saylov…")
            if _alike(k[a], k[j]) and _ordered_hits(k, a, end, j, n, strict_numbers=need > REREAD_HITS[0]) >= need:
                return a
        return None

    out: list[CutProposal] = []
    j = 1
    while j < n - 1:
        hit = None
        if REREAD_CUES.match(k[j - 1]) or (ws[j].start_ms - ws[j - 1].end_ms >= REREAD_PAUSE_MS and phrase(j)):
            cue = j - 1 if REREAD_CUES.match(k[j - 1]) else None
            cands = [x for x in range(j, min(n - 1, j + 16)) if phrase(x)
                     and ws[x].start_ms - ws[j - 1].end_ms <= 15000] if cue is not None else [j]
            for x in cands:
                a = match(x, cue if cue is not None else x, REREAD_HITS[0] if cue is not None else REREAD_HITS[1])
                if a is not None:
                    hit = (_sentence_start(ws, a), x)
                    break
        if hit:
            s, x = hit
            for _ in range(3):   # yangi urinish ertaroq boshlangan bo'lishi mumkin (ASR uni boshqacha yozgan)
                p = next((y for y in range(x - 1, s, -1) if phrase(y)), None)
                if p is None or ws[x].start_ms - ws[p].start_ms > 8000:
                    break
                m = _loose_tail(k, max(0, s - 15), s, p, x)
                if m is None:
                    break
                s, x = _sentence_start(ws, m), p
            lo = ws[s - 1].end_ms if s else ws[s].start_ms
            cs, ce = _mid_frame(lo, ws[s].start_ms, fps, True), _mid_frame(ws[x - 1].end_ms, ws[x].start_ms, fps, False)
            if ce > cs:
                out.append(CutProposal(start=cs, end=ce, reason="takror"))
            j = x + 8
        else:
            j += 1
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
