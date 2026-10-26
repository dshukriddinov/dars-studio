"""Kompozitsiya (FR-12, FR-13 o'tishlar va logo). GPU tensorlar, gamma fazosi (TZ 9.8), premultiplied alfa.

A `split_right_teacher`: fon -> warp qilingan slayd -> o'qituvchi -> logo.
B `fullscreen_slide`:    slayd 1920x1080 (contain, pillarbox) -> logo. O'qituvchi yashirin, audio davom etadi.
O'tishlar: A ichida slayd->slayd crossfade (slide_frames), A<->B crossfade (layout_frames). O'tish chegaradan
boshlanadi va N kadr davom etadi.
"""

import bisect
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from darsstudio.project.model import LayoutSpan, SlideSpan, TeacherPlacement
from darsstudio.render.templates import Template
from darsstudio.slides.warp import fit_contain, hex_rgb, read_rgb

Tensor = torch.Tensor


def load_rgba(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"rasmni o'qib bo'lmadi: {path}")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)


def premult(rgba: np.ndarray, device: torch.device, dtype: torch.dtype) -> Tensor:
    """uint8 RGBA (to'g'ri alfa) -> [4,H,W] premultiplied."""
    t = torch.from_numpy(rgba).to(device).permute(2, 0, 1).float() / 255.0
    return torch.cat([t[:3] * t[3:], t[3:]], 0).to(dtype)


def over(top: Tensor, bottom_rgb: Tensor) -> Tensor:
    """top [..,4,H,W] premult ustiga; bottom [..,3,H,W] shaffof emas."""
    return top[..., :3, :, :] + bottom_rgb * (1 - top[..., 3:, :, :])


@dataclass
class Timeline:
    """Har chiqish kadri uchun: joriy/oldingi slayd, slayd o'tish vazni, sahna va sahna o'tish vazni."""
    slide_starts: list[int]
    slides: list[int]
    layout_starts: list[int]
    layouts: list[str]
    slide_frames: int
    layout_frames: int

    @classmethod
    def build(cls, slide_spans: Sequence[SlideSpan], layout_spans: Sequence[LayoutSpan], tpl: Template) -> "Timeline":
        ss = sorted(slide_spans, key=lambda s: s.start)
        ls = sorted(layout_spans, key=lambda s: s.start)
        return cls([s.start for s in ss], [s.slide for s in ss], [s.start for s in ls], [s.layout for s in ls],
                   tpl.transitions.slide_frames, tpl.transitions.layout_frames)

    @staticmethod
    def _at(starts: list[int], vals: list[object], f: int, n: int) -> tuple[object, object, float]:
        i = max(0, bisect.bisect_right(starts, f) - 1)
        cur = vals[i]
        if i == 0 or n <= 0 or f - starts[i] >= n or vals[i - 1] == cur:
            return cur, cur, 1.0
        return cur, vals[i - 1], (f - starts[i] + 1) / (n + 1)

    def slide(self, f: int) -> tuple[int, int, float]:
        c, p, w = self._at(self.slide_starts, self.slides, f, self.slide_frames)
        return int(c), int(p), w  # type: ignore[call-overload,unused-ignore]

    def layout(self, f: int) -> tuple[str, str, float]:
        c, p, w = self._at(self.layout_starts, self.layouts, f, self.layout_frames)
        return str(c), str(p), w


