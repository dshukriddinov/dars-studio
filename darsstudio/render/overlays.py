"""Overlay'lar (FR-13): lower-third va mualliflik matni. Pillow bilan bir marta RGBA qatlam chiziladi; kompozitorda
chiqish vaqti bo'yicha shaffoflik va siljish (drift) qo'llanadi.

Uslublar: "default" (Noto Sans, fade 0.3 s) va "akademiya" (montajchi namunasidan: pastki chapda ko'k gradient
polosa, ism Roboto Slab qalin, 2 qator unvon, matn sekin chapga siljiydi, fade'siz). Shriftlar: Noto (OFL),
Roboto Slab (Apache-2.0).
"""

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from darsstudio import paths
from darsstudio.asr import uz_text

FADE_S = 0.3
FONT_DIR = paths.ROOT / "templates" / "fonts"
U8 = npt.NDArray[np.uint8]


@dataclass
class Overlay:
    """RGBA qatlam (kanvas o'lchamida, to'g'ri alfa) chiqish kadrlarida [start, end) ko'rinadi."""
    layer: U8
    start: int
    end: int
    fade_frames: int = 0
    drift_px_per_frame: float = 0.0     # manfiy — chapga
    slide_in_px: int = 0                # boshida shuncha o'ngda, slide_frames davomida chiziqli joyiga keladi
    slide_frames: int = 0
    clip_x: int | None = None           # shu ustundan o'ngi ko'rinmaydi (niqob)

    def alpha_at(self, g: int) -> float:
        if not self.start <= g < self.end:
            return 0.0
        if self.fade_frames <= 0:
            return 1.0
        return max(0.0, min(1.0, (g - self.start + 1) / self.fade_frames, (self.end - g) / self.fade_frames))

    def shift_at(self, g: int) -> int:
        k = g - self.start
        slide = self.slide_in_px * max(0.0, 1 - k / self.slide_frames) if self.slide_frames else 0.0
        return int(round(self.drift_px_per_frame * k + slide))

    def moves(self) -> bool:
        return bool(self.drift_px_per_frame or self.slide_frames)


def font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / ("NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf")), size)


def slab(weight: int, size: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT_DIR / "RobotoSlab-VF.ttf"), size)
    f.set_variation_by_axes([weight])
    return f


def glyph_safe(text: str, f: ImageFont.FreeTypeFont) -> str:
    """Shriftda oʻ/gʻ uchun U+02BB (yoki U+02BC) bo'lmasa ‘ / ’ ga almashtiradi (Roboto Slab'da U+02BB yo'q —
    aks holda "notdef" kvadrat chiqadi)."""
    def mask(c: str) -> bytes:
        m = f.getmask(c)
        return np.asarray(m).tobytes() + str(m.size).encode()
    nd = mask("")
    for ch, alt in (("ʻ", "‘"), ("ʼ", "’")):
        if ch in text and mask(ch) == nd:
            text = text.replace(ch, alt)
    return text


def _meta(meta: dict[str, str], *keys: str) -> str:
    return next((uz_text.normalize_display(meta[k]) for k in keys if meta.get(k)), "")


def _lines(meta: dict[str, str]) -> tuple[str, list[str]]:
    """Ism + 2 qator. UI maydonlari: ish_joyi + lavozim (1-qator), ilmiy_unvon (2-qator); eski "unvon" ("a | b")."""
    name = _meta(meta, "oqituvchi", "o'qituvchi", "oʻqituvchi", "teacher")
    job = " ".join(x for x in (_meta(meta, "ish_joyi"), _meta(meta, "lavozim")) if x)
    degree = _meta(meta, "ilmiy_unvon")
    if job or degree:
        return name, [x for x in (job, degree) if x]
    unvon = _meta(meta, "unvon", "title")
    sub = [x.strip() for x in unvon.split("|") if x.strip()] if unvon else \
        [x for x in (" · ".join(y for y in (_meta(meta, "fan", "subject"), _meta(meta, "mavzu", "topic")) if y),) if x]
    return name, sub


def lower_third(meta: dict[str, str], canvas: tuple[int, int], margin: int = 24) -> npt.NDArray[np.uint8] | None:
    """"default" uslub: bitta qatlam. meta: oqituvchi, unvon ("1-qator | 2-qator") yoki fan/mavzu."""
    name, sub = _lines(meta)
    if not name and not sub:
        return None
    cw, ch = canvas
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1, f2 = font(True, 44), font(False, 30)
    w = max([d.textlength(name, font=f1)] + [d.textlength(s, font=f2) for s in sub]) + 2 * 32
    h = 44 + sum(30 + 10 for _ in sub) + 2 * 22
    x0, y1 = margin + 40, ch - margin - 60
    y0 = y1 - h
    d.rounded_rectangle([x0, y0, x0 + w, y1], 12, fill=(16, 32, 72, 225))
    d.rectangle([x0, y0, x0 + 8, y1], fill=(255, 196, 0, 255))
    d.text((x0 + 32, y0 + 16), name, font=f1, fill=(255, 255, 255, 255))
    for i, s in enumerate(sub):
        d.text((x0 + 32, y0 + 22 + 44 + 8 + i * 40), s, font=f2, fill=(220, 228, 245, 255))
    return np.asarray(img).copy()


