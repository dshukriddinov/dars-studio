"""SRT (FR-17): so'z vaqtlari TimeMap orqali chiqish vaqtiga; satr <= 42 belgi, <= 2 qator, 1–7 s, gap chegarasida
bo'lish. Matn "chiroyli" normallashtiriladi (lotin, toʻgʻri apostrof, raqamlar raqamligicha)."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from darsstudio.asr import uz_text
from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import Word

MAX_LINE, MAX_LINES = 42, 2
MIN_S, MAX_S = 1.0, 7.0
GAP_SPLIT_MS = 700


@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str


def _out_ms(ms: int, tm: TimeMap) -> int | None:
    f = int(Fraction(ms, 1000) * tm.fps)
    g = tm.src_to_out(f)
    if g is None:
        return None
    return int((Fraction(g) / tm.fps + (Fraction(ms, 1000) - Fraction(f) / tm.fps)) * 1000)


def _wrap(words: list[str]) -> list[str] | None:
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= MAX_LINE:
            cur = f"{cur} {w}" if cur else w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines if len(lines) <= MAX_LINES and all(len(x) <= MAX_LINE for x in lines) else None


def build_cues(words: Sequence[Word], tm: TimeMap) -> list[Cue]:
    items = []
    for w in words:
        s, e = _out_ms(w.start_ms, tm), _out_ms(max(w.start_ms, w.end_ms - 1), tm)
        if s is None or e is None:   # kesilgan qismdagi so'z (bo'lmasligi kerak)
            continue
        items.append((s, e + 1, uz_text.normalize_display(w.text)))
    cues: list[Cue] = []
    cur: list[tuple[int, int, str]] = []

    def flush() -> None:
        if cur:
            cues.append(Cue(cur[0][0], cur[-1][1], "\n".join(_wrap([t for _, _, t in cur]) or [])))
            cur.clear()

    for it in items:
        if cur:
            dur = (it[1] - cur[0][0]) / 1000
            fits = _wrap([t for _, _, t in cur] + [it[2]]) is not None
            sentence_end = re.search(r"[.!?…]$", cur[-1][2]) is not None
            gap = it[0] - cur[-1][1]
            long_enough = (cur[-1][1] - cur[0][0]) / 1000 >= MIN_S
            if not fits or dur > MAX_S or gap > GAP_SPLIT_MS or (sentence_end and long_enough):
                flush()
        cur.append(it)
    flush()
    # gap boshidagi harf katta; minimal davomiylik (keyingi titrgacha cho'zish)
    for i, c in enumerate(cues):
        c.text = c.text[:1].upper() + c.text[1:]
        if (c.end_ms - c.start_ms) < MIN_S * 1000:
            nxt = cues[i + 1].start_ms if i + 1 < len(cues) else c.start_ms + int(MIN_S * 1000)
            c.end_ms = min(c.start_ms + int(MIN_S * 1000), nxt)
    end_ms = int(Fraction(tm.out_total) / tm.fps * 1000)   # titr videodan uzun bo'lmasin (QA)
    cues = [c for c in cues if c.start_ms < end_ms]
    for c in cues:
        c.end_ms = min(c.end_ms, end_ms)
    return cues


def _ts(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: Sequence[Cue]) -> str:
    return "".join(f"{i}\n{_ts(c.start_ms)} --> {_ts(c.end_ms)}\n{c.text}\n\n" for i, c in enumerate(cues, 1))
