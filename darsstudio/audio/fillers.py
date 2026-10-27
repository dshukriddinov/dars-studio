"""O'ylab turish tovushlari ("mmm", "eee") — ASR ularni yozmaydi. Belgilari (sinov videosi, 1113.6 s, o'lchandi):
so'zlar orasidagi bo'shliqda nutq balandligidagi (-9..-12 dBFS) ovozli tovush, ohang (F0) deyarli o'zgarmaydi
(110–115 Hz, oddiy nutqda doim o'zgaradi), >= 250 ms. Model kerak emas: avtokorrelyatsiya, 30 ms kadrlar."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from darsstudio.project.model import Word

SR = 16000
HOP = 480                 # 30 ms
MIN_GAP_MS = 250
MIN_RUN_MS = 240
VOICED = 0.5              # avtokorrelyatsiya cho'qqisi (0..1)
LEVEL_DB = 18.0           # butun audio RMS'idan shuncha past bo'lsa ham hisoblanadi
F0_TOL, F0_SHARE = 0.08, 0.75   # kadrlarning >= 75% i F0 medianasidan +-8% ichida (oktava xatolariga chidamli)
F0_RANGE = (70, 400)


@dataclass
class Filler:
    start_ms: int          # tovush
    end_ms: int
    gap: tuple[int, int]   # u joylashgan so'zlar orasidagi bo'shliq
    f0: float
    level_db: float


def _frames(seg: npt.NDArray[np.float32]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """-> rms_db, voiced (0..1), f0 (Hz) har 30 ms kadr uchun."""
    fr = seg[: len(seg) // HOP * HOP].reshape(-1, HOP).astype(np.float64)
    fr = fr - fr.mean(1, keepdims=True)
    rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    spec = np.fft.rfft(fr, 2 * HOP)
    ac = np.fft.irfft(np.abs(spec) ** 2)[:, :HOP]
    lo, hi = SR // F0_RANGE[1], SR // F0_RANGE[0]
    lag = lo + np.argmax(ac[:, lo:hi], axis=1)
    voiced = ac[np.arange(len(fr)), lag] / (ac[:, 0] + 1e-12)
    return rms, voiced, SR / lag


def detect(wav: npt.NDArray[np.float32], words: Sequence[Word]) -> list[Filler]:
    """wav 16 kHz mono (denoise qilingan bo'lsa yaxshi) + so'z vaqtlari -> bo'shliqlardagi o'ylab turish tovushlari."""
    ws = sorted(words, key=lambda w: w.start_ms)
    ref = 20 * np.log10(np.sqrt(float((wav.astype(np.float64) ** 2).mean())) + 1e-9)
    need = int(np.ceil(MIN_RUN_MS / 30))
    out = []
    for a, b in zip(ws, ws[1:], strict=False):
        g0, g1 = a.end_ms + 30, b.start_ms - 30         # so'z chetlaridagi tovushlarni chetlab
        if g1 - g0 < MIN_GAP_MS:
            continue
        rms, v, f0 = _frames(wav[g0 * SR // 1000: g1 * SR // 1000])
        on = (v >= VOICED) & (rms >= ref - LEVEL_DB)
        i = 0
        while i < len(on):
            if not on[i]:
                i += 1
                continue
            j = i
            while j < len(on) and on[j]:
                j += 1
            if j - i >= need:
                f = f0[i:j]
                med = float(np.median(f))
                if float(np.mean(np.abs(f - med) / med <= F0_TOL)) >= F0_SHARE:
                    out.append(Filler(g0 + i * 30, g0 + j * 30, (a.end_ms, b.start_ms), round(med, 1),
                                      round(float(rms[i:j].mean()), 1)))
            i = j
    return out
