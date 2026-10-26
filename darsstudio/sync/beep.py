"""Beep sinxroni (TZ 9.6, FR-07): 1 kHz, 300 ms, Hann oyna; 16 kHz audioda matched filter (FFT korrelatsiya),
birinchi 120 s ichida; cho'qqi parabolik interpolatsiya bilan (namunadan aniqroq)."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

SR = 16000
FREQ, DUR_S, SEARCH_S = 1000.0, 0.3, 120.0
MIN_SNR = 6.0


@dataclass(frozen=True)
class BeepResult:
    start_s: float       # beep boshlanishi, audio boshidan
    snr: float           # cho'qqi / korrelatsiya medianasi
    reliable: bool


def template(sr: int = SR) -> npt.NDArray[np.float64]:
    t = np.arange(int(DUR_S * sr)) / sr
    return np.sin(2 * np.pi * FREQ * t) * np.hanning(len(t))


def find_beep(audio: npt.NDArray[np.float32], sr: int = SR, search_s: float = SEARCH_S) -> BeepResult:
    x = audio[: int(search_s * sr)].astype(np.float64)
    tpl = template(sr)
    n = len(x) + len(tpl) - 1
    nfft = 1 << (n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(x, nfft) * np.conj(np.fft.rfft(tpl, nfft)), nfft)[: len(x) - len(tpl) + 1]
    # energiya bo'yicha normallashtirish: baland nutq "beep"ga o'xshab ketmasin
    energy = np.sqrt(np.convolve(x * x, np.ones(len(tpl)), "valid")) + 1e-9
    score = np.abs(corr) / energy
    i = int(np.argmax(score))
    off = 0.0
    if 0 < i < len(score) - 1:  # parabolik interpolatsiya
        a, b, c = score[i - 1], score[i], score[i + 1]
        den = a - 2 * b + c
        off = 0.5 * (a - c) / den if den else 0.0
    snr = float(score[i] / (np.median(score) + 1e-12))
    return BeepResult(start_s=(i + off) / sr, snr=round(snr, 2), reliable=snr >= MIN_SNR)
