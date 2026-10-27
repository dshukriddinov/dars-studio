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


def _w(items: list[tuple[str, int]]) -> list[Word]:
    return [Word(text=t, start_ms=s, end_ms=s + 300, conf=0.9) for t, s in items]


def test_event_cuts_only_in_word_gaps() -> None:
    fps = Fraction(25)
    ws = _w([("bir", 0), ("ikki", 1000), ("uch", 4000), ("tort", 4400)])
    ev = [{"start_ms": 2000, "end_ms": 2800, "kind": "yo'tal", "prob": 0.9},     # 1300..4000 bo'shliqda
          {"start_ms": 4100, "end_ms": 4300, "kind": "aksa", "prob": 0.9},       # so'zlar orasi 100 ms — yo'q
          {"start_ms": 2000, "end_ms": 2800, "kind": "yo'tal", "prob": 0.3}]     # past ehtimol
    c = cuts.event_cuts(ev, ws, fps, 200)
    assert [(x.start, x.end, x.reason, x.status) for x in c] == [
        (math.ceil(1.475 * 25), math.floor(3.825 * 25), "yo'tal", "taklif")]
    assert cuts.check_no_word_cut([x.model_copy(update={"status": "tasdiqlangan"}) for x in c], ws, fps) == []


def test_stutter_cuts_first_repeat() -> None:
    fps = Fraction(25)
    ws = _w([("demak", 0), ("yaʼni", 1000), ("yaʼni,", 1500), ("saylov", 2000), ("saylov", 5000)])
    c = cuts.stutter_cuts(ws, fps)
    assert [(x.start, x.end, x.reason) for x in c] == [(math.ceil(0.3 * 25), math.floor(1.5 * 25), "takror")]


def test_stutter_false_positives_skipped() -> None:
    fps = Fraction(25)
    ws = [Word(text=x, start_ms=s, end_ms=e, conf=0.9) for x, s, e in
          [("uch", 0, 150), (".uch", 500, 620), ("rais,", 1000, 1300), ("rais", 1400, 1600),
           ("saylov", 2000, 2000), ("saylov", 2000, 2300)]]
    assert cuts.stutter_cuts(ws, fps) == []
