# Qarorlar jurnali

Har yozuv: sana, bosqich, qaror yoki o'lchov, sabab, dalil (commit, fayl, buyruq). Yangi yozuvlar yuqoriga.

---

## 2026-10-26 — Denoise: DeepFilterNet3 rasmiy CLI

- Foydalanuvchi ruxsati bilan `deep-filter-0.5.6-x86_64-pc-windows-msvc.exe` (GitHub Rikorose/DeepFilterNet v0.5.6,
  MIT OR Apache-2.0, 26 912 256 bayt — reliz hajmi bilan mos; GitHub sha256 e'lon qilmagan, o'zimiz hisobladik
  `75e11fa1...7915`) `models/deep-filter/` ga, manifestga `deep-filter-cli` sifatida yozildi.
- `audio/denoise.py`: "auto" tartibi — CLI -> Python paket -> afftdn. CLI `-D -a <dB> -o <dir>`; chiqish manbaga
  FFT korrelyatsiya bilan namuna aniqligida tekislanadi va uzunligi manbaga tenglanadi (A/V qoidasi), so'ng HPF 80 Hz.
  Test: soxta CLI 480 namuna kechiktirib, 0.2 s uzun yozadi — natija lag 0, uzunlik teng.
- **O'lchandi (foydalanuvchi `.claude/settings.json` da ruxsat berganidan keyin):** namuna, atten 15 dB.
  Nutqsiz joylar RMS: 0–0.7 s -25.4 -> -40.8, 2.2–3.7 s -19.4 -> -34.4, 825–826.4 s -26.0 -> -41.2 dBFS (= 15 dB,
  chegara); 50 ms freymlar p5 -39.3 -> -42.9; nutq median -17.3 -> -17.7 dBFS. Tekislashdan keyin qoldiq siljish
  1 namuna (0.02 ms), uzunlik teng. Eksport v9: A/V 0 ms, QA faqat tasdiqlanmagan shubhali joylar.
- Kuzatildi: `test_scheduler.py::test_interrupted_jobs_requeued` to'liq to'plamda 1/3 marta yiqildi, alohida 6/6 o'tdi
  (yuklama ostida vaqt) — denoise o'zgarishiga aloqasiz, keyin ko'riladi.

---

## 2026-10-26 — Dars boshi/oxirini kesish; shovqin o'lchovi

- `cuts.trim_cuts`: birinchi salomlashish so'zidan ("assalomu", "salom", "hurmatli"...; boshidagi 60 s ichida)
  0.3 s oldingacha va oxirgi xayrlashish so'zidan ("ko'rishguncha", "xayr", "rahmat"...; oxirgi 60 s) 0.6 s keyindan
  oxirigacha kesiladi. Avtomatik tasdiqlanadi (`reason` "bosh"/"oxir", inson rad etishi mumkin); so'z invarianti
  (TZ 8.2) ularga qo'llanmaydi. Namuna: 0–3.84 s (montajchi 3.94 s kesgan) va 824.76 s dan oxirigacha.
  Eksport v8: 831.64 s, A/V 0 ms.
- Shovqin: manba (src_48k) 50 ms freymlar p5 -39 dBFS, nutq median -17 dBFS. Joriy `afftdn` (nr 15, nf -50)
  p5 ni 0.3 dB ga, eng kuchli sozlama (nr 25, nf -36) 2.7 dB ga pasaytiradi — statsionar filtr bu shovqinni olmaydi.
  Neyron denoiser kerak: DeepFilterNet3 (MIT/Apache-2.0). `deepfilternet` pip paketi numpy'ni 1.26 ga tushiradi va
  torchaudio talab qiladi (venv'ni buzadi) — rasmiy Rust CLI (`deep-filter-0.5.6-x86_64-pc-windows-msvc.exe`, model
  ichida) varianti foydalanuvchi ruxsatini kutmoqda. Montajchi namunasi ham denoise qilinmagan (p5 -39 dBFS).

---

## 2026-10-26 — O'qituvchi tiniqligi, subtitr ixtiyoriy

