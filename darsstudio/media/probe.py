"""Media probe va validatsiya (FR-02, TZ 4.1). fps va vaqtlar Fraction."""

import json
import os
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import xxhash

from darsstudio.media import ffmpeg

SUPPORTED_PIX = ("yuv420p", "yuvj420p")
SUPPORTED_FPS = (Fraction(25), Fraction(30000, 1001), Fraction(30))
SUPPORTED_SIZE = (1920, 1080)


class MediaError(ValueError):
    """Foydalanuvchiga ko'rsatiladigan xato (o'zbekcha, sabab + nima qilish kerak)."""


@dataclass(frozen=True)
class VideoInfo:
    codec: str
    width: int                 # rotation hisobga olingan (dekoder buradi)
    height: int
    rotation: int
    fps: Fraction              # r_frame_rate
    avg_fps: Fraction
    pix_fmt: str
    color_range: str | None    # "tv" | "pc"
    color_space: str | None
    color_primaries: str | None
    color_trc: str | None
    start_time: Fraction       # s, start_pts * time_base
    time_base: Fraction
    nb_frames: int             # paketlar sanab
    vfr: bool                  # paket vaqtlari bo'yicha
    bit_rate: int


@dataclass(frozen=True)
class AudioInfo:
    codec: str
    sample_rate: int
    channels: int
    start_time: Fraction


@dataclass(frozen=True)
class ProbeResult:
    path: str
    format_name: str
    duration: Fraction         # s, video stream davomiyligi (bo'lmasa format)
    format_start_time: Fraction
    video: VideoInfo
    audio: AudioInfo | None

    @property
    def full_range(self) -> bool:
        return self.video.color_range == "pc" or self.video.pix_fmt == "yuvj420p"

    @property
    def matrix(self) -> str:
        cs = self.video.color_space
        return cs if cs in ("bt709", "bt470bg", "smpte170m", "bt2020nc") else "bt709"

    @property
    def av_offset(self) -> Fraction:
        """video start_time - audio start_time, s (audio yo'q bo'lsa 0)."""
        return self.video.start_time - self.audio.start_time if self.audio else Fraction(0)

    def to_dict(self) -> dict[str, Any]:
        """JSON uchun: Fraction -> "num/den" satr."""
        def conv(v: Any) -> Any:
            if isinstance(v, Fraction):
                return f"{v.numerator}/{v.denominator}"
            if isinstance(v, dict):
                return {k: conv(x) for k, x in v.items()}
            return v
        out: dict[str, Any] = conv(asdict(self))
        return out


def _frac(v: Any, default: str = "0") -> Fraction:
    s = str(v) if v not in (None, "N/A", "") else default
    return Fraction(s) if "/" in s else Fraction(s).limit_denominator(1_000_000)


def _packet_pts(path: str) -> list[int]:
    r = ffmpeg.run(["-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts",
                    "-of", "csv=p=0", path], tool="ffprobe")
    return sorted(int(x) for x in r.stdout.split() if x.strip().lstrip("-").isdigit())


def detect_vfr(pts: list[int], time_base: Fraction, fps: Fraction) -> bool:
    """Ketma-ket kadrlar orasi nominal 1/fps dan yarim kadrdan ko'p farq qilsa VFR.
    r_frame_rate != avg_frame_rate ga ishonilmaydi (konteyner/edit list tufayli noto'g'ri bo'lishi mumkin)."""
    step = 1 / (fps * time_base)  # bir kadr, time_base birligida
    return any(abs((b - a) - step) > step / 2 for a, b in zip(pts, pts[1:], strict=False))


