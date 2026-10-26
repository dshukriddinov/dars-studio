"""Portativ paket (NFR-11, B10): papka nusxalanib ishga tushadi, o'rnatish va administrator kerak emas.

    python tools/package.py OUT_DIR [--with-models] [--dry-run]

Tarkib: runtime/python (python-build-standalone 3.11 + kutubxonalar, requirements.lock dagi versiyalar),
runtime/ffmpeg (7.1.1), runtime/maxine, [models], darsstudio, ui/dist, templates, engines/eye-contact, tools,
docs, README.md, DarsStudio.bat, Ish_stoliga_yorliq.bat. Oxirida paket ichidagi Python bilan doctor ishga tushadi.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from darsstudio import paths
from darsstudio.media import ffmpeg

ROOT = paths.ROOT
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".venv", ".pytest_cache", ".mypy_cache",
                                ".ruff_cache", "node_modules", "*.mp4", "*.mov", "*.mkv", "workdir", "_gui_out")
APP_DIRS = ["darsstudio", "templates", "tools", "docs"]
APP_FILES = ["README.md", "CLAUDE.md", "CHANGELOG.md", "pyproject.toml", "requirements.lock", "DarsStudio.bat",
             "driver_pin.txt", "glossary.json"]
SHORTCUT_BAT = r"""@echo off
rem Ish stoliga "Dars Studio" yorlig'i
set TARGET=%~dp0DarsStudio.bat
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Dars Studio.lnk');$s.TargetPath='%TARGET%';$s.WorkingDirectory='%~dp0';$s.Save()"
echo Yorliq yaratildi.
"""


def venv_python_home() -> Path:
    cfg = Path(sys.prefix) / "pyvenv.cfg"
    for line in cfg.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        if k.strip() == "home":
            return Path(v.strip())
    return Path(sys.base_prefix)


def copytree(src: Path, dst: Path, dry: bool) -> None:
    print(f"  {src} -> {dst}", flush=True)
    if not dry:
        shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)


def copyfile(src: Path, dst: Path, dry: bool) -> None:
    print(f"  {src} -> {dst}", flush=True)
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build(out: Path, with_models: bool, dry: bool) -> int:
    rt = out / "runtime"
    print("1/5 Python", flush=True)
    copytree(venv_python_home(), rt / "python", dry)
    site = Path(sys.prefix) / "Lib" / "site-packages"
    copytree(site, rt / "python" / "Lib" / "site-packages", dry)
    if not dry:
        for f in (rt / "python" / "Lib" / "site-packages").glob("__editable__*darsstudio*"):
            f.unlink()
        for f in (rt / "python" / "Lib" / "site-packages").glob("_darsstudio*.pth"):
            f.unlink()
        marker = rt / "python" / "Lib" / "EXTERNALLY-MANAGED"
        if marker.exists():
            marker.unlink()  # Eye Contact tajribasi: aks holda paket ichida pip ishlamaydi
    print("2/5 ffmpeg", flush=True)
    for tool in ("ffmpeg", "ffprobe"):
        copyfile(ffmpeg.find(tool), rt / "ffmpeg" / (tool + ".exe"), dry)
    print("3/5 Maxine", flush=True)
    mx = paths.maxine_dir()
    if (mx / "nvARPose.dll").is_file():
        copytree(mx, rt / "maxine", dry)
    else:
        print("  ogohlantirish: Maxine topilmadi (DARS_MAXINE_DIR) — Eye Contact paketda ishlamaydi", flush=True)
    print("4/5 dastur", flush=True)
    for d in APP_DIRS:
        copytree(ROOT / d, out / d, dry)
    copytree(ROOT / "engines" / "eye-contact", out / "engines" / "eye-contact", dry)
    if (ROOT / "ui" / "dist").is_dir():
        copytree(ROOT / "ui" / "dist", out / "ui" / "dist", dry)
    for f in APP_FILES:
        if (ROOT / f).is_file():
            copyfile(ROOT / f, out / f, dry)
    if not dry:
        (out / "Ish_stoliga_yorliq.bat").write_text(SHORTCUT_BAT, encoding="utf-8")
    print("5/5 modellar", flush=True)
    copyfile(paths.models_dir() / "manifest.json", out / "models" / "manifest.json", dry)
    if with_models:
        for m in json.loads((paths.models_dir() / "manifest.json").read_text(encoding="utf-8"))["models"]:
            for f in m.get("files") or [{"file": m["file"]}]:
                src = paths.models_dir() / f["file"]
                if src.is_file():
                    copyfile(src, out / "models" / f["file"], dry)
    if dry:
        return 0
    py = rt / "python" / "python.exe"
    r = subprocess.run([str(py), "-m", "darsstudio.doctor"], cwd=out, capture_output=True, encoding="utf-8",
                       errors="replace")
    print(r.stdout[-3000:], r.stderr[-2000:], sep="\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--with-models", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return build(Path(a.out).resolve(), a.with_models, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