- Foydalanuvchi: o'qituvchi xira. O'lchov (yuz hududi, Laplacian dispersiyasi, 1080p): v6 1297; o'qituvchi
  kichraytirish bilinear+antialias -> **bicubic+antialias**, keyin premult RGB'ga unsharp mask (sigma 1, kuch 1.0,
  natija alfa bilan cheklanadi): **1497**. Kuch 0.6 da 1412. Ko'z bilan montajchi namunasiga yaqin (manbaning o'zi
  yumshoq). Sozlash: `compositor.TEACHER_SHARPEN`.
- Topildi: `RENDER_VERSION` oshirilmagani uchun v5/v6 eski segment keshidan yig'ilgan (zoom blur 16 namuna
  qo'llanmagan). RENDER_VERSION 3, kesh kalitida sharpen ham bor.
- Subtitr default o'chiq (foydalanuvchi: hozircha kerak emas; UI'da katakcha bo'ladi). CLI: `export --srt`.
- Eksport v7: 837.28 s, A/V 0 ms, QA faqat tasdiqlanmagan shubhali joylar bo'yicha ogohlantirish.

---

## 2026-10-26 — Montajchi uslubi Studio'da: `akademiya` shabloni, o'tishlar, sahna qoidasi, signallar, intro/outro

**Qarorlar:**
- `templates/akademiya` (`tools/make_template.py` bilan): fon x0.9145 (-4, 0), ekran quad avtomatik topildi
  TL(15,20) TR(1026,141) BR(1026,698) BL(15,742) (qo'lda o'lchangandan +-1 px), o'qituvchi joyi shablonda qotirilgan
  (`teacher_placement`: 0.929 @ (692, 79)), logosiz.
