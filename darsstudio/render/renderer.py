"""Yakuniy render, bitta o'tish (D-01, FR-16).

dekod (yuv420p, CPU, alohida oqim; TimeMap bo'yicha saqlanadigan oraliqlar) -> ko'z patchi (YUV, rampa bilan)
-> GPU batch: keyer -> rang -> joylashtirish -> kompozit -> lower-third -> yuv420p BT.709 tv -> NVENC (alohida oqim).
Chunk'lar chiqish kadrlarida: cache/render/<kalit>/seg_XXXXX.mp4 + .json checkpoint; oxirida concat -c copy.
Audio: tayyor WAV (kesilgan + loudnorm, chiqish vaqt o'qida) yoki (kesishsiz bo'lsa) manbadan.
"""

import bisect
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
from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import LayoutSpan, Project, SlideSpan
from darsstudio.project.store import atomic_write_json
from darsstudio.render import compositor, eyepatch, overlays
from darsstudio.render.compositor import Compositor, Timeline, over, premult, rgb_to_yuv420
from darsstudio.render.keyer import Keyer
from darsstudio.render.overlays import Overlay
from darsstudio.render.templates import Template

log = logging.getLogger(__name__)

RENDER_VERSION = 3  # render natijasiga ta'sir qiluvchi kod o'zgarsa oshiriladi (checkpoint kaliti)
BT709_TAGS = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
PROFILES = {
    # TZ FR-16
    "web": ["-rc", "vbr", "-b:v", "8M", "-maxrate", "12M", "-bufsize", "16M"],
    "arxiv": ["-rc", "vbr", "-cq", "19", "-b:v", "0", "-maxrate", "16M", "-bufsize", "32M"],
    # Batafsil tahrirdagi "Tayyor video" ekrani uchun (faqat ko'rish, eksport emas)
    "korish": ["-rc", "vbr", "-b:v", "2M", "-maxrate", "4M", "-bufsize", "8M"],
}


SIZE_AUDIO_KBPS = 128      # hajm chegarali eksportda ovoz (nutq uchun yetarli)
SIZE_MARGIN = 0.93         # konteyner, intro/outro va VBR og'ishi uchun zaxira


def size_profile(max_mb: float, seconds: float, main_seconds: float | None = None, reserved_bytes: int = 0) -> str:
    """Butun fayl max_mb dan oshmasin: video bitreyti uzunlikdan hisoblanadi ("size850" = 850 kbit/s).
    main_seconds/reserved_bytes: intro/outro alohida (yuqori sifatda) kodlanadi — ularning baytlari byudjetdan
    ayiriladi, bitreyt faqat asosiy qism uzunligiga bo'linadi. Natija PROFILES ga qo'shiladi."""
    budget_bits = max_mb * 1024 * 1024 * 8 * SIZE_MARGIN - SIZE_AUDIO_KBPS * 1000 * max(seconds, 1.0) \
        - reserved_bytes * 8
    kbps = int(budget_bits / max(main_seconds if main_seconds is not None else seconds, 1.0) / 1000)
    kbps = max(250, min(kbps, 8000))
    name = f"size{kbps}"
    PROFILES[name] = size_args(kbps)
    return name


def audio_kbps(profile: str) -> int:
    return SIZE_AUDIO_KBPS if profile.startswith("size") else 192


def encoder_args(profile: str, preset: str = "p7") -> list[str]:
    if profile.startswith("size") and profile not in PROFILES:   # boshqa jarayonda (render ishchisi) qayta tiklash
        PROFILES[profile] = size_args(int(profile[4:]))
    if ffmpeg.nvenc_ok():
        return ["-c:v", "h264_nvenc", "-preset", preset, "-tune", "hq", "-profile:v", "high", "-g", "50",
                *PROFILES[profile], "-pix_fmt", "yuv420p"]
    if profile.startswith("size"):   # ponytail: NVENC yo'q -> CPU x264, bitreyt bo'yicha
        return ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{profile[4:]}k", "-g", "50", "-pix_fmt", "yuv420p"]
    crf = "19" if profile == "arxiv" else "21"  # ponytail: NVENC yo'q -> CPU x264 (sekin)
    return ["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-g", "50", "-pix_fmt", "yuv420p"]


