"""AI slayd moslashtirish (FR-08, TZ 9.4): nutq segmentlari x slaydlar o'xshashligi -> monoton DP (Viterbi),
forward-backward ishonchlilik, minimal turish, chegarani gap boshi / pauzaga surish, qisqa qaytishlarni belgilash.

O'xshashlik: S = a*cos(embedding) + b*cos(char 3..5-gram TF-IDF) + c*kalit so'zlar; har segment qatori
z-normallashtiriladi. Embedding modeli bo'lmasa (a = 0) faqat leksik qism ishlaydi.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
import numpy.typing as npt

from darsstudio.asr import uz_text
from darsstudio.project.model import Slide, SlideSpan, Word

F = npt.NDArray[np.float64]
Embedder = Callable[[list[str], str], F]   # (matnlar, "query"|"passage") -> L2-normallangan [n, d]

FIELD_W = {"title": 2.0, "body": 1.0, "notes": 1.5, "ocr": 0.7}
STOP = set("va bilan uchun bu u ham esa lekin chunki agar yoki hamda bo'yicha kabi qilib bo'ladi edi emas "
           "deb shu ushbu bunda biz siz ular men sen".split())


@dataclass
class Params:
    a: float = 0.6
    b: float = 0.3
    c: float = 0.1
    lam_next: float = 0.5
    lam_skip: float = 2.5
    lam_back: float = 3.0
    tau: float = 0.5
    min_dwell_s: float = 3.0
    seg_min_s: float = 6.0
    seg_max_s: float = 12.0
    suspicious_below: float = 0.6
    short_back_s: float = 10.0


@dataclass
class TextSeg:
    start_ms: int
    end_ms: int
    text: str
    sent_starts: list[int] = field(default_factory=list)   # gap boshlari, ms
    words: list[Word] = field(default_factory=list)


@dataclass
class Boundary:
    frame: int
    prev_slide: int
    slide: int
    confidence: float
    reason: str = ""


@dataclass
class AlignResult:
    spans: list[SlideSpan]
    boundaries: list[Boundary]
    suspicious: list[Boundary]


def segments(words: Sequence[Word], p: Params, gap_ms: int = 600) -> list[TextSeg]:
    """So'zlar -> gaplar (tinish belgisi yoki >= gap_ms pauza) -> 6..12 s oynalar (gapni buzmasdan)."""
    sents: list[list[Word]] = []
    for w in words:
        if not sents or (sents[-1] and (re.search(r"[.!?…]$", sents[-1][-1].text) or
                                        w.start_ms - sents[-1][-1].end_ms >= gap_ms)):
            sents.append([])
        sents[-1].append(w)
    out: list[TextSeg] = []
    for s in sents:
        cur = out[-1] if out else None
        dur_if = (s[-1].end_ms - cur.start_ms) if cur else 0
        if cur is None or (cur.end_ms - cur.start_ms >= p.seg_min_s * 1000) or dur_if > p.seg_max_s * 1000 * 1.5:
            out.append(TextSeg(s[0].start_ms, s[-1].end_ms, "", []))
            cur = out[-1]
        cur.sent_starts.append(s[0].start_ms)
        cur.words += s
        cur.end_ms = s[-1].end_ms
        cur.text = " ".join(w.text for w in cur.words)
    return out


def slide_fields(s: Slide) -> dict[str, str]:
    return {"title": s.title, "body": s.body, "notes": s.notes, "ocr": s.ocr or ""}


def keywords(text: str) -> set[str]:
    return {t for t in uz_text.tokenize(text) if len(t) >= 4 and t not in STOP}


def _cos(a: F, b: F) -> F:
    an = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
    bn = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
    out: F = an @ bn.T
    return out


