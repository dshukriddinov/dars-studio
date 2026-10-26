"""Modellarni models/manifest.json bo'yicha yuklash va sha256 tekshiruvi (TZ 10.2, FR-22).
Tizimda tarmoqqa murojaat qiladigan yagona joy.

    python tools/fetch_models.py            # yo'q yoki hash mos kelmaganlarini yuklaydi
    python tools/fetch_models.py --verify   # faqat tekshiradi, tarmoqsiz
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from darsstudio import paths

REQUIRED = ("name", "version", "file", "source_url", "sha256", "license", "vram_mb", "size_mb")
# TZ 10.2: ruxsat etilgan litsenziyalar (SPDX). AGPL, "non-commercial" va noma'lumlar rad etiladi.
ALLOWED_LICENSES = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "PSF-2.0", "ISC", "MPL-2.0",
                    "LGPL-2.1", "LGPL-3.0", "CC-BY-4.0"}


def load_manifest(path: Path) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["models"]
    for m in models:
        missing = [k for k in REQUIRED if k not in m]
        if missing:
            raise ValueError(f"{m.get('name', '?')}: manifestda maydon yo'q: {', '.join(missing)}")
        if m["license"] not in ALLOWED_LICENSES:
            raise ValueError(f"{m['name']}: litsenziya '{m['license']}' ruxsat etilmagan (TZ 10.2)")
    return models


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def is_valid(m: dict[str, Any], models_dir: Path) -> bool:
    p = models_dir / m["file"]
    return p.is_file() and sha256(p) == m["sha256"].lower()


def fetch(m: dict[str, Any], models_dir: Path) -> None:
    dst = models_dir / m["file"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    urllib.request.urlretrieve(m["source_url"], tmp)
    got = sha256(tmp)
    if got != m["sha256"].lower():
        tmp.unlink()
        raise ValueError(f"{m['name']}: sha256 mos emas ({got})")
    tmp.replace(dst)


def main(argv: list[str]) -> int:
    models_dir = paths.models_dir()
    models = load_manifest(models_dir / "manifest.json")
    bad = 0
    for m in models:
        if is_valid(m, models_dir):
            status = "ok"
        elif "--verify" in argv:
            status, bad = "yo'q yoki buzilgan", bad + 1
        else:
            fetch(m, models_dir)
            status = "yuklandi"
        sys.stdout.write(f"{m['name']} {m['version']}: {status}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
