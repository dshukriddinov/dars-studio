"""Asosiy papkalar. Har biri muhit o'zgaruvchisi bilan qayta belgilanadi."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env_path(var: str, default: Path) -> Path:
    v = os.environ.get(var)
    return Path(v).expanduser().resolve() if v else default


def runtime_dir() -> Path:
    return _env_path("DARS_RUNTIME", ROOT / "runtime")


def ffmpeg_dir() -> Path:
    return _env_path("DARS_FFMPEG_DIR", runtime_dir() / "ffmpeg")


def maxine_dir() -> Path:
    """Paketda runtime/maxine; ishlab chiqish muhitida yonidagi "eye contact" loyihasi (ish stoli yorlig'i .bat'siz
    ochganda ham Eye Contact ishlasin)."""
    sibling = ROOT.parent / "eye contact" / "runtime" / "maxine"
    default = runtime_dir() / "maxine"
    return _env_path("DARS_MAXINE_DIR", default if default.is_dir() or not sibling.is_dir() else sibling)


def python_exe() -> Path:
    return runtime_dir() / "python" / ("python.exe" if os.name == "nt" else "bin/python3")


def models_dir() -> Path:
    return _env_path("DARS_MODELS", ROOT / "models")


def workdir() -> Path:
    """Loyihalar saqlanadigan ishchi papka."""
    return _env_path("DARS_WORKDIR", ROOT / "workdir")


def logs_dir() -> Path:
    return _env_path("DARS_LOGS", ROOT / "logs")
