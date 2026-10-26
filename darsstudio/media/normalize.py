"""VFR -> CFR va audio -> 48 kHz (FR-02, TZ 4.1). Kerak bo'lmasa hech narsa yozilmaydi."""

from pathlib import Path

from darsstudio.media import ffmpeg
from darsstudio.media.probe import ProbeResult, probe

TARGET_RATE = 48000


def needs_normalize(p: ProbeResult) -> bool:
    return p.video.vfr or (p.audio is not None and p.audio.sample_rate != TARGET_RATE)


def color_flags(p: ProbeResult) -> list[str]:
    """Manba rang teglari chiqishga aniq yoziladi (CLAUDE.md, 3-qoida)."""
    v, out = p.video, []
    for flag, val in (("-color_range", v.color_range), ("-colorspace", v.color_space),
                      ("-color_primaries", v.color_primaries), ("-color_trc", v.color_trc)):
        if val and val != "unknown":
            out += [flag, val]
    return out


def normalize(p: ProbeResult, dst: Path) -> ProbeResult:
    """Normallashtirilgan nusxa (MKV). Video: VFR bo'lsa fps filtri bilan CFR (Eye Contact EC-2 bilan bir xil
    to'r: tushgan kadr o'rnini oldingisi to'ldiradi), yuqori sifatli H.264 (crf 12, GOP 25), aks holda copy.
    Audio: 48 kHz bo'lmasa soxr bilan resample, PCM s24le; aks holda copy."""
    v = p.video
    args = ["-v", "error", "-nostdin", "-y", "-i", p.path, "-map", "0:v:0", "-map", "0:a:0?"]
    if v.vfr:
        args += ["-vf", f"fps={v.fps}:round=near", "-fps_mode", "passthrough", "-c:v", "libx264", "-preset", "fast",
                 "-crf", "12", "-g", "25", "-pix_fmt", v.pix_fmt, *color_flags(p)]
    else:
        args += ["-c:v", "copy"]
    if p.audio and p.audio.sample_rate != TARGET_RATE:
        args += ["-af", f"aresample={TARGET_RATE}:resampler=soxr", "-c:a", "pcm_s24le"]
    else:
        args += ["-c:a", "copy"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".tmp" + dst.suffix)
    ffmpeg.run([*args, str(tmp)])
    tmp.replace(dst)
    return probe(dst)
