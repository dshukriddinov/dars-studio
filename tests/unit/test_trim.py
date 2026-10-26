"""Dars boshi/oxirini kesish (salomlashish / xayrlashish signallari)."""

import math
from fractions import Fraction

from darsstudio.project import cuts
from darsstudio.project.model import Word


def test_trim_head_and_tail() -> None:
    """Salomdan oldingi va xayrlashishdan keyingi qism kesiladi; so'z invarianti ularga tegmaydi."""
    fps = Fraction(25)
    ws = [Word(text=t, start_ms=s, end_ms=s + 400, conf=0.9) for t, s in
          [("boshlasangiz", 800), ("bo'ladi.", 1400), ("Assalomu", 4100), ("alaykum,", 4600), ("ma'ruza", 10000),
           ("rahmat.", 90000), ("keyingi", 91000), ("darsda", 91500), ("ko'rishguncha.", 92000), ("musiqa", 92500)]]
    total = 95 * 25
    c = cuts.trim_cuts(ws, fps, total)
    assert [(x.start, x.end, x.reason, x.status) for x in c] == [
        (0, 95, "bosh", "tasdiqlangan"), (math.ceil(93.0 * 25), total, "oxir", "tasdiqlangan")]
    assert cuts.check_no_word_cut(c, ws, fps) == []
    assert cuts.trim_cuts(ws[2:5], fps, 11 * 25) == []     # salom boshida, xayr yo'q
