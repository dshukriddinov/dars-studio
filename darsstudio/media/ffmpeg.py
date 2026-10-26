"""Yagona ffmpeg/ffprobe qatlami. Tizimda ffmpeg faqat shu modul orqali chaqiriladi (CLAUDE.md, 2-qoida)."""

import functools
import glob
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from darsstudio import paths

log = logging.getLogger(__name__)

EXPECTED_VERSION = "7.1.1"  # D-13
Tool = Literal["ffmpeg", "ffprobe"]

# Windows'da konsol oynasi ochilmasin
_CREATIONFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_EXE = ".exe" if os.name == "nt" else ""


class FfmpegError(RuntimeError):
    pass


def _candidates(tool: Tool) -> list[Path]:
    out = [paths.ffmpeg_dir() / (tool + _EXE)]
    if w := shutil.which(tool):
        out.append(Path(w))
    if os.name == "nt":
        pat = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")
        out += [Path(d) / (tool + _EXE) for d in sorted(glob.glob(pat), reverse=True)]
    return out


@functools.cache
def find(tool: Tool) -> Path:
    """Avval runtime/ffmpeg, keyin PATH, keyin winget papkasi."""
    for p in _candidates(tool):
        if p.is_file():
            v = _version_of(p)
            if v != EXPECTED_VERSION:
                log.warning("%s versiyasi %s, kutilgan %s: %s", tool, v, EXPECTED_VERSION, p)
            return p
    raise FfmpegError(f"{tool} topilmadi: runtime/ffmpeg papkasiga ffmpeg {EXPECTED_VERSION} ni joylang.")


def parse_version(banner: str) -> str:
    """'ffmpeg version 7.1.1-full_build-www.gyan.dev ...' -> '7.1.1'. Topilmasa "noma'lum"."""
    m = re.search(r"version n?(\d+(?:\.\d+){1,2})", banner)
    return m.group(1) if m else "noma'lum"


def _version_of(exe: Path) -> str:
    r = subprocess.run([str(exe), "-version"], capture_output=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, creationflags=_CREATIONFLAGS)
    return parse_version(r.stdout or "")


def version(tool: Tool = "ffmpeg") -> str:
    return _version_of(find(tool))


def run(args: Sequence[str], tool: Tool = "ffmpeg", check: bool = True,
        timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    """ffmpeg/ffprobe ni ishga tushiradi, stdout/stderr matn (UTF-8) sifatida qaytadi."""
    cmd = [str(find(tool)), *args]
    log.debug("run: %s", cmd)
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, creationflags=_CREATIONFLAGS, timeout=timeout)
    if check and r.returncode != 0:
        tail = (r.stderr or "").strip()[-800:]
        raise FfmpegError(f"{tool} xato bilan tugadi (kod {r.returncode}): {tail}")
    return r


def popen(args: Sequence[str], tool: Tool = "ffmpeg", *, stdin: bool = False,
          stdout: bool = False, bufsize: int = -1) -> "subprocess.Popen[bytes]":
    """rawvideo pipe'lar uchun. stderr faylga emas, PIPE'ga: xato bo'lsa chaqiruvchi o'qiydi."""
    cmd = [str(find(tool)), *args]
    log.debug("popen: %s", cmd)
    return subprocess.Popen(cmd, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                            stdout=subprocess.PIPE if stdout else subprocess.DEVNULL, stderr=subprocess.PIPE,
                            creationflags=_CREATIONFLAGS, bufsize=bufsize)


@functools.cache
def nvenc_ok(encoder: str = "h264_nvenc") -> bool:
    """NVENC shu drayver bilan ishlaydimi (1 kadr sinov). Natija jarayon davomida keshlanadi."""
    r = run(["-v", "error", "-nostdin", "-f", "lavfi", "-i", "color=c=gray:s=256x256:r=25:d=0.04",
             "-c:v", encoder, "-f", "null", "-"], check=False)
    return r.returncode == 0
