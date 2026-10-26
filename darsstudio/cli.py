"""Dars Studio buyruq qatori. `python -m darsstudio.cli <buyruq> --help`."""

import argparse
import logging
import sys
from pathlib import Path

from darsstudio import paths
from darsstudio.media.probe import MediaError
from darsstudio.project import importer
from darsstudio.project.store import ProjectStore


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
