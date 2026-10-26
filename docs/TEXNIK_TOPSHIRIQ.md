# Texnik topshiriq: Dars Studio — lokal, yarim avtomatik videodars montaj tizimi

| | |
|---|---|
| Versiya | 2.0 (Claude Code uchun ishchi spetsifikatsiya) |
| Sana | 2026-10-24 |
| Asos | TZ v1.0 (24.10.2026, `AI_Video_Dars_Studio_Texnik_Topshiriq.docx`), Eye Contact moduli (`github.com/dshukriddinov/eye-contact`, commit `cfb8288`), TZ v1.0 sharhi va Eye Contact sinov natijalari |
| Ijrochi | Claude Code (bosqichma-bosqich, `docs/BOSQICHLAR.md` bo'yicha) |
| Maqsadli apparat | Intel i7-14700K, 64 GB DDR5, NVIDIA RTX 5070 Ti 16 GB, Windows 11 Pro |

Belgilar: **[M]** majburiy, **[T]** tavsiya, **[I]** ixtiyoriy (keyingi versiya). Talab ID'lari: `FR-xx` funksional,
`NFR-xx` nofunksional, `AC-xx` qabul mezoni, `D-xx` arxitektura qarori, `EC-x` Eye Contact moduliga o'zgarish.

---

## 0. Qisqacha

**Nima qiladi.** Yashil fonda yozilgan 10–25 daqiqalik o'qituvchi videosi va PPTX slaydlarni oladi. Nutqqa mos slayd
almashinuvini aniqlaydi yoki suratga olish paytida yozilgan slayd jurnalidan oladi. O'qituvchini fondan ajratadi,
nigohini kameraga qaratadi, ovozni tozalaydi, pauzalarni qisqartirishni taklif qiladi. Ikki sahna ko'rinishini yig'adi:
A) studiyada o'qituvchi + ekranda slayd, B) slayd to'liq ekran. Natija: MP4, SRT, slayd vaqtlari va Premiere/DaVinci
uchun tahrirlanadigan paket.

**Ish prinsipi.** AI taklif qiladi, montajchi faqat shubhali joylarni tekshiradi va tasdiqlaydi. Asosiy o'lchov:
25 daqiqalik darsga montajchi sarflaydigan vaqt (maqsad ≤ 45 daqiqa) va mashina vaqti (maqsad ≤ 30 daqiqa, odamsiz).

**Asosiy g'oya.** Barcha og'ir tahlillar (ASR, slayd moslashtirish, Eye Contact, kalibrlash) asl video vaqt chizig'ida
yon fayllarga yoziladi. Yakuniy video **bitta render o'tishida** quriladi: dekod → ko'z patchlari → keyer → kompozit →
NVENC. Oraliq to'liq videolar yozilmaydi.

---

## 1. Maqsad va qamrov

### 1.1 Kiradi
- Bitta o'qituvchi, bitta kamera, yashil fon, statik kamera (tripod).
- 1080p, 25 / 29.97 / 30 kadr/s, 8-bit 4:2:0 (H.264/H.265/ProRes). VFR import paytida CFR'ga o'tkaziladi.
- PPTX (asosiy) va PDF (zaxira) slaydlar.
- Ikki sahna shabloni (A `split_right_teacher`, B `fullscreen_slide`), brending (logo, lower-third, intro/outro).
- O'zbek tili (lotin; kirill matn lotinga o'giriladi), ruscha/inglizcha atamalar qo'shilishi mumkin.
- Windows 11, bitta NVIDIA RTX GPU, to'liq offline ish.
- Navbat bilan bir nechta darsni odamsiz ishlash (kechki rejim).