def similarity(segs: list[TextSeg], slides: Sequence[Slide], p: Params,
               embed: Embedder | None = None) -> F:
    from sklearn.feature_extraction.text import TfidfVectorizer

    seg_txt = [uz_text.normalize(s.text) for s in segs]
    fields = [slide_fields(s) for s in slides]
    corpus = seg_txt + [uz_text.normalize(f[k]) for f in fields for k in FIELD_W]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1).fit(corpus)
    X = vec.transform(seg_txt).toarray()
    Y = np.zeros((len(slides), X.shape[1]))
    for i, f in enumerate(fields):
        for k, w in FIELD_W.items():
            if f[k].strip():
                Y[i] += w * vec.transform([uz_text.normalize(f[k])]).toarray()[0]
    lex = _cos(X, Y)
    S = p.b * lex
    if embed is not None and p.a:
        slide_txt = [". ".join(f[k] for k in ("title", "title", "body", "notes", "ocr") if f[k]) for f in fields]
        S = S + p.a * (embed([s.text for s in segs], "query") @ embed(slide_txt, "passage").T)
    if p.c:
        kws = [keywords(f["title"] + " " + f["body"]) for f in fields]
        hits = np.array([[len(keywords(s.text) & k) / max(1, min(len(k), 8)) for k in kws] for s in segs])
        S = S + p.c * hits
    mu, sd = S.mean(1, keepdims=True), S.std(1, keepdims=True) + 1e-9
    z: F = (S - mu) / sd
    return z


def _log_softmax(x: F) -> F:
    m = x.max(1, keepdims=True)
    out: F = x - m - np.log(np.exp(x - m).sum(1, keepdims=True))
    return out


def transitions(n: int, p: Params) -> F:
    """[from, to] xarajat (inf — taqiqlangan): qolish 0, keyingi λ1, bittasini o'tkazib λ2, bitta orqaga λ3."""
    T = np.full((n, n), np.inf)
    for i in range(n):
        T[i, i] = 0.0
        if i + 1 < n:
            T[i, i + 1] = p.lam_next
        if i + 2 < n:
            T[i, i + 2] = p.lam_skip
        if i - 1 >= 0:
            T[i, i - 1] = p.lam_back
    return T


def viterbi(cost: F, trans: F, init: F) -> list[int]:
    n_seg, n = cost.shape
    d = init + cost[0]
    back = np.zeros((n_seg, n), np.int64)
    for t in range(1, n_seg):
        cand = d[:, None] + trans
        back[t] = cand.argmin(0)
        d = cand[back[t], np.arange(n)] + cost[t]
    path = [int(d.argmin())]
    for t in range(n_seg - 1, 0, -1):
        path.append(int(back[t, path[-1]]))
    return path[::-1]


def posteriors(cost: F, trans: F, init: F) -> F:
    """Forward-backward (log fazosida), ehtimollar exp(-xarajat)."""
    from scipy.special import logsumexp

    n_seg, n = cost.shape
    lt = -trans
    la = np.empty((n_seg, n))
    la[0] = -init - cost[0]
    for t in range(1, n_seg):
        la[t] = logsumexp(la[t - 1][:, None] + lt, axis=0) - cost[t]
    lb = np.zeros((n_seg, n))
    for t in range(n_seg - 2, -1, -1):
        lb[t] = logsumexp(lt + (-cost[t + 1] + lb[t + 1])[None, :], axis=1)
    post = la + lb
    out: F = np.exp(post - logsumexp(post, axis=1, keepdims=True))
    return out


BOUNDARY_BONUS = 1.0  # gap boshi yoki >= 0.3 s pauza oldidagi nuqtaga bonus (so'z mosligi birligida)


def _refine(segs: list[TextSeg], i: int, old: int, new: int, vocab: list[set[str]]) -> int:
    """i-1 va i segmentlar orasidagi chegara (ms): change-point. Har so'z uchun s = [yangi slayd lug'atida] -
    [eski slayd lug'atida]; chegara c — o'ngdagi s yig'indisi + (gap boshi / pauza bonusi) maksimal nuqta."""
    words = segs[i - 1].words + segs[i].words
    starts = set(segs[i - 1].sent_starts + segs[i].sent_starts)
    toks = [uz_text.tokenize(w.text) for w in words]
    s = np.array([sum((t in vocab[new]) - (t in vocab[old]) for t in tk) for tk in toks], np.float64)
    tail = np.cumsum(s[::-1])[::-1]   # tail[k] = sum(s[k:])
    best, best_score = segs[i].start_ms, -np.inf
    for k, w in enumerate(words):
        if k == 0:
            continue
        brk = w.start_ms in starts or w.start_ms - words[k - 1].end_ms >= 300
        sc = float(tail[k]) + (BOUNDARY_BONUS if brk else 0.0)
        if sc > best_score:
            best, best_score = w.start_ms, sc
    return best


