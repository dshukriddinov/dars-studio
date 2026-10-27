"""Chroma keyer (TZ 9.1, D-07), PyTorch, batch. CPU'da ham ishlaydi (testlar uchun, sekin).

Kirish: yuv420p kadrlar batch'i (Y [B,H,W], U/V [B,H/2,W/2], uint8). Chiqish: premultiplied RGB va alfa
(float, BT.709, gamma fazosi).
Qadamlar: 1) chroma upsampling luma'ga tayangan holda (guided) 2) diapazon/matritsa bo'yicha normallashtirish
3) matte = smoothstep(tol, tol+soft, ||CbCr - key||) 4) garbage/keep ko'pburchaklari 5) choke + feather
6) [ixtiyoriy] guided filter bilan chegara aniqlash 7) spill suppression G' = min(G, max(R,B)+k).
"""

from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt
import torch
import torch.nn.functional as F

from darsstudio.project.model import KeySettings

Tensor = torch.Tensor

# BT.709 YCbCr -> RGB (Cb, Cr markazlangan, [-0.5, 0.5])
KR, KB = 0.2126, 0.0722
KG = 1.0 - KR - KB
SPILL_K = 0.0  # G' = min(G, max(R,B) + k)


def box(x: Tensor, r: int) -> Tensor:
    return F.avg_pool2d(x, 2 * r + 1, stride=1, padding=r, count_include_pad=False)


def guided_filter(guide: Tensor, src: Tensor, r: int, eps: float) -> Tensor:
    """He va boshq. guided filter (bir kanalli yo'riqchi). guide, src: [B,C,H,W]."""
    mg, ms = box(guide, r), box(src, r)
    cov = box(guide * src, r) - mg * ms
    var = box(guide * guide, r) - mg * mg
    a = cov / (var + eps)
    b = ms - a * mg
    return box(a, r) * guide + box(b, r)


def gaussian_blur(x: Tensor, sigma: float) -> Tensor:
    if sigma <= 0.05:
        return x
    r = max(1, int(round(3 * sigma)))
    t = torch.arange(-r, r + 1, device=x.device, dtype=x.dtype)
    k = torch.exp(-(t * t) / (2 * sigma * sigma))
    k = (k / k.sum()).view(1, 1, 1, -1)
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode="replicate"), k)
    return F.conv2d(F.pad(x, (0, 0, r, r), mode="replicate"), k.view(1, 1, -1, 1))


def erode(a: Tensor, px: float) -> Tensor:
    r = int(round(px))
    if r <= 0:
        return a
    return -F.max_pool2d(-a, 2 * r + 1, stride=1, padding=r)


def raster_polys(polys: list[list[tuple[int, int]]], w: int, h: int) -> npt.NDArray[np.bool_]:
    m = np.zeros((h, w), np.uint8)
    for p in polys:
        if len(p) >= 3:
            cv2.fillPoly(m, [np.array(p, np.int32)], 255)
    return m > 0


def ycbcr(y: Tensor, u: Tensor, v: Tensor, full_range: bool, guided: bool = True) -> tuple[Tensor, Tensor, Tensor]:
    """uint8 tekisliklar -> (Y [0,1], Cb, Cr [-0.5,0.5]) to'liq o'lchamda, [B,1,H,W] float32."""
    yf = y.float().unsqueeze(1) / 255.0
    cb = u.float().unsqueeze(1) / 255.0
    cr = v.float().unsqueeze(1) / 255.0
    h, w = yf.shape[-2:]
    cbcr = F.interpolate(torch.cat([cb, cr], 1), size=(h, w), mode="bilinear", align_corners=False)
    if guided:
        # luma'ga tayangan upsampling: yarim o'lchamli xroma chegaralari luma chegaralariga tortiladi
        # (4:2:0 "zinapoyasi" kamayadi)
        g = yf.expand(-1, 2, -1, -1)
        cbcr = guided_filter(g, cbcr, r=2, eps=1e-4)
    cb, cr = cbcr[:, :1], cbcr[:, 1:]
    if full_range:
        return yf, cb - 128 / 255, cr - 128 / 255
    return (yf * 255 - 16) / 219, (cb * 255 - 128) / 224, (cr * 255 - 128) / 224


def to_rgb(y: Tensor, cb: Tensor, cr: Tensor) -> Tensor:
    r = y + 2 * (1 - KR) * cr
    b = y + 2 * (1 - KB) * cb
    g = (y - KR * r - KB * b) / KG
    return torch.cat([r, g, b], 1).clamp(0, 1)


def smoothstep(e0: float, e1: float, x: Tensor) -> Tensor:
    t = ((x - e0) / max(e1 - e0, 1e-6)).clamp(0, 1)
    return t * t * (3 - 2 * t)