def probe(path: str | os.PathLike[str]) -> ProbeResult:
    path = str(path)
    if not os.path.isfile(path):
        raise MediaError(f"Fayl topilmadi: {path}. Yo'lni tekshiring.")
    r = ffmpeg.run(["-v", "error", "-show_streams", "-show_format", "-of", "json", path], tool="ffprobe",
                   check=False)
    if r.returncode != 0 or not r.stdout.strip():
        raise MediaError(f"Faylni o'qib bo'lmadi: {Path(path).name}. Fayl buzilgan yoki video emas.")
    d = json.loads(r.stdout)
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    if v is None:
        raise MediaError(f"{Path(path).name} da video yo'q. Video faylni tanlang.")
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = d["format"]

    fps = _frac(v.get("r_frame_rate"), "0/1")
    tb = _frac(v.get("time_base"), "1/90000")
    pts = _packet_pts(path)
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(sd["rotation"]) % 360
    w, h = int(v["width"]), int(v["height"])
    if rot in (90, 270):
        w, h = h, w
    vstart = _frac(v.get("start_pts"), "0") * tb if v.get("start_pts") is not None else _frac(v.get("start_time"))
    video = VideoInfo(
        codec=v["codec_name"], width=w, height=h, rotation=rot, fps=fps,
        avg_fps=_frac(v.get("avg_frame_rate"), "0/1"), pix_fmt=v.get("pix_fmt", "?"),
        color_range=v.get("color_range"), color_space=v.get("color_space"),
        color_primaries=v.get("color_primaries"), color_trc=v.get("color_trc"),
        start_time=vstart, time_base=tb, nb_frames=len(pts),
        vfr=bool(fps) and detect_vfr(pts, tb, fps), bit_rate=int(v.get("bit_rate") or fmt.get("bit_rate") or 0))
    audio = None
    if a is not None:
        atb = _frac(a.get("time_base"), "1/48000")
        astart = _frac(a.get("start_pts"), "0") * atb if a.get("start_pts") is not None else _frac(a.get("start_time"))
        audio = AudioInfo(codec=a["codec_name"], sample_rate=int(a.get("sample_rate") or 0),
                          channels=int(a.get("channels") or 0), start_time=astart)
    dur = _frac(v.get("duration") or fmt.get("duration"))
    return ProbeResult(path=path, format_name=fmt.get("format_name", "?"), duration=dur,
                       format_start_time=_frac(fmt.get("start_time")), video=video, audio=audio)


def frame_count(p: ProbeResult) -> int:
    """Loyiha kadr soni: CFR'da paketlar soni, VFR'da round(davomiylik x fps) (CFR'ga o'tkazilgandan keyingi son)."""
    return round(p.duration * p.video.fps) if p.video.vfr else p.video.nb_frames


def validate(p: ProbeResult) -> None:
    """TZ 4.1: 1920x1080, 8-bit 4:2:0, 25 / 29.97 / 30 kadr/s. Mos kelmasa MediaError."""
    name, v = Path(p.path).name, p.video
    if (v.width, v.height) != SUPPORTED_SIZE:
        raise MediaError(f"{name}: o'lcham {v.width}x{v.height}. Faqat 1920x1080 qo'llanadi, "
                         "videoni 1080p da eksport qiling.")
    if v.pix_fmt not in SUPPORTED_PIX:
        raise MediaError(f"{name}: piksel formati {v.pix_fmt}. Faqat 8-bit 4:2:0 (yuv420p) qo'llanadi, "
                         "videoni H.264 8-bit da eksport qiling.")
    if v.fps not in SUPPORTED_FPS:
        raise MediaError(f"{name}: kadr tezligi {float(v.fps):.3f}. Faqat 25, 29.97 yoki 30 kadr/s qo'llanadi.")
    if p.audio is None:
        raise MediaError(f"{name}: ovoz yo'lagi yo'q. Kamera ovozi bilan yozilgan faylni tanlang.")


def file_id(path: str | os.PathLike[str], block: int = 1 << 20) -> str:
    """Asset identifikatori (FR-01): hajm, mtime_ns, boshidagi va oxiridagi 1 MB ning xxhash64'i."""
    st = os.stat(path)
    with open(path, "rb") as f:
        head = xxhash.xxh64_hexdigest(f.read(block))
        f.seek(max(0, st.st_size - block))
        tail = xxhash.xxh64_hexdigest(f.read(block))
    return f"{st.st_size}-{st.st_mtime_ns}-{head}-{tail}"
