"""TimeMap property testlari (TZ 13.2: hypothesis, >= 500 misol)."""

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from darsstudio.media.timemap import TimeMap

FPS = st.sampled_from([Fraction(25), Fraction(30000, 1001), Fraction(30)])
TOTAL = st.integers(min_value=0, max_value=5000)


@st.composite
def cuts_case(draw: st.DrawFn) -> tuple[int, list[tuple[int, int]], Fraction]:
    total = draw(TOTAL)
    pts = st.integers(min_value=-10, max_value=total + 10)
    cuts = draw(st.lists(st.tuples(pts, pts).map(lambda t: (min(t), max(t))), max_size=20))
    return total, cuts, draw(FPS)


def kept(total: int, cuts: list[tuple[int, int]]) -> list[int]:
    return [f for f in range(total) if not any(s <= f < e for s, e in cuts)]


@settings(max_examples=500, deadline=None)
@given(cuts_case())
def test_mapping_properties(case: tuple[int, list[tuple[int, int]], Fraction]) -> None:
    total, cuts, fps = case
    tm = TimeMap.from_cuts(total, cuts, fps)
    k = kept(total, cuts)
    # jami davomiylik
    assert tm.out_total == len(k)
    # kesilgan kadrlar None, saqlanganlari ketma-ket 0..out_total-1 (monoton, bo'shliqsiz)
    assert [tm.src_to_out(f) for f in k] == list(range(len(k)))
    assert all(tm.src_to_out(f) is None for f in set(range(total)) - set(k))
    # teskarilanuvchanlik
    assert [tm.out_to_src(g) for g in range(tm.out_total)] == k


@settings(max_examples=500, deadline=None)
@given(cuts_case(), st.integers(min_value=-10, max_value=5010), st.integers(min_value=0, max_value=5000))
def test_map_span(case: tuple[int, list[tuple[int, int]], Fraction], s: int, length: int) -> None:
    total, cuts, fps = case
    tm = TimeMap.from_cuts(total, cuts, fps)
    e = s + length
    spans = tm.map_span(s, e)
    inside = [tm.src_to_out(f) for f in kept(total, cuts) if s <= f < e]
    # chiqish uzluksiz: bitta oraliq yoki bo'sh, uzunligi saqlangan kadrlar soniga teng
    assert len(spans) <= 1
    assert sum(b - a for a, b in spans) == len(inside)
    if spans:
        assert spans[0] == (inside[0], inside[-1] + 1)


@settings(max_examples=500, deadline=None)
@given(FPS, st.integers(min_value=0, max_value=200_000))
def test_audio_sample(fps: Fraction, f: int) -> None:
    tm = TimeMap([(0, f + 1)], fps)
    a = tm.audio_sample(f)
    assert a == round(Fraction(f) * 48000 / fps)
    assert abs(Fraction(a, 48000) - Fraction(f) / fps) <= Fraction(1, 96000)
    assert tm.audio_sample(f + 1) > a


def test_merge_and_errors() -> None:
    tm = TimeMap([(10, 20), (0, 5), (5, 8), (15, 30), (40, 40)], Fraction(25))
    assert tm.ranges == [(0, 8), (10, 30)]
    assert tm.out_total == 28
    with pytest.raises(ValueError):
        TimeMap([(5, 3)], Fraction(25))
    with pytest.raises(IndexError):
        tm.out_to_src(28)


def test_ntsc_audio_exact() -> None:
    # 29.97: 1001 kadr = 1601.6 ... 30000 kadr = 1001 s -> aniq 48 048 000 namuna, suzuvchi xato yig'ilmaydi
    tm = TimeMap([(0, 30000)], Fraction(30000, 1001))
    assert tm.audio_sample(30000) == 48_048_000
    assert tm.audio_ranges() == [(0, 48_048_000)]
