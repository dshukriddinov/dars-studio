"""O'ylab turish tovushlari: so'zlar orasidagi barqaror ohangli tovush topiladi, ohangi o'zgaruvchan tovush va
shovqin (nafas) topilmaydi; kesish so'zlarga tegmaydi; ustma-ust takliflar birlashadi."""

from fractions import Fraction
from types import SimpleNamespace

import numpy as np

from darsstudio.audio import fillers
from darsstudio.project import cuts
from darsstudio.project.model import CutProposal, Word

SR = 16000


def harmonic(f0: np.ndarray, amp: float = 0.3) -> np.ndarray:
    ph = 2 * np.pi * np.cumsum(f0) / SR
    return (amp * sum(np.sin(k * ph) / k for k in range(1, 6))).astype(np.float32)


def test_detect_steady_hum_only() -> None:
    rng = np.random.default_rng(0)
    x = np.zeros(SR * 6, np.float32)
    x[: SR] = harmonic(np.linspace(100, 180, SR))                           # "so'z" 0–1 s
    x[int(1.5 * SR): int(2.1 * SR)] = harmonic(np.full(int(0.6 * SR), 112.0))  # mmm 1.5–2.1 s
    x[int(3.4 * SR): int(4.0 * SR)] = harmonic(np.linspace(90, 220, int(0.6 * SR)))  # ohang o'zgaradi
    x[int(4.4 * SR): int(4.9 * SR)] = (0.2 * rng.standard_normal(int(0.5 * SR))).astype(np.float32)  # nafas
    x[5 * SR:] = harmonic(np.linspace(150, 100, SR))
    ws = [Word(text="bir", start_ms=0, end_ms=1000, conf=0.9), Word(text="ikki", start_ms=2600, end_ms=3000, conf=0.9),
          Word(text="uch", start_ms=5000, end_ms=6000, conf=0.9)]
    f = fillers.detect(x, ws)
    assert len(f) == 1 and abs(f[0].start_ms - 1500) <= 60 and abs(f[0].end_ms - 2100) <= 60
    assert abs(f[0].f0 - 112) < 3 and f[0].gap == (1000, 2600)


def test_filler_cut_covers_hum_not_words() -> None:
    f = SimpleNamespace(start_ms=1500, end_ms=2100, gap=(1000, 2600))
    c = cuts.filler_cuts([f], Fraction(25))[0]
    assert c.reason == "to'ldiruvchi" and c.start / 25 * 1000 <= 1500 and c.end / 25 * 1000 >= 2100
    assert c.start / 25 * 1000 >= 1030 and c.end / 25 * 1000 <= 2570


def test_union_keeps_specific_reason() -> None:
    u = cuts.union([CutProposal(start=10, end=20, reason="pause"), CutProposal(start=18, end=30, reason="to'ldiruvchi"),
                    CutProposal(start=40, end=50, reason="pause")])
    assert [(c.start, c.end, c.reason) for c in u] == [(10, 30, "to'ldiruvchi"), (40, 50, "pause")]


def test_union_word_cutting_reason_wins() -> None:
    """"mmm" + takror birlashmasi takror bo'lib qoladi (so'zlarni ataylab kesadi — eksport to'xtamaydi)."""
    u = cuts.union([CutProposal(start=10, end=16, reason="to'ldiruvchi"),
                    CutProposal(start=14, end=40, reason="takror"), CutProposal(start=38, end=50, reason="pause")])
    assert [(c.start, c.end, c.reason) for c in u] == [(10, 50, "takror")]
