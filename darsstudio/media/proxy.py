"""Proxy (FR-02): 960x540, H.264 qisqa GOP (12), AAC 128k, +faststart — brauzerda kadr-aniq ko'rish uchun."""

from pathlib import Path

from darsstudio.media import ffmpeg
from darsstudio.media.probe import ProbeResult

PROXY_SIZE = (960, 540)
GOP = 12


def encoder_args() -> list[str]:
    if ffmpeg.nvenc_ok():
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "26", "-b:v", "0", "-bf", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-bf", "0"]  # ponytail: NVENC yo'q -> CPU


def make_proxy(p: ProbeResult, dst: Path) -> Path:
    """Manba CFR bo'lishi kerak (VFR -> avval normalize). Rang: BT.709 limited (brauzer uchun)."""
    w, h = PROXY_SIZE
    rng = "pc" if p.full_range else "tv"
    vf = f"scale={w}:{h}:in_range={rng}:out_range=tv:in_color_matrix={p.matrix}:out_color_matrix=bt709,format=yuv420p"
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".tmp" + dst.suffix)
    ffmpeg.run(["-v", "error", "-nostdin", "-y", "-i", p.path, "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf,
                *encoder_args(), "-g", str(GOP), "-keyint_min", str(GOP), "-fps_mode", "passthrough",
                "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp)])
    tmp.replace(dst)
    return dst