class Compositor:
    def __init__(self, tpl: Template, warped: list[Path], slides_4k: list[Path], placement: TeacherPlacement,
                 src_size: tuple[int, int], device: torch.device, dtype: torch.dtype = torch.float16) -> None:
        self.tpl, self.dev, self.dtype, self.pl = tpl, device, dtype, placement
        cw, ch = tpl.canvas
        self.canvas = (cw, ch)
        bg = fit_contain(read_rgb(tpl.asset(tpl.background)), cw, ch)
        self.bg = torch.from_numpy(bg).to(device).permute(2, 0, 1).to(dtype) / 255.0
        self.warped = [premult(load_rgba(p), device, dtype) for p in warped]
        box = hex_rgb(tpl.fullscreen.pillarbox_color)
        self.full = [torch.from_numpy(fit_contain(read_rgb(p), cw, ch, box)).to(device).permute(2, 0, 1).to(dtype)
                     / 255.0 for p in slides_4k]
        self.logo = None
        if tpl.logo:
            lg = load_rgba(tpl.asset(tpl.logo.file))
            lh = tpl.logo.height
            lw = max(1, round(lg.shape[1] * lh / lg.shape[0]))
            lg = cv2.resize(lg, (lw, lh), interpolation=cv2.INTER_AREA)
            layer = np.zeros((ch, cw, 4), np.uint8)
            x, y = tpl.logo.pos
            x1, y1 = min(cw, x + lw), min(ch, y + lh)
            layer[y:y1, x:x1] = lg[: y1 - y, : x1 - x]
            self.logo = premult(layer, device, dtype)
        # o'qituvchi: manba -> kanvasdagi joy (masshtab + siljish), bir marta hisoblanadigan oyna
        sw, sh = src_size
        self.tw, self.th = max(1, round(sw * placement.scale)), max(1, round(sh * placement.scale))
        x0, y0 = placement.x, placement.y
        self.dst = (max(0, x0), max(0, y0), min(cw, x0 + self.tw), min(ch, y0 + self.th))
        self.src = (self.dst[0] - x0, self.dst[1] - y0, self.dst[2] - x0, self.dst[3] - y0)

    def teacher_layer(self, rgb: Tensor, alpha: Tensor) -> Tensor:
        """[B,3,H,W] premult + [B,1,H,W] -> kanvas [B,4,ch,cw]."""
        t = torch.cat([rgb, alpha], 1).to(self.dtype)
        if (self.th, self.tw) != tuple(t.shape[-2:]):
            t = F.interpolate(t.float(), size=(self.th, self.tw), mode="bilinear", align_corners=False,
                              antialias=self.pl.scale < 1).to(self.dtype)
        cw, ch = self.canvas
        out = torch.zeros((t.shape[0], 4, ch, cw), device=self.dev, dtype=self.dtype)
        dx0, dy0, dx1, dy1 = self.dst
        sx0, sy0, sx1, sy1 = self.src
        if dx1 > dx0 and dy1 > dy0:
            out[:, :, dy0:dy1, dx0:dx1] = t[:, :, sy0:sy1, sx0:sx1]
        return out

    def scene_a(self, slide_layer: Tensor, teacher: Tensor) -> Tensor:
        return over(teacher, over(slide_layer, self.bg))

    def scene(self, layout: str, slide: tuple[int, int, float], teacher: Tensor) -> Tensor:
        cur, prev, ws = slide
        layers = self.full if layout == "B" else self.warped
        sl = layers[cur - 1] if ws >= 1 else (1 - ws) * layers[prev - 1] + ws * layers[cur - 1]
        return sl if layout == "B" else self.scene_a(sl, teacher)

    def compose(self, frames: Sequence[int], tl: Timeline, teacher: Tensor) -> Tensor:
        """frames: asl kadr indekslari; teacher: teacher_layer() natijasi. -> [B,3,ch,cw] RGB [0,1]."""
        outs = []
        for i, f in enumerate(frames):
            slide = tl.slide(f)
            lc, lp, wl = tl.layout(f)
            img = self.scene(lc, slide, teacher[i])
            if wl < 1:
                img = (1 - wl) * self.scene(lp, slide, teacher[i]) + wl * img
            if self.logo is not None:
                img = over(self.logo, img)
            outs.append(img)
        return torch.stack(outs).clamp(0, 1)


def rgb_to_yuv420(rgb: Tensor) -> Tensor:
    """[B,3,H,W] RGB [0,1] -> [B, H*W*3/2] uint8 yuv420p, BT.709 limited range (TZ 4.6)."""
    r, g, b = rgb.float().unbind(1)
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    cb = (b - y) / 1.8556
    cr = (r - y) / 1.5748
    Y = 16 + 219 * y
    U = F.avg_pool2d((128 + 224 * cb).unsqueeze(1), 2).squeeze(1)
    V = F.avg_pool2d((128 + 224 * cr).unsqueeze(1), 2).squeeze(1)
    q = lambda a: a.round().clamp(0, 255).to(torch.uint8).flatten(1)  # noqa: E731
    return torch.cat([q(Y), q(U), q(V)], 1)
