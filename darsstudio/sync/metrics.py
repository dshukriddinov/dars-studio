"""Slayd chegaralari baholash (FR-08, AC-03): ground truth bilan solishtirish."""

import csv
import statistics
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from darsstudio.render.prepare import parse_time


@dataclass
class GtBoundary:
    t_s: float
    slide: int


def read_gt(path: Path) -> list[GtBoundary]:
    """CSV `time,slide` (soniya yoki m:ss): shu paytdan boshlab shu slayd. Birinchi qator (0 s) chegara emas."""
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out.append(GtBoundary(float(parse_time(r["time"])), int(r["slide"])))
    out.sort(key=lambda b: b.t_s)
    return [b for b in out if b.t_s > 0]


@dataclass
class Report:
    n_gt: int
    n_pred: int
    within_1s: float
    within_2s: float
    within_5s: float
    median_err_s: float | None
    suspicious_share: float          # bashorat qilingan chegaralardan "shubhali"lar ulushi (AC: <= 20%)
    wrong_flagged_share: float | None  # xato (> 2 s yoki yo'q) chegaralardan shubhali deb belgilanganlar (>= 70%)


def evaluate(gt: list[GtBoundary], pred: list[tuple[float, int, bool]], tol_s: float = 2.0) -> Report:
    """pred: (vaqt s, yangi slayd, shubhalimi). Har GT chegarasi uchun shu slaydga o'tgan eng yaqin bashorat."""
    errs: list[float] = []
    used: set[int] = set()
    for g in gt:
        cand = [(abs(t - g.t_s), i) for i, (t, s, _) in enumerate(pred) if s == g.slide and i not in used]
        if cand:
            e, i = min(cand)
            used.add(i)
            errs.append(e)
        else:
            errs.append(float("inf"))
    n = max(1, len(gt))
    finite = [e for e in errs if e != float("inf")]
    # xato bashoratlar: GT bilan +-tol ichida mos kelmagan bashoratlar
    matched_ok = {i for i, (t, s, _) in enumerate(pred) if any(s == g.slide and abs(t - g.t_s) <= tol_s for g in gt)}
    wrong = [i for i in range(len(pred)) if i not in matched_ok]
    return Report(
        n_gt=len(gt), n_pred=len(pred),
        within_1s=round(sum(e <= 1 for e in errs) / n, 4), within_2s=round(sum(e <= 2 for e in errs) / n, 4),
        within_5s=round(sum(e <= 5 for e in errs) / n, 4),
        median_err_s=round(statistics.median(finite), 3) if finite else None,
        suspicious_share=round(sum(p[2] for p in pred) / max(1, len(pred)), 4),
        wrong_flagged_share=round(sum(pred[i][2] for i in wrong) / len(wrong), 4) if wrong else None)


def frames_to_pred(boundaries: list[tuple[int, int, bool]], fps: Fraction) -> list[tuple[float, int, bool]]:
    return [(float(Fraction(f) / fps), s, susp) for f, s, susp in boundaries]
