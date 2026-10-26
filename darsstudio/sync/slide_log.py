"""Slayd jurnali (FR-07, TZ 4.4): `tools/slide_logger.py` yozgan CSV -> SlideSpan (source="log").

CSV: birinchi qator `sync_beep_t_ns,<ns>`, keyin sarlavha `t_ns,event,slide_index,build_index` va hodisalar.
Jurnal vaqti -> video vaqti: video_s = (t_ns - beep_ns) / 1e9 + beep_video_s (beep audioda topilgan joy).
"""

import csv
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from darsstudio.project.model import SlideSpan

SHORT_S = 1.0  # bundan qisqa oraliqlar foydalanuvchiga ko'rsatiladi (FR-07)


@dataclass(frozen=True)
class LogEvent:
    t_ns: int
    event: str
    slide: int
    build: int


def read_log(path: Path) -> tuple[int, list[LogEvent]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0][0] != "sync_beep_t_ns":
        raise ValueError(f"{path.name}: birinchi qator 'sync_beep_t_ns,<ns>' bo'lishi kerak")
    beep = int(rows[0][1])
    head = rows[1]
    ev = [dict(zip(head, r, strict=False)) for r in rows[2:] if r]
    return beep, [LogEvent(int(e["t_ns"]), e["event"], int(e["slide_index"] or 0), int(e.get("build_index") or 0))
                  for e in ev]


def to_spans(beep_ns: int, events: list[LogEvent], beep_video_s: float, fps: Fraction,
             total: int) -> tuple[list[SlideSpan], list[tuple[int, int]]]:
    """(oraliqlar, qisqa oraliqlar [s, e) kadrlarda). Ortga qaytishlar ham saqlanadi (jurnal haqiqatni yozadi)."""
    changes: list[tuple[int, int]] = []
    for e in events:
        if e.event in ("SlideShowBegin", "SlideShowNextSlide") and e.slide > 0:
            f = round((Fraction(e.t_ns - beep_ns, 10**9) + Fraction(beep_video_s).limit_denominator(10**6)) * fps)
            f = min(max(f, 0), total)
            if changes and changes[-1][0] == f:
                changes[-1] = (f, e.slide)
            elif not changes or changes[-1][1] != e.slide:
                changes.append((f, e.slide))
    if not changes:
        return [], []
    changes[0] = (0, changes[0][1])  # yozuv jurnaldan oldin boshlangan: birinchi slayd boshidan
    spans, short = [], []
    for i, (f, slide) in enumerate(changes):
        end = changes[i + 1][0] if i + 1 < len(changes) else total
        if end <= f:
            continue
        spans.append(SlideSpan(start=f, end=end, slide=slide, source="log", confidence=1.0, approved=False))
        if (end - f) < SHORT_S * fps:
            short.append((f, end))
    return spans, short
