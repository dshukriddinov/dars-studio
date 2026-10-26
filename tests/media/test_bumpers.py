"""Intro/outro: boshqa o'lcham/fps/balandlikdagi klip loyiha formatiga keltiriladi, concat qayta kodlashsiz;
davomiylik = intro + asosiy + outro, A/V boshlanishi bir xil, rang teglari BT.709 limited."""

from fractions import Fraction
from pathlib import Path

import pytest

from darsstudio.media import ffmpeg, probe
from darsstudio.render import bumpers
from darsstudio.render.renderer import BT709_TAGS, encoder_args
from darsstudio.render.templates import Template

pytestmark = pytest.mark.media
FPS = Fraction(25)


def test_wrap_intro_outro(tmp_path: Path) -> None:
    main = tmp_path / "main.mp4"
    ffmpeg.run(["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=2", "-f", "lavfi",
                "-i", "sine=f=440:r=48000:d=2", *encoder_args("web"), *BT709_TAGS, "-c:a", "aac", "-shortest",
                str(main)])
    ffmpeg.run(["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=640x480:r=30:d=1.5", "-f", "lavfi",
                "-i", "sine=f=880:r=44100:d=1.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", str(tmp_path / "intro.mp4")])
    tpl = Template(id="t", canvas=(320, 180), background="bg.png", screen_quad=((0, 0), (1, 0), (1, 1), (0, 1)),
                   teacher_anchor=(0, 0, 10, 10), intro="intro.mp4", outro="intro.mp4", dir=str(tmp_path))
    cache = tmp_path / "cache"
    cache.mkdir()
    lead, tail = bumpers.wrap(main, tpl, FPS, "web", cache)
    assert (lead, tail) == (37, 37)
    q = probe.probe(main)
    assert q.video.width == 320 and q.video.fps == FPS and q.audio is not None
    assert abs(float(q.duration * FPS) - (37 + 50 + 37)) <= 1
    assert q.video.start_time == q.audio.start_time == 0
    assert abs(float(q.duration - Fraction(124, 25))) < 0.03          # audio = video
    assert q.video.color_range == "tv" and q.video.color_space == "bt709"
    assert not (tmp_path / "main.body.mp4").exists()