def size_args(kbps: int) -> list[str]:
    # maxrate 3x: sahna o'tishi (zoom blur) uchun bit qarzga olinadi — 1.5x da 1 s davomida bloklar ko'rinardi
    return ["-rc", "vbr", "-b:v", f"{kbps}k", "-maxrate", f"{kbps * 3}k", "-bufsize", f"{kbps * 4}k",
            "-multipass", "fullres", "-spatial-aq", "1", "-temporal-aq", "1"]


@dataclass
class RenderOptions:
    profile: str = "web"
    preset: str = "p7"
    batch: int = 8
    chunk_sec: int = 60
    start: int = 0                    # chiqish kadri (bo'lak render uchun)
    frames: int | None = None         # chiqish kadrlari soni
    device: str | None = None
    dtype: torch.dtype = torch.float16
    on_progress: Callable[[int, int], None] | None = None


@dataclass
class RenderInputs:
    """Ixtiyoriy kirishlar (B6): kesishlar, ko'z patchlari, tayyor audio, lower-third."""
    timemap: TimeMap | None = None
    eyepatch_dir: Path | None = None
    audio_wav: Path | None = None     # chiqish vaqt o'qidagi WAV (audio.mix.final_audio)
    lower_third: np.ndarray | None = None          # eski API: "default" uslub, fade 0.3 s
    lower_third_s: float = 6.0
    overlays: list[Overlay] = field(default_factory=list)   # chiqish (asosiy qism) kadrlarida
    display: list[tuple[int, int, int]] | None = None        # anim.display_spans (animatsiya qadamlari bilan)


@dataclass
class RenderReport:
    output: str
    frames: int
    seconds: float
    fps: float
    vram_peak_mb: float
    warnings: list[dict[str, Any]] = field(default_factory=list)


class TeacherParts:
    """Video qismlari bo'yicha key va joylashuv (bitta faylli loyihada bitta qism)."""

    def __init__(self, project: Project, w: int, h: int, full_range: bool, dev: torch.device) -> None:
        ps = project.part_settings()
        self.starts = [s for s, _, _ in ps]
        self.keyers = [Keyer(k, w, h, full_range, dev) for _, k, _ in ps]
        self.placements = [pl for _, _, pl in ps]

    def __call__(self, idx: Sequence[int], y: torch.Tensor, u: torch.Tensor, v: torch.Tensor,
                 comp: Compositor) -> tuple[torch.Tensor, torch.Tensor]:
        """-> (kanvasdagi o'qituvchi qatlami, alfa). Batch qism chegarasini kesib o'tsa — bo'lib ishlanadi."""
        part = [bisect.bisect_right(self.starts, f) - 1 for f in idx]
        layers, alphas = [], []
        for q in sorted(set(part)):
            js = [j for j, x in enumerate(part) if x == q]
            sl = slice(js[0], js[-1] + 1)                       # idx o'suvchi — qism kadrlari ketma-ket
            kr = self.keyers[q](y[sl], u[sl], v[sl])
            comp.set_placement(self.placements[q])
            layers.append(comp.teacher_layer(color_correct(kr.rgb, kr.alpha, self.placements[q].color), kr.alpha))
            alphas.append(kr.alpha)
        return torch.cat(layers), torch.cat(alphas)


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
    """Asl kadr raqamlari -> ketma-ket >= min_len kadrli oraliqlar (TZ 9.3 ogohlantirishlari)."""
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
               opts: RenderOptions, probe: ProbeResult, tm: TimeMap, extra: RenderInputs) -> str:
    h = hashlib.sha256()
    ep = ""
    if extra.eyepatch_dir and (extra.eyepatch_dir / "meta.json").is_file():
        ep = json.loads((extra.eyepatch_dir / "meta.json").read_text(encoding="utf-8")).get("cfg_key", "")
    h.update(json.dumps({"v": RENDER_VERSION, "key": project.key.model_dump(mode="json"),
                         "placement": project.placement.model_dump(mode="json"), "tpl": tpl.content_hash(),
                         "parts": [p.model_dump(mode="json") for p in project.parts],
                         "slides": [str(p) + str(p.stat().st_mtime_ns) for p in slide_files],
                         "spans": [[s.model_dump(mode="json") for s in g] for g in spans],
                         "eye_off": [s.model_dump(mode="json") for s in project.eye_off], "eyepatch": ep,
                         "lt": None if extra.lower_third is None else hashlib.md5(extra.lower_third).hexdigest(),
                         "ov": [[hashlib.md5(o.layer).hexdigest(), o.start, o.end, o.fade_frames, o.drift_px_per_frame,
                                 o.slide_in_px, o.slide_frames, o.clip_x]
                                for o in extra.overlays],
                         "tm": tm.ranges, "profile": opts.profile, "preset": opts.preset,
                         # profil nomi bir xil bo'lsa ham sozlamasi o'zgargan bo'lishi mumkin ("size679")
                         "enc": encoder_args(opts.profile, opts.preset), "chunk": opts.chunk_sec,
                         "src": probe.path, "start": opts.start, "sharpen": compositor.TEACHER_SHARPEN,
                         "display": extra.display},
                        sort_keys=True).encode())
    return h.hexdigest()[:16]


