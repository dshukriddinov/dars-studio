"""Har ASR modeli uchun GPU xotira pikini o'lchab models/manifest.json dagi `vram_mb` ga yozadi (TZ 3.4, FR-20).

    python tools/vram_probe.py [NOM ...]      # nom berilmasa manifestdagi barcha asr-* modellar

Har model alohida jarayonda (worker): 30 s shovqin bilan yuklab ishlatiladi, nvidia-smi bo'yicha pik - boshlang'ich.
"""

import json
import sys

from darsstudio import paths
from darsstudio.jobs.worker import run_isolated


def main(names: list[str]) -> int:
    mf = paths.models_dir() / "manifest.json"
    data = json.loads(mf.read_text(encoding="utf-8"))
    for m in data["models"]:
        if (names and m["name"] not in names) or not str(m.get("kind", "")).startswith("asr-"):
            continue
        r = run_isolated("vram_probe", {"model": m["name"]})
        m["vram_mb"] = r["vram_mb"]
        print(f"{m['name']}: {r['vram_mb']} MB", flush=True)
    mf.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
