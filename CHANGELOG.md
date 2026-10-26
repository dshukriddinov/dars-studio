# O'zgarishlar

## [Unreleased]

### B2 — media qatlami, TimeMap, loyiha modeli (2026-10-26)
- `media/probe.py` (FR-02, Fraction fps, paket bo'yicha VFR, validatsiya, `file_id`), `media/normalize.py`
  (VFR->CFR, 48 kHz), `media/frames.py` (FrameReader/Writer, aniq seek), `media/proxy.py` (540p, GOP 12).
- `media/timemap.py` (TZ 9.5) + hypothesis property testlari.
- `project/model.py` (TZ 8.2 + invariantlar), `store.py` (atomik), `migrations.py`, `commands.py` (undo/redo diskda).
- FR-01: `project/importer.py`, `python -m darsstudio.cli import|import-dir|info`.

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
