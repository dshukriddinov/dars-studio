# O'zgarishlar

## [Unreleased]

### B1 — Eye Contact EC-1..EC-5 (2026-10-26)
- `engines/eye-contact` -> `studio-ec` branch (`00db238`): A/V start_time farqi saqlanadi (EC-1, haqiqiy klipdagi
  80 ms xato ham tuzatildi), VFR (EC-2), resume kalitida fayl identifikatori (EC-3), `--patches-out` va
  `eyecontact/patches.py` (EC-4), GPU'siz stub testlari (EC-5).

### B0 — repo skeleti (2026-10-26)
- `darsstudio` paket tuzilmasi (TZ 11), `pyproject.toml` (ruff, mypy strict, pytest belgilari).
- `paths.py`: runtime, ffmpeg, maxine, models, ishchi papka; `DARS_*` muhit o'zgaruvchilari.
- `media/ffmpeg.py`: yagona ffmpeg/ffprobe qatlami (topish, 7.1.1 versiya ogohlantirishi, `run()`).
- `doctor.py`: OS, Python, ffmpeg, GPU, drayver, disk, RAM tekshiruvlari.
- `tools/make_test_media.py`: TZ 13.3 dagi 6 klip + 12 slaydli PPTX; `tests/conftest.py` session fixture.
- `models/manifest.json` sxemasi, `tools/fetch_models.py` (sha256, litsenziya tekshiruvi).
- `engines/eye-contact` submodule (`cfb8288`).