@dataclass
class KeyResult:
    rgb: Tensor     # [B,3,H,W] premultiplied
    alpha: Tensor   # [B,1,H,W]


class Keyer:
    def __init__(self, s: KeySettings, w: int, h: int, full_range: bool, device: torch.device,
                 guided_chroma: bool = True) -> None:
        self.s, self.full, self.dev, self.guided = s, full_range, device, guided_chroma
        self.key = torch.tensor(s.key_cbcr, device=device, dtype=torch.float32).view(1, 2, 1, 1)
        self.garbage = torch.from_numpy(raster_polys(s.garbage_polys, w, h)).to(device).view(1, 1, h, w)
        self.keep = torch.from_numpy(raster_polys(s.keep_polys, w, h)).to(device).view(1, 1, h, w)

    @torch.no_grad()
    def __call__(self, y: Tensor, u: Tensor, v: Tensor) -> KeyResult:
        s = self.s
        yy, cb, cr = ycbcr(y, u, v, self.full, self.guided)
        d = torch.sqrt((cb - self.key[:, :1]) ** 2 + (cr - self.key[:, 1:]) ** 2)
        a = smoothstep(s.tolerance, s.tolerance + s.softness, d)
        a = a.masked_fill(self.garbage, 0.0).masked_fill(self.keep, 1.0)
        a = gaussian_blur(erode(a, s.choke_px), s.feather_px)
        if s.edge_refine:
            a = guided_filter(yy, a, r=6, eps=1e-3).clamp(0, 1)
        a = a.masked_fill(self.garbage, 0.0)  # feather garbage hududiga oqib kirmasin
        rgb = to_rgb(yy, cb, cr)
        if s.spill > 0:
            r, g, b = rgb[:, :1], rgb[:, 1:2], rgb[:, 2:]
            g2 = torch.minimum(g, torch.maximum(r, b) + SPILL_K)
            rgb = torch.cat([r, g + s.spill * (g2 - g), b], 1)
        return KeyResult(rgb=rgb * a, alpha=a)


GARBAGE_FILL = 0.95


def suggest(y: npt.NDArray[np.uint8], u: npt.NDArray[np.uint8], v: npt.NDArray[np.uint8], full_range: bool,
            margin_px: int = 6) -> KeySettings:
    """Bitta kadrdan boshlang'ich sozlamalar: key rangi (yashil piksellar medianasi), tolerantlik (fon
    piksellarining 99.5-persentili), garbage (yashil maydon tashqarisi: ustunlar/qatorlar bo'yicha)."""
    dev = torch.device("cpu")
    t = lambda a: torch.from_numpy(np.ascontiguousarray(a)).unsqueeze(0).to(dev)  # noqa: E731
    _, cb, cr = ycbcr(t(y), t(u), t(v), full_range, guided=False)
    cb, cr = cb[0, 0].numpy(), cr[0, 0].numpy()
    green = (cb < -0.06) & (cr < -0.06)
    if green.sum() < 1000:
        raise ValueError("kadrda yashil fon topilmadi")
    key = (float(np.median(cb[green])), float(np.median(cr[green])))
    d = np.hypot(cb - key[0], cr - key[1])
    tol = float(np.percentile(d[green], 99.5)) + 0.02
    h, w = green.shape
    # chegara — deyarli to'liq yashil ustun/qator: mato chekkasi qiyshiq bo'lsa (DSBA9359: 30% — 348, 98% — 370-ustun)
    # 30% chegarasida devordan yupqa oq chiziq qolardi (kanvasda slayd ostidan pastgacha)
    cols = np.flatnonzero(green.mean(axis=0) > GARBAGE_FILL)
    inner = green[:, cols[0]:cols[-1] + 1] if len(cols) else green   # qatorlar — yashil ustunlar oralig'ida
    rows = np.flatnonzero(inner.mean(axis=1) > GARBAGE_FILL)
    polys: list[list[tuple[int, int]]] = []
    if len(cols):
        x0, x1 = int(cols[0]) + margin_px, int(cols[-1]) - margin_px
        if x0 > margin_px:
            polys.append([(0, 0), (x0, 0), (x0, h), (0, h)])
        if x1 < w - 1 - margin_px:
            polys.append([(x1, 0), (w, 0), (w, h), (x1, h)])
    if len(rows):
        y0 = int(rows[0]) + margin_px
        if y0 > margin_px:
            polys.append([(0, 0), (w, 0), (w, y0), (0, y0)])
    return KeySettings(key_cbcr=key, tolerance=round(tol, 4), softness=0.08, spill=0.8, choke_px=1.0,
                       feather_px=1.0, garbage_polys=polys)
