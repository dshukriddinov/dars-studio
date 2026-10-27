"""Render oldidan tayyorgarlik: slaydlar (4K + matn), warp, key va joylashtirish (bo'lmasa avtomatik taklif),
qo'lda berilgan slayd vaqtlari (CSV, B3)."""

import csv
import logging
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch

from darsstudio.media.frames import FrameReader, planes
from darsstudio.media.probe import MediaError, ProbeResult, probe
from darsstudio.project.commands import CommandStack
from darsstudio.project.model import LayoutSpan, Project, SlideSpan, TeacherPlacement
from darsstudio.render import keyer, placement
from darsstudio.render.templates import Template
from darsstudio.slides import extract, render, warp

log = logging.getLogger(__name__)


def work_probe(project: Project) -> ProbeResult:
    """Ishchi video: normallashtirilgan nusxa bo'lsa o'sha, aks holda manba."""
    v = project.asset("video")
    if v is None:
        raise MediaError("Loyihada video yo'q.")
    return probe(v.cfr_path or v.path)


def parse_time(s: str) -> Fraction:
    """'75.5', '1:15.5', '0:01:15.5' -> soniya (Fraction)."""
    parts = s.strip().split(":")
    t = Fraction(0)
    for p in parts:
        t = t * 60 + Fraction(p)
    return t


def read_slides_csv(path: Path, fps: Fraction, total: int, n_slides: int) -> tuple[list[SlideSpan], list[LayoutSpan]]:
    """CSV: `start,slide[,layout]` (sarlavha qatori bilan). start — soniya yoki m:ss. Har qator keyingisigacha."""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            start = round(parse_time(r["start"]) * fps)
            slide = int(r["slide"])
            if not 1 <= slide <= n_slides:
                raise MediaError(f"{path.name}: {slide}-slayd yo'q (jami {n_slides}).")
            rows.append((start, slide, (r.get("layout") or "A").strip().upper()))
    rows.sort()
    rows = [r for r in rows if r[0] < total]
    if not rows:
        raise MediaError(f"{path.name}: qatorlar yo'q.")
    if rows[0][0] > 0:
        rows[0] = (0, rows[0][1], rows[0][2])
    ss: list[SlideSpan] = []
    ls: list[LayoutSpan] = []
    for i, (s, slide, lay) in enumerate(rows):
        e = rows[i + 1][0] if i + 1 < len(rows) else total
        if e <= s:
            continue
        ss.append(SlideSpan(start=s, end=e, slide=slide, source="manual", approved=True))
        if ls and ls[-1].layout == lay:
            ls[-1] = ls[-1].model_copy(update={"end": e})
        else:
            ls.append(LayoutSpan(start=s, end=e, layout=lay))  # type: ignore[arg-type,unused-ignore]
    return ss, ls


def ensure_slides(stack: CommandStack) -> list[Path]:
    """4K PNG'lar (kesh) va PPTX matni loyihaga (bir marta)."""
    p = stack.project
    src = p.asset("pptx") or p.asset("pdf")
    if src is None:
        raise MediaError("Loyihada slaydlar yo'q.")
    out = stack.store.cache("slides") / "4k"
    pngs, method = render.render_slides(Path(src.path), out)
    if len(pngs) != len(p.slides):
        raise MediaError(f"Slaydlar soni o'zgargan: loyihada {len(p.slides)}, faylda {len(pngs)}.")
    if src.kind == "pptx":  # matn yo'q yoki PPTX o'zgargan (masalan 1-slayd almashtirilgan) — yangilanadi
        slides, general = extract.extract_pptx(src.path)
        for s, png in zip(slides, pngs, strict=True):
            s.png_4k = str(png)
        key = lambda xs: [(x.title, x.body, x.notes) for x in xs]  # noqa: E731
        if key(slides) != key(p.slides):
            stack.do("slaydlar matni", {"slides": [s.model_dump(mode="json") for s in slides]})
            for g in general:
                log.warning("slaydlar: %s", g)
    log.info("slaydlar: %d ta, usul %s", len(pngs), method)
    return pngs


def ensure_warped(stack: CommandStack, tpl: Template, pngs: list[Path]) -> list[Path]:
    return warp.warp_all(pngs, tpl, stack.store.cache("slides") / "warped")


def read_frame(p: ProbeResult, frame: int) -> np.ndarray:
    with FrameReader(p, start=frame, count=1) as r:
        f = r.read()
    if f is None:
        raise MediaError(f"{frame}-kadrni o'qib bo'lmadi.")
    return f


