"""Muhit tekshiruvi (FR-21 skeleti). `python -m darsstudio.doctor`."""

import ctypes
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from darsstudio import paths
from darsstudio.media import ffmpeg

Status = Literal["ok", "ogohlantirish", "xato"]

MIN_DRIVER = 570
MIN_RAM_GB = 32
WARN_DISK_GB = 500  # O-03
MIN_DISK_GB = 20


@dataclass
class Check:
    name: str
    status: Status
    detail: str
    fix: str = ""


def check_os() -> Check:
    if sys.platform == "win32":
        build = sys.getwindowsversion().build
        if build >= 22000:
            return Check("OS", "ok", f"Windows 11 (build {build})")
        return Check("OS", "ogohlantirish", f"Windows build {build}", "Windows 11 tavsiya etiladi.")
    return Check("OS", "ogohlantirish", platform.platform(), "Toʻliq ish faqat Windows 11 da; bu yerda faqat testlar.")


def check_python() -> Check:
    v = platform.python_version()
    if sys.version_info[:2] == (3, 11):
        return Check("Python", "ok", v)
    return Check("Python", "ogohlantirish", v, "Python 3.11 ishlating (runtime/python).")


def check_ffmpeg() -> Check:
    try:
        exe = ffmpeg.find("ffmpeg")
        ffmpeg.find("ffprobe")
        v = ffmpeg.version()
    except ffmpeg.FfmpegError as e:
        return Check("ffmpeg", "xato", "topilmadi", str(e))
    if v != ffmpeg.EXPECTED_VERSION:
        return Check("ffmpeg", "ogohlantirish", f"{v} ({exe})", f"ffmpeg {ffmpeg.EXPECTED_VERSION} ni oʻrnating.")
    return Check("ffmpeg", "ok", f"{v} ({exe})")


def _nvidia_smi() -> list[str] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    r = subprocess.run([exe, "--query-gpu=name,driver_version,compute_cap,memory.total",
                        "--format=csv,noheader,nounits"], capture_output=True, encoding="utf-8",
                       errors="replace", stdin=subprocess.DEVNULL,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return [s.strip() for s in r.stdout.splitlines()[0].split(",")]


def check_gpu() -> list[Check]:
    q = _nvidia_smi()
    if q is None:
        fix = "NVIDIA drayverini oʻrnating (nvidia.com/drivers)."
        return [Check("GPU", "xato", "nvidia-smi ishlamadi", fix), Check("Drayver", "xato", "nomaʼlum", fix)]
    name, driver, cap, mem = q
    gpu = Check("GPU", "ok", f"{name}, sm_{cap.replace('.', '')}, {round(float(mem) / 1024)} GB")
    try:
        major = int(driver.split(".")[0])
    except ValueError:
        major = 0
    if major >= MIN_DRIVER:
        drv = Check("Drayver", "ok", driver)
    else:
        drv = Check("Drayver", "xato", driver, f"Drayverni {MIN_DRIVER} yoki yangiroq versiyaga yangilang.")
    return [gpu, drv]


def check_disk() -> Check:
    wd = paths.workdir()
    target = next((p for p in (wd, *wd.parents) if p.exists()), wd.anchor)
    free_gb = shutil.disk_usage(target).free / 1024**3
    detail = f"{free_gb:.0f} GB boʻsh ({wd})"
    if free_gb < MIN_DISK_GB:
        fix = "Ishchi diskda joy boʻshating yoki DARS_WORKDIR ni boshqa diskka oʻtkazing."
        return Check("Disk", "xato", detail, fix)
    if free_gb < WARN_DISK_GB:
        return Check("Disk", "ogohlantirish", detail, f"{WARN_DISK_GB} GB dan koʻp boʻsh joy tavsiya etiladi.")
    return Check("Disk", "ok", detail)


def total_ram_gb() -> float:
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(st)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return float(st.ullTotalPhys) / 1024**3
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3


def check_ram() -> Check:
    gb = total_ram_gb()
    if gb + 1 < MIN_RAM_GB:  # tizim bir oz kamroq koʻrsatadi
        return Check("RAM", "ogohlantirish", f"{gb:.0f} GB", f"Kamida {MIN_RAM_GB} GB RAM tavsiya etiladi.")
    return Check("RAM", "ok", f"{gb:.0f} GB")


CHECKS: list[Callable[[], Check | list[Check]]] = [
    check_os, check_python, check_ffmpeg, check_gpu, check_disk, check_ram,
]


def run_all() -> list[Check]:
    out: list[Check] = []
    for fn in CHECKS:
        try:
            r = fn()
        except Exception as e:  # bitta tekshiruv yiqilsa qolganlari ishlasin
            r = Check(fn.__name__.removeprefix("check_"), "xato", f"tekshiruv yiqildi: {e}")
        out += r if isinstance(r, list) else [r]
    return out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    checks = run_all()
    w = max(len(c.name) for c in checks)
    for c in checks:
        line = f"{c.name:<{w}}  {c.status:<13}  {c.detail}"
        if c.fix:
            line += f"\n{'':<{w}}  {'':<13}  -> {c.fix}"
        print(line)
    return 1 if any(c.status == "xato" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
