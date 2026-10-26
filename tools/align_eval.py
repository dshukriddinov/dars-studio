"""Slayd moslashtirish baholash va parametr tanlash (FR-08, G3).

    python tools/align_eval.py --lesson NOM=LOYIHA:GT.csv ... [--grid] [--out natija.md]

LOYIHA da cache/asr/words.json (python -m darsstudio.cli asr) va slaydlar matni bo'lishi kerak.
GT.csv — qo'lda belgilangan chegaralar: `time,slide` (soniya yoki m:ss, "shu paytdan boshlab shu slayd").
--grid: (a, b, c, λ1, λ2, λ3, τ) bo'yicha qidiruv, hamma darslar o'rtacha ±2 s ulushi bo'yicha eng yaxshisi.
"""

import argparse
import itertools
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from darsstudio.project.model import Word
from darsstudio.project.store import ProjectStore
from darsstudio.sync import ai_align, metrics


def load(spec: str) -> tuple[str, list[Word], object, list[metrics.GtBoundary]]:
    name, rest = spec.split("=", 1)
    proj, gt = rest.rsplit(":", 1)
    store = ProjectStore(Path(proj))
    p = store.load()
    words = [Word(**w) for w in json.loads((store.cache("asr") / "words.json").read_text(encoding="utf-8"))]
    return name, words, p, metrics.read_gt(Path(gt))


def run(lessons: list, params: ai_align.Params) -> list[tuple[str, metrics.Report]]:
    out = []
    for name, words, p, gt in lessons:
        r = ai_align.align(words, p.slides, p.total_frames, p.fps_frac, params)
        pred = metrics.frames_to_pred([(b.frame, b.slide, b in r.suspicious) for b in r.boundaries], p.fps_frac)
        out.append((name, metrics.evaluate(gt, pred)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson", action="append", required=True, metavar="NOM=LOYIHA:GT.csv")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    lessons = [load(s) for s in a.lesson]
    best = ai_align.Params()
    if a.grid:
        score_best = -1.0
        for b, c, l1, l2, l3, tau in itertools.product([0.3, 0.6, 1.0], [0.0, 0.1, 0.3], [0.2, 0.5, 1.0],
                                                       [1.5, 2.5], [2.0, 3.0, 5.0], [0.3, 0.5, 1.0]):
            prm = replace(best, b=b, c=c, lam_next=l1, lam_skip=l2, lam_back=l3, tau=tau)
            sc = sum(r.within_2s for _, r in run(lessons, prm)) / len(lessons)
            if sc > score_best:
                score_best, chosen = sc, prm
        best = chosen
    rows = run(lessons, best)
    cols = list(asdict(rows[0][1]).keys())
    md = ["| dars | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    md += [f"| {n} | " + " | ".join(str(v) for v in asdict(r).values()) + " |" for n, r in rows]
    text = "\n".join(md) + f"\n\nParametrlar: {asdict(best)}\n"
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