def align(words: Sequence[Word], slides: Sequence[Slide], total: int, fps: Fraction, p: Params | None = None,
          embed: Embedder | None = None) -> AlignResult:

    p = p or Params()
    n = len(slides)
    segs = segments(words, p)
    if not segs or n == 0:
        return AlignResult([SlideSpan(start=0, end=total, slide=1, source="ai", confidence=0.0)], [], [])
    z = similarity(segs, slides, p, embed)
    cost = -_log_softmax(z / p.tau)
    trans = transitions(n, p)
    init = np.array([k * p.lam_skip for k in range(n)], np.float64)
    path = viterbi(cost, trans, init)
    post = posteriors(cost, trans, init)

    # minimal turish: qisqa yugurishni o'xshashroq qo'shnisiga qo'shamiz
    changed = True
    while changed:
        changed = False
        runs = _runs(path)
        for k, (s, e, _st) in enumerate(runs):
            dur = (segs[e - 1].end_ms - segs[s].start_ms) / 1000
            if dur < p.min_dwell_s and len(runs) > 1:
                nb = [runs[j][2] for j in (k - 1, k + 1) if 0 <= j < len(runs)]
                tgt = max(nb, key=lambda x: z[s:e, x].mean())
                path[s:e] = [tgt] * (e - s)
                changed = True
                break

    fields = [slide_fields(s) for s in slides]
    # slaydga xos so'zlar: boshqa slaydlarda ham ko'p uchraydiganlari (umumiy so'zlar) chiqariladi
    raw = [{t for t in uz_text.tokenize(" ".join(f.values())) if len(t) >= 3 and t not in STOP} for f in fields]
    df = {t: sum(t in v for v in raw) for v in raw for t in v}
    vocab = [{t for t in v if df[t] <= max(1, n // 3)} for v in raw]

    bounds: list[Boundary] = []
    for i in range(1, len(segs)):
        if path[i] != path[i - 1]:
            ms = _refine(segs, i, path[i - 1], path[i], vocab)
            lo, hi = max(0, i - 2), min(len(segs), i + 2)
            conf = float(min(post[t, path[t]] for t in range(lo, hi)))
            bounds.append(Boundary(round(Fraction(ms, 1000) * fps), path[i - 1] + 1, path[i] + 1, round(conf, 3)))
    spans: list[SlideSpan] = []
    pos, cur = 0, path[0] + 1
    for b in bounds:
        f = min(max(b.frame, pos + 1), total - 1)
        spans.append(SlideSpan(start=pos, end=f, slide=cur, source="ai", confidence=b.confidence))
        pos, cur = f, b.slide
    spans.append(SlideSpan(start=pos, end=total, slide=cur, source="ai",
                           confidence=bounds[-1].confidence if bounds else 1.0))
    susp = []
    for k, b in enumerate(bounds):
        if b.confidence < p.suspicious_below:
            b.reason = "past ishonchlilik"
            susp.append(b)
        elif b.slide == b.prev_slide - 1:
            nxt = bounds[k + 1].frame if k + 1 < len(bounds) else total
            if (nxt - b.frame) / fps <= p.short_back_s:
                b.reason = "qisqa orqaga qaytish"
                susp.append(b)
    return AlignResult(spans, bounds, susp)


def _runs(path: list[int]) -> list[tuple[int, int, int]]:
    out, s = [], 0
    for i in range(1, len(path) + 1):
        if i == len(path) or path[i] != path[s]:
            out.append((s, i, path[s]))
            s = i
    return out