def src_ranges(tm: TimeMap, g0: int, n: int) -> list[tuple[int, int]]:
    """Chiqish [g0, g0+n) -> asl kadrlarning uzluksiz oraliqlari."""
    out: list[tuple[int, int]] = []
    for s, e in tm.ranges:
        o = tm.src_to_out(s)
        assert o is not None
        a, b = max(g0, o), min(g0 + n, o + (e - s))
        if a < b:
            out.append((s + a - o, s + b - o))
    return out


def _reader(p: ProbeResult, ranges: list[tuple[int, int]], batch: int, q: "queue.Queue[Any]",
            patches: eyepatch.EyePatches | None, eye_off: Sequence[Any]) -> None:
    try:
        buf, idx = [], []
        for s, e in ranges:
            with FrameReader(p, start=s, count=e - s) as r:
                for i, f in enumerate(r):
                    fi = s + i
                    if patches is not None:
                        rec = patches.get(fi)
                        if rec is not None:
                            eyepatch.apply(f, rec, eyepatch.weight(fi, eye_off))
                    buf.append(f)
                    idx.append(fi)
                    if len(buf) == batch:
                        q.put((idx, np.stack(buf)))
                        buf, idx = [], []
        if buf:
            q.put((idx, np.stack(buf)))
        q.put(None)
    except BaseException as e:
        q.put(e)


def _writer(wr: FrameWriter, q: "queue.Queue[Any]", err: list[BaseException]) -> None:
    try:
        while (item := q.get()) is not None:
            for f in item:
                wr.write(f)
        wr.close()
    except BaseException as e:
        err.append(e)
        while q.get() is not None:
            pass


