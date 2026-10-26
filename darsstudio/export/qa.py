"""QA hisoboti (FR-19): eksport qilingan MP4 va yon fayllarni avtomatik tekshirish. Natija `qa.json` va UI'da.

Tekshiruvlar: chiqish faylini ffprobe bilan qayta o'qish, kadr soni va davomiylik, A/V siljish, loudness va true peak,
qora/muzlagan kadrlar, har kadrda aynan bitta sahna, barcha slayd oraliqlari slayd fayliga ega, tasdiqlanmagan
shubhali joylar, SRT vaqtlari monoton.
"""

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

from darsstudio.audio import loudness
from darsstudio.media import ffmpeg
from darsstudio.media.probe import MediaError, probe
from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import LayoutSpan, Project

Status = Literal["ok", "ogohlantirish", "xato"]
LUFS_TOL = 1.0
TP_MAX = -1.5
FREEZE_S = 4.0     # A sahnada o'qituvchi harakatlanadi: shundan uzun muzlash — shubhali
BLACK_S = 0.5


@dataclass
class QaCheck:
    id: str
    status: Status
    detail: str


def check_file(out: Path, expected_frames: int, fps: Fraction) -> list[QaCheck]:
    try:
        q = probe(out)
    except MediaError as e:
        return [QaCheck("fayl", "xato", str(e))]
    res = [QaCheck("fayl", "ok", f"{q.video.codec} {q.video.width}x{q.video.height}, {q.video.pix_fmt}, "
                                 f"{q.video.color_space}/{q.video.color_range}")]
    n = q.video.nb_frames
    res.append(QaCheck("kadr_soni", "ok" if n == expected_frames else "xato", f"{n} kadr, kutilgan {expected_frames}"))
    d_frames = abs(float(q.duration * fps) - expected_frames)
    res.append(QaCheck("davomiylik", "ok" if d_frames <= 1 else "xato", f"{float(q.duration):.3f} s"))
    if q.audio is None:
        res.append(QaCheck("av_siljish", "xato", "audio yo'q"))
    else:
        off = abs(float(q.av_offset)) * float(fps)
        res.append(QaCheck("av_siljish", "ok" if off <= 1 else "xato", f"{float(q.av_offset) * 1000:.1f} ms"))
    return res


def check_loudness(out: Path, target: float = -16.0) -> QaCheck:
    m = loudness.ebur128(out)
    ok = abs(m.integrated - target) <= LUFS_TOL and m.true_peak <= TP_MAX
    return QaCheck("loudness", "ok" if ok else "xato", f"{m.integrated} LUFS (maqsad {target}), TP {m.true_peak} dBTP")


def _intervals(stderr: str, start_key: str, end_key: str) -> list[tuple[float, float]]:
    s = [float(x) for x in re.findall(rf"{start_key}[:=]\s*([\d.]+)", stderr)]
    e = [float(x) for x in re.findall(rf"{end_key}[:=]\s*([\d.]+)", stderr)]
    return list(zip(s, e + [float("inf")] * (len(s) - len(e)), strict=False))


def check_black_frozen(out: Path, b_ranges_s: Sequence[tuple[float, float]] = ()) -> list[QaCheck]:
    r = ffmpeg.run(["-v", "info", "-nostdin", "-i", str(out), "-map", "0:v:0", "-vf",
                    f"blackdetect=d={BLACK_S}:pix_th=0.10,freezedetect=n=0.002:d={FREEZE_S}", "-f", "null", "-"])
    black = _intervals(r.stderr, "black_start", "black_end")
    fz = _intervals(r.stderr, r"lavfi\.freezedetect\.freeze_start", r"lavfi\.freezedetect\.freeze_end")
    # B sahna (statik slayd) muzlash emas: to'liq B oralig'i ichidagilar hisobga olinmaydi
    # fayl oxirigacha davom etgan muzlashda freeze_end yo'q (inf): oxiri sifatida boshlanishi olinadi
    frozen = [(s, e) for s, e in fz
              if not any(bs - 0.5 <= s and (e if e != float("inf") else s) <= be + 0.5 for bs, be in b_ranges_s)]
    fmt = lambda xs: ", ".join(f"{s:.1f}-{e:.1f} s" for s, e in xs[:5])  # noqa: E731
    return [QaCheck("qora_kadrlar", "ok" if not black else "ogohlantirish", fmt(black) or "yo'q"),
            QaCheck("muzlagan_kadrlar", "ok" if not frozen else "ogohlantirish", fmt(frozen) or "yo'q")]


