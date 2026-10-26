"""Yakuniy render, bitta o'tish (D-01, FR-16 soddalashtirilgan, B3).

dekod (yuv420p, CPU, alohida oqim) -> GPU batch: keyer -> rang -> joylashtirish -> kompozit -> yuv420p BT.709 tv
-> NVENC (alohida oqim). Chunk'lar: cache/render/<kalit>/seg_XXXXX.mp4 + .json checkpoint; oxirida concat -c copy
va audio manbadan (AAC 192k). Video/audio boshlanish munosabati saqlanadi (Eye Contact EC-1 bilan bir xil tamoyil).
"""

import hashlib
import json
import logging
import math
import queue
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import torch

from darsstudio.media import ffmpeg
from darsstudio.media.frames import FrameReader, FrameWriter
from darsstudio.media.probe import ProbeResult
from darsstudio.project.model import LayoutSpan, Project, SlideSpan
from darsstudio.project.store import atomic_write_json
from darsstudio.render.compositor import Compositor, Timeline, rgb_to_yuv420
from darsstudio.render.keyer import Keyer
from darsstudio.render.templates import Template

log = logging.getLogger(__name__)

RENDER_VERSION = 1  # render natijasiga ta'sir qiluvchi kod o'zgarsa oshiriladi (checkpoint kaliti)
BT709_TAGS = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
PROFILES = {
    # TZ FR-16
    "web": ["-rc", "vbr", "-b:v", "8M", "-maxrate", "12M", "-bufsize", "16M"],
    "arxiv": ["-rc", "vbr", "-cq", "19", "-b:v", "0", "-maxrate", "16M", "-bufsize", "32M"],
}


def encoder_args(profile: str, preset: str = "p7") -> list[str]:
    if ffmpeg.nvenc_ok():
        return ["-c:v", "h264_nvenc", "-preset", preset, "-tune", "hq", "-profile:v", "high", "-g", "50",
                *PROFILES[profile], "-pix_fmt", "yuv420p"]
    crf = "19" if profile == "arxiv" else "21"  # ponytail: NVENC yo'q -> CPU x264 (sekin)
    return ["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-g", "50", "-pix_fmt", "yuv420p"]


@dataclass
class RenderOptions:
    profile: str = "web"
    preset: str = "p7"
    batch: int = 8
    chunk_sec: int = 60
    start: int = 0                    # asl kadr (bo'lak render uchun)
    frames: int | None = None
    device: str | None = None         # None: cuda bo'lsa cuda
    dtype: torch.dtype = torch.float16
    on_progress: Callable[[int, int], None] | None = None
    workdir: Path | None = None


@dataclass
class RenderReport:
    output: str
    frames: int
    seconds: float
    fps: float
    vram_peak_mb: float
    warnings: list[dict[str, Any]] = field(default_factory=list)


def color_correct(rgb: torch.Tensor, alpha: torch.Tensor, c: dict[str, float]) -> torch.Tensor:
    """O'qituvchi rangi (TZ 9.8): exposure (stop), saturation (1 = o'zgarishsiz). Premultiplied kirish/chiqish."""
    ev, sat = c.get("exposure", 0.0), c.get("saturation", 1.0)
    if ev:
        rgb = rgb * (2.0 ** ev)
    if sat != 1.0:
        y = (0.2126 * rgb[:, :1] + 0.7152 * rgb[:, 1:2] + 0.0722 * rgb[:, 2:])
        rgb = y + (rgb - y) * sat
    return torch.minimum(rgb.clamp(min=0), alpha)


def spans_to_warnings(flags: dict[str, list[int]], min_len: int = 5) -> list[dict[str, Any]]:
    """Kadr raqamlari ro'yxati -> ketma-ket >= min_len kadrli oraliqlar (TZ 9.3 ogohlantirishlari)."""
    out = []
    for kind, frames in flags.items():
        run: list[int] = []
        for f in [*sorted(frames), None]:
            if run and (f is None or f != run[-1] + 1):
                if len(run) >= min_len:
                    out.append({"kind": kind, "start": run[0], "end": run[-1] + 1})
                run = []
            if f is not None:
                run.append(f)
    return sorted(out, key=lambda w: w["start"])


