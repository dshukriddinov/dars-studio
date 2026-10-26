"""ASR vazifasi (worker ichida ishlaydi): transkripsiya + CTC bilan so'z vaqtlari. Modellar manifest nomi bilan."""

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from darsstudio import paths


def model_entry(name: str) -> dict[str, Any]:
    data = json.loads((paths.models_dir() / "manifest.json").read_text(encoding="utf-8"))
    for m in data["models"]:
        if m["name"] == name:
            out: dict[str, Any] = m
            return out
    raise KeyError(f"'{name}' modeli manifestda yo'q (tools/fetch_models.py)")


def model_dir(name: str) -> str:
    return str(paths.models_dir() / name)


class GpuMemPeak:
    """nvidia-smi bilan butun GPU band xotirasining pik qiymati (CTranslate2 VRAM'ini torch ko'rmaydi)."""

    def __init__(self) -> None:
        self.base = self.peak = self._read()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    @staticmethod
    def _read() -> int:
        exe = shutil.which("nvidia-smi")
        if not exe:
            return 0
        r = subprocess.run([exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True,
                           encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            return int(r.stdout.split()[0])
        except (ValueError, IndexError):
            return 0

    def _loop(self) -> None:
        while not self._stop.wait(0.25):
            self.peak = max(self.peak, self._read())

    def stop(self) -> int:
        self._stop.set()
        self._t.join()
        return max(0, self.peak - self.base)


def task(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    """args: wav16k, engine (manifest nomi), align (CTC model nomi yoki None), hotwords, out_dir."""
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from darsstudio.asr import word_align
    from darsstudio.asr.engines.base import load_engine
    from darsstudio.asr.engines.ctc import CtcEngine
    from darsstudio.audio.extract import read_pcm

    wav = read_pcm(Path(args["wav16k"]))
    dur = len(wav) / 16000
    mem = GpuMemPeak()
    t0 = time.time()
    ent = model_entry(args["engine"])
    eng = load_engine(ent["kind"], model_dir(args["engine"]), device=args.get("device", "cuda"))
    emit.log(f"model yuklandi: {args['engine']}")
    segs = eng.transcribe(wav, hotwords=args.get("hotwords"), on_progress=lambda x: emit.progress(0.7 * x))
    t_asr = time.time() - t0
    em = eng.last_emissions if isinstance(eng, CtcEngine) else None
    eng.close()
    aligned = 0
    words = [w for s in segs for w in s.words]
    if args.get("align"):
        if em is None or args["align"] != args["engine"]:
            ctc = CtcEngine(model_dir(args["align"]), device=args.get("device", "cuda"))
            em = ctc.emissions(wav, on_progress=lambda x: emit.progress(0.7 + 0.3 * x))
            ctc.close()
        words, aligned = word_align.align(segs, em)
    out = {"engine": args["engine"], "align": args.get("align"), "audio_s": round(dur, 2),
           "asr_s": round(t_asr, 2), "total_s": round(time.time() - t0, 2), "rtf": round(t_asr / max(dur, 1e-9), 4),
           "gpu_mem_peak_mb": mem.stop(), "segments": len(segs), "aligned_segments": aligned, "words": len(words)}
    od = Path(args["out_dir"])
    od.mkdir(parents=True, exist_ok=True)
    (od / "words.json").write_text(json.dumps([w.model_dump() for w in words], ensure_ascii=False), encoding="utf-8")
    (od / "segments.json").write_text(json.dumps(
        [{"start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text} for s in segs], ensure_ascii=False),
        encoding="utf-8")
    (od / "asr_stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def vram_task(args: dict[str, Any], emit: Any) -> dict[str, Any]:
    """vram_probe: modelni yuklab 30 s audio bilan ishlatadi, GPU xotira pikini qaytaradi."""
    import numpy as np

    from darsstudio.asr.engines.base import load_engine
    mem = GpuMemPeak()
    ent = model_entry(args["model"])
    eng = load_engine(ent["kind"], model_dir(args["model"]))
    rng = np.random.default_rng(0)
    eng.transcribe((rng.standard_normal(16000 * 30) * 0.05).astype(np.float32))
    eng.close()
    return {"model": args["model"], "vram_mb": mem.stop()}
