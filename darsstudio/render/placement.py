"""O'qituvchini joylashtirish (TZ 9.3): har ~2 s dan bitta kadr 540p da matte qilinadi, matte'lar birlashmasining
bounding box'i (2/98-persentil) olinadi, masshtab va joy bir marta hisoblanadi. Kadr bo'yicha framing yo'q."""

import threading
from dataclasses import dataclass

import numpy as np
import torch

from darsstudio.media import ffmpeg
from darsstudio.media.frames import planes
from darsstudio.media.probe import ProbeResult
from darsstudio.project.model import KeySettings, TeacherPlacement
from darsstudio.render.keyer import Keyer
from darsstudio.render.templates import Template

SAMPLE_SEC = 2
HEADROOM = 0.03
MAX_SCALE = 1.0  # ponytail: 1080p manbani kattalashtirish xiralashtiradi; kerak bo'lsa foydalanuvchi o'zgartiradi


@dataclass
class BBox:
    x0: int
    y0: int
    x1: int
    y1: int


def scaled_settings(s: KeySettings, f: float) -> KeySettings:
    sc = lambda polys: [[(round(x * f), round(y * f)) for x, y in p] for p in polys]  # noqa: E731
    return s.model_copy(update={"garbage_polys": sc(s.garbage_polys), "keep_polys": sc(s.keep_polys),
                                "choke_px": s.choke_px * f, "feather_px": s.feather_px * f})


def sample_alphas(p: ProbeResult, key: KeySettings, device: torch.device, every_sec: float = SAMPLE_SEC,
                  max_samples: int | None = None) -> list[np.ndarray]:
    """~every_sec dan bitta kalit kadr (skip_frame nokey: tez), 960x540, keyer alfasi > 0.5."""
    w, h = p.video.width // 2, p.video.height // 2
    args = ["-v", "error", "-nostdin", "-skip_frame", "nokey", "-i", p.path, "-map", "0:v:0",
            "-vf", f"fps=1/{every_sec},scale={w}:{h}:flags=area", "-fps_mode", "passthrough"]
    if max_samples:
        args += ["-frames:v", str(max_samples)]
    args += ["-f", "rawvideo", "-pix_fmt", p.video.pix_fmt, "-"]
    proc = ffmpeg.popen(args, stdout=True)
    err: list[bytes] = []
    threading.Thread(target=lambda: err.extend(proc.stderr or []), daemon=True).start()
    keyer = Keyer(scaled_settings(key, 0.5), w, h, p.full_range, device)
    n = w * h * 3 // 2
    out = []
    assert proc.stdout is not None
    while len(buf := proc.stdout.read(n)) == n:
        pl = planes(np.frombuffer(buf, np.uint8), w, h)
        y, u, v = (torch.from_numpy(a.copy()).unsqueeze(0).to(device) for a in pl)
        out.append((keyer(y, u, v).alpha[0, 0] > 0.5).cpu().numpy())
    proc.wait()
    return out


def union_bbox(alphas: list[np.ndarray], scale_back: int = 2) -> BBox:
    boxes = []
    for a in alphas:
        rows, cols = np.flatnonzero(a.any(axis=1)), np.flatnonzero(a.any(axis=0))
        if len(rows) and len(cols):
            boxes.append((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))
    if not boxes:
        raise ValueError("o'qituvchi topilmadi: key sozlamalarini tekshiring")
    b = np.array(boxes, np.float64)
    x0, y0 = np.percentile(b[:, 0], 2), np.percentile(b[:, 1], 2)
    x1, y1 = np.percentile(b[:, 2], 98), np.percentile(b[:, 3], 98)
    return BBox(*(int(round(v * scale_back)) for v in (x0, y0, x1, y1)))


def compute(bbox: BBox, src_size: tuple[int, int], tpl: Template, max_scale: float = MAX_SCALE) -> TeacherPlacement:
    ax0, ay0, ax1, ay1 = tpl.teacher_anchor
    sw, sh = src_size
    bw, bh = bbox.x1 - bbox.x0, bbox.y1 - bbox.y0
    head = HEADROOM * (ay1 - ay0)
    s = min((ax1 - ax0) / bw, (ay1 - ay0 - head) / bh, max_scale)
    x = (ax0 + ax1) / 2 - (bbox.x0 + bbox.x1) / 2 * s
    cut_bottom = bbox.y1 >= sh - 2   # tana kadr pastida kesilgan: manba pastki cheti anchor pastiga
    y = ay1 - (sh if cut_bottom else bbox.y1) * s
    return TeacherPlacement(scale=round(s, 4), x=int(round(x)), y=int(round(y)))
