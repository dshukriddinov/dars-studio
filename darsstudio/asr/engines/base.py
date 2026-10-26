"""ASR dvigatel interfeysi (FR-05): transcribe(wav16k) -> segmentlar (so'zlar bilan). Vaqtlar ms, WAV boshidan
(audio.extract WAV'ni video 0-kadriga tekislaydi, shuning uchun ms -> kadr to'g'ridan)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import numpy.typing as npt

from darsstudio.project.model import Word

F32 = npt.NDArray[np.float32]


@dataclass
class Segment:
    start_ms: int
    end_ms: int
    text: str
    words: list[Word] = field(default_factory=list)


class AsrEngine(Protocol):
    name: str

    def transcribe(self, wav16k: F32, *, hotwords: str | None = None,
                   on_progress: Callable[[float], None] | None = None) -> list[Segment]: ...

    def close(self) -> None: ...


def load_engine(kind: str, model_dir: str, device: str = "cuda", **kw: object) -> AsrEngine:
    """manifest `kind` bo'yicha: asr-ct2 (faster-whisper) yoki asr-ctc (wav2vec2)."""
    if kind == "asr-ct2":
        from darsstudio.asr.engines.whisper_ct2 import WhisperCT2
        return WhisperCT2(model_dir, device=device, **kw)  # type: ignore[arg-type,unused-ignore]
    if kind == "asr-ctc":
        from darsstudio.asr.engines.ctc import CtcEngine
        return CtcEngine(model_dir, device=device)
    raise ValueError(f"noma'lum ASR turi: {kind}")
