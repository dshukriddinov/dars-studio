"""Hajm chegarali eksport: bitreyt uzunlikdan, butun fayl chegaradan oshmasin."""
from pathlib import Path

from darsstudio.export.qa import check_size
from darsstudio.render import renderer


def test_size_profile_bitrate_fits_limit() -> None:
    prof = renderer.size_profile(100, 16 * 60)
    kbps = int(prof[4:])
    total_mb = (kbps + renderer.SIZE_AUDIO_KBPS) * 1000 * 16 * 60 / 8 / 2**20
    assert prof in renderer.PROFILES and 600 < kbps < 900 and total_mb <= 100 * renderer.SIZE_MARGIN + 0.5
    assert renderer.size_profile(100, 30) == "size8000"            # qisqa — yuqori chegara
    assert renderer.size_profile(10, 3 * 3600) == "size250"         # juda uzun — quyi chegara
    assert renderer.audio_kbps(prof) == 128 and renderer.audio_kbps("web") == 192
    renderer.PROFILES.pop("size777", None)                          # boshqa jarayon: nomdan tiklanadi
    assert "777k" in renderer.encoder_args("size777")


def test_check_size(tmp_path: Path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0" * (3 * 2**20))
    assert check_size(f, 5).status == "ok"
    bad = check_size(f, 2)
    assert bad.status == "ogohlantirish" and "3.0 MB" in bad.detail


def test_size_profile_reserves_bumper_bytes() -> None:
    # intro/outro 6 MB yuqori sifatda: byudjetdan ayiriladi, bitreyt faqat asosiy qismga bo'linadi
    plain = int(renderer.size_profile(100, 16 * 60)[4:])
    with_bump = int(renderer.size_profile(100, 16 * 60 + 10, main_seconds=16 * 60, reserved_bytes=6 * 2**20)[4:])
    assert with_bump < plain and plain - with_bump < 120
    from darsstudio.render.bumpers import bumper_profile
    assert bumper_profile("size679") == "web" and bumper_profile("arxiv") == "arxiv"
