"""Slayd perspektivasi (TZ 9.2, D-08): bir marta oldindan, 4K da warp + INTER_AREA bilan 1080 ga (supersampling).
Natija: kanvas o'lchamidagi RGBA PNG (to'g'ri — premultiply qilinmagan alfa), kesh: warped/<template_hash>/NNN.png."""

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from darsstudio.render.templates import Template

U8 = npt.NDArray[np.uint8]


def hex_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def read_rgb(path: Path) -> U8:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)  # Unicode yo'llar uchun fromfile
    if img is None:
        raise ValueError(f"rasmni o'qib bo'lmadi: {path}")
    return np.ascontiguousarray(img[..., ::-1])


def write_rgba(path: Path, rgba: U8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    assert ok
    tmp = path.with_name(path.name + ".tmp")
    buf.tofile(str(tmp))
    tmp.replace(path)


def fit_contain(rgb: U8, w: int, h: int, color: tuple[int, int, int] = (0, 0, 0)) -> U8:
    """Nisbatni saqlab w x h ga joylash (16:9 bo'lmasa pillarbox/letterbox)."""
    sh, sw = rgb.shape[:2]
    s = min(w / sw, h / sh)
    nw, nh = max(1, round(sw * s)), max(1, round(sh * s))
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    img = cv2.resize(rgb, (nw, nh), interpolation=interp) if (nw, nh) != (sw, sh) else rgb
    out = np.empty((h, w, 3), np.uint8)
    out[:] = color
    x, y = (w - nw) // 2, (h - nh) // 2
    out[y:y + nh, x:x + nw] = img
    return out


def warp_slide(rgb: U8, quad: tuple[tuple[float, float], ...], canvas: tuple[int, int], ss: int = 2,
               pillarbox: tuple[int, int, int] = (0, 0, 0)) -> U8:
    """Slayd (istalgan nisbatda) -> kanvasdagi ekran to'rtburchagiga RGBA (to'g'ri alfa)."""
    cw, ch = canvas
    W, H = cw * ss, ch * ss
    src = fit_contain(rgb, W, H, pillarbox)
    rgba = np.dstack([src, np.full((H, W), 255, np.uint8)])
    src_pts = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    dst_pts = np.float32(quad) * ss
    m = cv2.getPerspectiveTransform(src_pts, dst_pts)
    big = cv2.warpPerspective(rgba, m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(0, 0, 0, 0))
    # Tashqarisi RGB=0, alfa=0 -> premultiplied ko'rinish; kichraytirish chegarada to'g'ri anti-alias beradi.
    # INTER_CUBIC overshoot: alfa 255 ichida, tashqarida 0 — premult shartini tiklaymiz.
    a = big[..., 3:4].astype(np.float32)
    prem = np.minimum(big[..., :3].astype(np.float32), a)
    small_p = cv2.resize(prem, (cw, ch), interpolation=cv2.INTER_AREA)
    small_a = cv2.resize(a, (cw, ch), interpolation=cv2.INTER_AREA)[..., None]
    rgb_out = np.where(small_a > 0, small_p * 255.0 / np.maximum(small_a, 1e-6), 0)
    return np.dstack([np.clip(np.rint(rgb_out), 0, 255), np.clip(np.rint(small_a), 0, 255)]).astype(np.uint8)


def warp_all(pngs: list[Path], tpl: Template, cache_root: Path) -> list[Path]:
    """Har slaydni shablon ekraniga warp qiladi; shablon yoki slayd o'zgarmagan bo'lsa keshdan."""
    d = cache_root / tpl.content_hash()
    out = []
    for p in pngs:
        dst = d / p.name
        if not dst.is_file() or dst.stat().st_mtime_ns < p.stat().st_mtime_ns:
            write_rgba(dst, warp_slide(read_rgb(p), tpl.screen_quad, tpl.canvas,
                                       pillarbox=hex_rgb(tpl.fullscreen.pillarbox_color)))
        out.append(dst)
    return out


def quad_mask(quad: tuple[tuple[float, float], ...], canvas: tuple[int, int],
              dilate_px: int = 0) -> npt.NDArray[np.bool_]:
    """Ekran ko'pburchagi maskasi (testlar va kalibrlash uchun)."""
    m = np.zeros((canvas[1], canvas[0]), np.uint8)
    cv2.fillPoly(m, [np.round(np.float32(quad) * 16).astype(np.int32)], 255, lineType=cv2.LINE_8, shift=4)
    if dilate_px:
        m = cv2.dilate(m, np.ones((2 * dilate_px + 1, 2 * dilate_px + 1), np.uint8))
    return m > 0