def calibrated(p: Project) -> bool:
    return p.key.key_cbcr != (0.0, 0.0)


def ensure_key(stack: CommandStack, pr: ProbeResult, frame: int | None = None) -> None:
    if calibrated(stack.project) and frame is None:
        return
    p0 = stack.project.parts[0].frames if stack.project.parts else stack.project.total_frames
    f = frame if frame is not None else p0 // 10   # 1-qism (qolganlari ensure_parts)
    y, u, v = planes(read_frame(pr, f), pr.video.width, pr.video.height)
    ks = keyer.suggest(y, u, v, pr.full_range)
    log.info("key taklifi (%d-kadr): %s", f, ks)
    stack.do(f"key taklifi ({f}-kadr)", {"key": ks.model_dump(mode="json")})


def ensure_parts(stack: CommandStack, pr: ProbeResult, tpl: Template, force: bool = False) -> None:
    """Video qismlari (2-qismdan boshlab): kamera joyi/yorug'lik boshqa bo'lishi mumkin — key va joylashuv qismning
    o'z kadrlaridan (1-qism loyihaning key/joylashuvini ishlatadi)."""
    p = stack.project
    if len(p.parts) < 2 or tpl.teacher_fit is None:
        return
    fps = float(p.fps_frac)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    parts = list(p.parts)
    changed = False
    for i, part in enumerate(parts[1:], 1):
        key, pl = part.key, part.placement
        if key is None or force:
            y, u, v = planes(read_frame(pr, part.start + part.frames // 10), pr.video.width, pr.video.height)
            key = keyer.suggest(y, u, v, pr.full_range)
        if pl is None or force:
            f = tpl.teacher_fit
            win = (part.start / fps, part.frames / fps)
            b = placement.body_landmarks(pr, key, dev, every_sec=max(2.0, min(30.0, win[1] / 10)), window=win)
            pl = placement.fit_body(b, f.head_y, f.head_px, f.shoulder_px, f.center_x, src_h=pr.video.height,
                                    canvas_h=tpl.canvas[1])
            log.info("%d-qism joylashuvi: %s -> %s", i + 1, b, pl)
        if (key, pl) != (part.key, part.placement):
            parts[i] = part.model_copy(update={"key": key, "placement": pl})
            changed = True
    if changed:
        stack.do("qismlar: key va joylashuv", {"parts": [x.model_dump(mode="json") for x in parts]})


def ensure_placement(stack: CommandStack, pr: ProbeResult, tpl: Template, force: bool = False) -> None:
    if stack.project.placement != TeacherPlacement() and not force:
        return
    if tpl.teacher_fit is not None:  # gavda: bosh/kaftlar/markaz shablondagi joyga (montajchi namunasi)
        f = tpl.teacher_fit
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        p0 = stack.project.parts[0] if stack.project.parts else None   # 1-qism kadrlaridan
        win = (0.0, p0.frames / float(stack.project.fps_frac)) if p0 else None
        b = placement.body_landmarks(pr, stack.project.key, dev, window=win)
        pl = placement.fit_body(b, f.head_y, f.head_px, f.shoulder_px, f.center_x, src_h=pr.video.height,
                                canvas_h=tpl.canvas[1])
        if pl.scale > 1.2:
            log.warning("o'qituvchi %.2fx kattalashtirildi (kamera uzoq): tasvir yumshoqroq bo'ladi", pl.scale)
        log.info("joylashtirish (gavda): %s -> %s", b, pl)
        stack.do("o'qituvchi joyi (gavda)", {"placement": pl.model_dump(mode="json")})
        return
    if tpl.teacher_placement is not None:  # kamera qotirilgan studiya: joy shablonda (namunadan o'lchangan)
        fp = tpl.teacher_placement
        stack.do("o'qituvchi joyi (shablon)", {"placement": TeacherPlacement(scale=fp.scale, x=fp.x, y=fp.y)
                                                .model_dump(mode="json")})
        return
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    alphas = placement.sample_alphas(pr, stack.project.key, dev)
    bb = placement.union_bbox(alphas)
    pl = placement.compute(bb, (pr.video.width, pr.video.height), tpl)
    log.info("joylashtirish: bbox %s -> %s (%d namuna)", bb, pl, len(alphas))
    stack.do("o'qituvchi joyi", {"placement": pl.model_dump(mode="json")})
