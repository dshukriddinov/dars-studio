"""FR-03: PowerPoint COM bilan 4K render (Windows + PowerPoint kerak)."""

import sys
from pathlib import Path
from typing import Any

import pytest

from darsstudio.slides import render, warp

pytestmark = pytest.mark.skipif(sys.platform != "win32" or not render.powerpoint_available(),
                                reason="PowerPoint yo'q")


def test_render_pptx_com(test_media: dict[str, Any], tmp_path: Path) -> None:
    pngs, method = render.render_slides(Path(test_media["lesson.pptx"]["path"]), tmp_path / "4k")
    assert method == "powerpoint" and len(pngs) == 12
    img = warp.read_rgb(pngs[0])
    assert img.shape == (2160, 3840, 3) and img.std() > 5   # bo'sh emas
    again, _ = render.render_slides(Path(test_media["lesson.pptx"]["path"]), tmp_path / "4k")  # kesh
    assert [p.stat().st_mtime_ns for p in again] == [p.stat().st_mtime_ns for p in pngs]
