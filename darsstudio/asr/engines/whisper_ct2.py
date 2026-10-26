"""Whisper (faster-whisper / CTranslate2). VAD filtri yoqilgan (gallyutsinatsiyaga qarshi, FR-05).
So'z vaqtlari Whisper'niki — faqat zaxira; aniq chegaralar asr.word_align (CTC) bilan."""

from collections.abc import Callable

from darsstudio.asr.engines.base import F32, Segment
from darsstudio.project.model import Word


APOSTROPHES = "'`‘’ʻʼ"


def merge_apostrophe_pieces(words: list[Word]) -> list[Word]:
    """Whisper o'zbekcha so'zni apostrof joyidan bo'ladi ("o" + "'zbekiston"): apostrof bilan boshlangan bo'lak
    oldingi so'zga qo'shiladi."""
    out: list[Word] = []
    for w in words:
        if out and w.text[:1] in APOSTROPHES and len(w.text) > 1:
            p = out[-1]
            out[-1] = Word(text=p.text + w.text, start_ms=p.start_ms, end_ms=w.end_ms, conf=min(p.conf, w.conf))
        else:
            out.append(w)
    return out


class WhisperCT2:
    def __init__(self, model_dir: str, device: str = "cuda", compute_type: str = "float16", beam_size: int = 5,
                 language: str = "uz") -> None:
        import torch  # noqa: F401  # CUDA/cuDNN DLL'lari torch/lib dan yuklansin (Windows)
        from faster_whisper import WhisperModel

        self.name = f"whisper-ct2:{model_dir}"
        self.model = WhisperModel(model_dir, device=device, compute_type=compute_type)
        self.beam_size, self.language = beam_size, language

    def transcribe(self, wav16k: F32, *, hotwords: str | None = None,
                   on_progress: Callable[[float], None] | None = None) -> list[Segment]:
        total = len(wav16k) / 16000
        segs, _ = self.model.transcribe(wav16k, language=self.language, beam_size=self.beam_size, vad_filter=True,
                                        word_timestamps=True, condition_on_previous_text=False, hotwords=hotwords)
        out = []
        for s in segs:
            words = merge_apostrophe_pieces(
                [Word(text=w.word.strip(), start_ms=int(w.start * 1000), end_ms=int(w.end * 1000),
                      conf=round(float(w.probability), 3)) for w in (s.words or []) if w.word.strip()])
            out.append(Segment(int(s.start * 1000), int(s.end * 1000), s.text.strip(), words))
            if on_progress:
                on_progress(min(1.0, s.end / total))
        return out

    def close(self) -> None:
        del self.model
