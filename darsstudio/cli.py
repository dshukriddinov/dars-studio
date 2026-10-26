"""Dars Studio buyruq qatori. `python -m darsstudio.cli <buyruq> --help`."""

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from darsstudio import paths
from darsstudio.media.probe import MediaError
from darsstudio.project import importer
from darsstudio.project.store import ProjectStore

if TYPE_CHECKING:
    from darsstudio.project.commands import CommandStack


def _meta(items: list[str]) -> dict[str, str]:
    out = {}
    for it in items:
        k, sep, v = it.partition("=")
        if not sep:
            raise MediaError(f"--meta '{it}': kalit=qiymat ko'rinishida bering (masalan fan=Matematika).")
        out[k.strip()] = v.strip()
    return out


def cmd_import(a: argparse.Namespace) -> int:
    store = importer.import_project(Path(a.video), Path(a.slides), a.template, Path(a.workdir), name=a.name,
                                    meta=_meta(a.meta), slide_log=Path(a.slide_log) if a.slide_log else None,
                                    copy=a.copy, make_proxy=not a.no_proxy,
                                    on_step=lambda s: print(f"... {s}", file=sys.stderr))
    p = store.load()
    print(f"Loyiha yaratildi: {store.root}\n  {p.total_frames} kadr @ {p.fps} fps, {len(p.slides)} slayd")
    return 0


def cmd_import_dir(a: argparse.Namespace) -> int:
    pairs = importer.find_pairs(Path(a.folder))
    if not pairs:
        raise MediaError(f"{a.folder} da juftlik topilmadi (masalan dars05.mov + dars05.pptx).")
    failed = 0
    for video, slides in pairs:
        try:
            store = importer.import_project(video, slides, a.template, Path(a.workdir), make_proxy=not a.no_proxy)
            print(f"ok    {video.name} -> {store.root}")
        except MediaError as e:
            failed += 1
            print(f"xato  {video.name}: {e}")
    return 1 if failed else 0


def cmd_info(a: argparse.Namespace) -> int:
    p = ProjectStore(Path(a.project)).load()
    print(f"{p.name} ({p.id}): {p.total_frames} kadr @ {p.fps} fps, {len(p.slides)} slayd, shablon {p.template_id}")
    for asset in p.assets:
        print(f"  {asset.kind:<9} {asset.path}" + (f"  (CFR: {asset.cfr_path})" if asset.cfr_path else ""))
    return 0


def _stack(project: str) -> "CommandStack":
    from darsstudio.project.commands import CommandStack
    return CommandStack(ProjectStore(Path(project)))


def cmd_render(a: argparse.Namespace) -> int:
    from darsstudio.render import prepare, renderer, templates
    st = _stack(a.project)
    p = st.project
    tpl = templates.load(a.template or p.template_id)
    pr = prepare.work_probe(p)
    pngs = prepare.ensure_slides(st)
    warped = prepare.ensure_warped(st, tpl, pngs)
    prepare.ensure_key(st, pr)
    prepare.ensure_placement(st, pr, tpl)
    if a.slides_csv:
        ss, ls = prepare.read_slides_csv(Path(a.slides_csv), p.fps_frac, p.total_frames, len(p.slides))
        st.do("slayd vaqtlari (CSV)", {"slide_spans": [s.model_dump(mode="json") for s in ss],
                                       "layout_spans": [s.model_dump(mode="json") for s in ls]})
    p = st.project
    if not p.slide_spans:
        raise MediaError("Slayd vaqtlari yo'q: --slides-csv bering.")
    fps = p.fps_frac
    start = round(prepare.parse_time(a.start) * fps) if a.start else 0
    frames = round(prepare.parse_time(a.duration) * fps) if a.duration else None
    out = Path(a.out)

    def progress(d: int, t: int) -> None:
        print(f"\r{d}/{t} kadr ({100 * d // max(t, 1)}%)", end="", file=sys.stderr, flush=True)

    opts = renderer.RenderOptions(profile=a.profile, preset=a.preset, chunk_sec=a.chunk_sec, start=start,
                                  frames=frames, on_progress=progress)
    rep = renderer.render(p, pr, tpl, warped, pngs, p.slide_spans, p.layout_spans, out,
                          st.store.cache("render"), opts)
    print(f"\nTayyor: {out}\n  {rep.frames} kadr, {rep.seconds} s ({rep.fps} kadr/s), "
          f"VRAM pik {rep.vram_peak_mb} MB, ogohlantirishlar {len(rep.warnings)}")
    return 0


