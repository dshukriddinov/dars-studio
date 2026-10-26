"""Loudness (FR-04, AC-08): EBU R128 o'lchovi va ikki o'tishli loudnorm (2-o'tish chiziqli rejimda)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from darsstudio.media import ffmpeg

PROFILES = {"standart": (-16.0, -1.5, 11.0), "youtube": (-14.0, -1.5, 11.0)}  # I, TP, LRA


@dataclass(frozen=True)
class Loudness:
    integrated: float   # LUFS
    true_peak: float    # dBTP
    lra: float          # LU
    threshold: float    # LUFS (loudnorm "input_thresh")
    offset: float = 0.0


def _loudnorm_json(stderr: str) -> dict[str, str]:
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.S)
    if not m:
        raise ffmpeg.FfmpegError("loudnorm o'lchovi o'qilmadi")
    out: dict[str, str] = json.loads(m.group(0))
    return out


def measure(path: Path, pre_filter: str = "") -> Loudness:
    """1-o'tish: loudnorm o'lchovi (EBU R128 integrated, true peak, LRA)."""
    af = (pre_filter + "," if pre_filter else "") + "loudnorm=print_format=json"
    r = ffmpeg.run(["-v", "info", "-nostdin", "-i", str(path), "-af", af, "-f", "null", "-"])
    d = _loudnorm_json(r.stderr)
    return Loudness(float(d["input_i"]), float(d["input_tp"]), float(d["input_lra"]), float(d["input_thresh"]),
                    float(d.get("target_offset", 0.0)))


def loudnorm_filter(m: Loudness, profile: str = "standart") -> str:
    """2-o'tish filtri. linear=true: dinamika saqlanadi (faqat gain); true peak chegarasi limiter bilan."""
    i, tp, lra = PROFILES[profile]
    return (f"loudnorm=I={i}:TP={tp}:LRA={max(lra, m.lra)}:measured_I={m.integrated}:measured_TP={m.true_peak}"
            f":measured_LRA={m.lra}:measured_thresh={m.threshold}:offset={m.offset}:linear=true:print_format=summary")


def ebur128(path: Path) -> Loudness:
    """Mustaqil tekshiruv (QA, AC-08): ebur128 filtri bilan integrated va true peak."""
    r = ffmpeg.run(["-v", "info", "-nostdin", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    def get(k: str) -> float:
        m = re.search(rf"{k}:\s+(-?[\d.]+|-inf)", tail)
        if m is None:
            raise ffmpeg.FfmpegError(f"ebur128 natijasida {k} yo'q")
        return float(m.group(1).replace("-inf", "-120"))

    return Loudness(integrated=get("I"), true_peak=get("Peak"), lra=get("LRA"), threshold=get("Threshold"))
