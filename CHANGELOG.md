# O'zgarishlar

## [Unreleased]

### Montajchi uslubi (2026-10-26)
- `templates/akademiya`, `tools/make_template.py` (fon joylash, ekran quad'ini avtomatik topish).
- O'tishlar: zoom blur (A<->B), clock wipe (A ichida); o'tish chegaradan oldin tugaydi.
- Sahna qoidasi `scene_policy` (`words` | `a_then_b`); "keyingi slayd" og'zaki signallari.
- Intro/outro (A/V 0 ms), `akademiya` lower-third, mualliflik matni; SRT/jadval/QA intro bilan suriladi.

### B9–B11 — eksport tuzatishlari, barqarorlik, offline, qabul jadvali (2026-10-26)
- TP limiter + lowpass, SRT chegaralari, sinxron oldidan slayd matni; `project.lock` (lost update); `asr_raw`.
- `docs/QABUL.md` — AC-01..AC-15 holati, o'lchov va dalillar.

### B4–B6, B8 — o'lchovlar va tuzatishlar (2026-10-26)
- ASR benchmark (5 model x 3 namuna), vram_probe; tavsiya: rubaistt-v2-medium + sarahai CTC.
- `ui/`: React UI (Tekshirish, Bosh sahifa, Yangi loyiha, Key/Shablon kalibrlash, Eksport, Sozlamalar).

### B7 — API, navbat, rejalashtiruvchi (2026-10-26)
- `jobs/`: resources (FR-20 qoidasi), queue_db (SQLite WAL), scheduler (resurs, bog'liqlik, to'xtatish, resume,
  qayta urinish), tasks (vazifa turlari + resurslar), worker (keep-awake); `power.py`.
- `api/app.py`: FastAPI 127.0.0.1, loyihalar, buyruqlar/undo/redo, proxy/slayd fayllari, shubhali joylar,
  vazifalar, WebSocket progress.
- doctor: drayver pin, torch CUDA, NVENC, Maxine, modellar, PowerPoint/LibreOffice, CPU mikrokod (HW-2).

### B3 — vertikal kesim, birinchi MP4 (2026-10-26)
- `slides/`: `extract.py` (matn, jadval, eslatmalar, animatsiya/media/shrift ogohlantirishlari), `render.py`
  (PowerPoint COM / LibreOffice / pypdfium2, 4K, kesh), `warp.py` (TZ 9.2, supersampling).
- `render/`: `templates.py` (TZ 8.3), `keyer.py` (TZ 9.1, PyTorch), `placement.py` (TZ 9.3), `compositor.py`
  (A/B, crossfade, logo), `renderer.py` (bitta o'tish, NVENC, chunk + checkpoint, A/V sinxron), `prepare.py`.
- `templates/demo` (`tools/make_demo_template.py`), CLI: `render`, `calibrate-key`, `calibrate-screen`.
- `tools/render_bench.py`: 147 kadr/s (1080p25, RTX 5070 Ti).

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
