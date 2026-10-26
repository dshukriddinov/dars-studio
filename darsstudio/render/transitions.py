"""O'tish effektlari (FR-13), montajchi namunasidan (`docs/QAROR_JURNALI.md`, 2026-10-26 tahlil):
- zoom_blur: "kamera ichkariga uchib o'tadi" — chiquvchi kadr kattalashib xiralashadi, kiruvchi kadr kattalashgan va
  xira holatdan joyiga tushadi (A <-> B, ~1.0–1.3 s);
- clock_wipe: yangi slayd ekran markazi atrofida aylanma (soat 3 dan, soat miliga teskari) ochiladi (A ichida, ~1 s);
- crossfade.
Barcha tensorlar [3,H,W] (yoki premult [4,H,W]) gamma fazosida; w — 0 (eski) .. 1 (yangi).
"""

import math

import torch
import torch.nn.functional as F

Tensor = torch.Tensor
ZOOM_K = 0.6          # o'tish o'rtasida maksimal kattalashish (1 + K)
BLUR_SAMPLES = 16     # radial (zoom) blur namunalari (8 da alohida "nusxalar" ko'rinadi)
BLUR_SPREAD = 0.12    # bitta kadr ichidagi masshtab farqi (xiralik kuchi)


def smoothstep(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def crossfade(a: Tensor, b: Tensor, w: float) -> Tensor:
    return (1 - w) * a + w * b


def zoom(img: Tensor, scale: float, blur: float, center: tuple[float, float]) -> Tensor:
    """img [C,H,W]; markaz (cx, cy) piksellarda. blur 0..1 — radial xiralik (bir nechta masshtab o'rtachasi)."""
    c, h, w = img.shape
    if scale <= 1.0001 and blur <= 1e-3:
        return img
    n = BLUR_SAMPLES if blur > 1e-3 else 1
    cx, cy = center[0] / (w - 1) * 2 - 1, center[1] / (h - 1) * 2 - 1
    scales = [scale * (1 + BLUR_SPREAD * blur * k / max(1, n - 1)) for k in range(n)]
    theta = torch.tensor([[[1 / s, 0, cx * (1 - 1 / s)], [0, 1 / s, cy * (1 - 1 / s)]] for s in scales],
                         device=img.device, dtype=torch.float32)
    grid = F.affine_grid(theta, [n, c, h, w], align_corners=True)
    x = img.float().unsqueeze(0).expand(n, -1, -1, -1)
    out = F.grid_sample(x, grid, mode="bilinear", padding_mode="border", align_corners=True).mean(0)
    return out.to(img.dtype)


def zoom_blur(a: Tensor, b: Tensor, w: float, center_a: tuple[float, float], center_b: tuple[float, float]) -> Tensor:
    """a -> b: a markaz_a atrofida kattalashib xiralashadi; b kattalashgan/xira holatdan joyiga tushadi."""
    e = smoothstep(w)
    za = zoom(a, 1 + ZOOM_K * e * e, min(1.0, 2 * e), center_a)
    zb = zoom(b, 1 + ZOOM_K * (1 - e) ** 2, min(1.0, 2 * (1 - e)), center_b)
    m = smoothstep((w - 0.35) / 0.3)          # o'rtada tez almashadi (xira kadrlar ustida — chok ko'rinmaydi)
    return (1 - m) * za + m * zb


class ClockWipe:
    """Kanvasdagi markaz atrofida burchak xaritasi (bir marta hisoblanadi)."""

    def __init__(self, size: tuple[int, int], center: tuple[float, float], device: torch.device,
                 soft_deg: float = 2.0) -> None:
        cw, ch = size
        ys = torch.arange(ch, device=device, dtype=torch.float32).view(-1, 1) - center[1]
        xs = torch.arange(cw, device=device, dtype=torch.float32).view(1, -1) - center[0]
        self.ang = torch.remainder(torch.atan2(-ys, xs), 2 * math.pi)   # 0 = soat 3, soat miliga teskari o'sadi
        self.soft = math.radians(soft_deg)

    def mask(self, w: float) -> Tensor:
        lim = 2 * math.pi * w
        return ((lim - self.ang) / self.soft + 0.5).clamp(0, 1)

    def __call__(self, a: Tensor, b: Tensor, w: float) -> Tensor:
        if w <= 0:
            return a
        if w >= 1:
            return b
        m = self.mask(w).to(a.dtype)
        return a * (1 - m) + b * m
