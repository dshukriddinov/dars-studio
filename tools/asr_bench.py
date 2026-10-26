"""ASR benchmark (FR-05, D-06, G2): WER, CER, atamalar aniqligi, RTF, GPU xotira; ixtiyoriy — so'z chegarasi xatosi.

    python tools/asr_bench.py --sample NOM=WAV16K[:REF.txt] ... --engines a,b,c --align CTC_NOMI
                              [--glossary glossary.json] [--boundaries NOM=belgilar.csv] [--out natija.md]

REF.txt — qo'lda tuzatilgan matn (O-06). Bo'lmasa faqat RTF/xotira va transkriptlar (sifatni inson baholaydi).
belgilar.csv — `word,start_ms,end_ms` (qo'lda belgilangan so'zlar, AC: median <= 60 ms).
Har model alohida jarayonda (worker), natijalar workdir/asr_bench/<namuna>/<model>/ da.
"""

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from rapidfuzz.distance import Levenshtein

from darsstudio import paths
from darsstudio.asr import glossary, uz_text
from darsstudio.jobs.worker import WorkerError, run_isolated


def wer(ref: list[str], hyp: list[str]) -> float:
    return Levenshtein.distance(ref, hyp) / max(1, len(ref))


def cer(ref: str, hyp: str) -> float:
    return Levenshtein.distance(ref, hyp) / max(1, len(ref))


def term_accuracy(ref_norm: str, hyp_norm: str, terms: list[glossary.Term]) -> float | None:
    found = [t for t in terms if f" {uz_text.normalize(t.term)} " in f" {ref_norm} "]
    if not found:
        return None
    return sum(f" {uz_text.normalize(t.term)} " in f" {hyp_norm} " for t in found) / len(found)


def boundary_error(words: list[dict[str, Any]], marks: Path) -> float | None:
    """Har belgilangan so'z uchun eng yaqin (vaqt bo'yicha) bir xil normallashgan so'z; |start| va |end| xatolar
    medianasi, ms."""
    errs = []
    with open(marks, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            tw, s, e = uz_text.normalize(r["word"]), int(r["start_ms"]), int(r["end_ms"])
            cands = [w for w in words if uz_text.normalize(w["text"]) == tw]
            if cands:
                w = min(cands, key=lambda w: abs(w["start_ms"] - s))
                errs += [abs(w["start_ms"] - s), abs(w["end_ms"] - e)]
    return statistics.median(errs) if errs else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="append", required=True, metavar="NOM=WAV[:REF]")
    ap.add_argument("--engines", required=True)
    ap.add_argument("--align")
    ap.add_argument("--glossary")
    ap.add_argument("--boundaries", action="append", default=[], metavar="NOM=CSV")
    ap.add_argument("--out")
    a = ap.parse_args()
    terms = glossary.load(Path(a.glossary)) if a.glossary else []
    marks = dict(b.split("=", 1) for b in a.boundaries)
    rows = []
    for s in a.sample:
        name, rest = s.split("=", 1)
        wav, _, ref = rest.partition(":")
        ref_text = Path(ref).read_text(encoding="utf-8") if ref else None
        for eng in a.engines.split(","):
            od = paths.workdir() / "asr_bench" / name / eng
            print(f"... {name} / {eng}", file=sys.stderr, flush=True)
            try:
                st = run_isolated("asr_raw", {"wav16k": wav, "engine": eng, "align": a.align,
                                          "hotwords": glossary.hotwords(terms) if terms else None,
                                          "out_dir": str(od)})
            except WorkerError as e:
                rows.append({"sample": name, "engine": eng, "error": str(e)[-300:]})
                continue
            words = json.loads((od / "words.json").read_text(encoding="utf-8"))
            hyp = uz_text.normalize(" ".join(w["text"] for w in words))
            row = {"sample": name, "engine": eng, **st}
            if ref_text is not None:
                r = uz_text.normalize(ref_text)
                row.update(wer=round(wer(r.split(), hyp.split()), 4), cer=round(cer(r, hyp), 4),
                           terms=term_accuracy(r, hyp, terms))
            if name in marks:
                row["boundary_median_ms"] = boundary_error(words, Path(marks[name]))
            (od / "transcript.txt").write_text(" ".join(w["text"] for w in words), encoding="utf-8")
            rows.append(row)
    cols = ["sample", "engine", "wer", "cer", "terms", "boundary_median_ms", "rtf", "asr_s", "gpu_mem_peak_mb",
            "words", "aligned_segments", "segments", "error"]
    cols = [c for c in cols if any(c in r for r in rows)]
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join("" if r.get(c) is None else str(r[c]) for c in cols) + " |" for r in rows]
    text = "\n".join(md)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n\n```json\n" + json.dumps(rows, ensure_ascii=False, indent=1) + "\n```\n",
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
