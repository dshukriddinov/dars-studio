# Qarorlar jurnali

Har yozuv: sana, bosqich, qaror yoki o'lchov, sabab, dalil (commit, fayl, buyruq). Yangi yozuvlar yuqoriga.

---

## 2026-10-26 — B1, Eye Contact EC-1..EC-5

**Joy:** `engines/eye-contact`, branch `studio-ec` (`cfb8288` dan 8 commit, oxirgisi `00db238`). Remote'ga push
qilinmagan, PR ochilmagan.

**Natijalar (Windows 11, ffmpeg 7.1.1, drayver 610.88, Maxine `D:\projects\eye contact\runtime\maxine`):**
- GPU'siz `pytest tests/test_pipeline_stub.py`: 11 passed (stub, sintetik media). Linux'da ishga tushirilmagan.
- `tests/test_smoke.py` (GPU): OK, 250 kadr, mask_leak 0, audio teng, 54 kadr/s. `tests/test_gui.py`: OK.
- EC-1: 52 ms siljishli MOV -> chiqishda 52.00 ms (FFV1) / 52.03 ms (H.264 MOV). **Topilma:** `cfb8288` haqiqiy
  `clip_10s` (Canon: video va audio 0.08 s, data stream 0 s) da ham chiqishda video 0.00, audio 0.08 beradi — ovoz
  80 ms kech. Sabab: ffmpeg audioni fayl `start_time` ga nisbatan siljitadi. Tuzatildi: video `-itsoffset` =
  video start − format start. Endi ikkalasi 0.08.
- EC-2: VFR (294 paket, 11.96 s) -> 299 kadr, chunk 4 s va 3.96 s (chunk tushgan kadrdan boshlanadi) da ideal CFR
  bilan framemd5 teng. Usul: `-copyts` + `fps` filtri + `trim=start_pts` (`-fps_mode cfr` o'rniga).
- EC-3: resume kaliti + fayl identifikatori (hajm, mtime_ns, bosh/oxir 1 MB xxhash64). Yangi bog'liqlik `xxhash`
  (BSD-2-Clause). Ishlab turgan portativ paketga `pip install xxhash` kerak bo'ladi.
- EC-4: `--patches-out` + `eyecontact/patches.py`. Stub bilan: patch qo'llangan kadrlar oddiy lossless chiqish bilan
  Y va UV bo'yicha bayt-aniq (360 kadr). Haqiqiy klipda patch va alohida oddiy ishga tushirish: Y max farq 1,
  45 piksel / 250 kadr. Hajm 384 KB / 10 s (25 min ≈ 56 MB, TZ taxmini 100–300 MB).
- Eski xatti-harakat: yangi va `cfb8288` lossless chiqishi max farq 2 (844 bayt / 250 kadr); `cfb8288` ning o'zi
  ikki marta ishga tushirilganda max 3 (871 bayt). Ya'ni farq Maxine'ning noaniqligi darajasida.
  **TZ "±1 piksel" mezoni amalda ±3** — Maxine run-to-run bit-aniq emas.

**Ochiq:** PR ochish (push ruxsati), Linux'da stub testlari, `D:\projects\eye contact` ishchi paketini yangilash.

---

## 2026-10-26 — B0, repo skeleti

**Muhit (o'lchangan, `python -m darsstudio.doctor`):** Windows 11 build 26200, Python 3.11.16 (uv venv, dasturchi
muhiti; `runtime/python` hali yo'q), ffmpeg 7.1.1 gyan.dev (winget, PATH orqali; `runtime/ffmpeg` hali yo'q),
RTX 5070 Ti sm_120 16 303 MiB, **drayver 610.88** (Eye Contact sinovidagi 591.86 dan yangilangan — HW-4 pin
versiyasi shu bo'yicha aniqlanishi kerak), RAM 64 GB, D: diskda 2 750 GB bo'sh.

**Qarorlar:**
- Sintetik media to'plami (TZ 13.3) ~5 s da yaratiladi, `tests/fixtures/generated/` (gitignore), `VERSION` o'zgarsa
  qayta yaratiladi. A/V siljish klipi: `-itsoffset` lavfi kirishda 1/25 ga yaxlitlanib 40 ms beradi, shuning uchun
  1/25000 time base'da butun son siljish (`setpts=PTS+1300`), `-copyts`, encoder/trek/movie timescale 25000.
  Natija: video `start_time` 0.052000, audio 0.000000 (ffprobe).
- Testlar papka bo'yicha avtomatik belgilanadi (`tests/unit` -> `unit` va h.k., `conftest.py`).
- `logging_setup.py` (NFR-09 JSON-lines) hali yozilmadi — B7 da worker jurnali bilan birga. Hozircha `logging.getLogger`.
- `doctor` B0 tekshiruvlari: OS, Python, ffmpeg (7.1.1), GPU, drayver >= 570, disk (< 20 GB xato, < 500 GB
  ogohlantirish), RAM (< 32 GB ogohlantirish). Mikrokod (HW-2), pin drayver (HW-4), NVENC, torch, Maxine — B7.
- `engines/eye-contact` submodule `cfb8288` da.

**Tekshirilmagan:** DoD'dagi Linux'da `pytest -m "unit or media"` — bu mashinada Linux yo'q (WSL/CI'da tekshirilsin).

---

## 2026-10-24 — TZ v2.0, boshlang'ich qarorlar

**Qarorlar:** D-01..D-13 (TZ 2-bo'lim). Asosiylari: bitta o'tishli render, Eye Contact patch fayli, asl kadr indeksi
vaqtning yagona manbai, har GPU vazifa alohida jarayonda, slayd sinxroni ikki rejimli, ASR benchmark bilan tanlanadi.

**Apparat (aniqlangan):** i7-14700K, 64 GB DDR5, RTX 5070 Ti 16 GB (2 × NVENC, 1 × NVDEC, sm_120), Windows 11 Pro,
drayver 591.86. BIOS 04.12.2023 — yangilanishi kerak (HW-1).

**Eye Contact moduli (commit `cfb8288`) bo'yicha mavjud o'lchovlar** (modul TZ'si v2.0 dan):
1080p25 da 62–70 kadr/s, VRAM 0.9 GB, RAM pik 1.7 GB, identity median 0.993, EAR farqi 10.9%, blink 1.01,
flicker 1.01, VMAF 97.8. Faqat bitta videoda (13 min, ko'zoynakli, 1080p25) baholangan.

**Eye Contact sinovi (2026-10-24, Linux, ffmpeg 6.1.1, Maxine o'rniga identity stub, sintetik media):**

| Holat | Natija |
|---|---|
| MOV 25 fps PCM, video audiodan 52 ms keyin boshlanadi | Kadrlar 300/300 bayt-aniq (lossless). **A/V siljish −52 ms**: chiqishda video va audio ikkalasi 0 dan → EC-1 |
| MP4 29.97 fps AAC | Kadrlar 360/360 bayt-aniq; lossy rejimda siljish 0 ms |
| VFR MP4 (6 kadr tushgan, 294 kadr, 11.96 s) | Chiqish 11.76 s (299 kadr o'rniga 294, ya'ni 0.2 s qisqa), birinchi chunk'dan keyin 1 kadr siljish, xato berilmagan → EC-2 |

Windows'da ffmpeg 7.1.1 va haqiqiy Canon fayli bilan qayta tekshirilishi kerak (B1).

**Ochiq:** TZ 18-bo'lim (O-01..O-09).
