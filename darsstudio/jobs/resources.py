"""Vazifa resurslari va qabul qoidasi (FR-20, TZ 3.4): Σvram <= 13 000 MB; NVENC <= 2; NVDEC <= 1;
cpu_heavy <= 2; pptx <= 1; exclusive — yolg'iz."""

from collections.abc import Iterable

from pydantic import BaseModel

VRAM_BUDGET_MB = 13_000
LIMITS = {"nvenc": 2, "nvdec": 1, "cpu_heavy": 2, "pptx": 1}


class Resources(BaseModel):
    vram_mb: int = 0
    nvenc: int = 0
    nvdec: int = 0
    cpu_heavy: int = 0
    pptx: int = 0
    exclusive: bool = False


def fits(new: Resources, running: Iterable[Resources]) -> bool:
    run = list(running)
    if new.exclusive:
        return not run
    if any(r.exclusive for r in run):
        return False
    if sum(r.vram_mb for r in run) + new.vram_mb > VRAM_BUDGET_MB:
        return False
    return all(sum(getattr(r, k) for r in run) + getattr(new, k) <= lim for k, lim in LIMITS.items())
