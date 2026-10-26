"""Shovqin tozalash (FR-04, TZ 9.9): DeepFilterNet3 — rasmiy CLI (`models/deep-filter/`, model ichida) yoki
Python paketi; ikkalasi ham yo'q bo'lsa ffmpeg afftdn (namunada shovqinni deyarli olmaydi: p5 -0.3 dB). Keyin HPF 80 Hz.
Susaytirish chegarasi 12–18 dB (artefaktlarsiz), default 15 dB.
CLI chiqishi manbaga namuna aniqligida tekislanadi (kechikish korrelyatsiya bilan o'lchanadi) — A/V saqlanadi."""

import logging
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from darsstudio import paths
from darsstudio.audio.extract import read_pcm
from darsstudio.media import ffmpeg

log = logging.getLogger(__name__)
HPF_HZ = 80
DEFAULT_ATTEN_DB = 15.0


def deepfilternet_available() -> bool:
    try:
        import df  # noqa: F401
        return True
    except ImportError:
        return False


DF_CLI = "deep-filter/deep-filter-0.5.6-x86_64-pc-windows-msvc.exe"   # models/manifest.json: deep-filter-cli
SR = 48000
MAX_LAG_S = 0.5


def deepfilter_cli() -> Path | None:
    exe = paths.models_dir() / DF_CLI
    return exe if exe.is_file() else None


def lag_samples(ref: np.ndarray, out: np.ndarray, sr: int = SR, seconds: int = 120) -> int:
    """out ref'dan necha namuna kechikkan (musbat — kechikkan): boshidagi `seconds` bo'yicha FFT korrelyatsiya."""
    n = min(len(ref), len(out), sr * seconds)
    a, b = ref[:n].astype(np.float64), out[:n].astype(np.float64)
    m = int(MAX_LAG_S * sr)
    spec = np.fft.rfft(a, 2 * n) * np.conj(np.fft.rfft(b, 2 * n))
    cc = np.fft.irfft(spec, 2 * n)
    cand = np.concatenate([cc[-m:], cc[: m + 1]])          # lag -m..m: b[t] ~ a[t - lag]
    return int(m - np.argmax(cand))


def _run_cli(exe: Path, src: Path, dst: Path, atten_db: float) -> None:
    with tempfile.TemporaryDirectory(dir=dst.parent) as td:
        r = subprocess.run([str(exe), "-D", "-a", f"{atten_db:g}", "-o", td, str(src)], capture_output=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = Path(td) / src.name
        if r.returncode != 0 or not out.is_file():
            raise RuntimeError(f"deep-filter xato ({r.returncode}): {(r.stderr or r.stdout)[-500:]}")
        ref = read_pcm(src, SR)
        lag, n = lag_samples(ref, read_pcm(out, SR)), len(ref)
        log.info("deep-filter kechikishi: %d namuna", lag)
        # kechikishni olib tashlash va manba uzunligiga keltirish (A/V)
        shift = f"atrim=start_sample={lag}," if lag > 0 else f"adelay={-lag}S:all=1," if lag < 0 else ""
        af = f"{shift}apad=whole_len={n},atrim=end_sample={n},highpass=f={HPF_HZ}"
        ffmpeg.run(["-v", "error", "-nostdin", "-y", "-i", str(out), "-af", af, "-ar", str(SR), "-c:a", "pcm_s16le",
                    str(dst)])


def afftdn_filter(atten_db: float = DEFAULT_ATTEN_DB) -> str:
    """ffmpeg afftdn: nr — susaytirish (dB), nf — shovqin sathi, tn — shovqin profilini kuzatish."""
    return f"highpass=f={HPF_HZ},afftdn=nr={atten_db:.1f}:nf=-50:tn=1"


def denoise(src: Path, dst: Path, atten_db: float = DEFAULT_ATTEN_DB, engine: str = "auto") -> str:
    """src (48 kHz WAV) -> dst. Qaytaradi: ishlatilgan usul."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".tmp.wav")
    exe = deepfilter_cli()
    if engine in ("auto", "deepfilternet") and exe is not None:
        _run_cli(exe, src, tmp, atten_db)
        tmp.replace(dst)
        return "deepfilternet3-cli"
    if engine in ("auto", "deepfilternet") and deepfilternet_available():
        from df.enhance import enhance, init_df, load_audio, save_audio  # type: ignore[import-not-found,unused-ignore]
        model, state, _ = init_df()
        audio, _ = load_audio(str(src), sr=state.sr())
        save_audio(str(tmp), enhance(model, state, audio, atten_lim_db=atten_db), state.sr())
        ffmpeg.run(["-v", "error", "-nostdin", "-y", "-i", str(tmp), "-af", f"highpass=f={HPF_HZ}",
                    "-c:a", "pcm_s16le", str(dst)])
        tmp.unlink()
        return "deepfilternet3"
    if engine == "deepfilternet":
        raise RuntimeError("DeepFilterNet o'rnatilmagan")
    ffmpeg.run(["-v", "error", "-nostdin", "-y", "-i", str(src), "-af", afftdn_filter(atten_db), "-c:a", "pcm_s16le",
                str(tmp)])
    tmp.replace(dst)
    return "afftdn"
