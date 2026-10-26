"""Shovqin tozalash (FR-04, TZ 9.9): DeepFilterNet3 (o'rnatilgan bo'lsa), aks holda ffmpeg afftdn. Keyin HPF 80 Hz.
Susaytirish chegarasi 12–18 dB (artefaktlarsiz), default 15 dB."""

import logging
from pathlib import Path

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


def afftdn_filter(atten_db: float = DEFAULT_ATTEN_DB) -> str:
    """ffmpeg afftdn: nr — susaytirish (dB), nf — shovqin sathi, tn — shovqin profilini kuzatish."""
    return f"highpass=f={HPF_HZ},afftdn=nr={atten_db:.1f}:nf=-50:tn=1"


def denoise(src: Path, dst: Path, atten_db: float = DEFAULT_ATTEN_DB, engine: str = "auto") -> str:
    """src (48 kHz WAV) -> dst. Qaytaradi: ishlatilgan usul."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".tmp.wav")
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
