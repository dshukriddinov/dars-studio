"""CTC forced alignment (Viterbi) sintetik emissiyalarda; worker protokoli."""

import numpy as np

from darsstudio.asr import word_align
from darsstudio.asr.engines.base import Segment
from darsstudio.asr.engines.ctc import Emissions
from darsstudio.jobs import worker
from darsstudio.project.model import Word

VOCAB = {"|": 0, "a": 1, "b": 2, "l": 3, "o": 4, "m": 5, "‘": 6, "[PAD]": 7}
BLANK = 7


def emissions(frames: list[str], peak: float = 0.9) -> Emissions:
    """Har kadr uchun eng ehtimolli belgi ('_' = blank)."""
    V = len(VOCAB)
    lp = np.full((len(frames), V), np.log((1 - peak) / (V - 1)), np.float32)
    for t, ch in enumerate(frames):
        lp[t, BLANK if ch == "_" else VOCAB[ch]] = np.log(peak)
    return Emissions(lp, 20.0, VOCAB, BLANK, 0)


def test_viterbi_recovers_known_path() -> None:
    frames = list("__aaa__bb___")
    path = word_align.viterbi(emissions(frames).logp, [1, 2], BLANK)
    assert path is not None
    toks = ["_" if s % 2 == 0 else "ab"[s // 2] for s in path]
    assert "".join(toks) == "".join(frames)


def test_viterbi_repeated_letters_need_blank() -> None:
    # "oo" (bir xil ketma-ket token) o'rtasida blank shart
    path = word_align.viterbi(emissions(list("_o_o_")).logp, [4, 4], BLANK)
    assert path is not None and [s for s in path if s % 2] == [1, 3]
    assert word_align.viterbi(emissions(list("oo")).logp, [4, 4], BLANK) is None


def test_align_segment_word_times() -> None:
    # "bola" 5-12 kadrlar, ajratgich, "olma" 15-22 kadrlar (20 ms kadr)
    frames = list("_____bbool_a__|_oollmmaa______")
    em = emissions(frames)
    seg = Segment(0, 600, "bola olma", [Word(text="Bola", start_ms=0, end_ms=100, conf=0.5),
                                        Word(text="olma,", start_ms=100, end_ms=200, conf=0.5)])
    out = word_align.align_segment(seg, em, pad_ms=0)
    assert out is not None
    assert [(w.text, w.start_ms, w.end_ms) for w in out] == [("Bola", 100, 240), ("olma,", 320, 480)]
    assert all(w.conf > 0.8 for w in out)


def test_word_tokens_okina_alias() -> None:
    assert word_align.word_tokens("Oʻ", VOCAB) == [4, 6]
    assert word_align.word_tokens("o'", VOCAB) == [4, 6]


def test_worker_error_is_reported() -> None:
    try:
        worker.run_isolated("asr_raw", {"wav16k": "yoq.wav", "engine": "yoq", "out_dir": "x"})
    except worker.WorkerError as e:
        assert "asr_raw" in str(e)
    else:
        raise AssertionError("xato kutilgan edi")
