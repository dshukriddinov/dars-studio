"""So'z vaqtlari CTC forced alignment bilan (FR-05, D-06). Har ASR segmenti (± pad) alohida tekislanadi:
uzun audioda butun trellis xotiraga sig'maydi, segment esa 30 s dan qisqa. Algoritm — standart CTC Viterbi
(blank'lar bilan kengaytirilgan ketma-ketlik, qolish / keyingi / bittasini o'tkazib yuborish)."""

import numpy as np
import numpy.typing as npt

from darsstudio.asr import uz_text
from darsstudio.asr.engines.base import Segment
from darsstudio.asr.engines.ctc import Emissions
from darsstudio.project.model import Word

# CTC lug'atlari o'zbekcha belgilar uchun ko'pincha ‘ va ’ ishlatadi
CHAR_ALIASES = {uz_text.OKINA: ("‘", "'", "`"), uz_text.TUTUQ: ("’", "'", "`")}


def word_tokens(word: str, vocab: dict[str, int]) -> list[int]:
    out = []
    for ch in uz_text.normalize(word).replace(" ", ""):
        if ch in vocab:
            out.append(vocab[ch])
        else:
            alt = next((a for a in CHAR_ALIASES.get(ch, ()) if a in vocab), None)
            if alt is not None:
                out.append(vocab[alt])
    return out


def viterbi(logp: npt.NDArray[np.float32], tokens: list[int], blank: int) -> list[int] | None:
    """Har kadr uchun kengaytirilgan holat indeksi (2k+1 — k-token). Mumkin bo'lmasa None."""
    T, N = logp.shape[0], len(tokens)
    S = 2 * N + 1
    if N == 0 or T < N:
        return None
    ext = np.full(S, blank, np.int64)
    ext[1::2] = tokens
    skip = np.zeros(S, bool)
    skip[3::2] = ext[3::2] != ext[1:-2:2]
    neg = np.float32(-1e30)
    dp = np.full(S, neg, np.float32)
    dp[0], dp[1] = logp[0, blank], logp[0, ext[1]]
    back = np.zeros((T, S), np.int8)  # 0 qolish, 1 bitta oldin, 2 ikkita oldin
    for t in range(1, T):
        stay = dp
        prev1 = np.concatenate([[neg], dp[:-1]])
        prev2 = np.where(skip, np.concatenate([[neg, neg], dp[:-2]]), neg)
        cand = np.stack([stay, prev1, prev2])
        k = cand.argmax(0)
        dp = cand[k, np.arange(S)] + logp[t, ext]
        back[t] = k
    s = S - 1 if dp[S - 1] >= dp[S - 2] else S - 2
    if dp[s] <= neg / 2:
        return None
    path = [0] * T
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(back[t, s])
    return path


def align_segment(seg: Segment, em: Emissions, pad_ms: int = 400) -> list[Word] | None:
    words = [w for w in seg.words if w.text.strip()]
    if not words:
        return None
    f0 = max(0, int((seg.start_ms - pad_ms) / em.frame_ms))
    f1 = min(len(em.logp), int((seg.end_ms + pad_ms) / em.frame_ms) + 1)
    toks: list[int] = []
    owner: list[int] = []   # token -> so'z indeksi (-1: ajratgich)
    for i, w in enumerate(words):
        wt = word_tokens(w.text, em.vocab)
        if i and wt and em.sep is not None and toks:
            toks.append(em.sep)
            owner.append(-1)
        toks += wt
        owner += [i] * len(wt)
    lp = em.logp[f0:f1]
    path = viterbi(lp, toks, em.blank)
    if path is None:
        return None
    first: dict[int, int] = {}
    last: dict[int, int] = {}
    score: dict[int, list[float]] = {}
    for t, s in enumerate(path):
        if s % 2 == 1:
            wi = owner[s // 2]
            if wi >= 0:
                first.setdefault(wi, t)
                last[wi] = t
                score.setdefault(wi, []).append(float(np.exp(lp[t, toks[s // 2]])))
    out = []
    for i, w in enumerate(words):
        if i in first:
            out.append(Word(text=w.text, start_ms=int((f0 + first[i]) * em.frame_ms),
                            end_ms=int((f0 + last[i] + 1) * em.frame_ms), conf=round(float(np.mean(score[i])), 3)))
        else:
            out.append(w)  # tekislanmadi (masalan faqat belgilar): ASR vaqti qoladi
    return out


def align(segments: list[Segment], em: Emissions) -> tuple[list[Word], int]:
    """(so'zlar, CTC bilan tekislangan segmentlar soni)."""
    words: list[Word] = []
    ok = 0
    for seg in segments:
        a = align_segment(seg, em)
        if a is None:
            words += seg.words
        else:
            words += a
            ok += 1
    # segment oynalari (± pad) ustma-ust tushadi: so'zlar vaqt bo'yicha kesishmasin
    for i in range(1, len(words)):
        p, w = words[i - 1], words[i]
        if w.start_ms < p.end_ms:
            mid = max(p.start_ms + 1, min(w.start_ms, p.end_ms))
            words[i - 1] = p.model_copy(update={"end_ms": mid})
            words[i] = w.model_copy(update={"start_ms": mid, "end_ms": max(w.end_ms, mid + 1)})
    return words, ok