def cmd_calibrate_key(a: argparse.Namespace) -> int:
    import cv2
    import numpy as np
    import torch

    from darsstudio.media.frames import planes
    from darsstudio.render import prepare
    from darsstudio.render.keyer import Keyer, to_rgb, ycbcr
    st = _stack(a.project)
    pr = prepare.work_probe(st.project)
    prepare.ensure_key(st, pr, frame=a.frame)
    w, h = pr.video.width, pr.video.height
    y, u, v = planes(prepare.read_frame(pr, a.frame), w, h)
    t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).unsqueeze(0)  # noqa: E731
    res = Keyer(st.project.key, w, h, pr.full_range, torch.device("cpu"))(t(y), t(u), t(v))
    before = to_rgb(*ycbcr(t(y), t(u), t(v), pr.full_range))[0].permute(1, 2, 0).numpy()
    checker = ((np.indices((h, w)).sum(0) // 32) % 2 * 0.35 + 0.35)[..., None].repeat(3, 2)
    a_ = res.alpha[0].permute(1, 2, 0).numpy()
    after = res.rgb[0].permute(1, 2, 0).numpy() + checker * (1 - a_)
    out = st.store.cache("render") / "calib"
    out.mkdir(parents=True, exist_ok=True)
    for name, img in (("oldin", before), ("keyin", after), ("matte", a_.repeat(3, 2))):
        cv2.imwrite(str(out / f"key_{a.frame}_{name}.png"), (np.clip(img, 0, 1) * 255).astype(np.uint8)[..., ::-1])
    print(f"Key: {st.project.key.model_dump()}\nRasmlar: {out}")
    return 0


def cmd_calibrate_screen(a: argparse.Namespace) -> int:
    import json as _json

    from darsstudio.render import templates
    tpl = templates.load(a.template)
    pts = _json.loads(Path(a.points).read_text(encoding="utf-8") if Path(a.points).is_file() else a.points)
    if len(pts) != 4:
        raise MediaError("4 ta nuqta kerak: TL, TR, BR, BL.")
    tpl = tpl.model_copy(update={"screen_quad": tuple(tuple(map(float, p)) for p in pts)})
    templates.save(tpl)
    print(f"{a.template}: screen_quad = {pts}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="darsstudio")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("import", help="video + slaydlardan yangi loyiha (FR-01)")
    s.add_argument("video")
    s.add_argument("slides", help="PPTX yoki PDF")
    s.add_argument("--template", default="demo")
    s.add_argument("--name")
    s.add_argument("--meta", action="append", default=[], metavar="KALIT=QIYMAT")
    s.add_argument("--slide-log", help="slide_logger CSV (FR-07)")
    s.add_argument("--copy", action="store_true", help="manba fayllarni loyiha papkasiga nusxalash")
    s.add_argument("--no-proxy", action="store_true")
    s.add_argument("--workdir", default=str(paths.workdir()))
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("import-dir", help="papkadagi barcha juftliklar (dars05.mov + dars05.pptx)")
    s.add_argument("folder")
    s.add_argument("--template", default="demo")
    s.add_argument("--no-proxy", action="store_true")
    s.add_argument("--workdir", default=str(paths.workdir()))
    s.set_defaults(fn=cmd_import_dir)

    s = sub.add_parser("info", help="loyiha haqida qisqa ma'lumot")
    s.add_argument("project")
    s.set_defaults(fn=cmd_info)
    s = sub.add_parser("render", help="yakuniy MP4 (B3: slayd vaqtlari CSV'dan)")
    s.add_argument("project")
    s.add_argument("--slides-csv", help="start,slide[,layout] (soniya yoki m:ss)")
    s.add_argument("--out", required=True)
    s.add_argument("--template")
    s.add_argument("--profile", choices=("web", "arxiv"), default="web")
    s.add_argument("--preset", default="p7", help="NVENC preset p1..p7")
    s.add_argument("--chunk-sec", type=int, default=60)
    s.add_argument("--start", help="bo'lak boshi (soniya yoki m:ss)")
    s.add_argument("--duration", help="bo'lak uzunligi (soniya yoki m:ss)")
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("calibrate-key", help="kadrdan key rangi va garbage taklifi + oldin/keyin PNG")
    s.add_argument("project")
    s.add_argument("--frame", type=int, required=True)
    s.set_defaults(fn=cmd_calibrate_key)

    s = sub.add_parser("calibrate-screen", help="shablon ekran to'rtburchagi (4 nuqta JSON)")
    s.add_argument("--template", required=True)
    s.add_argument("--points", required=True, help="JSON fayl yoki '[[x,y],[x,y],[x,y],[x,y]]'")
    s.set_defaults(fn=cmd_calibrate_screen)
    return ap


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    a = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        rc: int = a.fn(a)
        return rc
    except (MediaError, FileNotFoundError) as e:
        print(f"xato: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
