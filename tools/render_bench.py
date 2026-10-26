"""Render unumdorligi (TZ 13.4, AC-10): kadr/s, VRAM pik (torch + nvidia-smi), CPU yuklamasi.

    python tools/render_bench.py LOYIHA [--start 0:30] [--duration 2:00] [--profile web] [--preset p7]

Loyihada key, joylashtirish va slayd vaqtlari bo'lishi kerak (masalan `darsstudio.cli render` dan keyin).
Natija JSON qatori sifatida chiqadi (QAROR_JURNALI'ga ko'chirish uchun).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from darsstudio.project.store import ProjectStore
from darsstudio.render import prepare, renderer, templates


def gpu_mem_sampler(stop: threading.Event, peak: list[int]) -> None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return
    while not stop.is_set():
        r = subprocess.run([exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True,
                           encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            peak[0] = max(peak[0], int(r.stdout.split()[0]))
        except (ValueError, IndexError):
            pass
        stop.wait(0.5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--start", default="0")
    ap.add_argument("--duration")
    ap.add_argument("--profile", default="web")
    ap.add_argument("--preset", default="p7")
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args()

    p = ProjectStore(Path(a.project)).load()
    if not p.slide_spans:
        print("Loyihada slayd vaqtlari yo'q: avval `darsstudio.cli render --slides-csv ...`", file=sys.stderr)
        return 2
    tpl = templates.load(p.template_id)
    pr = prepare.work_probe(p)
    store = ProjectStore(Path(a.project))
    pngs = sorted((store.cache("slides") / "4k").glob("*.png"))
    from darsstudio.slides import warp
    warped = warp.warp_all(pngs, tpl, store.cache("slides") / "warped")
    fps = p.fps_frac
    start = round(prepare.parse_time(a.start) * fps)
    frames = round(prepare.parse_time(a.duration) * fps) if a.duration else None
    peak = [0]
    stop = threading.Event()
    th = threading.Thread(target=gpu_mem_sampler, args=(stop, peak), daemon=True)
    th.start()
    with tempfile.TemporaryDirectory() as tmp:
        c0, t0 = os.times(), time.time()
        rep = renderer.render(p, pr, tpl, warped, pngs, p.slide_spans, p.layout_spans, Path(tmp) / "bench.mp4",
                              Path(tmp) / "r", renderer.RenderOptions(profile=a.profile, preset=a.preset,
                                                                      batch=a.batch, start=start, frames=frames))
        c1, wall = os.times(), time.time() - t0
    stop.set()
    th.join()
    cpu = (c1.user - c0.user + c1.system - c0.system) / wall  # yadrolar soni ekvivalenti (asosiy jarayon)
    print(json.dumps({"frames": rep.frames, "wall_s": round(wall, 1), "fps": round(rep.frames / wall, 1),
                      "torch_vram_peak_mb": rep.vram_peak_mb, "gpu_mem_used_peak_mb": peak[0],
                      "cpu_cores_main_process": round(cpu, 2), "profile": a.profile, "preset": a.preset,
                      "batch": a.batch}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
