"""Audio ajratish (FR-04): 48 kHz stereo (montaj) va 16 kHz mono (ASR) WAV.

Muhim: WAV'ning 0-namunasi = video 0-kadrining vaqti. Shunda ASR so'z vaqtlari (ms) to'g'ridan asl kadr
indekslariga o'tadi: kadr = ms * fps / 1000. Audio videodan oldin boshlansa boshi kesiladi, keyin boshlansa
oldiga jimlik qo'shiladi; uzunligi video davomiyligiga tenglanadi.
"""

from fractions import Fraction
from pathlib import Path

import numpy as np
import numpy.typing as npt

from darsstudio.media import ffmpeg
from darsstudio.media.probe import MediaError, ProbeResult, frame_count

F32 = npt.NDArray[np.float32]


def _aligned_args(p: ProbeResult, rate: int, channels: int) -> list[str]:
    if p.audio is None:
        raise MediaError(f"{Path(p.path).name}: ovoz yo'lagi yo'q.")
    dur = Fraction(frame_count(p)) / p.video.fps
    lead = p.audio.start_time - p.video.start_time      # > 0: audio keyin boshlanadi
    pre: list[str] = []
    af = []
    if lead < 0:
        pre = ["-ss", f"{float(p.video.start_time - p.format_start_time):.6f}"]
    elif lead > 0:
        af.append(f"adelay={float(lead) * 1000:.3f}:all=1")
    af += [f"aresample={rate}:resampler=soxr", f"apad=whole_dur={float(dur):.6f}"]
    return [*pre, "-i", p.path, "-map", "0:a:0", "-af", ",".join(af), "-ac", str(channels), "-t", f"{float(dur):.6f}"]


def extract_wav(p: ProbeResult, dst: Path, rate: int = 48000, channels: int = 2) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".tmp.wav")
    ffmpeg.run(["-v", "error", "-nostdin", "-y", *_aligned_args(p, rate, channels), "-c:a", "pcm_s16le", str(tmp)])
    tmp.replace(dst)
    return dst


def extract_all(p: ProbeResult, audio_dir: Path) -> tuple[Path, Path]:
    """(src_48k.wav, asr_16k.wav) — TZ 8.4 nomlari."""
    return (extract_wav(p, audio_dir / "src_48k.wav", 48000, 2), extract_wav(p, audio_dir / "asr_16k.wav", 16000, 1))


def read_pcm(path: Path, rate: int = 16000, channels: int = 1) -> F32:
    """WAV/istalgan audio -> float32 [-1, 1] (mono bo'lsa 1D, aks holda [n, ch])."""
    proc = ffmpeg.popen(["-v", "error", "-nostdin", "-i", str(path), "-f", "f32le", "-ac", str(channels),
                         "-ar", str(rate), "-"], stdout=True)
    assert proc.stdout is not None
    data = np.frombuffer(proc.stdout.read(), np.float32).copy()
    if proc.wait() != 0:
        raise ffmpeg.FfmpegError(f"audioni o'qib bo'lmadi: {path}")
    return data if channels == 1 else data.reshape(-1, channels)
