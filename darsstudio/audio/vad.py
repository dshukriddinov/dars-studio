"""Nutq faolligi (FR-05): Silero VAD (MIT, model paket ichida — tarmoq kerak emas). CPU'da ishlaydi."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

SR = 16000


@dataclass(frozen=True)
class Speech:
    start_ms: int
    end_ms: int


def detect(wav16k: npt.NDArray[np.float32], threshold: float = 0.5, min_silence_ms: int = 300,
           speech_pad_ms: int = 60) -> list[Speech]:
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    model = load_silero_vad(onnx=False)
    ts = get_speech_timestamps(torch.from_numpy(wav16k), model, sampling_rate=SR, threshold=threshold,
                               min_silence_duration_ms=min_silence_ms, speech_pad_ms=speech_pad_ms)
    return [Speech(int(t["start"] * 1000 // SR), int(t["end"] * 1000 // SR)) for t in ts]


def silences(speech: list[Speech], total_ms: int) -> list[tuple[int, int]]:
    """Nutqsiz oraliqlar [s, e) ms (VAD teskarisi)."""
    out, pos = [], 0
    for s in speech:
        if s.start_ms > pos:
            out.append((pos, s.start_ms))
        pos = max(pos, s.end_ms)
    if pos < total_ms:
        out.append((pos, total_ms))
    return out