def render(project: Project, probe: ProbeResult, tpl: Template, warped: list[Path] | dict[int, Path],
           slides_4k: list[Path] | dict[int, Path],
           slide_spans: list[SlideSpan], layout_spans: list[LayoutSpan], out: Path, work_root: Path,
           opts: RenderOptions | None = None, extra: RenderInputs | None = None) -> RenderReport:
    opts = opts or RenderOptions()
    extra = extra or RenderInputs()
    dev = torch.device(opts.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    dtype = opts.dtype if dev.type == "cuda" else torch.float32
    v = probe.video
    w, h, fps = v.width, v.height, v.fps
    tm = extra.timemap or TimeMap([(0, project.total_frames)], fps)
    total = tm.out_total - opts.start if opts.frames is None else min(opts.frames, tm.out_total - opts.start)
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dev)

    parts = TeacherParts(project, w, h, probe.full_range, dev)
    keyer = parts.keyers[0]
    comp = Compositor(tpl, warped, slides_4k, project.placement, (w, h), dev, dtype)
    tl = Timeline.build(slide_spans, layout_spans, tpl, extra.display)
    patches = eyepatch.EyePatches(extra.eyepatch_dir) if extra.eyepatch_dir else None
    ovs = list(extra.overlays)
    if extra.lower_third is not None:
        n_lt = round(Fraction(extra.lower_third_s).limit_denominator(1000) * fps)
        ovs.append(overlays.Overlay(extra.lower_third, 0, n_lt, fade_frames=round(overlays.FADE_S * float(fps))))
    ov_t = [premult(o.layer, dev, dtype) for o in ovs]
    files = sorted(slides_4k.values()) if isinstance(slides_4k, dict) else slides_4k
    key = render_key(project, tpl, files, (slide_spans, layout_spans), opts, probe, tm, extra)
    wd = work_root / key
    wd.mkdir(parents=True, exist_ok=True)
    chunk = max(1, int(opts.chunk_sec * fps))
    nchunks = math.ceil(total / chunk)
    enc = encoder_args(opts.profile, opts.preset)
    cw, ch = tpl.canvas
    ax0, ay0, ax1, ay1 = tpl.teacher_anchor
    top_zone = max(1, int(0.02 * ch))
    gmask = keyer.garbage.float()
    gedge = (torch.nn.functional.max_pool2d(gmask, 9, stride=1, padding=4) - gmask) > 0
    flags: dict[str, list[int]] = {"bosh_yuqori_chetda": [], "anchor_tashqarisida": [], "yashil_maydon_chetida": []}

    t0 = time.time()
    done = 0
    segments = []
    for k in range(nchunks):
        g0 = opts.start + k * chunk
        n = min(chunk, opts.start + total - g0)
        seg = wd / f"seg_{k:05d}.mp4"
        mark = seg.with_suffix(".json")
        segments.append(seg)
        if seg.is_file() and mark.is_file() and json.loads(mark.read_text())["frames"] == n:
            for kind, fr in json.loads(mark.read_text()).get("flags", {}).items():
                flags[kind] += fr
            done += n
            continue
        cflags: dict[str, list[int]] = {kk: [] for kk in flags}
        qin: queue.Queue[Any] = queue.Queue(maxsize=4)
        qout: queue.Queue[Any] = queue.Queue(maxsize=4)
        werr: list[BaseException] = []
        wr = FrameWriter(seg, cw, ch, fps, None, enc, tags=BT709_TAGS)
        threading.Thread(target=_reader, args=(probe, src_ranges(tm, g0, n), opts.batch, qin, patches,
                                               project.eye_off), daemon=True).start()
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
                teacher, kalpha = parts(idx, y, u, vv, comp)
                img = comp.compose(idx, tl, teacher)
                for o, ot in zip(ovs, ov_t, strict=True):
                    for j in range(len(idx)):
                        g = g0 + got + j
                        a = o.alpha_at(g)
                        if a > 0:
                            # roll: qatlam chetlari shaffof (lower-third 16 px/s, mualliflik matni <= 640 px o'ngga)
                            layer = torch.roll(ot, o.shift_at(g), dims=-1) if o.moves() else ot
                            if o.clip_x is not None:
                                layer = layer.clone()
                                layer[..., o.clip_x:] = 0
                            img[j] = over(layer * a, img[j])
                qout.put(rgb_to_yuv420(img).cpu().numpy())
                ta = teacher[:, 3] > 0.5
                top = ta[:, :top_zone].flatten(1).any(1)
                outside = ta.clone()
                outside[:, ay0:ay1, ax0:ax1] = False
                edge = (kalpha[:, 0] > 0.5)[:, gedge[0, 0]].any(1) if gedge.any() else torch.zeros_like(top)
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

    _mux(segments, probe, tm, opts.start, total, out, wd, extra.audio_wav, audio_kbps(opts.profile))
    secs = time.time() - t0
    vram = torch.cuda.max_memory_allocated(dev) / 2**20 if dev.type == "cuda" else 0.0
    rep = RenderReport(output=str(out), frames=total, seconds=round(secs, 1), fps=round(total / max(secs, 1e-9), 1),
                       vram_peak_mb=round(vram), warnings=spans_to_warnings(flags))
    atomic_write_json(out.with_suffix(".render.json"), rep.__dict__)
    return rep


