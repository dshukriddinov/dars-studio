"""CTC model (wav2vec2, transformers). Uzun audio 30 s oynalarda (2 s kontekst bilan) ishlanadi, logit'lar
tikiladi. Emissiyalar (log-softmax, 20 ms kadr) so'z vaqtlarini aniqlash (word_align) uchun ham ishlatiladi."""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from darsstudio.asr.engines.base import F32, Segment
from darsstudio.project.model import Word

SR = 16000
WIN_S, CTX_S = 30, 2


@dataclass
class Emissions:
    logp: npt.NDArray[np.float32]   # [T, V] log-softmax
    frame_ms: float                 # bitta kadr, ms (wav2vec2: 20)
    vocab: dict[str, int]
    blank: int
    sep: int | None                 # so'z ajratgich ("|")


class CtcEngine:
    def __init__(self, model_dir: str, device: str = "cuda") -> None:
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

        self.name = f"ctc:{model_dir}"
        self.torch, self.device = torch, torch.device(device)
        self.proc = Wav2Vec2Processor.from_pretrained(model_dir)
        self.model = Wav2Vec2ForCTC.from_pretrained(model_dir).to(self.device).eval()
        if self.device.type == "cuda":
            self.model = self.model.half()
        vocab = self.proc.tokenizer.get_vocab()
        n_out = int(self.model.config.vocab_size)  # qo'shimcha tokenlar (<s>, </s>) model chiqishida yo'q
        self.vocab: dict[str, int] = {t: i for t, i in vocab.items() if i < n_out}
        self.blank = int(self.proc.tokenizer.pad_token_id)
        self.sep = self.vocab.get(self.proc.tokenizer.word_delimiter_token or "|")
        self.inv = {i: t for t, i in self.vocab.items()}

    def emissions(self, wav16k: F32, on_progress: Callable[[float], None] | None = None) -> Emissions:
        torch = self.torch
        n, win, ctx = len(wav16k), WIN_S * SR, CTX_S * SR
        parts: list[npt.NDArray[np.float32]] = []
        frame = 320  # wav2vec2 qadami (namuna)
        pos = 0
        while pos < n:
            a, b = max(0, pos - ctx), min(n, pos + win + ctx)
            x = self.proc(wav16k[a:b], sampling_rate=SR, return_tensors="pt").input_values.to(self.device)
            with torch.no_grad():
                logits = self.model(x.half() if self.device.type == "cuda" else x).logits[0].float()
            lp = torch.log_softmax(logits, -1).cpu().numpy()
            s, e = (pos - a) // frame, (min(n, pos + win) - a) // frame
            parts.append(lp[s:e])
            pos += win
            if on_progress:
                on_progress(min(1.0, pos / n))
        return Emissions(np.concatenate(parts), frame * 1000 / SR, self.vocab, self.blank, self.sep)

    def transcribe(self, wav16k: F32, *, hotwords: str | None = None,
                   on_progress: Callable[[float], None] | None = None) -> list[Segment]:
        """Greedy dekod; so'z vaqti — so'z harflari egallagan birinchi/oxirgi kadr."""
        em = self.emissions(wav16k, on_progress)
        self.last_emissions = em
        ids = em.logp.argmax(-1)
        conf = np.exp(em.logp.max(-1))
        words: list[Word] = []
        cur, start, last = "", -1, -1
        cs: list[float] = []
        prev = -1
        for t, i in enumerate(ids):
            i = int(i)
            if i != prev and i != em.blank:
                if i == em.sep:
                    if cur:
                        words.append(Word(text=cur, start_ms=int(start * em.frame_ms),
                                           end_ms=int((last + 1) * em.frame_ms), conf=round(float(np.mean(cs)), 3)))
                    cur, cs = "", []
                else:
                    tok = self.inv.get(i, "")
                    if tok and not tok.startswith("<") and not tok.startswith("["):
                        if not cur:
                            start = t
                        cur += tok
                        last = t
                        cs.append(float(conf[t]))
            elif i == prev and i != em.blank and i != em.sep and cur:
                last = t
            prev = i
        if cur:
            words.append(Word(text=cur, start_ms=int(start * em.frame_ms), end_ms=int((last + 1) * em.frame_ms),
                              conf=round(float(np.mean(cs)), 3)))
        return segments_from_words(words)

    def close(self) -> None:
        del self.model
        if self.device.type == "cuda":
            self.torch.cuda.empty_cache()


def segments_from_words(words: list[Word], gap_ms: int = 700, max_ms: int = 12000) -> list[Segment]:
    """So'zlarni pauza (>= gap_ms) yoki uzunlik bo'yicha segmentlarga guruhlash."""
    segs: list[Segment] = []
    for w in words:
        if segs and w.start_ms - segs[-1].end_ms < gap_ms and w.end_ms - segs[-1].start_ms <= max_ms:
            s = segs[-1]
            s.words.append(w)
            s.end_ms, s.text = w.end_ms, s.text + " " + w.text
        else:
            segs.append(Segment(w.start_ms, w.end_ms, w.text, [w]))
    return segs