### 1.2 Kirmaydi (v2.0)
- Real-time / jonli efir, bir nechta kamera, bir nechta so'zlovchi.
- 4K chiqish, 10-bit/HDR chiqish (4:2:2 10-bit kirish — 17-bo'lim, keyingi bosqich).
- Bulut xizmatlari, tashqi API'lar, avtomatik yuklash (YouTube/LMS).
- macOS/Linux'da to'liq ishlash (birlik testlari Linux'da ishlashi kerak, 13-bo'lim).

---

## 2. Asosiy arxitektura qarorlari

| ID | Qaror | Sabab |
|---|---|---|
| D-01 | **Yakuniy render bitta o'tishda**, oraliq to'liq videolar yo'q | Har bir lossy avlod yashil fon chegaralarini buzadi; disk va vaqt tejaladi (3.6-bo'lim) |
| D-02 | **Eye Contact natijasi patch fayli** (`eyepatch/`), asl kadr indeksi bo'yicha | Modul kadrda ~1 100 piksel o'zgartiradi; to'liq H.264 nusxa (~5 GB) o'rniga ~100–300 MB; kesishlardan mustaqil |
| D-03 | **Vaqtning yagona manbai — asl videodagi kadr indeksi** (`fractions.Fraction` fps). Chiqish vaqti faqat `TimeMap` orqali hisoblanadi | Pauza kesish qayta tasdiqlanganda ma'lumot buzilmaydi; suzuvchi nuqta xatosi yig'ilmaydi |
| D-04 | **Har GPU vazifasi alohida jarayonda**, VRAM budjetli rejalashtiruvchi orqali | Jarayon tugaganda VRAM to'liq bo'shaydi; model yiqilsa asosiy dastur yiqilmaydi (Eye Contact GUI'da sinalgan usul) |
| D-05 | **Slayd sinxroni ikki rejimli**: 1) PowerPoint hodisa jurnali (yangi yozuvlar uchun asosiy), 2) AI moslashtirish (zaxira, eski yozuvlar) | Jurnal aniqligi < 0.5 s va deyarli bepul; AI faqat jurnal yo'q bo'lganda |
| D-06 | **ASR modeli benchmark bilan tanlanadi**; so'z vaqtlari CTC forced alignment bilan aniqlanadi | Standart Whisper large-v3 o'zbek tilida zaif; pauza kesish uchun aniq so'z chegaralari kerak |
| D-07 | **Keyer GPU'da (PyTorch)**: chroma upsampling, rang masofasi, spill suppression, garbage matte | 4:2:0 materialda chegara sifati chroma upsampling'ga bog'liq; GPU'da 1080p yuzlab kadr/s |
| D-08 | **Slayd qatlamlari bir marta oldindan perspektivaga moslanadi** (4K'dan supersampling) | Slayd statik — har kadrda warp shart emas; kichik matn o'qiladigan bo'ladi |
| D-09 | **UI: FastAPI + React/TypeScript**, pywebview (WebView2) oynasida; portativ paket | Timeline va video preview uchun web UI qulay; Eye Contact'dagi portativ paket tajribasi qayta ishlatiladi |
| D-10 | **Loyiha holati Pydantic JSON** (atomik saqlash, buyruqlar tarixi = undo/redo); global navbat SQLite | Diff qilish, tiklash va test qilish oson; bir foydalanuvchili lokal tizim |
| D-11 | **Premiere paketi**: qatlamlar 1920×1080 kanvasda oldindan joylashtirilgan; XML faqat kesishlarni saqlaydi | Corner Pin kabi effektlar XML orqali ishonchli o'tmaydi; montajchi kesishlarni Premiere'da o'zgartira oladi |
| D-12 | **Eye Contact alohida repo** (git submodule `engines/eye-contact`), CLI orqali chaqiriladi; avval EC-1..EC-5 o'zgarishlari | Modul sinalgan va barqaror; mustaqil rivojlanadi |
| D-13 | **Bitta ffmpeg versiyasi butun tizimda: 7.1.1** (gyan.dev full build) | Eye Contact shu versiyaga qotirilgan; yangi ffmpeg NVENC uchun yangiroq drayver talab qiladi |

---

## 3. Apparat profili va resurs budjeti

### 3.1 Ish stansiyasi

| Komponent | Qiymat | Holat |
|---|---|---|
| CPU | Intel Core i7-14700K, 20 yadro (8P + 12E), 28 oqim | Aniqlangan |
| RAM | 64 GB DDR5 (2 × 32 GB, Kingston Fury KF560C…, XMP 6000) | Aniqlangan (modul tezligi barqarorligi HW-3 da tekshiriladi) |
| GPU | GeForce RTX 5070 Ti 16 GB GDDR7, Blackwell, compute capability 12.0 (sm_120) | Aniqlangan |
| Video dvigatellar | 2 × NVENC (9-avlod), 1 × NVDEC (6-avlod), 4:2:2 apparat kodlash/dekodlash, AV1 | Aniqlangan |
| OS | Windows 11 Pro x64 | Aniqlangan |
| Drayver | 591.86 (Eye Contact sinovida); minimal 570 | Pin qilinadi (HW-4) |
| Ona plata / BIOS | ASUS TUF Gaming Z790-Plus WiFi, BIOS 04.12.2023 | **Yangilash shart** (HW-1) |
| Disk | Aniqlanmagan | Ishchi NVMe ≥ 1 TB, bo'sh joy ≥ 500 GB tavsiya |
| Kamera | Canon EOS 5D Mark III: H.264 1080p25, yuvj420p (to'liq diapazon), BT.709, ~22.7 Mbit/s, PCM 48 kHz stereo | Eye Contact test videosidan |

### 3.2 Ishdan oldin majburiy sozlash

| ID | Ish | Sabab |
|---|---|---|
| HW-1 [M] | BIOS'ni ASUS saytidagi eng so'nggi versiyaga yangilash (Intel mikrokod 0x12F yoki yangiroq), keyin "Intel Default Settings" profilini yoqish | 13/14-avlod Raptor Lake'dagi Vmin Shift muammosi. 2023-yil dekabrdagi BIOS'da 0x12B va 0x12F tuzatishlari yo'q. Uzoq renderlar aynan shu muammoda crash beradi |
| HW-2 [M] | `doctor` mikrokod versiyasini o'qib, < 0x12B bo'lsa ogohlantirsin (Windows registry: `HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0`, `Update Revision`; o'qish usuli 0-bosqichda tekshiriladi) | Kelajakda BIOS qaytarilsa yoki boshqa kompyuterga ko'chirilsa |
| HW-3 [M] | RAM barqarorlik sinovi: XMP 6000 bilan 1 soat OCCT/MemTest; xato bo'lsa 5600 MT/s ga tushirish | 2 × 32 GB DDR5-6000 uzoq yuklamada xato berishi mumkin; render crash'lari sabablarini ajratish uchun |
| HW-4 [M] | NVIDIA Studio Driver o'rnatib, versiyani pin qilish; `doctor` versiya o'zgarsa ogohlantirsin | Maxine, NVENC va CUDA birga sinalgan versiya |
| HW-5 [T] | Ishchi papka NVMe'da; Windows Defender'da shu papka uchun istisno (foydalanuvchi qarori) | Katta fayllarda I/O tezligi |
| HW-6 [M] | Vazifa ishlayotganda tizim uxlab qolmasin (`SetThreadExecutionState(ES_CONTINUOUS \| ES_SYSTEM_REQUIRED)` worker'da) | Kechki navbat rejimi |

### 3.3 Dasturiy stek GPU uchun

- CUDA ≥ 12.8 (Blackwell sm_120 uchun shart). PyTorch ≥ 2.7, `cu128` build. CTranslate2 ≥ 4.5 (Whisper tanlansa).
- Maxine AR SDK v0.8.7 Blackwell build o'zining CUDA/TensorRT runtime'i bilan keladi va alohida jarayonda ishlaydi;
  PyTorch CUDA runtime bilan to'qnashmaydi.
- Barcha GPU kutubxonalari bitta `runtime/python` ichida; versiyalar `requirements.lock` da qotiriladi.

### 3.4 VRAM budjeti (16 GB)

Tizim (Windows, displey, ochiq Premiere) uchun **3 GB zaxira**. Vazifalar uchun **≤ 13 GB**.

| Vazifa | Taxminiy VRAM | Eslatma |
|---|---|---|
| Eye Contact (Maxine) | 0.9 GB | O'lchangan (1080p) |
| ASR, Whisper large-v3 (fp16 / int8_float16) | 4.5–5 / ~3 GB | faster-whisper ma'lumotlari bo'yicha large-v2 fp16 ≈ 4.7 GB |
| ASR, CTC model (~600M) | 2–3 GB | Taxminiy |
| Forced alignment (CTC) | 1–2 GB | Taxminiy |
| Embedding (BGE-M3 / e5-large, fp16) | 1.5–2.5 GB | Taxminiy |
| Renderer (keyer + kompozit, 1080p, 8 kadrlik batch) | 1.5–3 GB | Taxminiy |
| Proxy render | < 1 GB | NVENC |
| [I] VLM slayd tavsifi (7B, 4-bit) | 6–8 GB | Faqat yolg'iz ishlaydi (`exclusive`) |

Taxminiy qiymatlar 0-bosqichda `tools/vram_probe.py` bilan o'lchanib, `models/manifest.json` dagi `vram_mb` maydoniga
yoziladi. Rejalashtiruvchi aynan shu qiymatlardan foydalanadi (FR-20).

### 3.5 RAM budjeti (64 GB)

| Iste'molchi | Budjet |
|---|---|
| Windows + Premiere/DaVinci (parallel ochiq bo'lishi mumkin) | ≥ 24 GB bo'sh qoldiriladi |
| Dars Studio jami | ≤ 32 GB (`doctor` va rejalashtiruvchi nazorat qiladi) |
| Kadr navbatlari (1080p yuv420p 3.1 MB/kadr) | ≤ 64 kadr/jarayon ≈ 200 MB |
| 4K slayd PNG'lar xotirada (100 slayd) | ≤ 1 GB |
| Audio (25 min, 48 kHz float32 stereo) | ~0.6 GB |
| CPU vazifalar pool'i | 8 jarayongacha (PPTX, audio, OCR, proxy dekod) |

### 3.6 Disk budjeti (25 daqiqalik bitta dars)

| Fayl | Hajm |
|---|---|
| Manba video (22.7 Mbit/s) | ~4.3 GB |
| Audio WAV (48 kHz stereo + 16 kHz mono) | ~0.6 GB |
| Proxy (960×540, qisqa GOP) | ~1–1.5 GB |
| Eye Contact patchlari | ~0.1–0.3 GB |
| Slaydlar (4K PNG + oldindan warp qilingan qatlamlar) | ~0.3–0.6 GB |
| Yakuniy MP4 (8–12 Mbit/s) | ~1.5–2.3 GB |
| **Jami (Premiere paketisiz)** | **~8–10 GB** |
| [I] Premiere paketi: o'qituvchi qatlami ProRes 4444 | +30–60 GB |

Render boshlanishidan oldin bo'sh joy tekshiriladi (taxminiy hajm × 1.5 zaxira). Kesh tozalash siyosati FR-23 da.

### 3.7 Video dvigatellardan foydalanish

- 2 × NVENC: yakuniy render va proxy/preview parallel ishlashi mumkin.
- 1 × NVDEC: bir vaqtda faqat bitta NVDEC iste'molchisi. Eye Contact CPU dekod ishlatadi (o'zgartirilmaydi).
  Renderer dekodni CPU'da (ffmpeg, ko'p oqim) qiladi, NVDEC — ixtiyoriy optimallashtirish.
- [I] Zero-copy: `PyNvVideoCodec` (NVDEC/NVENC → GPU tensor) — faqat NFR-01 maqsadiga yetilmasa.

### 3.8 Unumdorlik maqsadlari (25 daqiqalik 1080p25 dars, RTX 5070 Ti)

| Bosqich | Maqsad | Asos |
|---|---|---|
| Import + validatsiya + proxy | ≤ 3 min | NVENC proxy |
| PPTX render + matn | ≤ 3 min (CPU, parallel) | PowerPoint COM / LibreOffice |
| Audio tayyorlash (denoise + o'lchov) | ≤ 3 min (CPU, parallel) | |
| ASR + so'z vaqtlari | ≤ 4 min | GPU |
| Slayd moslashtirish | ≤ 1 min | |
| Eye Contact (patch rejimi) | ≤ 10 min | Hozir 62–70 kadr/s, encode'siz tezroq |
| Yakuniy render | ≤ 8 min (≥ 80 kadr/s) | GPU keyer + kompozit, patchlar tayyor |
| **Jami mashina vaqti** | **≤ 30 min**, asosan parallel | |
| Montajchi vaqti | ≤ 45 min | Pilotda o'lchanadi, hozirgi qo'lda montaj vaqti bilan solishtiriladi |

---

## 4. Kirish va chiqish

### 4.1 Kirish video
- Konteyner MP4/MOV/MKV; kodek ffmpeg dekodlay oladigan har qanday (asosan H.264).
- [M] 8-bit 4:2:0 (`yuv420p`, `yuvj420p`), 1920×1080, 25/29.97/30 kadr/s. Boshqa format — tushunarli xato.
- [M] VFR aniqlansa (`r_frame_rate ≠ avg_frame_rate` va paket vaqtlari notekis) importda CFR'ga o'tkaziladi
  (`-fps_mode cfr`, H.264 all-intra yoki yuqori bitrate oraliq fayl), loyiha shu fayl bilan ishlaydi.
- [M] Video va audio `start_time` farqi saqlanadi (AC-07).

### 4.2 Slaydlar
- PPTX asosiy. PDF zaxira (matn PDF'dan olinadi, eslatmalar yo'q).
- Render: PowerPoint COM (o'rnatilgan bo'lsa) → `Slide.Export(PNG, 3840, 2160)`; aks holda LibreOffice headless
  → PDF → `pypdfium2` bilan 3840×2160 PNG. PyMuPDF ishlatilmaydi (AGPL).
- Matn: `python-pptx` bilan sarlavha, asosiy matn, jadval kataklari va **ma'ruzachi eslatmalari** (notes).
- Animatsiyalar (build): v2.0 da slaydning **yakuniy holati** ko'rsatiladi; animatsiyali slaydlar ro'yxati
  ogohlantirish sifatida chiqadi. [I] Har build bosqichini alohida rasm sifatida ishlatish (slayd jurnali `NextBuild`
  hodisalari bilan).
- Slayd ichidagi video/audio: statik kadr ko'rsatiladi, ogohlantirish.
- Nisbat 16:9 bo'lmasa (masalan 4:3) — 16:9 maydonga pillarbox bilan joylanadi.

### 4.3 Shablon assetlari
- Studiya fon rasmi PNG 1920×1080 yoki 3840×2160; ekrandagi eski slayd tozalangan.
- Ekran to'rtburchagi: 4 nuqta (TL, TR, BR, BL) kanvas koordinatasida, UI'da kalibrlanadi.
- O'qituvchi joyi (anchor box), xavfsiz maydon chegaralari.
- Logo PNG (alfa bilan), lower-third uslubi, intro/outro MP4 (ixtiyoriy), shrift (Noto Sans yoki boshqa ochiq
  litsenziyali, `ʻ` va `ʼ` belgilarini qo'llaydigan).

### 4.4 Slayd jurnali (ixtiyoriy, FR-07)
CSV: `t_ns,event,slide_index,build_index` + birinchi qatorda `sync_beep_t_ns`. `tools/slide_logger.py` yozadi.

### 4.5 Metama'lumot
Fan, mavzu, o'qituvchi F.I.O., dars raqami, til, shablon, eksport profili.

### 4.6 Chiqishlar

| Fayl | Format | Majburiylik |
|---|---|---|
| Yakuniy video | MP4, H.264 High (NVENC p7, VBR), 1920×1080, manba fps, BT.709 limited range; AAC-LC 48 kHz 192 kbit/s | [M] |
| Subtitr | SRT (UTF-8), chiqish vaqt chizig'ida | [M] |
| Slayd vaqtlari | CSV + JSON (asl va chiqish vaqtlari) | [M] |
| Loyiha | `project.json` (to'liq holat) | [M] |
| QA hisoboti | `qa.json` + UI'da ko'rinish | [M] |
| Premiere/DaVinci paketi | FCP7 XML (xmeml v5) + qatlam fayllari (FR-18) | [T] |
| Ixtiyoriy kodeklar | H.265, AV1 (NVENC) | [I] |

---

## 5. Ish jarayoni

```
[Import] ─► probe, validatsiya, VFR→CFR, hash ─► proxy 540p (NVENC)
   │
   ├──► [Slaydlar, CPU]  PPTX → 4K PNG + matn + eslatmalar (+OCR) ─► oldindan warp (shablon bo'yicha)
   ├──► [Audio, CPU]     48 kHz WAV ─► denoise ─► loudness o'lchovi;  16 kHz mono ─► VAD
   ├──► [ASR, GPU]       16 kHz ─► ASR ─► forced alignment ─► so'z vaqtlari ─► normallashtirish + lug'at
   └──► [Eye Contact, GPU] asl video ─► eyepatch/ (asl kadr indekslari)
            │
[Sinxron]  slayd jurnali bo'lsa ─► beep sync ─► slayd oraliqlari
           bo'lmasa ─► AI moslashtirish (embedding + leksik + DP) ─► oraliqlar + ishonchlilik
            │
[Kalibrlash, bir martalik / shablon]  key rangi, garbage matte, o'qituvchi joyi
            │
[Tekshirish UI]  shubhali chegaralar, sahna turi (A/B), pauza kesish takliflari, Eye Contact o'chiq oraliqlar
            │
[Preview]  oraliq bo'yicha haqiqiy kompozit (540p) yoki to'liq proxy kompozit
            │
[Yakuniy render, bitta o'tish]  dekod ─► ko'z patchi ─► GPU keyer ─► kompozit ─► o'tishlar/overlay ─► NVENC
                                audio: denoise ─► kesishlar (crossfade) ─► loudnorm ─► AAC ─► mux
            │
[Eksport + QA]  MP4, SRT, CSV/JSON, [Premiere paketi], qa.json
```

Parallellik: Slaydlar, Audio va (GPU budjeti yetsa) ASR va Eye Contact bir vaqtda ishlaydi. Rejalashtiruvchi FR-20.

---

## 6. Funksional talablar

### FR-01 Loyiha va import [M]
- Yangi loyiha: video, PPTX/PDF, shablon, metama'lumot, ixtiyoriy slayd jurnali.
- Loyiha papkasi tuzilishi 8.4-bo'limda. Manba fayllar ko'chirilmaydi (havola + hash), foydalanuvchi so'rasa nusxalanadi.
- Asset identifikatori: fayl hajmi + `mtime_ns` + boshidagi va oxiridagi 1 MB'ning xxhash64'i.
- Bir nechta loyihani birdaniga qo'shish (papkadagi juftliklar: `dars05.mov` + `dars05.pptx`).

**AC:** 10, 15, 25 daqiqalik haqiqiy video + PPTX ochiladi; slayd soni PPTX bilan mos; noto'g'ri fayl tushunarli
o'zbekcha xato bilan rad etiladi.

### FR-02 Media validatsiya va normallashtirish [M]
- ffprobe: kodek, o'lcham, fps (Fraction), pix_fmt, rang teglari, rotation, video/audio `start_time`, davomiylik,
  kadr soni (paketlar sanab tekshiriladi), audio namuna chastotasi/kanallar.
- VFR → CFR (4.1). 48 kHz bo'lmagan audio — 48 kHz'ga resample (sifatli `soxr`).
- Proxy: 960×540, H.264 NVENC, GOP 12, AAC 128k, `+faststart` (brauzerda ijro uchun).

**AC:** sintetik test media to'plamidagi (13.3) barcha holatlar to'g'ri aniqlanadi; VFR klipda chiqish davomiyligi
manba bilan ±1 kadr.

### FR-03 Slaydlarni tayyorlash [M]
- 4K PNG render (4.2), matn + eslatmalar ekstraksiyasi, animatsiya/video/shrift ogohlantirishlari.
- PowerPoint COM bir vaqtda faqat bitta jarayonda (rejalashtiruvchida `pptx` resursi = 1).
- Shrift almashganini aniqlash: PowerPoint va LibreOffice render natijalari bo'yicha emas, PPTX'dagi shriftlar
  tizimda borligini tekshirish orqali.
- [T] OCR: matni 15 so'zdan kam slaydlar uchun Tesseract (`uzb`, `uzb_cyrl`, `rus`, `eng`).
- [I] VLM tavsifi (diagramma/rasm slaydlar uchun), `exclusive` GPU vazifa.
- Oldindan warp: har slayd shablondagi ekran to'rtburchagiga (9.2), natija RGBA PNG 1920×1080 kesh'da.

**AC:** 3 ta haqiqiy PPTX'da render vizual jihatdan PowerPoint bilan mos (PowerPoint bo'lmasa LibreOffice farqlari
ro'yxati chiqadi); warp qilingan slayd ramkadan chiqmaydi (AC-04).

### FR-04 Audio tayyorlash [M]
- 48 kHz WAV ajratish; 16 kHz mono (ASR uchun).
- Denoise: DeepFilterNet3 (CPU yoki GPU), susaytirish chegarasi 12–18 dB (artefakt bo'lmasligi uchun sozlanadi);
  zaxira — ffmpeg `afftdn`.
- High-pass 80 Hz; loudness o'lchovi (EBU R128).
- Yakuniy loudness profili (FR-16): standart −16 LUFS, true peak ≤ −1.5 dBTP; YouTube profili −14 LUFS.

**AC:** denoise oldin/keyin 3 ta klip montajchi tomonidan tinglanadi; loudness AC-08 ga mos.

### FR-05 ASR va so'z vaqtlari [M]
- Dvigatel interfeysi `AsrEngine.transcribe(wav16k) -> list[Word]` (matn, `start_ms`, `end_ms`, ishonchlilik).
- Nomzodlar (benchmark bilan tanlanadi, D-06):
  1. Whisper large-v3 (faster-whisper, CTranslate2) — zero-shot baza.
  2. O'zbekchaga fine-tune qilingan Whisper (CTranslate2 formatiga o'girilgan).
  3. O'zbekcha CTC model (GigaAM asosidagi kabi).
  Har nomzodning litsenziyasi tekshirilmaguncha ishlatilmaydi (`models/manifest.json` da `license` majburiy).
- So'z vaqtlari: CTC forced alignment (tanlangan CTC model yoki alohida o'zbekcha CTC alignment modeli). Whisper'ning
  o'z so'z vaqtlari faqat zaxira.
- Silero VAD bilan nutqsiz qismlar aniqlanadi; Whisper ishlatilsa VAD filtri yoqiladi (gallyutsinatsiyaga qarshi).
- `tools/asr_bench.py`: 3 fan × 5 daqiqalik qo'lda tuzatilgan matnga nisbatan WER, CER, atamalar aniqligi,
  tezlik (RTF), VRAM. Natija `docs/QAROR_JURNALI.md` ga yoziladi.
- Foydalanuvchi transkriptni UI'da tuzatishi mumkin; tuzatish so'z vaqtlarini saqlaydi (matn almashtirish, vaqt emas).

**AC:** tanlangan model 3 ta dars namunasida CER ≤ 10% (maqsad, pilotda tasdiqlanadi); so'z chegarasi xatosi
median ≤ 60 ms (qo'lda belgilangan 100 ta so'z bo'yicha).

### FR-06 O'zbek matnini normallashtirish va lug'at [M]
- `uz_text.normalize()`: apostrof variantlari (`'`, `‘`, `’`, `` ` ``, `ʻ`, `ʼ`) → `oʻ`, `gʻ` uchun U+02BB, tutuq belgisi
  uchun U+02BC; kirill → lotin (rasmiy jadval: ш→sh, ч→ch, ў→oʻ, ғ→gʻ, ҳ→h, қ→q, ё→yo, ю→yu, я→ya, ц→ts…);
  kichik harf; raqamlar → so'z (`2010-yilda` → `ikki ming oʻninchi yilda`) faqat moslashtirish uchun; tinish belgilari.
- Lug'at (`glossary.json`, global + loyiha): atama, variantlar, til. Ishlatilishi: Whisper `hotwords`/`initial_prompt`,
  ASR'dan keyin noaniq almashtirish (`rapidfuzz`, chegara sozlanadi), moslashtirishda vazn oshirish.
- Subtitrda ko'rsatish uchun alohida "chiroyli" normallashtirish (raqamlar raqamligicha qoladi).

**AC:** `tests/unit/test_uz_text.py` da ≥ 60 ta misol (apostrof, kirill, raqam, aralash matn).

### FR-07 Slayd sinxroni: jurnal rejimi [T]
- `tools/slide_logger.py` (Windows, pywin32): PowerPoint'ga `DispatchWithEvents` bilan ulanadi va
  `SlideShowBegin`, `SlideShowNextSlide`, `SlideShowNextBuild`, `SlideShowEnd` hodisalarini `perf_counter_ns` bilan
  yozadi. Boshlanishda 1 kHz, 300 ms "sync beep" chaladi (kamera mikrofoni yozib oladi).
- Import: audioda beep matched filter bilan topiladi → jurnal vaqti va video vaqti orasidagi siljish; slayd oraliqlari
  asl kadr indekslariga o'giriladi.
- Ortga qaytishlar ham saqlanadi (jurnal haqiqatni yozadi); juda qisqa (< 1 s) oraliqlar foydalanuvchiga ko'rsatiladi.

**AC:** sintetik beep klipda siljish xatosi ≤ 10 ms; haqiqiy darsda chegaralarning ≥ 98% i ±0.5 s ichida.

### FR-08 Slayd sinxroni: AI rejimi [M]
- Algoritm 9.4-bo'limda: segmentlar × slaydlar o'xshashlik matritsasi (embedding + belgi n-gram TF-IDF + sarlavha
  kalit so'zlari), monoton DP (qolish / keyingi / bittasini o'tkazib yuborish / bitta orqaga), minimal turish vaqti,
  forward-backward bilan ishonchlilik, chegarani eng yaqin pauza/gap boshiga surish.
- `tools/align_eval.py`: qo'lda belgilangan chegaralar ("ground truth") bilan solishtirish: ±1/±2/±5 s ichidagi ulush,
  median xato, shubhali deb belgilanganlar ulushi.
- Ishonchlilik < 0.6 bo'lgan chegaralar "Shubhali joylar" ro'yxatiga tushadi.

**AC:** 3 ta dars bo'yicha chegaralarning ≥ 85% i ±2 s ichida va shubhali chegaralar ≤ 20% (boshlang'ich maqsad;
pilotda aniqlashtiriladi). Xato chegaralarning ≥ 70% i "shubhali" ro'yxatda bo'lishi kerak (ishonchlilik foydali bo'lsin).

### FR-09 Pauzalarni kesish va CutMap [M]
- Nomzodlar: VAD + so'z vaqtlari bo'yicha nutqsiz oraliq ≥ `min_pause` (default 1.2 s) → `keep_pause` (default
  0.35 s) qoladi. So'z ichida kesish taqiqlanadi.
- Kesish nuqtalari kadr chegarasiga tekislanadi; audio namuna aniqligida (Fraction bilan) hisoblanadi.
- Takliflar ro'yxati: har biri tasdiqlanadi/rad etiladi (ommaviy tasdiqlash ham bor). Default — hammasi "taklif".
- Jump cut yumshatish variantlari (sozlama): `cut` (default), `crossfade` (2–4 kadr), `prefer_fullscreen`
  (B sahnadagi pauzalar birinchi taklif qilinadi).
- `TimeMap` (9.5, 8.2): saqlanadigan oraliqlar ro'yxati; barcha chiqish vaqtlari shundan hisoblanadi.

**AC:** property testlar (monotonlik, kesilmagan kadrlarda teskarilanuvchanlik, jami davomiylik); haqiqiy darsda
kesishlardan keyin lab-sync AC-07 ga mos; audio'da "chiq" ovozi yo'q (10 ms crossfade).

### FR-10 Eye Contact integratsiyasi [M]
- Modul `engines/eye-contact` (submodule) CLI'si alohida jarayonda `--patches-out` rejimida chaqiriladi (EC-4).
  Asl video (yoki CFR nusxasi) bo'yicha, kesishlardan mustaqil.
- Natija `cache/eyepatch/` (meta.json + chunk'lar), asset hash bilan bog'langan; hash mos kelmasa qayta ishlanadi.
- Renderer patchni kadr dekod qilingandan keyin, YUV fazosida qo'llaydi (9.7).
- Eye Contact o'chiq oraliqlar (o'qituvchi ataylab slaydga qaragan joylar) UI'dan belgilanadi; chegarada
  `ramp_frames` (default 8) davomida patch kuchi 0↔1 silliq o'zgaradi.
- Tuzatish kuchi (`lid_open`) loyiha sozlamasi (default 0.5, Eye Contact moduli tavsiyasi).

**AC:** modulning o'z metrikalari (identity ≥ 0.97 median, EAR farqi ≤ 15%, blink nisbati 0.95–1.05, flicker ≤ 1.5)
pilot darslardan birida qayta o'lchanadi; patch qo'llangan kadrlar Eye Contact'ning to'liq chiqishi bilan
lossless rejimda bayt-aniq (Y kanalida) mos.

### FR-11 Chroma key [M]
- GPU keyer (9.1): chroma upsampling (luma'ga tayangan), CbCr masofasi bo'yicha yumshoq matte, spill suppression,
  statik garbage matte (ko'pburchak, "doimo olib tashla"), "doimo saqla" ko'pburchagi, choke/feather, ixtiyoriy
  guided-filter bilan chegara aniqlash, ixtiyoriy light wrap.
- Kalibrlash UI: mos kadrda key rangini tanlash (pipetka + avtomatik taklif), slayderlar, oldin/keyin, matte ko'rinishi,
  bir nechta kadrda (har 2 daqiqada) tekshirish.
- Sozlamalar shablonga (studiya yorug'ligi bir xil bo'lsa) yoki loyihaga saqlanadi.
- [I] AI matting (soch qirralari) — litsenziyasi ruxsat bergan model bilan, alohida bosqich.

**AC:** 3 ta etalon klipda: garbage hududida alfa = 0; yashil spill o'lchovi (chegara zonasida G − max(R,B) median)
belgilangan chegaradan past; montajchi tekshiruv ro'yxati (soch, qo'l, ko'zoynak, qorong'i kiyim) bo'yicha "qabul".
Matte chegarasida kadrdan kadrga miltillash ko'zga tashlanmaydi.

### FR-12 Kompozitsiya va shablonlar [M]
- Shablon JSON (8.3): kanvas, fon, ekran to'rtburchagi, o'qituvchi anchor box, xavfsiz maydonlar, logo, lower-third,
  sahna turlari parametrlari.
- **A `split_right_teacher`**: fon → warp qilingan slayd qatlami → [I] ekran yaltirashi → o'qituvchi → logo/overlay.
- **B `fullscreen_slide`**: slayd 1920×1080 (pillarbox kerak bo'lsa) → logo; o'qituvchi yashirin, audio davom etadi.
  [I] C `fullscreen_pip`: B + burchakda kichik o'qituvchi.
- O'qituvchini joylashtirish statik (9.3): namunaviy kadrlardagi matte'lar birlashmasi bo'yicha masshtab va joy bir
  marta hisoblanadi; foydalanuvchi x/y/scale ni o'zgartira oladi. Kadr bo'yicha "kuzatib boruvchi" framing yo'q.
- Ogohlantirishlar: bosh yuqori chetga 2% dan yaqin, qo'l anchor box'dan chiqqan, o'qituvchi yashil maydondan chiqqan
  (garbage matte bilan kesishgan) kadrlar oraliqlari → "Shubhali joylar".
- Sahna turi tavsiyasi: slayd matni ≥ 60 so'z yoki jadval/diagramma bor → B tavsiya; inson tasdiqlaydi. Default A.
- Rang: o'qituvchi uchun ekspozitsiya, harorat/tint, to'yinganlik, [T] fonga moslashtirish (Lab o'rtacha/og'ish).

**AC:** slayd ekran ramkasidan chiqmaydi (piksel testi); o'qituvchi anchor box ichida; bitta videoda A→B→A almashinuvi
xatosiz (AC-05).

### FR-13 O'tishlar, brending, subtitr overlay [M]
- O'tishlar: A ichida slayd → slayd: slayd qatlamida crossfade (default 8 kadr); A ↔ B: crossfade (default 12 kadr)
  yoki cut. Shablonda sozlanadi.
- Logo (doimiy), lower-third (o'qituvchi, fan, mavzu; boshida 6 s, fade 0.3 s), intro/outro (fps/o'lcham mos
  kelmasa qayta kodlanadi, audio crossfade).
- [T] Subtitrni videoga "kuydirish" (alohida eksport profili): Pillow bilan RGBA overlay, ochiq shrift, qator ≤ 42 belgi,
  ≤ 2 qator.

### FR-14 Tekshirish UI va timeline [M]
- Asosiy ekran: video preview + slayd ko'rinishi + transkript + timeline yo'laklari:
  `Slayd`, `Sahna (A/B)`, `Kesishlar`, `Eye Contact oʻchiq`, `Subtitr`.
- "Shubhali joylar" paneli: ishonchlilik bo'yicha tartiblangan (slayd chegaralari, framing ogohlantirishlari,
  ASR past ishonchli so'zlar); bosilganda o'sha joyga o'tadi.
- Amallar: chegarani surish (kadr/±0.5 s), slaydni almashtirish, chegara qo'shish/o'chirish, sahna turini o'zgartirish,
  kesishni tasdiqlash/rad etish, Eye Contact o'chiq oraliq qo'shish, transkript so'zini tuzatish.
- Klaviatura: J/K/L, ←/→ (kadr), Shift+←/→ (1 s), `[`/`]` (chegarani surish), 1/2 (sahna A/B), Enter (tasdiqlash),
  Ctrl+Z / Ctrl+Y.
- Undo/redo: buyruqlar tarixi loyihada saqlanadi (qayta ochilganda ham ishlaydi).
- Avtosaqlash har o'zgarishda (atomik yozish).

**AC:** 25 daqiqalik darsda timeline silliq (60 fps scroll, 1 000+ element); dastur yopilib ochilganda barcha tuzatishlar
va undo tarixi tiklanadi.

### FR-15 Preview [M]
- **Tez ko'rinish** (darhol): manba proxy + joriy slayd rasmi yonma-yon (kompozitsiyasiz) — slayd vaqtlarini tekshirish uchun.
- **Haqiqiy ko'rinish**: tanlangan oraliq (default ±5 s) renderer bilan 960×540 da kompozit qilinadi, ≤ 3 s kutish.
- **To'liq proxy kompozit** (ixtiyoriy, navbatda): butun dars 540p.
- Brauzer pleyerida kadr aniqligi: qisqa GOP proxy + `requestVideoFrameCallback`; ko'rsatilayotgan kadr raqami
  UI'da ko'rinadi.

### FR-16 Yakuniy render [M]
- Bitta o'tish (D-01), ishlov 9.1–9.9 bo'limlarda. Chunk + resume (Eye Contact'dagi kabi: chunk segmentlari + JSON
  checkpoint + sozlamalar kaliti, concat `-c copy`).
- Profil: `arxiv` (H.264 cq 19, maxrate 16 Mbit/s), `web` (H.264 VBR 8 Mbit/s), [I] `hevc`, `av1`.
- Audio: denoise → kesishlar (10 ms crossfade) → loudnorm (ikki o'tishli, chiziqli rejim) → AAC 192 kbit/s.
- Video/audio boshlanish siljishi saqlanadi; chiqishdagi `start_time` farqi va davomiylik tekshiriladi.
- Render oldidan: bo'sh joy, barcha keshlar mosligi (hash), tasdiqlanmagan shubhali joylar soni haqida ogohlantirish.

**AC:** AC-01, AC-07, AC-08, AC-10.

### FR-17 Eksport: MP4, SRT, CSV/JSON [M]
- SRT: so'z vaqtlari CutMap orqali chiqish vaqtiga o'tkaziladi; satr ≤ 42 belgi, ≤ 2 qator, 1–7 s, gap chegarasida bo'lish.
- Slayd vaqtlari CSV: `slide_no, title, src_start, src_end, out_start, out_end, layout, source(log|ai|manual), confidence`.
- Fayl nomlari: `<fan>_<dars>_<mavzu>_v<N>.mp4` (sozlanadi), versiya avtomatik oshadi.

### FR-18 Premiere/DaVinci paketi [T]
- `premiere/` papkasi: `sequence.xml` (FCP7 xmeml v5), `background.png`, `slides_warped/*.png` (kanvas o'lchamida,
  allaqachon ekran joyida), `slides_full/*.png`, `teacher.mov` (ProRes 4444, alfa, **kesilmagan asl vaqt chizig'ida**,
  kanvasdagi yakuniy joyida, keyed + Eye Contact + rang), `audio.wav` (tozalangan, kesilmagan).
- XML: V1 fon, V2 slaydlar (oraliqlar bo'yicha), V3 o'qituvchi, A1 audio. Kesishlar V3/A1 klip in/out nuqtalari bilan
  ifodalanadi — montajchi Premiere'da kesishni o'zgartira oladi. Hech qanday effekt/transform ishlatilmaydi.
- [I] OTIO (Premiere 25.6+) — FCP7 XML ishlagandan keyin.

**AC:** Premiere Pro (buyurtmachidagi versiya) va DaVinci Resolve'da sinov loyihasi ochiladi, kadrlar va audio joyida,
render natijasi MP4 bilan vizual mos.

### FR-19 QA hisobot [M]
Avtomatik tekshiruvlar, natija `qa.json` va UI'da: kadr soni va davomiylik, A/V siljish, loudness va true peak,
qora/muzlagan kadrlar, har kadrda aynan bitta sahna, barcha slayd oraliqlari slayd fayliga ega, tasdiqlanmagan shubhali
joylar soni, SRT vaqtlari monoton, chiqish faylini ffprobe bilan qayta o'qish.

### FR-20 Navbat, rejalashtiruvchi, resume [M]
- Global navbat (SQLite `queue.db`): vazifa turi, loyiha, holat (`navbatda`, `ishlanmoqda`, `tayyor`, `xato`,
  `toʻxtatildi`), progress, log yo'li, urinishlar soni.
- Har vazifa resurs e'lon qiladi: `vram_mb`, `nvenc`, `nvdec`, `cpu_heavy`, `pptx`, `exclusive`.
- Qabul qoidasi: Σ`vram_mb` ≤ 13 000; NVENC ≤ 2; NVDEC ≤ 1; `cpu_heavy` ≤ 2; `pptx` ≤ 1; `exclusive` yolg'iz.
- Har vazifa alohida jarayon (`python -m darsstudio.worker <job_id>`), progress stderr/WebSocket orqali
  (Eye Contact'dagi `PROGRESS`/`OUTPUT` protokoli kabi).
- To'xtatish: jarayon daraxti o'ldiriladi; qayta boshlash chunk checkpoint'dan davom etadi.
- Xato bo'lsa 1 marta avtomatik qayta urinish (VRAM yetishmasligi bo'lsa — boshqa GPU vazifalar tugashini kutib).
- Kechki rejim: bir nechta loyihaning "tekshiruvgacha" bosqichlari navbatga qo'yiladi; ertalab faqat tekshirish qoladi.

**AC:** AC-10, AC-11.

### FR-21 Doctor [M]
Ishga tushishda va so'rov bo'yicha: GPU nomi va arxitekturasi, drayver (≥ 570, pin qilingan versiya), `torch.cuda`
mavjudligi va capability (12, 0), NVENC 1 kadr sinovi, Maxine (Eye Contact `doctor`), ffmpeg versiyasi (7.1.1),
modellar va hash'lari, PowerPoint/LibreOffice, bo'sh disk, RAM, CPU mikrokod (HW-2). Muammo — banner + sabab +
yechim (Eye Contact'dagi `DoctorBanner` uslubi).

### FR-22 Offline [M]
Ishga tushgandan keyin tarmoq talab qilinmaydi: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`; server faqat
`127.0.0.1` ga bog'lanadi; modellar `tools/fetch_models.py` bilan bir marta yuklanadi va hash bilan tekshiriladi.

### FR-23 Sozlamalar va profillar [M]
Eksport profillari, loudness profili, standart shablon, lug'at, ASR modeli tanlovi, ishchi papka, kesh siyosati
(tayyor eksportdan N kun keyin proxy va oraliq keshlarni o'chirish, manba va eksportga tegmaslik).

---

## 7. Nofunksional talablar

| ID | Talab | Maqsad |
|---|---|---|
| NFR-01 | Unumdorlik | 3.8-bo'lim jadvali |
| NFR-02 | VRAM | Har vazifa e'lon qilganidan ≤ 10% ko'p; jami ≤ 13 GB |
| NFR-03 | RAM | Dars Studio jami ≤ 32 GB |
| NFR-04 | Barqarorlik | 3 ta 25 daqiqalik loyiha ketma-ket, crash va progress yo'qolishisiz |
| NFR-05 | Tiklanish | Jarayon o'ldirilsa yoki kompyuter qayta yuklansa, vazifa oxirgi checkpoint'dan davom etadi; loyiha holati yo'qolmaydi |
| NFR-06 | Offline va maxfiylik | FR-22; manba videolar hech qayerga yuborilmaydi; telemetriya yo'q |
| NFR-07 | Determinizm | Bir xil kirish va sozlamalar → bir xil qarorlar (chegaralar, kesishlar); piksellar GPU tufayli ±1 farq qilishi mumkin |
| NFR-08 | Til | UI, xatolar, jurnal, qo'llanma — o'zbek (lotin). UI'da `oʻ`, `gʻ` uchun U+02BB |
| NFR-09 | Jurnal | Har vazifa uchun JSON-lines jurnal + o'zbekcha qisqa xabar; oxirgi 20 MB saqlanadi |
| NFR-10 | Uyqu | Vazifa ishlayotganda tizim uxlamaydi (HW-6) |
| NFR-11 | Portativlik | Papka nusxalanib ishga tushadi; administrator huquqi va o'rnatish kerak emas (PowerPoint/LibreOffice bundan mustasno) |
| NFR-12 | Litsenziyalar | 10.2-bo'limdagi ro'yxat; GPL/AGPL kutubxonalar Python jarayoniga import qilinmaydi (ffmpeg — alohida exe) |

---

## 8. Ma'lumot modeli

### 8.1 Asosiy tamoyillar
- Barcha vaqt oraliqlari **asl video kadr indekslarida**, yarim ochiq `[start, end)`.
- fps — `Fraction` (masalan `30000/1001`). Audio namuna indeksi: `round(frame * 48000 / fps)` Fraction bilan.
- Chiqish kadr indekslari faqat `TimeMap` orqali olinadi va saqlanmaydi (kesh sifatida hisoblanadi).
- Har model `schema_version` ga ega; migratsiyalar `project/migrations.py` da.

### 8.2 Pydantic modellar (soddalashtirilgan)

```python
class MediaAsset(BaseModel):
    id: str                      # hash (FR-01)
    path: str
    kind: Literal["video", "pptx", "pdf", "image", "audio", "slide_log"]
    probe: dict                  # ffprobe natijasi (fps Fraction satr ko'rinishida)
    cfr_path: str | None         # VFR bo'lsa normallashtirilgan nusxa

class Slide(BaseModel):
    index: int                   # 1..N
    title: str
    body: str
    notes: str
    ocr: str | None
    png_4k: str
    warped_png: str | None       # shablonga bog'liq kesh
    warnings: list[str]          # animatsiya, video, shrift

class Word(BaseModel):
    text: str
    start_ms: int
    end_ms: int
    conf: float

class SlideSpan(BaseModel):
    start: int; end: int         # asl kadrlar
    slide: int
    source: Literal["log", "ai", "manual"]
    confidence: float
    approved: bool

class LayoutSpan(BaseModel):
    start: int; end: int
    layout: Literal["A", "B", "C"]
    suggested: bool

class CutProposal(BaseModel):
    start: int; end: int         # olib tashlanadigan asl kadrlar
    reason: Literal["pause", "manual"]
    status: Literal["taklif", "tasdiqlangan", "rad_etilgan"]

class EyeOffSpan(BaseModel):
    start: int; end: int

class KeySettings(BaseModel):
    key_cbcr: tuple[float, float]
    tolerance: float; softness: float; spill: float
    choke_px: float; feather_px: float
    garbage_polys: list[list[tuple[int, int]]]
    keep_polys: list[list[tuple[int, int]]]
    edge_refine: bool; light_wrap: float

class TeacherPlacement(BaseModel):
    scale: float; x: int; y: int  # kanvasdagi joy
    color: dict                   # exposure, temp, tint, saturation

class Project(BaseModel):
    schema_version: int
    id: str; name: str
    meta: dict                    # fan, mavzu, o'qituvchi, dars raqami
    assets: list[MediaAsset]
    fps: str                      # Fraction
    total_frames: int
    template_id: str
    slides: list[Slide]
    words: str                    # yo'l: cache/asr/words.parquet
    slide_spans: list[SlideSpan]
    layout_spans: list[LayoutSpan]
    cuts: list[CutProposal]
    eye_off: list[EyeOffSpan]
    key: KeySettings
    placement: TeacherPlacement
    eye_contact: dict             # lid_open, holat, eyepatch yo'li va hash
    exports: list[dict]           # versiya, profil, yo'l, qa natijasi
```

Invariantlar (validatorlarda va testlarda): `slide_spans` va `layout_spans` butun `[0, total_frames)` ni bo'shliqsiz
va ustma-ust tushmasdan qoplaydi; tasdiqlangan kesishlar so'z ichiga tushmaydi; har chiqish kadrida aynan bitta sahna.

### 8.3 Shablon (`templates/<id>/template.json`)

```json
{
  "id": "studio_blue_v1",
  "canvas": [1920, 1080],
  "background": "background.png",
  "screen_quad": [[212, 188], [1004, 214], [998, 662], [206, 690]],
  "screen_aspect": "16:9",
  "teacher_anchor": [1080, 40, 1880, 1080],
  "safe_margin_px": 24,
  "logo": {"file": "logo.png", "pos": [40, 32], "height": 64},
  "lower_third": {"style": "default", "duration_s": 6},
  "transitions": {"slide_frames": 8, "layout_frames": 12},
  "fullscreen": {"fit": "contain", "pillarbox_color": "#000000"},
  "key_defaults": {}
}
```

### 8.4 Loyiha papkasi

```
<Ishchi papka>/<loyiha>/
  project.json            # 8.2, atomik yozish (tmp + os.replace)
  history/                # buyruqlar jurnali (undo/redo), oxirgi 500 ta
  cache/
    media/                # cfr nusxa (kerak bo'lsa), proxy_540p.mp4
    audio/                # src_48k.wav, asr_16k.wav, denoised_48k.wav, loudness.json
    asr/                  # words.parquet, segments.json, bench natijalari
    slides/               # 4k/*.png, warped/<template>/*.png, text.json
    sync/                 # slide_log.csv, beep.json, ai_align.json
    eyepatch/             # Eye Contact patchlari (EC-4)
    render/               # chunk segmentlari, checkpoint JSON
  exports/<versiya>/      # mp4, srt, csv, json, qa.json, premiere/
  logs/
```

---

## 9. Algoritmlar

### 9.1 Keyer (GPU, PyTorch)
1. Kirish: yuv420p kadr (patch qo'llangan). Y to'liq o'lchamda, U/V yarim o'lchamda.
2. **Chroma upsampling**: U/V ni luma'ga tayangan holda kattalashtirish (joint bilateral yoki guided upsampling,
   radius 2–3 px). Oddiy bilinear — zaxira. Bu 4:2:0 materialda chegaradagi "zinapoya"ni kamaytiradi.
3. Diapazon va matritsa bo'yicha normallashtirish (manba: BT.709, to'liq diapazon — probe'dan).
4. Matte: `d = ||(Cb, Cr) − key||`; `alpha = smoothstep(tol, tol + soft, d)`; luma bo'yicha qorong'i/yorug' zonalar
   uchun ixtiyoriy tuzatish.
5. Garbage: `alpha = 0` garbage ko'pburchaklarida, `alpha = 1` keep ko'pburchaklarida (statik, bir marta rasterlanadi).
6. Choke/feather: morfologik eroziya (px) + Gauss yumshatish.
7. [T] Chegara aniqlash: Y kanalini yo'riqchi qilib guided filter (radius 4–8, eps sozlanadi).
8. Spill suppression: chegara zonasida `G' = min(G, max(R, B) + k)` (k sozlanadi), rang balansi saqlanadi.
9. [I] Vaqt bo'yicha barqarorlik: harakat kichik bo'lgan piksellarda alfa EMA (miltillashga qarshi), faqat sinovdan keyin.
10. Chiqish: premultiplied RGBA float16.

### 9.2 Slayd perspektivasi
- Ekran 16:9 deb olinadi; slayd nisbati boshqacha bo'lsa 16:9 maydonga pillarbox bilan joylanadi.
- Gomografiya: `cv2.getPerspectiveTransform(src_rect_4k, quad × 2)`; 4K slayd 3840×2160 kanvasga `INTER_CUBIC` bilan
  warp qilinadi, keyin `INTER_AREA` bilan 1920×1080 ga kichraytiriladi (supersampling). Chegara 1 px anti-alias.
- Natija RGBA PNG keshlanadi (`warped/<template_hash>/<slide>.png`); shablon yoki slayd o'zgarsa qayta hisoblanadi.
- Test: warp qilingan alfa maskasi `screen_quad` ko'pburchagidan 1 px dan ortiq chiqmaydi.

### 9.3 O'qituvchini joylashtirish
- Har 2 s dan bitta kadr (jami ~750) keyer bilan matte qilinadi (540p yetarli), birlashma bounding box (98-persentil,
  tasodifiy shovqinsiz) olinadi.
- Masshtab: bounding box `teacher_anchor` ichiga sig'adi, boshdan yuqori chegaragacha ≥ 3% bo'shliq; joy — anchor
  pastki markaziga tekislangan (tana kesimi pastda bo'lsa).
- Foydalanuvchi o'zgartirishi mumkin; kadr bo'yicha framing yo'q.
- Ogohlantirish oraliqlari: matte anchor/kanvas chetiga tegsa yoki garbage chegarasiga tegsa (≥ 5 ketma-ket kadr).

### 9.4 AI slayd moslashtirish
1. **Segmentlar**: ASR gaplari, 6–12 s oynalarga birlashtiriladi (gap chegarasini buzmasdan).
2. **Slayd matni**: sarlavha (vazn 2.0), asosiy matn (1.0), eslatmalar (1.5), OCR (0.7), [I] VLM tavsifi (0.7);
   normallashtirilgan (FR-06).
3. **O'xshashlik**: `S = a·cos(emb_seg, emb_slide) + b·cos(tfidf_char(3..5)_seg, tfidf_char_slide) + c·keyword_hits`;
   `a, b, c` `align_eval` bilan tanlanadi (boshlang'ich 0.6, 0.3, 0.1). Har segment qatori z-normallashtiriladi.
4. **DP (Viterbi)**: holat — slayd raqami. O'tishlar: qolish 0, keyingi `λ1` (0.5), bittasini o'tkazib yuborish `λ2`
   (2.5), bitta orqaga `λ3` (3.0), boshqalari taqiqlangan. Emissiya `−log softmax(S/τ)`.
5. **Minimal turish**: slayd < 3 s bo'lsa qo'shnisiga qo'shiladi (jurnal rejimida emas).
6. **Ishonchlilik**: forward-backward posterior; chegara ishonchliligi = chegaraning ikki tomonidagi 2 segment
   posteriorlari minimumi.
7. **Chegarani aniqlash**: o'tish segmenti ichida chegara eng yaqin gap boshiga yoki ≥ 0.3 s pauzaga suriladi.
8. **Qisqa qaytishlar**: bitta orqaga o'tish ≤ 10 s bo'lsa "shubhali" belgilanadi (filtrlanmaydi, inson qaror qiladi).

### 9.5 Pauza aniqlash va TimeMap
- Pauza = ketma-ket so'zlar orasidagi bo'shliq ∩ VAD nutqsiz oraliq, uzunligi ≥ `min_pause`.
- Kesiladigan qism: pauza o'rtasidan `keep_pause` qoldirib (har tomonda `keep_pause/2`).
- `TimeMap(keep_ranges: list[tuple[int,int]])`: `src_to_out(f) -> int | None`, `out_to_src(f) -> int`,
  `map_span(s, e) -> list[tuple[int,int]]`, `out_total`, `audio_sample(f)`. Hammasi butun son/Fraction.

### 9.6 Beep sinxroni
- Shablon: 1 kHz, 300 ms, Hann oyna. Audio 16 kHz'da matched filter (FFT korrelatsiya), birinchi 120 s ichida qidiriladi.
- Aniqlik: korrelatsiya cho'qqisi parabolik interpolatsiya bilan; SNR past bo'lsa — foydalanuvchiga qo'lda belgilash.

### 9.7 Ko'z patchini qo'llash
- `eyepatch/` meta.json: format versiyasi, manba asset hash, o'lcham, fps, pix_fmt, rang matritsasi/diapazon,
  Eye Contact `cfg_key`, chunk ro'yxati.
- Chunk (`chunk_00000.npz`, zstd/zlib siqilgan): `frame_idx[int32]`, `box[int16, N×4]`, `y_data`, `uv_data`,
  `y_mask` (bitpack), `uv_mask` (bitpack), `offsets`.
- Qo'llash: `out = orig + w·(patch − orig)` faqat maska ichida, `w ∈ [0, 1]` (Eye Contact o'chiq oraliq rampasi).
  `w = 1` da natija Eye Contact'ning o'z chiqishi bilan bayt-aniq (Y).

### 9.8 Rang
- Ichki ishlov: RGB float16, BT.709. Kirish to'liq diapazon → chiqish limited range (`tv`), teglar aniq yoziladi.
- Fon/slayd PNG'lar sRGB deb qabul qilinadi; v2.0 da kompozit gamma fazosida (chiziqli fazo — [I]).
- O'qituvchi rang tuzatishlari 9.1 dan keyin, kompozitdan oldin.

### 9.9 Audio zanjiri
`src_48k.wav` → DeepFilterNet → HPF 80 Hz → TimeMap bo'yicha kesish (har kesishda 10 ms equal-power crossfade) →
intro/outro qo'shish → loudnorm 1-o'tish (o'lchov) → 2-o'tish (chiziqli) → AAC 192k. Chiqish audio uzunligi =
chiqish video uzunligi (±1 namuna bloki).

---

## 10. Texnologiyalar

### 10.1 Stek

| Qatlam | Tanlov | Versiya |
|---|---|---|
| Python | python-build-standalone (portativ) | 3.11.x |
| Backend | FastAPI + uvicorn, WebSocket | so'nggi barqaror |
| Frontend | React 18 + TypeScript + Vite; holat: Zustand; testlar: Vitest (+ [T] Playwright) | |
| Oyna | pywebview (Windows'da Edge WebView2) | |
| Video | ffmpeg / ffprobe 7.1.1 (D-13), rawvideo pipe | qotirilgan |
| GPU hisob | PyTorch `cu128` | ≥ 2.7 |
| ASR | faster-whisper (CTranslate2 ≥ 4.5) va/yoki CTC model (transformers/onnxruntime) | benchmark bo'yicha |
| VAD | Silero VAD | |
| Embedding | BGE-M3 yoki multilingual-e5-large yoki Qwen3-Embedding-0.6B | benchmark bo'yicha |
| Leksik | scikit-learn TF-IDF (char n-gram), rapidfuzz | |
| Audio | DeepFilterNet3, soundfile, soxr, numpy | |
| PPTX | pywin32 (PowerPoint COM), python-pptx, LibreOffice (zaxira), pypdfium2 | |
| OCR | Tesseract 5 + `uzb`, `uzb_cyrl`, `rus`, `eng` | [T] |
| Ma'lumot | Pydantic v2, SQLite (navbat), pyarrow (parquet) | |
| Eye Contact | `engines/eye-contact` submodule (Maxine AR SDK v0.8.7 Blackwell) | EC-1..EC-5 dan keyin |
| Sifat | ruff, mypy (asosiy modullar strict), pytest, hypothesis | |

### 10.2 Litsenziya qoidasi
- Ruxsat: MIT, BSD, Apache-2.0, PSF, ISC, MPL-2.0, LGPL (dinamik). Model og'irliklari uchun ham xuddi shu.
- Taqiqlangan: AGPL (masalan PyMuPDF), "non-commercial" model litsenziyalari, litsenziyasi noma'lum modellar.
- ffmpeg GPL build — alohida bajariladigan fayl sifatida; paket tashqariga berilsa GPL talablari bajariladi.
- NVIDIA Maxine EULA: qisqartirilgan SDK nusxasini qayta tarqatish shartlari tekshiriladi (ochiq savol O-07).
- Har model `models/manifest.json` da: `name, version, source_url, sha256, license, vram_mb, size_mb`.

---

## 11. Repo tuzilishi

```
dars-studio/
  CLAUDE.md
  README.md                    # o'zbekcha qo'llanma
  docs/
    TEXNIK_TOPSHIRIQ.md        # shu hujjat
    BOSQICHLAR.md              # Claude Code uchun bosqichlar
    QAROR_JURNALI.md           # ADR: sana, qaror, sabab, o'lchov natijalari
  darsstudio/
    config.py  paths.py  doctor.py  logging_setup.py  power.py
    media/      probe.py  ffmpeg.py  frames.py  normalize.py  proxy.py  timemap.py
    project/    model.py  store.py  commands.py  migrations.py
    slides/     render_pptx.py  render_pdf.py  extract.py  ocr.py  warp.py
    audio/      extract.py  denoise.py  loudness.py  vad.py  mix.py
    asr/        engines/ (base.py, whisper_ct2.py, ctc.py)  word_align.py  uz_text.py  glossary.py
    sync/       slide_log.py  beep.py  ai_align.py  metrics.py
    render/     keyer.py  compositor.py  templates.py  placement.py  transitions.py
                overlays.py  eyepatch.py  color.py  renderer.py
    export/     mp4.py  srt.py  tables.py  fcp7xml.py  premiere_pkg.py  qa.py
    jobs/       resources.py  scheduler.py  queue_db.py  worker.py  protocol.py
    api/        app.py  routes/  ws.py
  ui/                          # React + TS + Vite
  engines/eye-contact/         # git submodule
  templates/                   # shablonlar (fon, quad, logo)
  models/manifest.json
  tools/  make_test_media.py  asr_bench.py  align_eval.py  render_bench.py  vram_probe.py
          fetch_models.py  slide_logger.py  package.py
  tests/  unit/  media/  gpu/  windows/  fixtures/
  runtime/                     # .gitignore: python, ffmpeg, maxine
```

---

## 12. Eye Contact moduliga o'zgarishlar (`engines/eye-contact`)

| ID | O'zgarish | Sabab (sinovda topilgan) |
|---|---|---|
| EC-1 [M] | `concat()` video va audio `start_time` farqini saqlasin (`-itsoffset`); `eval.py` ga `av_offset_ms` metrikasi (chegara ±1 kadr) | Manbada video audiodan 52 ms keyin boshlangan MOV'da natijada farq yo'qoldi: ovoz 52 ms kechikadi |
| EC-2 [M] | VFR bo'lsa jami kadr soni `round(davomiylik × fps)` dan olinsin, yoki VFR aniq xato bilan rad etilsin; sintetik VFR test | 6 kadri tushgan VFR klipda natija 0.2 s qisqa chiqdi, xato berilmadi; chunk chegarasidan keyin 1 kadr siljish |
| EC-3 [M] | Resume kaliti (`cfg_key`) kirish fayli identifikatorini ham o'z ichiga olsin (hajm, `mtime_ns`, bosh/oxir hash) | Bir xil nomli boshqa video bilan eski chunk'lar qo'shilib ketishi mumkin |
| EC-4 [M] | `--patches-out DIR` rejimi: encode yo'q, 9.7 formatidagi patchlar yoziladi; chunk + resume saqlanadi | D-02 |
| EC-5 [M] | GPU'siz testlar: `GazeRedirector` stub bilan pipeline testi (Linux'da ham), sintetik media bilan | Hozirgi testlar faqat Windows + GPU + haqiqiy klipda ishlaydi |
| EC-6 [I] | 4:2:2 / 10-bit kirishni qo'llash (patch Y kanalida, U/V 4:2:2 to'rida) | 17-bo'lim |

Eye Contact'ning mavjud xatti-harakati (`lid_open`, iris toni, `FaceROI`, chegaralar) o'zgarmaydi.

---

## 13. Test strategiyasi

### 13.1 Pytest belgilari
- `unit` — sof Python, Linux/Windows, GPU'siz (TimeMap, uz_text, DP, SRT, XML, model invariantlari).
- `media` — ffmpeg kerak, GPU'siz (probe, CFR, A/V siljish, chunk/concat, audio zanjiri, proxy CPU rejimda).
- `gpu` — CUDA kerak (keyer, renderer, embedding, ASR, Eye Contact patch).
- `windows` — PowerPoint COM, slide_logger, pywebview, power.py.
- `pilot` — haqiqiy darslar (`DARS_PILOT_DIR` muhit o'zgaruvchisi), qo'lda ishga tushiriladi.

### 13.2 Majburiy testlar
- TimeMap: hypothesis bilan property testlar.
- Har eksport: ffprobe bilan qayta o'qish, kadr soni, davomiylik, A/V siljish.
- Renderer: sintetik yashil fon klipida alfa va kompozit oltin rasmlar bilan solishtirish (tolerantlik bilan).
- DP moslashtirish: sintetik segment/slayd matnlarida kutilgan chegaralar.
- XML: xmeml sxemasi bo'yicha tuzilma, klip in/out = TimeMap.

### 13.3 Sintetik test media (`tools/make_test_media.py`)
ffmpeg `lavfi` bilan, repo'ga qo'shilmaydi, test boshida yaratiladi:
1. Yashil fon + harakatlanuvchi "odam" (ellips + tekstura) + chetida oq "devor" polosasi — keyer uchun.
2. Video audiodan 52 ms keyin boshlangan MOV (PCM) — A/V siljish.
3. 29.97 fps MP4 (AAC) — Fraction va priming.
4. VFR klip (har 50-kadrdan keyin bitta kadr tushgan) — CFR.
5. Ma'lum vaqtda 1 kHz beep — beep sync.
6. Raqamli taymer ko'rsatilgan klip — kadr aniqligi (har kadr raqami OCR'siz, piksel kodi bilan).
7. python-pptx bilan yaratilgan 12 slaydli PPTX (ma'lum sarlavha va matnlar, eslatmalar, bitta animatsiyali slayd).

### 13.4 Benchmark vositalari
`asr_bench.py`, `align_eval.py`, `render_bench.py` (kadr/s, VRAM, CPU), `vram_probe.py`. Natijalar
`docs/QAROR_JURNALI.md` ga sana va commit bilan yoziladi.

---

## 14. Qabul mezonlari

| ID | Mezon | Chegara |
|---|---|---|
| AC-01 | Import | 10/15/25 daqiqalik haqiqiy video + PPTX ochiladi, slayd soni mos |
| AC-02 | Chroma key | FR-11 AC; garbage hududida alfa 0; montajchi tekshiruv ro'yxati bo'yicha qabul |
| AC-03 | Slayd sinxroni | Jurnal rejimi: ≥ 98% chegara ±0.5 s. AI rejimi: ≥ 85% chegara ±2 s, shubhali ≤ 20% |
| AC-04 | Kompozitsiya | Slayd ekran ramkasidan chiqmaydi; o'qituvchi anchor ichida |
| AC-05 | Sahnalar | Bitta videoda A→B→A xatosiz, o'tishlar sozlangan uzunlikda |
| AC-06 | ASR | Tanlangan model CER ≤ 10% (3 fan bo'yicha, pilotda tasdiqlanadi) |
| AC-07 | Lab-sync | A/V siljish ≤ ±1 kadr (25 fps da 40 ms) kirishdagi siljishga nisbatan; davomiylik farqi ≤ 1 kadr |
| AC-08 | Loudness | Integrated −16 ± 1 LUFS (yoki profil), true peak ≤ −1.5 dBTP |
| AC-09 | Eye Contact | FR-10 AC metrikalari |
| AC-10 | Unumdorlik | 3.8-bo'lim; yakuniy render ≥ 80 kadr/s; VRAM ≤ 13 GB; RAM ≤ 32 GB |
| AC-11 | Barqarorlik | 3 ta 25 daqiqalik loyiha ketma-ket; render o'rtasida jarayon o'ldirilib, qayta boshlanganda davom etadi |
| AC-12 | Eksport | MP4 standart pleyerlarda ochiladi; Premiere va DaVinci'da XML paketi ochiladi (FR-18) |
| AC-13 | Offline | Internet uzilgan holda to'liq ish (import → eksport) va qayta ochish |
| AC-14 | Montajchi vaqti | 25 daqiqalik darsga ≤ 45 daqiqa (pilotda o'lchanadi); hozirgi qo'lda montaj vaqti 0-bosqichda yozib olinadi |
| AC-15 | Tiklanish | Dastur yopilib ochilganda barcha tuzatishlar va undo tarixi joyida |

---

## 15. Bosqichlar (qisqa)

Batafsil — `docs/BOSQICHLAR.md`. Qaror nuqtalari (G):

| Bosqich | Natija | Qaror nuqtasi |
|---|---|---|
| B0 | Repo skeleti, tooling, doctor, sintetik media | |
| B1 | Eye Contact EC-1..EC-5 | |
| B2 | Media qatlami, TimeMap, loyiha modeli | |
| B3 | **Vertikal kesim**: qo'lda CSV slayd vaqtlari bilan MP4 (A/B, keyer, kompozit) | **G1**: haqiqiy darsda keyer va kompozit sifati qabul qilinadimi |
| B4 | Audio, ASR, so'z vaqtlari, uz_text, benchmark | **G2**: ASR modeli tanlovi |
| B5 | Slayd sinxroni (jurnal + AI), align_eval | **G3**: AI moslashtirish aniqligi yetarlimi, yoki jurnal rejimi majburiy qilinadimi |
| B6 | Pauza kesish, Eye Contact patchlari, o'tishlar, brending, subtitr | |
| B7 | Backend API, navbat, rejalashtiruvchi, worker'lar | |
| B8 | UI (React) | |
| B9 | Eksportlar, Premiere paketi, QA | |
| B10 | Portativ paket, offline, qo'llanma, barqarorlik testlari | |
| B11 | Pilot (3–10 dars), sozlash, qabul | **G4**: qabul |

---

## 16. Xavflar

| Xavf | Ehtimol | Ta'sir | Choralar |
|---|---|---|---|
| O'zbekcha ASR sifati past | O'rta | Yuqori | Benchmark (G2); jurnal rejimi (FR-07) slayd sinxronini ASR'dan mustaqil qiladi |
| 4:2:0 materialda soch/qo'l chegarasi | Yuqori | O'rta | Chroma upsampling, guided filter, garbage matte; [I] AI matting; 17-bo'limdagi 4:2:2 yozish |
| CPU degradatsiyasi / beqarorlik | O'rta | Yuqori | HW-1..HW-3, doctor ogohlantirishi |
| VRAM yetishmasligi | Past | O'rta | Budjet (3.4), alohida jarayonlar, rejalashtiruvchi |
| PowerPoint yo'q yoki shrift farqi | O'rta | O'rta | LibreOffice zaxira, shrift tekshiruvi, ogohlantirish |
| Brauzerda kadr-aniq preview | O'rta | O'rta | Qisqa GOP proxy, server tomonda oraliq render |
| Premiere XML importi kutilganidek emas | O'rta | Past | Effektsiz qatlamlar (D-11), ikkala NLE'da sinov |
| Litsenziya muammolari | Past | Yuqori | 10.2-bo'lim, manifest |
| Jump cut'lar ko'zga tashlanadi | O'rta | O'rta | Sozlanadigan `min_pause`, crossfade, B sahnada kesishni afzal ko'rish |

---

## 17. Keyingi bosqich g'oyalari (v2.0 ga kirmaydi)
- **4:2:2 yozish**: Canon 5D Mark III HDMI orqali toza 4:2:2 8-bit signal beradi (firmware 1.2.x); tashqi rekorderda
  ProRes 422 HQ yozilsa keying sifati sezilarli oshadi. Blackwell 4:2:2'ni apparatda dekodlaydi. Kerak bo'ladi: EC-6,
  FR-02/FR-11'da 4:2:2 yo'li. Avval kamera va rekorder bilan sinov.
- C sahna (fullscreen + PiP), animatsiya build'larini alohida ko'rsatish, chiziqli rang fazosida kompozit, 4K chiqish,
  AI matting, VLM slayd tavsifi, OTIO eksport.

---

## 18. Ochiq savollar (javob kelguncha default qaror ishlatiladi)

| ID | Savol | Default |
|---|---|---|
| O-01 | Ish stansiyasida PowerPoint o'rnatilganmi? | LibreOffice zaxira yo'li ishlaydi; PowerPoint topilsa u ishlatiladi |
| O-02 | Suratga olishda o'qituvchi slaydlarni noutbukda o'zi almashtiradimi (jurnal rejimi mumkinmi)? | AI rejimi asosiy; jurnal ixtiyoriy |
| O-03 | Ishchi disk hajmi va bo'sh joy | ≥ 500 GB bo'sh joy talab qilinadi, doctor tekshiradi |
| O-04 | Premiere Pro versiyasi, DaVinci ishlatiladimi | FCP7 XML ikkalasi uchun |
| O-05 | Chiqish qayerga: YouTube yoki LMS? | Loudness −16 LUFS, `web` profili |
| O-06 | 3 ta pilot dars uchun qo'lda tuzatilgan transkript (5 min) va slayd chegaralari kim tayyorlaydi? | Buyurtmachi; UI'da belgilash vositasi beriladi |
| O-07 | Maxine SDK'ni qisqartirilgan holda paketga qo'shish NVIDIA EULA bo'yicha ruxsat etilganmi? | Ichki foydalanish; tashqariga berishdan oldin aniqlanadi |
| O-08 | Intro/outro, logo va shriftlar tayyormi? | Shablonda ixtiyoriy |
| O-09 | Hozirgi qo'lda montajga bir dars uchun qancha vaqt ketadi? | 0-bosqichda o'lchanadi (AC-14 uchun baza) |

---

## 19. Manbalar va asoslar
- TZ v1.0 (24.10.2026) va unga sharh.
- Eye Contact moduli: `TEXNIK_TOPSHIRIQ.md` v2.0 (o'lchovlar: 62–70 kadr/s, VRAM 0.9 GB, identity 0.993, VMAF 97.8).
- Eye Contact sinovi (2026-10-24, Linux, ffmpeg 6.1, Maxine o'rniga stub): chunk chegaralarida kadr aniqligi to'g'ri;
  EC-1 va EC-2 muammolari topildi. Windows'da ffmpeg 7.1.1 bilan qayta tekshirilsin.
- NVIDIA: RTX 5070 Ti spetsifikatsiyasi (2 × NVENC 9-avlod, 1 × NVDEC 6-avlod); Blackwell 4:2:2 apparat kodlash/dekodlash.
- Intel: 13/14-avlod Vmin Shift, mikrokod 0x12B (2024-09) va 0x12F (2025-05).
- faster-whisper: CUDA 12 + cuDNN 9; large-v2 fp16 ≈ 4.7 GB VRAM. Blackwell uchun CUDA 12.8+, CTranslate2 ≥ 4.5.
- O'zbekcha ASR modellar kartalari (HF): zero-shot Whisper large-v3 o'zbekchada CER ~28%; fine-tune modellar ancha yaxshi
  (mualliflar ma'lumoti, o'z darslarimizda tekshiriladi).
