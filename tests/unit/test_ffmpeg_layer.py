from pathlib import Path

import pytest

from darsstudio import doctor, paths
from darsstudio.media import ffmpeg


@pytest.mark.parametrize("banner, expected", [
    ("ffmpeg version 7.1.1-full_build-www.gyan.dev Copyright (c) 2000-2025", "7.1.1"),
    ("ffmpeg version n7.1.1 Copyright", "7.1.1"),
    ("ffmpeg version 6.1.1-3ubuntu5 Copyright", "6.1.1"),
    ("ffprobe version 7.1 Copyright", "7.1"),
    ("ffmpeg version N-118000-gabcdef Copyright", "noma'lum"),
    ("", "noma'lum"),
])
def test_parse_version(banner: str, expected: str) -> None:
    assert ffmpeg.parse_version(banner) == expected


def test_paths_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DARS_RUNTIME", str(tmp_path))
    assert paths.ffmpeg_dir() == tmp_path / "ffmpeg"
    monkeypatch.setenv("DARS_WORKDIR", str(tmp_path / "w"))
    assert paths.workdir() == tmp_path / "w"


def test_doctor_survives_crashing_check(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> doctor.Check:
        raise OSError("disk yo'q")

    ok = doctor.Check("A", "ok", "")
    monkeypatch.setattr(doctor, "CHECKS", [lambda: ok, boom, lambda: [ok, ok]])
    res = doctor.run_all()
    assert [c.status for c in res] == ["ok", "xato", "ok", "ok"]
    assert "disk yo'q" in res[1].detail
