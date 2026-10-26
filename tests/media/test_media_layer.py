"""B2: probe, normalize (VFR->CFR, 48 kHz), FrameReader/Writer (aniq seek, bayt-aniqlik), proxy."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from darsstudio.media import ffmpeg, frames, normalize, probe, proxy
from tools.make_test_media import TIMER_BITS, TIMER_BLOCK

G = "tests/fixtures/generated/"


def framemd5(path: str, vf: str | None = None, pix_fmt: str = "yuv420p") -> list[str]:
    args = ["-v", "error", "-i", path, "-map", "0:v:0", *(["-vf", vf] if vf else []), "-pix_fmt", pix_fmt,
            "-f", "framemd5", "-"]
    out = ffmpeg.run(args).stdout
    return [ln.rsplit(",", 1)[1].strip() for ln in out.splitlines() if ln and not ln.startswith("#")]


@pytest.mark.parametrize("name", ["green_key.mp4", "av_offset.mov", "ntsc_2997.mp4", "vfr.mp4", "beep.mov",
                                  "timer.mp4"])
def test_probe_matches_manifest(test_media: dict[str, Any], name: str) -> None:
    exp = test_media[name]
    p = probe.probe(exp["path"])
    if "fps" in exp:
        assert p.video.fps == Fraction(exp["fps"])
    if "nb_frames" in exp:
        assert p.video.nb_frames == exp["nb_frames"]
    assert p.video.vfr == (name == "vfr.mp4")
    if name == "vfr.mp4":
        assert probe.frame_count(p) == exp["cfr_frames"]
    if name == "av_offset.mov":
        assert p.av_offset == Fraction(52, 1000)
        assert p.full_range and p.video.pix_fmt == "yuvj420p"
    json.dumps(p.to_dict())  # JSON'ga seriyalanadi


def test_validate_messages(test_media: dict[str, Any]) -> None:
    probe.validate(probe.probe(test_media["av_offset.mov"]["path"]))
    with pytest.raises(probe.MediaError, match="ovoz"):
        probe.validate(probe.probe(test_media["green_key.mp4"]["path"]))
    with pytest.raises(probe.MediaError, match="1920x1080"):
        probe.validate(probe.probe(test_media["beep.mov"]["path"]))
    with pytest.raises(probe.MediaError, match="topilmadi"):
        probe.probe("yoq.mp4")
    with pytest.raises(probe.MediaError, match="o'qib bo'lmadi"):
        probe.probe(test_media["lesson.pptx"]["path"])


def test_file_id_changes(tmp_path: Path) -> None:
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 3_000_000)
    a = probe.file_id(f)
    assert a == probe.file_id(f)
    f.write_bytes(b"x" * 2_999_999 + b"y")
    assert probe.file_id(f) != a


def test_normalize_vfr_to_cfr(test_media: dict[str, Any], tmp_path: Path) -> None:
    src = probe.probe(test_media["vfr.mp4"]["path"])
    assert normalize.needs_normalize(src)
    out = normalize.normalize(src, tmp_path / "cfr.mkv")
    assert not out.video.vfr and out.video.nb_frames == 299 == probe.frame_count(src)
    assert abs(out.duration - src.duration) * 25 <= 1
    # Eye Contact EC-2 bilan bir xil to'r: har kadr manbani fps=25 bilan o'qilgan ideal CFR kadri bilan mos
    # (crf 12 lossy, shuning uchun PSNR; noto'g'ri kadr (siljish) testsrc2 harakatida ~20 dB beradi)
    r = ffmpeg.run(["-v", "error", "-i", out.path, "-i", src.path, "-lavfi",
                    "[1:v]fps=25[r];[0:v][r]psnr=stats_file=-", "-f", "null", "-"])
    psnr = [float(ln.split("psnr_avg:")[1].split()[0]) for ln in r.stdout.splitlines() if "psnr_avg:" in ln]
    assert len(psnr) == 299 and min(psnr) > 40, min(psnr)


def test_normalize_resamples_audio(tmp_path: Path) -> None:
    src_path = tmp_path / "a44.mov"
    ffmpeg.run(["-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=25:d=2", "-f", "lavfi", "-i",
                "sine=f=440:r=44100:d=2", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "pcm_s16le", str(src_path)])
    src = probe.probe(src_path)
    assert src.audio and src.audio.sample_rate == 44100 and normalize.needs_normalize(src)
    out = normalize.normalize(src, tmp_path / "n.mkv")
    assert out.audio and out.audio.sample_rate == 48000
    assert framemd5(out.path) == framemd5(str(src_path))  # video copy, o'zgarmagan


def decode_timer(frame: frames.Frame, w: int, h: int) -> int:
    y = frames.planes(frame, w, h)[0]
    bits = [int(y[TIMER_BLOCK // 2, i * TIMER_BLOCK + TIMER_BLOCK // 2] > 128) for i in range(TIMER_BITS)]
    return sum(b << i for i, b in enumerate(bits))


def test_reader_exact_seek_timer(test_media: dict[str, Any]) -> None:
    p = probe.probe(test_media["timer.mp4"]["path"])
    w, h = p.video.width, p.video.height
    with frames.FrameReader(p) as r:
        assert [decode_timer(f, w, h) for f in r] == list(range(250))
    for start in (1, 49, 50, 123, 247):
        with frames.FrameReader(p, start=start, count=3) as r:
            assert [decode_timer(f, w, h) for f in r] == [start, start + 1, start + 2][: 250 - start]


@pytest.mark.parametrize("name", ["av_offset.mov", "ntsc_2997.mp4"])
def test_reader_seek_equals_sequential(test_media: dict[str, Any], name: str) -> None:
    p = probe.probe(test_media[name]["path"])
    with frames.FrameReader(p) as r:
        seq = [hashlib.md5(f).hexdigest() for f in r]
    assert len(seq) == p.video.nb_frames
    for start in (1, 100, 237):
        with frames.FrameReader(p, start=start, count=5) as r:
            assert [hashlib.md5(f).hexdigest() for f in r] == seq[start:start + 5]


def test_writer_lossless_roundtrip_full_range(test_media: dict[str, Any], tmp_path: Path) -> None:
    """yuvj420p (to'liq diapazon) baytlari FFV1 orqali o'zgarishsiz qaytadi: yashirin diapazon konvertatsiyasi yo'q."""
    p = probe.probe(test_media["av_offset.mov"]["path"])
    v = p.video
    with frames.FrameReader(p, count=20) as r:
        src = list(r)
    out = tmp_path / "o.mkv"
    with frames.FrameWriter(out, v.width, v.height, v.fps, p, ["-c:v", "ffv1"], pix_fmt=v.pix_fmt) as wr:
        for f in src:
            wr.write(f)
    q = probe.probe(out)
    assert q.video.color_range == "pc"
    with frames.FrameReader(q) as r:
        back = list(r)
    assert len(back) == 20 and all(np.array_equal(a, b) for a, b in zip(src, back, strict=True))


def test_proxy(test_media: dict[str, Any], tmp_path: Path) -> None:
    p = probe.probe(test_media["av_offset.mov"]["path"])
    out = proxy.make_proxy(p, tmp_path / "proxy.mp4")
    q = probe.probe(out)
    assert (q.video.width, q.video.height) == proxy.PROXY_SIZE
    assert q.video.nb_frames == p.video.nb_frames and q.video.color_range == "tv"
    assert q.audio and q.audio.codec == "aac"
    assert abs(q.av_offset - p.av_offset) <= Fraction(1, 25)
    keys = ffmpeg.run(["-v", "error", "-select_streams", "v:0", "-show_entries", "packet=flags", "-of", "csv=p=0",
                       str(out)], tool="ffprobe").stdout.split()
    kf = [i for i, f in enumerate(keys) if f.startswith("K")]
    assert max(b - a for a, b in zip(kf, kf[1:], strict=False)) <= proxy.GOP
    with open(out, "rb") as f:  # +faststart: moov mdat dan oldin
        head = f.read(1 << 16)
    assert head.find(b"moov") != -1 and (head.find(b"mdat") == -1 or head.find(b"moov") < head.find(b"mdat"))
