# Qarorlar jurnali

Har yozuv: sana, bosqich, qaror yoki o'lchov, sabab, dalil (commit, fayl, buyruq). Yangi yozuvlar yuqoriga.

---

## 2026-10-26 — B7, backend API, navbat, rejalashtiruvchi, to'liq doctor

**Natijalar:** `pytest -m "unit or media or windows"` — barchasi o'tdi (rejalashtiruvchi: 3 loyiha x 6 vazifa
aralash resurslar bilan — har tick'da Σvram <= 13 000, NVENC <= 2, NVDEC <= 1, cpu_heavy <= 2, pptx <= 1,
exclusive yolg'iz; to'xtatish -> 'toʻxtatildi', jarayon daraxti o'ldirilgan; resume checkpoint'dan; 1 marta
qayta urinish, "out of memory" bo'lsa GPU bo'shashini kutadi; dastur qayta ochilganda 'ishlanmoqda' -> navbat).

**Doctor (bu mashina):** hammasi ok, ikki ogohlantirish:
- **CPU mikrokod 0x11F** (registry `Update Revision`, 4 bayt LE) — 0x12B dan eski: **HW-1 (BIOS yangilash) zarur**.
- Drayver pin yozilmagan (`driver_pin.txt`, HW-4) — qaysi versiya sinalgan deb qotirilishi inson qarori.

**Qarorlar:**
- Navbat SQLite WAL (`workdir/queue.db`), vazifa = `python -m darsstudio.jobs.worker <tur> <json>`, protokol
  `PROGRESS/LOG/RESULT`, worker `SetThreadExecutionState` bilan uyquni bloklaydi (HW-6).
- Vazifa resurslari: asr — manifest `vram_mb` x 1.1 (o'lchanmagan bo'lsa 4500), eyecontact 1100 + cpu_heavy,
  render 3200 + NVENC, slides pptx + cpu_heavy, audio cpu_heavy, proxy NVENC.
- "Tekshiruvgacha tayyorlash" zanjiri: slides ‖ audio -> asr ‖ eyecontact ‖ proxy -> sync -> cuts.
- API: FastAPI, faqat 127.0.0.1; o'zgarishlar faqat buyruqlar orqali (undo/redo serverda); proxy/slaydlar
  FileResponse (Range 206); WebSocket `/ws` — vazifa yangilanishlari; `ui/dist` bo'lsa statik.
- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` server va ASR worker'da (FR-22).

---

## 2026-10-26 — B3, vertikal kesim: birinchi haqiqiy MP4

**O'lchovlar (RTX 5070 Ti, torch 2.11+cu128, ffmpeg 7.1.1, NVENC p7, profil `web`):**
- `tools/render_bench.py workdir/namuna` (to'liq 13 min 46 s, 20 664 kadr, A sahna, demo shablon):
  **147.3 kadr/s**, 140.3 s, torch VRAM pik 2 656 MB, GPU umumiy band xotira pik 6 594 MB (displey va boshqa
  dasturlar bilan), asosiy jarayon CPU ~1.3 yadro. Maqsad >= 80 kadr/s (AC-10) — bajarildi; 25 min ~4.3 min
  (ekstrapolyatsiya).
- 2.5 min bo'lak (`workdir/b3/namuna_frag.mp4`, A->B->A, 8 slayd CSV'dan): 47.5 s jami (slayd render PowerPoint
  COM, warp, key taklifi, joylashtirish 413 namunada, render 25.4 s).
- Testlar: `pytest -m "unit or media or windows"` 63 passed.

**Qarorlar:**
- PowerPoint 16.0 ish stansiyasida bor (O-01 javobi). LibreOffice yo'q: PPTX uchun zaxira yo'l faqat LibreOffice
  o'rnatilsa ishlaydi; PDF pypdfium2 bilan.
- `render_pptx.py` va `render_pdf.py` bitta `slides/render.py` ga birlashtirildi (umumiy kesh/stamp). 4K PNG
  slaydning o'z nisbatida, 16:9 ga pillarbox warp/kompozitda.
- Sarlavha placeholder'i bo'lmasa (namuna PPTX'da shunday) — eng yuqoridagi <= 12 so'zli matn sarlavha.
- Keyer: guided filter bilan luma'ga tayangan chroma upsampling (r=2), CbCr masofasi smoothstep, garbage/keep,
  choke + Gauss feather, spill G' = min(G, max(R,B)), [ixtiyoriy] guided edge refine. AI matting, light wrap,
  vaqt bo'yicha EMA — qilinmadi (TZ'da [T]/[I]).
- Key avtomatik taklifi (`keyer.suggest`): yashil piksellar medianasi, tolerantlik = 99.5-persentil + 0.02,
  garbage = yashil maydon (ustun/qator > 30% yashil) tashqarisi. Namunada: key (-0.175, -0.274), tol 0.1225,
  garbage x < 227 va x > 1627 (oq devorlar).
- Joylashtirish: `MAX_SCALE = 1.0` (1080p manbani kattalashtirmaslik). Namunada bbox (604, 208)-(1224, 1080),
  joy x=556, y=0, scale 1.0.
- Audio (B3): manbadan AAC 192k, video `start` kadridan `-ss` (fayl boshiga nisbatan) — lab-sync saqlanadi;
  52 ms siljishli sintetik klipda chaqnash (100-kadr) va beep 1 kadr ichida (test).
- Chunk 60 s, checkpoint `cache/render/<kalit>/seg_XXXXX.json`, kalit = sozlamalar + shablon hash + slaydlar +
  oraliqlar + profil. Qayta ishga tushirilganda tayyor segmentlar qayta yozilmaydi (test).
- mypy: render/slides/cli uchun `arg-type, call-overload, assignment, list-item, no-any-return` o'chirilgan
  (cv2/torch stub'lari), qolgan modullar strict.

**G1 (inson qarori kutilmoqda):** `workdir/b3/namuna_frag.mp4` ni montajchi ko'rishi kerak: soch, qo'l, ko'zoynak
(namunada yo'q), devor cheti, slayd o'qilishi, o'qituvchi joyi. Demo shablon sintetik (haqiqiy studiya foni — O-08).

---

## 2026-10-26 — B2, media qatlami, TimeMap, loyiha modeli

**O'lchovlar:** haqiqiy namuna (`namuna/video.MOV`, 13 min 46 s, 1080p25 yuvj420p, PCM 48 kHz, 20 664 kadr) +
`Taqdimot.pptx` (19 slayd): `python -m darsstudio.cli import` — 20.2 s (probe 0.6 s, NVENC proxy 540p 101 MB).
TZ 3.8 maqsadi 25 min uchun <= 3 min — bajarildi (~37 s ga ekstrapolyatsiya, o'lchanmagan).
Testlar: `pytest -m "unit or media"` 53 passed (TimeMap: 3 x 500 hypothesis misoli).

**Qarorlar:**
- VFR aniqlash paket vaqtlari bo'yicha (`detect_vfr`: kadrlar orasi nominaldan yarim kadrdan ko'p farq qilsa).
- VFR -> CFR: `fps` filtri (Eye Contact EC-2 bilan bir xil to'r), libx264 crf 12 GOP 25, MKV. Audio != 48 kHz ->
  soxr, PCM s24le. Normallashtirish kerak bo'lmasa nusxa yozilmaydi.
- FrameReader manba pix_fmt (yuv420p/yuvj420p) da o'qiydi — diapazon konvertatsiyasi yo'q; yuvj420p FFV1 orqali
  bayt-aniq qaytishi testda.
- Buyruqlar: har amal = maydon yo'li bo'yicha {old, new} (JSON), tarix `history/history.json` (oxirgi 500), avval
  tarix, keyin project.json yoziladi. Invariant buzilsa amal rad etiladi, holat o'zgarmaydi.
- Asset ID = `file_id` (hajm, mtime_ns, bosh/oxir 1 MB xxhash64) — Eye Contact EC-3 bilan bir xil formula.
- Import xatoda yarim loyiha papkasi o'chiriladi.
- Yangi bog'liqliklar: pydantic (MIT), xxhash (BSD-2), numpy (BSD-3), pypdfium2 (Apache-2.0/BSD-3), hypothesis
  (MPL-2.0, faqat dev).

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