def check_scenes(layouts: Sequence[LayoutSpan], tm: TimeMap) -> QaCheck:
    """Har chiqish kadrida aynan bitta sahna."""
    cover = [0] * tm.out_total
    for ls in layouts:
        for a, b in tm.map_span(ls.start, ls.end):
            for g in range(a, b):
                cover[g] += 1
    bad = [g for g, c in enumerate(cover) if c != 1]
    return QaCheck("sahna", "ok" if not bad else "xato",
                   "har kadrda bitta" if not bad else f"{len(bad)} kadrda sahna soni != 1 (birinchisi {bad[0]})")


def check_slide_files(p: Project, pngs: Sequence[Path]) -> QaCheck:
    have = {i + 1 for i, f in enumerate(pngs) if Path(f).is_file()}
    miss = sorted({s.slide for s in p.slide_spans} - have)
    return QaCheck("slayd_fayllari", "ok" if not miss else "xato",
                   "hammasi bor" if not miss else f"yo'q: {', '.join(map(str, miss))}")


def check_suspicious(n_unapproved: int, n_cut_proposals: int) -> QaCheck:
    total = n_unapproved + n_cut_proposals
    return QaCheck("tasdiqlanmagan", "ok" if total == 0 else "ogohlantirish",
                   f"shubhali chegaralar {n_unapproved}, ko'rib chiqilmagan kesish takliflari {n_cut_proposals}")


def check_srt(srt_text: str, duration_s: float) -> QaCheck:
    ts = re.findall(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)", srt_text)
    ms = lambda h, m, s, x: ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(x)  # noqa: E731
    cues = [(ms(*t[:4]), ms(*t[4:])) for t in ts]
    bad = [i for i, (a, b) in enumerate(cues) if b <= a or (i and a < cues[i - 1][1])]
    over = cues and cues[-1][1] > duration_s * 1000 + 40
    ok = not bad and not over and bool(cues)
    detail = f"{len(cues)} titr" + (f", monoton emas: {bad[:3]}" if bad else "")
    detail += ", oxiri videodan uzun" if over else ""
    return QaCheck("srt", "ok" if ok else "xato", detail)


def run(p: Project, out: Path, tm: TimeMap, pngs: Sequence[Path], srt_path: Path | None, n_unapproved: int,
        loudness_target: float = -16.0) -> dict[str, Any]:
    fps = p.fps_frac
    checks = check_file(out, tm.out_total, fps)
    checks.append(check_loudness(out, loudness_target))
    b_ranges = [(float(Fraction(a) / fps), float(Fraction(b) / fps)) for ls in p.layout_spans if ls.layout == "B"
                for a, b in tm.map_span(ls.start, ls.end)]
    checks += check_black_frozen(out, b_ranges)
    checks.append(check_scenes(p.layout_spans, tm))
    checks.append(check_slide_files(p, pngs))
    checks.append(check_suspicious(n_unapproved, sum(c.status == "taklif" for c in p.cuts)))
    if srt_path is not None:
        checks.append(check_srt(srt_path.read_text(encoding="utf-8"), tm.out_total / float(fps)))
    verdict = "xato" if any(c.status == "xato" for c in checks) else (
        "ogohlantirish" if any(c.status == "ogohlantirish" for c in checks) else "ok")
    return {"verdict": verdict, "checks": [asdict(c) for c in checks]}
