"""Overlay'lar (FR-13): lower-third (o'qituvchi, fan, mavzu; boshida duration_s, fade 0.3 s). Pillow bilan bir marta
RGBA qatlam chiziladi, kompozitorda chiqish vaqti bo'yicha shaffofligi o'zgaradi. Shrift: Noto Sans (OFL)."""

from fractions import Fraction
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFont

from darsstudio import paths
from darsstudio.asr import uz_text

FADE_S = 0.3
FONT_DIR = paths.ROOT / "templates" / "fonts"


def font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / ("NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf")), size)


def lower_third(meta: dict[str, str], canvas: tuple[int, int], margin: int = 24) -> npt.NDArray[np.uint8] | None:
    """meta: oqituvchi, fan, mavzu (kalitlar: "oqituvchi"/"o'qituvchi", "fan", "mavzu"). Bo'sh bo'lsa None."""
    get = lambda *ks: next((uz_text.normalize_display(meta[k]) for k in ks if meta.get(k)), "")  # noqa: E731
    name = get("oqituvchi", "o'qituvchi", "oʻqituvchi", "teacher")
    sub = " · ".join(x for x in (get("fan", "subject"), get("mavzu", "topic")) if x)
    if not name and not sub:
        return None
    cw, ch = canvas
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1, f2 = font(True, 44), font(False, 30)
    w = max(d.textlength(name, font=f1), d.textlength(sub, font=f2)) + 2 * 32
    h = 44 + (30 + 14 if sub else 0) + 2 * 22
    x0, y1 = margin + 40, ch - margin - 60
    y0 = y1 - h
    d.rounded_rectangle([x0, y0, x0 + w, y1], 12, fill=(16, 32, 72, 225))
    d.rectangle([x0, y0, x0 + 8, y1], fill=(255, 196, 0, 255))
    d.text((x0 + 32, y0 + 16), name, font=f1, fill=(255, 255, 255, 255))
    if sub:
        d.text((x0 + 32, y0 + 22 + 44 + 8), sub, font=f2, fill=(220, 228, 245, 255))
    return np.asarray(img).copy()


def lower_third_alpha(out_frame: int, fps: Fraction, duration_s: float) -> float:
    """Chiqish kadri bo'yicha shaffoflik: 0..fade kirish, duration oxirida fade chiqish."""
    t = float(Fraction(out_frame) / fps)
    if t >= duration_s:
        return 0.0
    return max(0.0, min(1.0, t / FADE_S, (duration_s - t) / FADE_S))


def save_preview(arr: npt.NDArray[np.uint8], path: Path) -> None:
    Image.fromarray(arr).save(path)
