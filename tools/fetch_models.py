"""Modellarni models/manifest.json bo'yicha yuklash va sha256 tekshiruvi (TZ 10.2, FR-22).
Tizimda tarmoqqa murojaat qiladigan yagona joy.

    python tools/fetch_models.py                 # yo'q yoki hash mos kelmaganlarini yuklaydi
    python tools/fetch_models.py --verify        # faqat tekshiradi, tarmoqsiz
    python tools/fetch_models.py --add-hf REPO REVISION NAME LICENSE KIND
                                                 # HF modelini qotirilgan revision bilan qo'shish (dasturchi uchun)

Manifest yozuvi: name, version, license, kind, vram_mb, size_mb va fayllar. Fayl(lar): bitta `file` + `sha256` +
`source_url`, yoki `files: [{file, sha256, source_url, size_mb}]` (ko'p faylli modellar). `file` — models/ ga nisbatan.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from darsstudio import paths

REQUIRED = ("name", "version", "license", "vram_mb", "size_mb")
FILE_KEYS = ("file", "sha256", "source_url")
# TZ 10.2: ruxsat etilgan litsenziyalar (SPDX). AGPL, "non-commercial" va noma'lumlar rad etiladi.
ALLOWED_LICENSES = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "PSF-2.0", "ISC", "MPL-2.0",
                    "LGPL-2.1", "LGPL-3.0", "CC-BY-4.0"}
SKIP_FILES = {"README.md", ".gitattributes", "training_args.bin"}


def files_of(m: dict[str, Any]) -> list[dict[str, Any]]:
    return list(m["files"]) if "files" in m else [{k: m[k] for k in FILE_KEYS}]


def load_manifest(path: Path) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["models"]
    for m in models:
        missing = [k for k in REQUIRED if k not in m]
        if "files" not in m:
            missing += [k for k in FILE_KEYS if k not in m]
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
    return all((models_dir / f["file"]).is_file() and sha256(models_dir / f["file"]) == f["sha256"].lower()
               for f in files_of(m))


def fetch_file(f: dict[str, Any], models_dir: Path) -> None:
    dst = models_dir / f["file"]
    if dst.is_file() and sha256(dst) == f["sha256"].lower():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    urllib.request.urlretrieve(f["source_url"], tmp)
    got = sha256(tmp)
    if got != f["sha256"].lower():
        tmp.unlink()
        raise ValueError(f"{f['file']}: sha256 mos emas ({got})")
    tmp.replace(dst)


def add_hf(repo: str, revision: str, name: str, license_: str, kind: str, models_dir: Path) -> dict[str, Any]:
    """HF repo'ni qotirilgan revision bilan models/<name>/ ga yuklab, manifestga yozadi."""
    if license_ not in ALLOWED_LICENSES:
        raise ValueError(f"litsenziya '{license_}' ruxsat etilmagan (TZ 10.2)")
    from huggingface_hub import HfApi, hf_hub_download

    info = HfApi().model_info(repo, revision=revision)
    files = []
    for s in info.siblings or []:
        fn = s.rfilename
        if fn in SKIP_FILES or fn.startswith(".") or fn.endswith((".png", ".jpg", ".md")):
            continue
        local = Path(hf_hub_download(repo, fn, revision=revision, local_dir=models_dir / name))
        files.append({"file": f"{name}/{fn}", "sha256": sha256(local),
                      "source_url": f"https://huggingface.co/{repo}/resolve/{revision}/{fn}",
                      "size_mb": round(local.stat().st_size / 2**20, 1)})
    entry = {"name": name, "version": revision, "source": f"hf:{repo}", "license": license_, "kind": kind,
             "vram_mb": None, "size_mb": round(sum(f["size_mb"] for f in files), 1), "files": files}
    mf = models_dir / "manifest.json"
    data = json.loads(mf.read_text(encoding="utf-8"))
    data["models"] = [m for m in data["models"] if m["name"] != name] + [entry]
    mf.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return entry


def main(argv: list[str]) -> int:
    models_dir = paths.models_dir()
    if argv[:1] == ["--add-hf"]:
        repo, rev, name, lic, kind = argv[1:6]
        e = add_hf(repo, rev, name, lic, kind, models_dir)
        sys.stdout.write(f"{name}: {len(e['files'])} fayl, {e['size_mb']} MB\n")
        return 0
    models = load_manifest(models_dir / "manifest.json")
    bad = 0
    for m in models:
        if is_valid(m, models_dir):
            status = "ok"
        elif "--verify" in argv:
            status, bad = "yo'q yoki buzilgan", bad + 1
        else:
            for f in files_of(m):
                fetch_file(f, models_dir)
            status = "yuklandi"
        sys.stdout.write(f"{m['name']} {m['version']}: {status}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