def render_key(project: Project, tpl: Template, slide_files: Sequence[Path], spans: tuple[Any, Any],
               opts: RenderOptions, probe: ProbeResult) -> str:
    h = hashlib.sha256()
    h.update(json.dumps({"v": RENDER_VERSION, "key": project.key.model_dump(mode="json"),
                         "placement": project.placement.model_dump(mode="json"), "tpl": tpl.content_hash(),
                         "slides": [str(p) + str(p.stat().st_mtime_ns) for p in slide_files],
                         "spans": [[s.model_dump(mode="json") for s in g] for g in spans],
                         "profile": opts.profile, "preset": opts.preset, "chunk": opts.chunk_sec,
                         "src": probe.path, "start": opts.start}, sort_keys=True).encode())
    return h.hexdigest()[:16]


def _reader(p: ProbeResult, start: int, count: int, batch: int, q: "queue.Queue[Any]") -> None:
    try:
        buf, idx = [], []
        with FrameReader(p, start=start, count=count) as r:
            for i, f in enumerate(r):
                buf.append(f)
                idx.append(start + i)
                if len(buf) == batch:
                    q.put((idx, np.stack(buf)))
                    buf, idx = [], []
        if buf:
            q.put((idx, np.stack(buf)))
        q.put(None)
    except BaseException as e:  # asosiy oqimga yetkazamiz
        q.put(e)


def _writer(wr: FrameWriter, q: "queue.Queue[Any]", err: list[BaseException]) -> None:
    try:
        while (item := q.get()) is not None:
            for f in item:
                wr.write(f)
        wr.close()
    except BaseException as e:
        err.append(e)
        while q.get() is not None:  # ishlab chiqaruvchi bloklanmasin
            pass