def lower_third_akademiya(meta: dict[str, str], canvas: tuple[int, int]) -> tuple[U8, U8] | None:
    """(polosa, matn) qatlamlari. Namunadan: polosa y 870–982, chapdan ~840 px gacha yorqin ko'k, o'ngga shaffoflashadi;
    ism Roboto Slab 700 ~44 px, unvon Roboto Slab 300 ~28 px, oq, yengil soya."""
    name, sub = _lines(meta)
    if not name and not sub:
        return None
    cw, ch = canvas
    bar = np.zeros((ch, cw, 4), np.uint8)
    y0, y1, solid, fade_to = 870, 982, 600, 880
    a = np.clip((fade_to - np.arange(cw)) / (fade_to - solid), 0, 1)
    bar[y0:y1, :, :3] = (10, 60, 200)
    bar[y0:y1, :, 3] = (a * 235).astype(np.uint8)[None, :]
    txt = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    f1, f2 = slab(700, 44), slab(300, 28)
    x = 160
    d.text((x, y0 + 4), glyph_safe(name, f1), font=f1, fill=(255, 255, 255, 255))
    for i, s in enumerate(sub[:2]):
        d.text((x, y0 + 56 + i * 30), glyph_safe(s, f2), font=f2, fill=(235, 240, 255, 255))
    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    shadow.putalpha(txt.getchannel("A").filter(ImageFilter.GaussianBlur(3)).point(lambda v: v * 0.6))
    out = Image.alpha_composite(Image.new("RGBA", (cw, ch), (0, 0, 0, 0)), shadow.transform(
        (cw, ch), Image.Transform.AFFINE, (1, 0, -2, 0, 1, -2)))
    out = Image.alpha_composite(out, txt)
    return bar, np.asarray(out).copy()


COPYRIGHT_BOX_X1 = 900   # polosa o'ng cheti (sirg'alish niqobi)


def copyright_layer(text: str, canvas: tuple[int, int]) -> U8:
    """Mualliflik matni (namunadan): oq kursiv, KATTA harflar, 3 qatorgacha, pastki chap-markazda, qora yarim shaffof
    polosa ustida."""
    cw, ch = canvas
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONT_DIR / "NotoSerif-Italic.ttf"), 19)
    words, lines, cur = glyph_safe(uz_text.normalize_display(text).upper(), f).split(), [], ""
    for w in words:
        if d.textlength(f"{cur} {w}".strip(), font=f) > 820:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    lines = lines[:3]
    lh, cx = 25, 470
    y0 = ch - 26 - lh * len(lines)
    d.rectangle([0, y0 - 8, COPYRIGHT_BOX_X1, ch - 18], fill=(0, 0, 0, 110))
    for i, ln in enumerate(lines):
        d.text((cx - d.textlength(ln, font=f) / 2, y0 + i * lh), ln, font=f, fill=(255, 255, 255, 255))
    return np.asarray(img).copy()


def build(meta: dict[str, str], style: str, duration_s: float, copyright_text: str | None,
          copyright_from: int | None, main_frames: int, fps: Fraction, canvas: tuple[int, int],
          cp_slide: tuple[float, int] = (0.0, 0)) -> list[Overlay]:
    """Chiqish (asosiy qism) kadrlarida overlay'lar ro'yxati."""
    out: list[Overlay] = []
    dur = min(main_frames, round(Fraction(duration_s).limit_denominator(1000) * fps))
    if style == "akademiya":
        lt = lower_third_akademiya(meta, canvas)
        if lt is not None:
            out += [Overlay(lt[0], 0, dur), Overlay(lt[1], 0, dur, drift_px_per_frame=-16 / float(fps))]
    else:
        layer = lower_third(meta, canvas)
        if layer is not None:
            out.append(Overlay(layer, 0, dur, fade_frames=round(FADE_S * float(fps))))
    if copyright_text and copyright_from is not None and copyright_from < main_frames:
        sf = round(Fraction(cp_slide[0]).limit_denominator(1000) * fps)
        out.append(Overlay(copyright_layer(copyright_text, canvas), copyright_from, main_frames,
                           slide_in_px=cp_slide[1], slide_frames=sf, clip_x=COPYRIGHT_BOX_X1 if sf else None))
    return out


def lower_third_alpha(out_frame: int, fps: Fraction, duration_s: float) -> float:
    """Eski API (default uslub): chiqish kadri bo'yicha shaffoflik, fade 0.3 s."""
    t = float(Fraction(out_frame) / fps)
    if t >= duration_s:
        return 0.0
    return max(0.0, min(1.0, t / FADE_S, (duration_s - t) / FADE_S))


def save_preview(arr: npt.NDArray[np.uint8], path: Path) -> None:
    Image.fromarray(arr).save(path)