- O'tishlar (`render/transitions.py`): A<->B — **zoom blur** (ekran markazi atrofida kattalashish + radial xiralik,
  16 namuna; 8 da alohida "nusxalar" ko'rindi), A ichida slayd -> slayd — **clock wipe** (soat 3 dan, soat miliga
  teskari). **O'tish endi chegaradan oldin tugaydi** (avval chegaradan keyin boshlanardi): yangi slayd ma'ruzachi
  yangi gapni boshlaganda to'liq ko'rinadi — G3 o'lchovi ham shuni ko'rsatdi (o'tish oxiri bilan median 0.38 s).
- Sahna qoidasi shablonda (`scene_policy`). TZ FR-12 (so'z soni) default bo'lib qoladi (D-qarorlari o'zgarmadi);
  `akademiya` da `a_then_b`: slayd almashganda **10 s A**, keyin B; qolgan qism < 10 s bo'lsa A; birinchi va oxirgi
  slayd A. 10 s — tayyor.mp4 dagi A bo'laklari (5–17 s) o'rtasi; tayyor2.mp4 da montajchi har slayd uchun alohida
  qaror qilgan (A 16–120 s) — qiymat taxminiy, inson tahrirlaydi.
- AI sinxron: "keyingi/navbatdagi slayd..." signali (oldidagi "xo'p/endi/demak" bilan) +-25 s ichida oldinga
  chegarani o'ziga tortadi. "ushbu/mazkur slayd" signal emas.
- Intro/outro (`render/bumpers.py`): shablondagi klip bir marta loyiha formatiga kodlanadi (kesh), video concat
  demuxer bilan qayta kodlashsiz, audio PCM bo'laklardan bir marta AAC. AAC'ni `-c copy` bilan ulash har chokda
  ~21 ms A/V siljish berdi (o'lchandi: video start 0.021 s) — shuning uchun audio alohida. SRT, slayd jadvali va QA
  intro uzunligiga suriladi. Intro -12 LUFS -> loudnorm -16.
- Overlay'lar: `akademiya` lower-third (ko'k gradient polosa y 870–982, ism Roboto Slab 700, 2 qator unvon, matn
  16 px/s chapga siljiydi, 8.6 s, fade'siz); mualliflik matni oxirgi slaydda (oxirgi 15 s dan ko'p emas), Noto Serif
  Italic, KATTA harflar. Shriftlar: Roboto Slab (Apache-2.0), Noto Serif (OFL) — litsenziya tekshirildi.

**O'lchovlar (namuna, commit shu yozuv bilan):**
- G3 (montajchi GT, 18 chegara): o'tish boshi bilan +-2 s **83% -> 94%**, median 1.26 s; o'tish oxiri bilan
  +-1 s 72% -> **89%**, median **0.38 -> 0.20 s**. Slayd 7 (-14.9 s) tuzaldi (+1.26). Qolgan katta xato: slayd 10
  (-4.1 s; signal "xo'p, parij..." — umumiy ibora emas).
- Eksport v5: 837.28 s (intro 5.36 + 826.56 + outro 5.36), QA: fayl/kadr soni/davomiylik ok, **A/V 0.0 ms**,
  -16.1 LUFS / TP -2.4 dBTP, qora/muzlagan kadr yo'q (B oraliqlari intro bilan surildi), SRT 195 titr.
  Ogohlantirish faqat tasdiqlanmagan shubhali joylar uchun.

**Ochiq:** zoom blur va lower-third harakatini inson montajchi namunasi bilan yonma-yon ko'rib baholashi kerak (G1).

---

## 2026-10-26 — Montajchi tayyorlagan namuna (`namuna/tayyor.mp4`) tahlili: uslub va G3 ground truth

**Vaqt bog'lanishi (audio korrelatsiya):** tayyor = manba + 1.421 s (manba boshidagi 3.94 s — "boshlasangiz bo'ladi"
kesilgan, o'rniga intro 5.36 s); manba ~622–624 s da yana 1.72 s kesilgan; oxirida outro (o'sha intro).

**Uslub (qo'lda o'lchangan):**
- Fon: `background.png` 2321x1230, x0.9145 kichraytirilgan, (-4, +1) siljigan; ekran quad kanvasda
  TL(14,21) TR(1025,141) BR(1026,699) BL(15,743) (fonda TL(20,22) TR(1126,154) BR(1126,763) BL(20,811)).
- O'qituvchi: SIFT+RANSAC (197 inlier) — masshtab **0.929**, manba (0,0) -> kanvas (692, 79), pastga tekislangan,
  markaz x ~1584. Logo overlay yo'q.
- Sahnalar: har slayd almashinuvida B (eski slayd to'liq ekran) -> **zoom blur** (~1.28 s) -> A (yangi slayd ekranda,
  o'qituvchi) ~5–17 s -> **zoom blur** (~1.0 s) -> B keyingi slaydgacha. A->A almashinuvlar (slayd 2, 3, 13, 15, 18,
  19): **clock wipe** (~1.0 s). Uzun A bo'laklar: kirish (64 s), 518–588, 627–694, 780–824. A 41%, B 59%.
- PPTX'da transition/animatsiya yo'q — hammasi NLE'da qo'shilgan.
- Lower-third: pastki chap ko'k gradient polosa, ism (qalin) + 2 qator unvon, sekin chapga siljiydi, dars boshidan
  ~8.6 s, fade'siz yo'qoladi. Oxirgi slaydda (~815 s dan) mualliflik huquqi matni (oq kursiv, qora yarim shaffof polosa).
- Intro -> dars va dars -> outro: hard cut. Loudness normallashtirilmagan: -14.5 LUFS, TP +0.5 dBTP; intro -12 LUFS.

**G3 (AI sinxron) — birinchi haqiqiy ground truth** (`docs/pilot/namuna_gt_slides.csv`, 18 chegara, montajchi
o'tishlari boshlanishi): ±1 s 22%, ±2 s 83%, median 1.28 s. O'tish **oxiri** (yangi slayd to'liq ko'ringan payt) bilan:
±1 s 72%, ±2 s 72%, median **0.38 s**. Katta xatolar: slayd 7 (-14.9 s), 10 (-4.1), 13 (-4.6) — uchalasida ma'ruzachi
aniq signal bergan ("xo'p, keyingi slaydimizda...", "xo'p, parij..."), AI bitta gapga oldin surgan, ishonchliligi
yuqori (0.96–1.0) — ya'ni xato "shubhali" deb belgilanmagan (AC: xatolarning >= 70% i belgilanishi kerak — bajarilmadi).
"keyingi/navbatdagi slayd" signallari 7/18 chegarada 0..4 s ichida.

**Takliflar (inson tasdig'idan keyin):** (1) o'tish chegaradan oldin tugasin (montajchi uslubi); (2) "keyingi slayd"
signal so'zlari chegarani shu gapga bog'lasin; (3) sahna qoidasi "A N s, keyin B" (N~8 s) — so'z soni qoidasi o'rniga;
(4) zoom blur va clock wipe o'tishlari; (5) `akademiya` shabloni (yuqoridagi o'lchovlar), lower-third va mualliflik
matni uslubi; (6) intro/outro (loudness -16 LUFS ga moslab).

---

## 2026-10-26 — HW-3 bajarildi: RAM barqarorlik sinovi

**Sinov:** OCCT Personal 17.1.10, Stability Test -> Memory, preset "Heat" (DDR5), 80% xotira (band: ~59.7 GB / 64 GB, 91%), Threads Auto, **1 soat**. XMP 6000 MT/s (2 x 32 GB KF560C36-32), BIOS 1836, mikrokod 0x133, Intel Default Settings.

**Natija: 0 xato ("No errors detected", Schedule - Completed).** RAM harorati 44 -> ~68.5 °C (kuzatilgan pik; Kingston chegarasi 85 °C). CPU: ~188-190 W, Vcore 1.53-1.55 V (yangi mikrokod chegarasida), yadrolar pik 90 °C, o'rtacha ~70 °C.

**Xulosa:** XMP 6000 barqaror, 5600 ga tushirish shart emas. Dars renderida Python jarayonlari ~6.6 GB ishlatadi — RAM bu sinovdagidek qizimaydi. HW-1..HW-4 hammasi yopildi.

---

## 2026-10-26 — HW-4: drayver qotirildi, Intel Default Settings tasdiqlandi

- `driver_pin.txt` = **610.88** (NVIDIA Studio/Game drayveri; shu versiya bilan render 144.8 kadr/s, Eye Contact, ASR, NVENC sinalgan). Versiya o'zgarsa `doctor` ogohlantiradi.
- BIOS 1836 da "Intel Default Settings" yoqilgan (foydalanuvchi tasdiqladi).
- HW-3 (RAM barqarorlik sinovi) — foydalanuvchi o'tkazadi.

---

## 2026-10-26 — HW-1 bajarildi: BIOS yangilandi

**Holat:** ASUS TUF GAMING Z790-PLUS WIFI BIOS 1603 (2023-12-04) -> **1836** (barqaror, 2026-04-16 sanali; "Update Intel microcode"), Intel ME 16.1.40.2765. CPU mikrokod 0x11F -> **0x133** (>= 0x12B/0x12F). `doctor`: mikrokod ok.

**RAM:** 2 x 32 GB KF560C36-32, ConfiguredClockSpeed 6000 MT/s (XMP yoqilgan). HW-3 (1 soat OCCT/MemTest) — hali o'tkazilmagan.

**Render (to'liq namuna, 20 664 kadr):** 127.6 kadr/s (qayta yuklashdan keyingi birinchi, sovuq disk keshi), keyin **144.8 kadr/s** (avval 147.3). VRAM pik 2 656 MB. Xato yo'q.

**Tekshirilmagan:** "Intel Default Settings" BIOS'da yoqilgani Windows'dan aniqlanmaydi — foydalanuvchi tasdig'i kerak.

---

## 2026-10-26 — B10 portativ paket

`python tools/package.py workdir/DarsStudio --with-models`: 17 GB (runtime/python 3.11.16 + torch 2.11 cu128 va boshqalar, ffmpeg 7.1.1, Maxine, 5 model, UI build). Paket ichidagi Python bilan, `DARS_MAXINE_DIR` siz: doctor — ffmpeg, Maxine, torch paket ichidan; CLI ishlaydi. Boshqa kompyuterga nusxalab sinash — inson.

---

## 2026-10-26 — B9–B11: eksport, QA, paket, offline va barqarorlik sinovlari

**End-to-end (haqiqiy namuna):** `export` — 13.8 min dars, Eye Contact patchlari bilan, `b_scene_words=120`:
QA ogohlantirish (faqat inson tekshiruvi: 2 shubhali chegara, 1 kesish taklifi). Kadr 20 664 = kutilgan, A/V 0.0 ms,
-16.1 LUFS, TP -2.4 dBTP, qora/muzlagan kadr yo'q. To'liq eksport (render + audio + QA) ~3 min.

**QA haqiqiy xatolarni ushladi va tuzatildi:**
1. TP -0.5 / +3.6 dBTP — manba clipping (+0.5) va AAC'ning impulsda "ringing" i (+6 dB, 2.06 s dagi bitta impuls).
   Yechim: loudnorm (192 kHz) -> lowpass 16 kHz -> alimiter -3 dBFS -> 48 kHz. Natija -2.4 dBTP.
2. SRT oxirgi titri videodan uzun; so'z vaqtlari ustma-ust bo'lganda titrlar kesishgan — chegaralandi.
3. Sinxron slayd matnisiz (faqat sarlavhalar) ishlab 1 oraliq bergan — sinxrondan oldin matn ajratiladi.

**Barqarorlik sinovi topgan xatolar:** (a) worker'dagi eski `asr` nomi navbatdagi `asr` vazifasini to'sgan;
(b) **lost update** — parallel Eye Contact vazifasi eski project.json ni saqlab sinxron natijasini o'chirgan. Yechim:
`project.lock` (O_EXCL, 60 s dan eski qulf olib tashlanadi) + har buyruq diskdagi so'nggi holatga qo'llanadi.
Natija: 3 loyiha x 7 vazifa — hammasi tayyor; render 42% da worker o'ldirildi, qayta urinishda seg_00000 qayta
yozilmadi (checkpoint). Python jarayonlari RAM pik 6.6 GB. (25 min o'rniga 2 min bo'laklar — vaqt uchun.)

**Offline (AC-13):** `tools/offline_check.py` — socket qo'riqchisi bilan to'liq zanjir 117 s, tarmoqqa urinish 0.

**Premiere paketi:** 2 min -> 1.2 GB (teacher.mov ProRes 4444, yuva444p12le, 3001 kadr); 25 min ~15 GB (TZ
taxmini 30–60 GB). XML: V1 1, V2 4, V3 1, A1 1 klip. Premiere/DaVinci'da ochish — inson tekshiruvi.

**Qabul jadvali:** `docs/QABUL.md`.

---

## 2026-10-26 — B4/B5/B6/B8: audio, ASR, sinxron, kesish, Eye Contact, UI — o'lchovlar

**ASR benchmark (G2 — qaror inson tomonidan).** 3 x 5 min namuna (bitta dars, bitta fan — TZ 3 fan talab qiladi),
CTC alignment `sarahai-uzbek-stt-3`. **Qo'lda tuzatilgan referens matn yo'q (O-06), shuning uchun WER/CER
o'lchanmadi.** Model litsenziyalari HF kartasida va asos modelgacha tekshirildi; revision va har fayl sha256
`models/manifest.json` da.

| model (litsenziya) | RTF | GPU xotira pik | VRAM (vram_probe) | o'zaro "WER" vs rubaistt / kotib |
|---|---|---|---|---|
| whisper-large-v3-ct2 (MIT) | 0.060–0.064 | 4.2–4.3 GB | 3.6 GB | 0.730 / 0.728 (turkcha/ozarbayjoncha harflar) |
| rubaistt-v2-medium-ct2 (Apache-2.0) | 0.048–0.051 | 2.2–2.3 GB | 2.1 GB | — / 0.061 |
| kotib-uzbek-stt-v1-ct2 (Apache-2.0) | 0.060–0.078 | 2.4–2.9 GB | 2.1 GB | 0.063 / — |
| sarahai-uzbek-stt-3, CTC (Apache-2.0) | 0.015–0.020 | 1.9–2.3 GB | 1.9 GB | 0.407 / 0.427 (so'zlar qo'shilib ketadi) |
| xlsr-uzbek-cv8, CTC (Apache-2.0) | 0.016–0.020 | 1.9–2.9 GB | 1.7 GB | 0.424 / 0.444 |

"O'zaro WER" — referens emas, ikki kuchli model bilan kelishuv (sifat taxmini). **Tavsiya:** ASR —
rubaistt-v2-medium (eng tez, eng kam xotira, kotib bilan 94% kelishuv), so'z vaqtlari — sarahai CTC.
To'liq 13.8 min dars: ASR + CTC alignment 53 s, 32/32 segment tekislandi. So'z chegarasi xatosi (AC: median <= 60 ms)
— 100 ta qo'lda belgilangan so'z yo'q, o'lchanmadi (`tools/asr_bench.py --boundaries`).

**Topilmalar va qarorlar (B4):**
- Whisper o'zbekcha so'zni apostrof joyidan bo'ladi ("o" + "'zbekiston") — bo'laklar birlashtiriladi.
- CTC tokenizer lug'ati model chiqishidan katta (qo'shimcha tokenlar) — model `vocab_size` bilan cheklanadi.
- Segment oynalari (+-400 ms) kesishganda so'z vaqtlari ustma-ust tushardi (16 holat) — tuzatildi.
- `words.parquet` o'rniga `cache/asr/words.json` (25 min ~ 4 000 so'z, pyarrow bog'liqligi kerak emas).
- DeepFilterNet3 o'rnatilmagan (Windows g'ildiragi/Rust lib tekshirilmadi) — zaxira `afftdn` (nr 15 dB) ishlatiladi.
  Tinglash bo'yicha baho (FR-04 AC) — montajchi.
- Namuna audio: integrated -14.6 LUFS, **true peak +0.51 dBTP (manbada clipping)**. Ma'ruza deyarli uzluksiz:
  VAD 21 nutq bo'lagi, >= 1.2 s pauza deyarli yo'q (`cuts` 1 ta taklif, dars boshidagi jimlik).

**Slayd sinxroni (B5, G3 — qaror inson tomonidan).** Namunada (ground truth yo'q) AI rejimi 19 slaydni ketma-ket
topdi; tekshirilgan chegaralar gap boshiga to'g'ri tushgan ("keyingi slaydda dunyo bo'yicha emissiyalar..."), bitta
14 -> 15 -> 14 qaytish (ishonchlilik 0.505) "shubhali" deb belgilandi. Sintetik testda (5 dars) ±2 s ichida >= 90%.
Embedding (a = 0.6) hali ishlatilmaydi — model yuklanmagan; leksik qism (char 3–5 gram TF-IDF + kalit so'zlar) +
so'z darajasidagi change-point chegara. `tools/align_eval.py --grid` qo'lda belgilangan GT bilan parametr tanlaydi.
- **TZ FR-12 sahna qoidasi (>= 60 so'z -> B):** namuna slaydlarida 65–139 so'z, qoida bo'yicha deyarli butun dars B
  (o'qituvchi yashirin). Chegara loyiha meta `b_scene_words` ga chiqarildi (default 60); ko'rgazmali eksportda 120.
  Qaror — inson.

**Eye Contact (B6):** to'liq 13.8 min namuna — patchlar 21 MB; 2 min bo'lak (3001 kadr) 32 s (ishga tushish bilan).
TZ taxmini 100–300 MB / 25 min — amalda ~40 MB.

**UI (B8):** `npm --prefix ui run build` toza, Vitest 25 passed. Brauzerda haqiqiy `namuna` bilan tekshirildi:
Bosh sahifa (doctor bannerlari, loyihalar, navbat), Tekshirish (proxy + slayd, 5 yo'lak timeline, transkript,
shubhali joylar), Key kalibrlash (keyed kadr). Playwright [T] — yo'q.

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
