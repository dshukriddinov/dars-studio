import hashlib
import json
from pathlib import Path

import pytest

from darsstudio import paths
from tools import fetch_models


def _entry(**kw: object) -> dict[str, object]:
    m: dict[str, object] = {"name": "m", "version": "1", "file": "m.bin", "source_url": "https://x/m.bin",
                            "sha256": "0" * 64, "license": "MIT", "vram_mb": 0, "size_mb": 0}
    m.update(kw)
    return m


def _write(tmp_path: Path, *models: dict[str, object]) -> Path:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"schema_version": 1, "models": list(models)}), encoding="utf-8")
    return p


def test_repo_manifest_loads() -> None:
    assert fetch_models.load_manifest(paths.ROOT / "models" / "manifest.json") == []


@pytest.mark.parametrize("lic", ["AGPL-3.0", "CC-BY-NC-4.0", "unknown"])
def test_forbidden_license_rejected(tmp_path: Path, lic: str) -> None:
    with pytest.raises(ValueError, match="ruxsat etilmagan"):
        fetch_models.load_manifest(_write(tmp_path, _entry(license=lic)))


def test_missing_field_rejected(tmp_path: Path) -> None:
    m = _entry()
    del m["sha256"]
    with pytest.raises(ValueError, match="sha256"):
        fetch_models.load_manifest(_write(tmp_path, m))


def test_sha256_check(tmp_path: Path) -> None:
    (tmp_path / "m.bin").write_bytes(b"abc")
    good = hashlib.sha256(b"abc").hexdigest()
    assert fetch_models.is_valid(_entry(sha256=good.upper()), tmp_path)
    assert not fetch_models.is_valid(_entry(), tmp_path)
    assert not fetch_models.is_valid(_entry(file="yoq.bin", sha256=good), tmp_path)
