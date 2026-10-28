"""Premiere/DaVinci paketi (FR-18, D-11): qatlamlar 1920x1080 kanvasda oldindan joylashtirilgan, XML faqat kesishlar."""

import shutil
from collections.abc import Callable
from pathlib import Path

from darsstudio.export import fcp7xml
from darsstudio.media.probe import ProbeResult
from darsstudio.media.timemap import TimeMap
from darsstudio.project.model import Project
from darsstudio.render import renderer
from darsstudio.render.templates import Template
from darsstudio.slides import warp


def build(p: Project, tm: TimeMap, tpl: Template, pngs: list[Path], warped: list[Path], denoised_wav: Path,
          probe: ProbeResult, pkg: Path, name: str, eyepatch_dir: Path | None = None,
          teacher: bool = True, on_progress: Callable[[int, int], None] | None = None,
          display: list[tuple[int, int, str]] | None = None) -> Path:
    """pngs/warped — yakuniy slaydlar va animatsiya qadamlari (NNN_k.png) birga; display — fcp7xml.build."""
    pkg.mkdir(parents=True, exist_ok=True)
    cw, ch = tpl.canvas
    import cv2
    bg = warp.fit_contain(warp.read_rgb(tpl.asset(tpl.background)), cw, ch)
    cv2.imwrite(str(pkg / "background.png"), bg[..., ::-1])
    (pkg / "slides_warped").mkdir(exist_ok=True)
    (pkg / "slides_full").mkdir(exist_ok=True)
    box = warp.hex_rgb(tpl.fullscreen.pillarbox_color)
    for src, wp in zip(pngs, warped, strict=True):
        shutil.copy2(wp, pkg / "slides_warped" / wp.name)
        full = warp.fit_contain(warp.read_rgb(src), cw, ch, box)
        ok, buf = cv2.imencode(".png", full[..., ::-1])
        buf.tofile(str(pkg / "slides_full" / src.name))
    shutil.copy2(denoised_wav, pkg / "audio.wav")
    if teacher:
        renderer.render_teacher_layer(p, probe, tpl, pkg / "teacher.mov", eyepatch_dir, on_progress=on_progress)
    xml = pkg / "sequence.xml"
    fcp7xml.write(fcp7xml.build(p, tm, pkg, name, display), xml)
    return xml
