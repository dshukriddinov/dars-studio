"""Eye Contact patchlari (FR-10, D-02, TZ 9.7). Modul faqat CLI orqali (`--patches-out`), alohida jarayonda;
uning ichki kodi import qilinmaydi (CLAUDE.md, 7-qoida) — shu yerda format bo'yicha o'z o'quvchimiz.

Qo'llash: out = orig + w*(patch - orig) faqat maska ichida, YUV fazosida, kadr dekod qilingandan keyin.
w: Eye Contact o'chiq oraliqlarda 0, chegarada `ramp_frames` davomida 0<->1 silliq.
"""

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from darsstudio import paths
from darsstudio.media.probe import file_id
from darsstudio.project.model import EyeOffSpan

FORMAT_VERSION = 1
RAMP_FRAMES = 8
EC_DIR = paths.ROOT / "engines" / "eye-contact"


def run_eye_contact(src: Path, out_dir: Path, lid_open: float = 0.5,
                    on_progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """Eye Contact CLI (resume bilan). Maxine: DARS_MAXINE_DIR / runtime/maxine bo'lsa NVAR_SDK_DIR sifatida."""
    env = dict(os.environ)
    if paths.maxine_dir().is_dir():
        env["NVAR_SDK_DIR"] = str(paths.maxine_dir())
    cmd = [sys.executable, "-m", "eyecontact.cli", str(Path(src).resolve()), "--patches-out",
           str(Path(out_dir).resolve()), "--lid-open", str(lid_open), "--resume", "--progress", "-q"]
    proc = subprocess.Popen(cmd, cwd=EC_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    tail: list[str] = []
    assert proc.stderr is not None
    for line in proc.stderr:
        if line.startswith("PROGRESS") and on_progress:
            _, d, t = line.split()
            on_progress(int(d), int(t))
        else:
            tail = (tail + [line.rstrip()])[-20:]
    if proc.wait() != 0:
        raise RuntimeError("Eye Contact xato bilan tugadi: " + " | ".join(tail))
    meta: dict[str, Any] = json.loads((Path(out_dir) / "meta.json").read_text(encoding="utf-8"))
    return meta


def is_valid(out_dir: Path, src: Path, lid_open: float) -> bool:
    """Kesh yaroqli: meta bor, manba fayl o'sha (hash), lid_open o'sha."""
    mf = Path(out_dir) / "meta.json"
    if not mf.is_file():
        return False
    meta = json.loads(mf.read_text(encoding="utf-8"))
    return (meta.get("format_version") == FORMAT_VERSION and meta.get("source_id") == file_id(src)
            and f"lid_open={lid_open}" in meta.get("cfg_key", ""))


def read_chunk(path: Path) -> dict[int, dict[str, Any]]:
    """npz -> {kadr: yozuv}. Yozuv: box, size, y_mask, uv_mask (bool), y_data, uv_data."""
    with np.load(path) as z:
        d = {k: z[k] for k in z.files}
    w, h = (int(v) for v in d["size"])
    ym_all, uvm_all = np.unpackbits(d["y_mask"]).astype(bool), np.unpackbits(d["uv_mask"]).astype(bool)
    out: dict[int, dict[str, Any]] = {}
    yb = cb = 0
    for i, fi in enumerate(d["frame_idx"]):
        x0, y0, x1, y1 = (int(v) for v in d["box"][i])
        bh, bw = y1 - y0, x1 - x0
        ym = ym_all[yb:yb + bh * bw].reshape(bh, bw)
        uvm = uvm_all[cb:cb + bh * bw // 4].reshape(bh // 2, bw // 2)
        yb, cb = yb + bh * bw, cb + bh * bw // 4
        (ys, cs), (ye, ce) = d["offsets"][i], d["offsets"][i + 1]
        out[int(fi)] = {"box": (x0, y0, x1, y1), "size": (w, h), "y_mask": ym, "uv_mask": uvm,
                        "y_data": d["y_data"][ys:ye], "uv_data": d["uv_data"][cs:ce]}
    return out


def apply(frame: npt.NDArray[np.uint8], rec: dict[str, Any], w: float = 1.0) -> None:
    """yuv420p kadrga joyida. w = 1 -> Eye Contact chiqishi bilan bayt-aniq."""
    if w <= 0:
        return
    fw, fh = rec["size"]
    x0, y0, x1, y1 = rec["box"]
    n, q = fw * fh, (fw // 2) * (fh // 2)
    Y = frame[:n].reshape(fh, fw)[y0:y1, x0:x1]
    U = frame[n:n + q].reshape(fh // 2, fw // 2)[y0 // 2:y1 // 2, x0 // 2:x1 // 2]
    V = frame[n + q:n + 2 * q].reshape(fh // 2, fw // 2)[y0 // 2:y1 // 2, x0 // 2:x1 // 2]
    ym, uvm = rec["y_mask"], rec["uv_mask"]
    k = int(uvm.sum())
    py, pu, pv = rec["y_data"], rec["uv_data"][:k], rec["uv_data"][k:]
    if w >= 1:
        Y[ym], U[uvm], V[uvm] = py, pu, pv
        return
    mix = lambda o, p: np.clip(np.rint(o + w * (p.astype(np.float32) - o)), 0, 255).astype(np.uint8)  # noqa: E731
    Y[ym], U[uvm], V[uvm] = mix(Y[ym], py), mix(U[uvm], pu), mix(V[uvm], pv)


def weight(f: int, eye_off: Sequence[EyeOffSpan], ramp: int = RAMP_FRAMES) -> float:
    """O'chiq oraliq ichida 0, chetidan ramp kadr ichida chiziqli 0 -> 1."""
    w = 1.0
    for s in eye_off:
        if s.start <= f < s.end:
            return 0.0
        d = s.start - f if f < s.start else f - (s.end - 1)
        if ramp > 0 and d <= ramp:
            w = min(w, d / (ramp + 1))
    return w


class EyePatches:
    """Patch papkasi: kadr bo'yicha yozuv (chunk'lar kerak bo'lganda yuklanadi, bittasi xotirada)."""

    def __init__(self, out_dir: Path) -> None:
        self.dir = Path(out_dir)
        self.meta = json.loads((self.dir / "meta.json").read_text(encoding="utf-8"))
        self.chunks = [(c["start"], c["end"], c["file"]) for c in self.meta["chunks"]]
        self._cur: tuple[int, int, dict[int, dict[str, Any]]] | None = None

    def get(self, f: int) -> dict[str, Any] | None:
        if self._cur is None or not (self._cur[0] <= f < self._cur[1]):
            c = next((c for c in self.chunks if c[0] <= f < c[1]), None)
            if c is None:
                return None
            self._cur = (c[0], c[1], read_chunk(self.dir / c[2]))
        return self._cur[2].get(f)
