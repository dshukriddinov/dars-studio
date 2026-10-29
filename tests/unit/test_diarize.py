"""Diarization: fbank, boshqa-ovoz oraliqlari va ulardan kesish takliflari (modelsiz, sintetik)."""
from fractions import Fraction

import numpy as np

from darsstudio.audio import diarize
from darsstudio.project import cuts
from darsstudio.project.model import Word

FPS = Fraction(25)


def _w(t: str, s: int, e: int) -> Word:
    return Word(text=t, start_ms=s, end_ms=e, conf=0.9)


def test_fbank_shape_and_sanity() -> None:
    rng = np.random.default_rng(0)
    wav = (rng.standard_normal(16000) * 0.1).astype(np.float32)
    f = diarize.fbank(wav)
    assert f.shape == (98, 80) and np.isfinite(f).all()          # 1 s: 1 + (16000-400)//160 = 98 kadr
    assert diarize.fbank(wav[:300]).shape == (0, 80)             # juda qisqa


def test_other_spans_clusters_minority_voice() -> None:
    rng = np.random.default_rng(1)
    teacher = np.tile([1.0, 0.0], (40, 128)) + rng.standard_normal((40, 256)) * 0.05
    operator = np.tile([0.0, 1.0], (3, 128)) + rng.standard_normal((3, 256)) * 0.05
    embs = np.vstack([teacher[:20], operator, teacher[20:]]).astype(np.float32)
    embs /= np.linalg.norm(embs, axis=1, keepdims=True)
    spans = [(i * 1000, i * 1000 + 2000) for i in range(len(embs))]
    out = diarize.other_spans(embs, spans)
    assert len(out) == 1 and out[0].start_ms == 20000 and out[0].end_ms == 24000   # 3 oyna birlashdi
    assert diarize.other_spans(embs[:4], spans[:4]) == []        # juda kam oyna — ishonchsiz


def test_other_voice_cuts_snap_and_wordless() -> None:
    ws = [_w("dars", 0, 800), _w("boshlasangiz", 2000, 2700), _w("bo'ladi.", 2750, 3200), _w("assalomu", 4000, 4600)]
    out = cuts.other_voice_cuts([(1900, 3300), (10000, 11000)], ws, FPS, 2000)
    assert [c.reason for c in out] == ["boshqa_ovoz", "boshqa_ovoz"]
    assert out[0].start == 35 and out[0].end == 90               # (800+2000)/2=1400ms -> 35; (3200+4000)/2=3600 -> 90
    assert (out[1].start, out[1].end) == (250, 275)              # so'zsiz: diarization chegaralari
    assert cuts.check_no_word_cut(
        [c.model_copy(update={"status": "tasdiqlangan"}) for c in out], ws, FPS) == []


def test_reread_triggered_by_operator_voice() -> None:
    # signal so'z yo'q, uzun pauza yo'q — operator gapi o'zi signal: chala urinish + operator gapi kesiladi
    ws = ([_w(x, i * 400, i * 400 + 300) for i, x in enumerate(
        "soliq kodeksi soliqlarning to'qqiz turini belgilaydi bular davlat".split())]
        + [_w("to'xtang,", 3300, 3700), _w("xatolik", 3750, 4100), _w("bor.", 4150, 4400)]
        + [_w(x, 4600 + i * 400, 4600 + i * 400 + 300) for i, x in enumerate(
            "soliq kodeksi soliqlarning to'qqiz turini belgilaydi. bular respublika byudjetiga tushadi.".split())])
    plain = cuts.reread_cuts(ws, FPS)
    with_op = cuts.reread_cuts(ws, FPS, other_voice_ms=[(3250, 4450)])
    assert plain == []
    assert len(with_op) == 1
    kept = " ".join(w.text for w in ws if not any(c.start * 40 <= w.start_ms < c.end * 40 for c in with_op))
    assert kept == "soliq kodeksi soliqlarning to'qqiz turini belgilaydi. bular respublika byudjetiga tushadi."
