"""B2: FR-01 import (CLI orqali ham)."""

import shutil
from pathlib import Path
from typing import Any

import pytest

from darsstudio import cli
from darsstudio.media import probe
from darsstudio.media.probe import MediaError
from darsstudio.project import importer
from darsstudio.project.store import ProjectStore


def test_import_cli(test_media: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["import", test_media["av_offset.mov"]["path"], test_media["lesson.pptx"]["path"],
                   "--template", "demo", "--name", "dars01", "--meta", "fan=Matematika", "--workdir", str(tmp_path)])
    assert rc == 0
    store = ProjectStore(tmp_path / "dars01")
    p = store.load()
    assert p.total_frames == 300 and p.fps == "25/1" and len(p.slides) == 12
    assert [s.title for s in p.slides][:2] == ["Kirish", "Funksiya tushunchasi"]
    assert p.meta == {"fan": "Matematika"}
    v = p.asset("video")
    assert v is not None and v.cfr_path is None and v.id == probe.file_id(test_media["av_offset.mov"]["path"])
    assert (store.cache("media") / "proxy_540p.mp4").is_file()
    for d in ("audio", "asr", "slides", "sync", "eyepatch", "render"):
        assert store.cache(d).is_dir()
    assert "300 kadr" in capsys.readouterr().out

    # takroriy nom -> tushunarli xato, kod 2
    rc = cli.main(["import", test_media["av_offset.mov"]["path"], test_media["lesson.pptx"]["path"],
                   "--name", "dars01", "--workdir", str(tmp_path)])
    assert rc == 2 and "allaqachon bor" in capsys.readouterr().err


def test_import_vfr_makes_cfr(test_media: dict[str, Any], tmp_path: Path) -> None:
    store = importer.import_project(Path(test_media["vfr.mp4"]["path"]), Path(test_media["lesson.pptx"]["path"]),
                                    "demo", tmp_path, make_proxy=False)
    p = store.load()
    v = p.asset("video")
    assert v is not None and v.cfr_path and Path(v.cfr_path).is_file()
    assert p.total_frames == 299


def test_import_rejects(test_media: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(MediaError, match="1920x1080"):
        importer.import_project(Path(test_media["beep.mov"]["path"]), Path(test_media["lesson.pptx"]["path"]),
                                "demo", tmp_path)
    with pytest.raises(MediaError, match="PPTX yoki PDF"):
        importer.import_project(Path(test_media["av_offset.mov"]["path"]), Path(test_media["beep.mov"]["path"]),
                                "demo", tmp_path)
    assert not any(tmp_path.iterdir())  # xatoda loyiha papkasi qolmaydi


def test_find_pairs_and_import_dir(test_media: dict[str, Any], tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    shutil.copy(test_media["av_offset.mov"]["path"], src / "dars05.MOV")
    shutil.copy(test_media["lesson.pptx"]["path"], src / "dars05.pptx")
    shutil.copy(test_media["lesson.pptx"]["path"], src / "yolgiz.pptx")
    assert [(v.name, s.name) for v, s in importer.find_pairs(src)] == [("dars05.MOV", "dars05.pptx")]
    assert cli.main(["import-dir", str(src), "--no-proxy", "--workdir", str(tmp_path / "w")]) == 0
    assert ProjectStore(tmp_path / "w" / "dars05").load().total_frames == 300
