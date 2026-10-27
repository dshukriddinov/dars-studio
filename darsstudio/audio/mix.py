"""Yakuniy audio (TZ 9.9): tozalangan 48 kHz -> TimeMap bo'yicha kesish (har birlashishda 10 ms equal-power
crossfade) -> [intro/outro] -> loudnorm 1-o'tish (o'lchov) -> 2-o'tish (chiziqli) -> WAV (AAC mux'da).
Chiqish uzunligi = chiqish video uzunligi (kesish nuqtalari kadr chegarasidagi namunalar, Fraction bilan)."""

from pathlib import Path

import numpy as np
import numpy.typing as npt

from darsstudio.audio import loudness
from darsstudio.audio.extract import read_pcm
from darsstudio.media import ffmpeg
from darsstudio.media.timemap import TimeMap

SR = 48000
XFADE = 480  # 10 ms
LIMIT_LIN = 0.631  # -4 dBFS (192 kHz da): AAC +1.5 dB qo'shadi (DSBA9359: -3.0 -> -1.5 dBTP, chegarada) — zaxira 1 dB


def assemble(src: npt.NDArray[np.float32], tm: TimeMap, xfade: int = XFADE) -> npt.NDArray[np.float32]:
    """src [n, ch] (0-namuna = video 0-kadr). Har birlashish markazida xfade namunali equal-power crossfade:
    chap bo'lak kesish ichiga xfade/2 davom etadi, o'ng bo'lak xfade/2 oldinroq boshlanadi — uzunlik o'zgarmaydi."""
    n, ch = src.shape
    rngs = tm.audio_ranges()
    total = sum(e - s for s, e in rngs)
    out = np.zeros((total, ch), np.float32)
    h = xfade // 2
    t = np.linspace(0, np.pi / 2, xfade, dtype=np.float32)
    fade_out, fade_in = np.cos(t)[:, None], np.sin(t)[:, None]
    pos = 0

    def take(a: int, b: int) -> npt.NDArray[np.float32]:
        seg = np.zeros((b - a, ch), np.float32)
        lo, hi = max(a, 0), min(b, n)
        if lo < hi:
            seg[lo - a:hi - a] = src[lo:hi]
        return seg

    for i, (s, e) in enumerate(rngs):
        out[pos:pos + (e - s)] = take(s, e)
        if i > 0 and xfade:
            ps, pe = rngs[i - 1]
            # birlashish nuqtasi pos: [pos-h, pos+h) oralig'ida chap davomi va o'ng boshlanishi aralashtiriladi
            left = take(pe - h, pe + h)
            right = take(s - h, s + h)
            a, b = max(0, pos - h), min(total, pos + h)
            out[a:b] = (left * fade_out + right * fade_in)[a - (pos - h):b - (pos - h)]
        pos += e - s
    return out


def write_wav(path: Path, x: npt.NDArray[np.float32], sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = ffmpeg.popen(["-v", "error", "-nostdin", "-y", "-f", "f32le", "-ar", str(sr), "-ac", str(x.shape[1]),
                         "-i", "-", "-c:a", "pcm_f32le", str(path)], stdin=True)
    assert proc.stdin is not None
    proc.stdin.write(np.ascontiguousarray(x, np.float32).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise ffmpeg.FfmpegError(f"WAV yozilmadi: {path}")


def final_audio(denoised: Path, tm: TimeMap, out: Path, profile: str = "standart") -> loudness.Loudness:
    """Kesilgan + loudnorm qilingan WAV (pcm_f32le). Qaytaradi: natija o'lchovi (ebur128, AC-08 tekshiruvi uchun)."""
    x = read_pcm(denoised, SR, 2)
    cut = out.with_name(out.stem + ".cut.wav")
    write_wav(cut, assemble(x, tm))
    m = loudness.measure(cut)
    tmp = out.with_name(out.stem + ".tmp.wav")
    # loudnorm 192 kHz da chiqaradi: shu yerda limiter (4x oversampling ~ true peak). Manba clipping qilingan
    # bo'lsa (namunada +0.5 dBTP) loudnorm yolg'iz AAC dan keyin TP <= -1.5 ni ushlab turolmadi (QA ushladi).
    # 16 kHz lowpass: AAC yuqori chastotani kesganda impulsda "ringing" +6 dB cho'qqi berdi (namunada 2.06 s)
    ffmpeg.run(["-v", "error", "-nostdin", "-y", "-i", str(cut), "-af", loudness.loudnorm_filter(m, profile)
                + f",lowpass=f=16000:poles=2,alimiter=limit={LIMIT_LIN}:attack=1:release=50:level=0"
                f",aresample={SR}:resampler=soxr",
                "-c:a", "pcm_f32le", str(tmp)])
    tmp.replace(out)
    cut.unlink()
    return loudness.ebur128(out)