def render(project: Project, probe: ProbeResult, tpl: Template, warped: list[Path], slides_4k: list[Path],
           slide_spans: list[SlideSpan], layout_spans: list[LayoutSpan], out: Path, work_root: Path,
           opts: RenderOptions | None = None) -> RenderReport:
    opts = opts or RenderOptions()
    dev = torch.device(opts.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    dtype = opts.dtype if dev.type == "cuda" else torch.float32
    v = probe.video
    w, h, fps = v.width, v.height, v.fps
    total = (opts.frames if opts.frames is not None else project.total_frames - opts.start)
    total = min(total, project.total_frames - opts.start)
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dev)

    keyer = Keyer(project.key, w, h, probe.full_range, dev)
    comp = Compositor(tpl, warped, slides_4k, project.placement, (w, h), dev, dtype)
    tl = Timeline.build(slide_spans, layout_spans, tpl)
    key = render_key(project, tpl, slides_4k, (slide_spans, layout_spans), opts, probe)
    wd = work_root / key
    wd.mkdir(parents=True, exist_ok=True)
    chunk = max(1, int(opts.chunk_sec * fps))
    nchunks = math.ceil(total / chunk)
    enc = encoder_args(opts.profile, opts.preset)
    cw, ch = tpl.canvas
    # ogohlantirish zonalari (TZ 9.3, FR-12): bosh yuqori chetga 2% dan yaqin; anchor yoki garbage chegarasi
    ax0, ay0, ax1, ay1 = tpl.teacher_anchor
    top_zone = max(1, int(0.02 * ch))
    gmask = keyer.garbage.float()
    gedge = (torch.nn.functional.max_pool2d(gmask, 9, stride=1, padding=4) - gmask) > 0
    flags: dict[str, list[int]] = {"bosh_yuqori_chetda": [], "anchor_tashqarisida": [], "yashil_maydon_chetida": []}

    t0 = time.time()
    done = 0
    segments = []
    for k in range(nchunks):
        s = opts.start + k * chunk
        n = min(chunk, opts.start + total - s)
        seg = wd / f"seg_{k:05d}.mp4"
        mark = seg.with_suffix(".json")
        segments.append(seg)
        if seg.is_file() and mark.is_file() and json.loads(mark.read_text())["frames"] == n:
            st = json.loads(mark.read_text())
            for kind, fr in st.get("flags", {}).items():
                flags[kind] += fr
            done += n
            continue
        cflags: dict[str, list[int]] = {kk: [] for kk in flags}
        qin: queue.Queue[Any] = queue.Queue(maxsize=4)
        qout: queue.Queue[Any] = queue.Queue(maxsize=4)
        werr: list[BaseException] = []
        wr = FrameWriter(seg, cw, ch, fps, None, enc, tags=BT709_TAGS)
        threading.Thread(target=_reader, args=(probe, s, n, opts.batch, qin), daemon=True).start()
        tw = threading.Thread(target=_writer, args=(wr, qout, werr), daemon=True)
        tw.start()
        got = 0
        try:
            while (item := qin.get()) is not None:
                if isinstance(item, BaseException):
                    raise item
                idx, arr = item
                t = torch.from_numpy(arr).to(dev, non_blocking=True)
                ny = w * h
                y = t[:, :ny].view(-1, h, w)
                u = t[:, ny:ny + ny // 4].view(-1, h // 2, w // 2)
                vv = t[:, ny + ny // 4:].view(-1, h // 2, w // 2)
                kr = keyer(y, u, vv)
                rgb = color_correct(kr.rgb, kr.alpha, project.placement.color)
                teacher = comp.teacher_layer(rgb, kr.alpha)
                img = comp.compose(idx, tl, teacher)
                qout.put(rgb_to_yuv420(img).cpu().numpy())
                # ogohlantirishlar (faqat A sahnada mazmunli, lekin kadr bo'yicha belgilaymiz)
                ta = teacher[:, 3] > 0.5
                top = ta[:, :top_zone].flatten(1).any(1)
                outside = ta.clone()
                outside[:, ay0:ay1, ax0:ax1] = False
                edge = (kr.alpha[:, 0] > 0.5)[:, gedge[0, 0]].any(1) if gedge.any() else torch.zeros_like(top)
                for j, f in enumerate(idx):
                    if top[j]:
                        cflags["bosh_yuqori_chetda"].append(f)
                    if outside[j].any():
                        cflags["anchor_tashqarisida"].append(f)
                    if edge[j]:
                        cflags["yashil_maydon_chetida"].append(f)
                got += len(idx)
                if opts.on_progress:
                    opts.on_progress(done + got, total)
        finally:
            qout.put(None)
            tw.join()
        if werr:
            raise werr[0]
        if got != n:
            raise RuntimeError(f"chunk {k}: kutilgan {n} kadr, dekoddan {got} keldi")
        atomic_write_json(mark, {"frames": n, "flags": cflags})
        for kind, fr in cflags.items():
            flags[kind] += fr
        done += n

    _mux(segments, probe, opts.start, total, out, wd)
    secs = time.time() - t0
    vram = torch.cuda.max_memory_allocated(dev) / 2**20 if dev.type == "cuda" else 0.0
    rep = RenderReport(output=str(out), frames=total, seconds=round(secs, 1), fps=round(total / max(secs, 1e-9), 1),
                       vram_peak_mb=round(vram), warnings=spans_to_warnings(flags))
    atomic_write_json(out.with_suffix(".render.json"), rep.__dict__)
    return rep


def _mux(segments: list[Path], p: ProbeResult, start: int, frames: int, out: Path, wd: Path) -> None:
    """Segmentlar (-c copy) + manba audio (AAC 192k). Audio videoning `start` kadridan boshlab kesiladi:
    -ss fayl boshiga nisbatan, shuning uchun audio va video munosabati manbadagidek (A/V siljish saqlanadi)."""
    lst = wd / "concat.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")
    fps = p.video.fps
    t0 = p.video.start_time - p.format_start_time + Fraction(start) / fps
    dur = Fraction(frames) / fps
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".tmp" + out.suffix)
    args = ["-v", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
    if p.audio:
        args += ["-ss", f"{float(t0):.6f}", "-t", f"{float(dur):.6f}", "-i", p.path,
                 "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    args += ["-c:v", "copy", *BT709_TAGS, "-movflags", "+faststart", str(tmp)]
    ffmpeg.run(args)
    tmp.replace(out)
