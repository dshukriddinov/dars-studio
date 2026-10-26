"""Eksport fayl nomlari va slayd vaqtlari jadvali (FR-17).

Nom: `<fan>_<dars>_<mavzu>_v<N>` (sozlanadi), versiya avtomatik oshadi (exports/v<N>/).
CSV: slide_no, title, src_start, src_end, out_start, out_end, layout, source, confidence (soniya, 3 xona).
"""

import csv
import io
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from darsstudio.asr import uz_text
from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import Project

DEFAULT_PATTERN = "{fan}_{dars}_{mavzu}"


def slug(s: str, maxlen: int = 40) -> str:
    s = uz_text.normalize_display(s).replace(uz_text.OKINA, "").replace(uz_text.TUTUQ, "").replace("'", "")
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return s[:maxlen] or "dars"


def next_version(exports: Path) -> int:
    nums = [int(m.group(1)) for d in exports.glob("v*") if (m := re.fullmatch(r"v(\d+)", d.name))]
    return max(nums, default=0) + 1


def export_name(p: Project, version: int, pattern: str = DEFAULT_PATTERN) -> str:
    m = p.meta
    fields = {"fan": slug(m.get("fan", "")), "dars": slug(m.get("dars", m.get("dars_raqami", ""))),
              "mavzu": slug(m.get("mavzu", "")), "nom": slug(p.name)}
    base = "_".join(x for x in pattern.format(**fields).split("_") if x and x != "dars") or slug(p.name)
    return f"{base}_v{version}"


def _sec(f: int | None, fps: Fraction) -> float | None:
    return None if f is None else round(float(Fraction(f) / fps), 3)


def slide_rows(p: Project, tm: TimeMap) -> list[dict[str, Any]]:
    fps = p.fps_frac
    rows = []
    for sp in p.slide_spans:
        out = tm.map_span(sp.start, sp.end)
        lays = [ls.layout for ls in p.layout_spans if ls.start < sp.end and sp.start < ls.end]
        title = p.slides[sp.slide - 1].title if 0 < sp.slide <= len(p.slides) else ""
        rows.append({"slide_no": sp.slide, "title": title, "src_start": _sec(sp.start, fps),
                     "src_end": _sec(sp.end, fps), "out_start": _sec(out[0][0], fps) if out else None,
                     "out_end": _sec(out[-1][1], fps) if out else None, "layout": "/".join(dict.fromkeys(lays)),
                     "source": sp.source, "confidence": round(sp.confidence, 3),
                     "src_frames": [sp.start, sp.end], "out_frames": [out[0][0], out[-1][1]] if out else None})
    return rows


CSV_COLS = ["slide_no", "title", "src_start", "src_end", "out_start", "out_end", "layout", "source", "confidence"]


def to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, CSV_COLS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def write_tables(p: Project, tm: TimeMap, base: Path) -> tuple[Path, Path]:
    rows = slide_rows(p, tm)
    c, j = base.with_suffix(".slides.csv"), base.with_suffix(".slides.json")
    c.write_text(to_csv(rows), encoding="utf-8-sig")  # Excel o'zbekcha belgilarni to'g'ri ochsin
    j.write_text(json.dumps({"fps": p.fps, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    return c, j