def _mux(segments: list[Path], p: ProbeResult, tm: TimeMap, start: int, frames: int, out: Path, wd: Path,
         audio_wav: Path | None, a_kbps: int = 192) -> None:
    """Segmentlar (-c copy) + audio (AAC 192k).
    audio_wav (chiqish vaqt o'qida) bo'lsa — undan [start, start+frames). Aks holda manbadan: kesishlar yo'q deb
    hisoblanadi, -ss fayl boshiga nisbatan (lab-sync manbadagidek)."""
    lst = wd / "concat.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segments), encoding="utf-8")
    fps = p.video.fps
    dur = Fraction(frames) / fps
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".tmp" + out.suffix)
    args = ["-v", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
    if audio_wav is not None:
        args += ["-ss", f"{float(Fraction(start) / fps):.6f}", "-t", f"{float(dur):.6f}", "-i", str(audio_wav)]
    elif p.audio:
        if len(tm.ranges) > 1:
            raise ValueError("kesishlar bor: audio_wav (audio.mix.final_audio) berilishi kerak")
        src0 = tm.ranges[0][0] if tm.ranges else 0
        t0 = p.video.start_time - p.format_start_time + Fraction(src0 + start) / fps
        args += ["-ss", f"{float(t0):.6f}", "-t", f"{float(dur):.6f}", "-i", p.path]
    if audio_wav is not None or p.audio:
        args += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", f"{a_kbps}k", "-ar", "48000"]
    args += ["-c:v", "copy", *BT709_TAGS, "-movflags", "+faststart", str(tmp)]
    ffmpeg.run(args)
    tmp.replace(out)


PRORES_4444 = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0"]


def render_teacher_layer(project: Project, probe: ProbeResult, tpl: Template, out: Path,
                         eyepatch_dir: Path | None = None, batch: int = 8, device: str | None = None,
                         on_progress: Callable[[int, int], None] | None = None) -> Path:
    """Premiere paketi uchun (FR-18): o'qituvchi qatlami — keyed + Eye Contact + rang, kanvasdagi yakuniy joyida,
    kesilmagan asl vaqt chizig'ida, ProRes 4444 (to'g'ri alfa)."""
    dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    dtype = torch.float16 if dev.type == "cuda" else torch.float32
    v = probe.video
    w, h, fps = v.width, v.height, v.fps
    parts = TeacherParts(project, w, h, probe.full_range, dev)
    comp = Compositor(tpl, [], [], project.placement, (w, h), dev, dtype)
    cw, ch = tpl.canvas
    patches = eyepatch.EyePatches(eyepatch_dir) if eyepatch_dir else None
    total = project.total_frames
    qin: queue.Queue[Any] = queue.Queue(maxsize=4)
    qout: queue.Queue[Any] = queue.Queue(maxsize=4)
    werr: list[BaseException] = []
    tmp = out.with_name(out.stem + ".tmp" + out.suffix)
    wr = FrameWriter(tmp, cw, ch, fps, None, PRORES_4444, pix_fmt="rgba", tags=[],
                     extra_out=["-vf", "scale=out_color_matrix=bt709:out_range=tv", *BT709_TAGS])
    wr.nbytes = cw * ch * 4
    threading.Thread(target=_reader, args=(probe, [(0, total)], batch, qin, patches, project.eye_off),
                     daemon=True).start()
    tw = threading.Thread(target=_writer, args=(wr, qout, werr), daemon=True)
    tw.start()
    done = 0
    try:
        while (item := qin.get()) is not None:
            if isinstance(item, BaseException):
                raise item
            idx, arr = item
            t = torch.from_numpy(arr).to(dev)
            ny = w * h
            layer, _ = parts(idx, t[:, :ny].view(-1, h, w), t[:, ny:ny + ny // 4].view(-1, h // 2, w // 2),
                             t[:, ny + ny // 4:].view(-1, h // 2, w // 2), comp)
            layer = layer.float()
            a = layer[:, 3:4]
            rgb = torch.where(a > 1e-4, layer[:, :3] / a.clamp(min=1e-4), torch.zeros_like(layer[:, :3]))
            rgba = torch.cat([rgb.clamp(0, 1), a], 1).permute(0, 2, 3, 1)
            qout.put((rgba * 255).round().to(torch.uint8).cpu().numpy().reshape(len(idx), -1))
            done += len(idx)
            if on_progress:
                on_progress(done, total)
    finally:
        qout.put(None)
        tw.join()
    if werr:
        raise werr[0]
    tmp.replace(out)
    return out
