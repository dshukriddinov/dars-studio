# Bosqichlar: Dars Studio'ni Claude Code bilan qurish

Bu fayl `docs/TEXNIK_TOPSHIRIQ.md` (TZ) ni amalga oshirish tartibi. Har bosqich alohida Claude Code sessiyasida
bajariladi. Har birida: maqsad, vazifalar, tayyorlik mezoni (DoD), tekshirish buyruqlari va sessiyaga tashlash uchun
tayyor prompt.

## Umumiy ish tartibi (har bosqichda)

1. Sessiya boshida Claude Code `CLAUDE.md`, TZ'ning tegishli bo'limlari va shu fayldagi bosqichni o'qiydi.
2. Avval reja (plan mode): fayllar, interfeyslar, testlar ro'yxati. Inson tasdiqlaydi.
3. Kod + testlar. Har mantiqiy qadamdan keyin `pytest` (tegishli belgilar bilan).
4. Bosqich oxirida: DoD tekshiruvi, `docs/QAROR_JURNALI.md` ga qarorlar va o'lchovlar, `CHANGELOG.md` yozuvi, commit.
5. Qaror nuqtasi (G) bo'lsa — natijalar insonga ko'rsatiladi, keyingi bosqich tasdiqdan keyin boshlanadi.

Bosqichlar tartibi ataylab shunday: **B3'da (vertikal kesim) birinchi haqiqiy MP4 chiqadi** — keyer va kompozit
sifatini erta ko'rish uchun. ASR va AI moslashtirish undan keyin keladi.

---

## B0. Repo skeleti va asboblar

**Maqsad:** bo'sh, lekin ishlaydigan loyiha: paketlar, testlar, linter, doctor skeleti, sintetik media generatori.

**Vazifalar**
- [ ] TZ 11-bo'limdagi papka tuzilishi, `pyproject.toml` (ruff, mypy, pytest belgilari: unit, media, gpu, windows, pilot).
- [ ] `darsstudio/paths.py`: runtime (python, ffmpeg, maxine), models, ishchi papka; muhit o'zgaruvchilari bilan qayta belgilash.
- [ ] `darsstudio/media/ffmpeg.py`: ffmpeg/ffprobe topish (avval `runtime/ffmpeg`, keyin PATH), versiyani tekshirish (7.1.1 kutiladi, boshqasi bo'lsa ogohlantirish), barcha chaqiruvlar uchun yagona `run()` (encoding="utf-8", errors="replace", Windows'da oyna ochilmasin).
- [ ] `darsstudio/doctor.py` skeleti: tekshiruvlar ro'yxati, har biri `ok/ogohlantirish/xato` + o'zbekcha sabab + yechim. Hozircha: OS, Python, ffmpeg, GPU (`nvidia-smi`), drayver ≥ 570, bo'sh disk, RAM.
- [ ] `tools/make_test_media.py`: TZ 13.3 dagi 1–6 klip va 7-PPTX; `tests/conftest.py` da session fixture.
- [ ] `models/manifest.json` sxemasi va bo'sh ro'yxat; `tools/fetch_models.py` skeleti (sha256 tekshiruvi bilan).
- [ ] `docs/QAROR_JURNALI.md`, `CHANGELOG.md`, `.gitignore` (runtime, models, media, cache).
- [ ] `engines/eye-contact` submodule qo'shish.

**DoD**
- `python -m pytest -m "unit or media"` Linux va Windows'da o'tadi.
- `python -m darsstudio.doctor` jadval chiqaradi.
- `ruff check` va `mypy darsstudio` toza.

**Prompt**
```
docs/TEXNIK_TOPSHIRIQ.md (11, 13-bo'limlar) va docs/BOSQICHLAR.md dagi B0 ni bajar.
Avval reja tuz va menga ko'rsat. Keyin skeletni yarat: pyproject (ruff, mypy, pytest belgilari),
paths.py, media/ffmpeg.py (yagona ffmpeg qatlami), doctor.py skeleti, tools/make_test_media.py
(13.3 dagi 7 ta media), conftest fixture'lari, models/manifest.json sxemasi.
engines/eye-contact ni github.com/dshukriddinov/eye-contact dan submodule qilib qo'sh.
Oxirida pytest -m "unit or media", ruff va mypy natijalarini ko'rsat.
```

---

## B1. Eye Contact moduliga o'zgarishlar (EC-1..EC-5)

**Maqsad:** modulni Studio uchun tayyorlash. Ish `engines/eye-contact` repo'sida, alohida branch + PR.

**Vazifalar**
- [ ] EC-5 avval: `tests/test_pipeline_stub.py` — `GazeRedirector` stub (kadrni o'zgartirmaydi, `conf=0`), sintetik media bilan pipeline'ni GPU'siz ishlatadi. Lossless rejimda kadrlar bayt-aniq, chunk chegaralari to'g'ri.
- [ ] EC-1: `video_io.concat()` — probe'dagi video va audio `start_time` farqini saqlash (`-itsoffset` kerakli kirishga). `tools/eval.py` ga `av_offset_ms`. Test: video 52 ms kech boshlangan MOV → chiqishda farq ±1 kadr ichida.
- [ ] EC-2: VFR — jami kadr `round(davomiylik × fps)`; chunk o'qishda `-fps_mode cfr`. Test: VFR klipda chiqish davomiyligi ±1 kadr, chunk chegarasida siljish yo'q (ideal CFR ketma-ketlik bilan framemd5 taqqoslash).
- [ ] EC-3: `Config.key()` ga kirish fayli identifikatori (hajm, `mtime_ns`, bosh/oxir 1 MB xxhash64). Test: boshqa fayl bilan `--resume` eski chunk'larni ishlatmaydi.
- [ ] EC-4: `--patches-out DIR`: encode yo'q; har chunk uchun `chunk_XXXXX.npz` (TZ 9.7 formati) + `meta.json`; resume ishlaydi. Yangi `eyecontact/patches.py`: `write_chunk`, `read_chunk`, `apply(frame_yuv, rec, w=1.0)`. Test (stub bilan): patch fayli o'qilib qo'llanganda natija oddiy rejim chiqishi bilan Y kanalida bayt-aniq (lossless).
- [ ] README va TEXNIK_TOPSHIRIQ.md (modulniki) yangilanadi.

**DoD**
- Linux'da: `python -m pytest tests/test_pipeline_stub.py` o'tadi.
- Windows + GPU'da: mavjud `tests/test_smoke.py` va `tests/test_gui.py` o'tadi; haqiqiy klipda `--patches-out` va oddiy rejim natijalari mos.
- Eski xatti-harakat o'zgarmagan (default sozlamalar bilan natija oldingisi bilan bir xil, ±1 piksel).

**Prompt**
```
engines/eye-contact repo'sida ishlaymiz (alohida branch). docs/TEXNIK_TOPSHIRIQ.md 12-bo'lim (EC-1..EC-5)
va 9.7 (patch formati) ni o'qi. Avval EC-5: GazeRedirector stub bilan GPU'siz pipeline testi.
Keyin EC-1 (A/V start_time farqi), EC-2 (VFR), EC-3 (resume kaliti), EC-4 (--patches-out) ni,
har biriga test bilan, alohida commitlarda bajar. Mavjud default natija o'zgarmasligi kerak.
Oxirida testlar natijasini va PR tavsifini ko'rsat.
```

---

## B2. Media qatlami, TimeMap, loyiha modeli

**Maqsad:** vaqt va media bilan ishlashning ishonchli poydevori.

**Vazifalar**
- [ ] `media/probe.py`: TZ FR-02 dagi barcha maydonlar; fps `Fraction`; VFR aniqlash (paket vaqtlari bo'yicha, faqat `r_frame_rate ≠ avg_frame_rate` ga ishonmasdan).
- [ ] `media/normalize.py`: VFR → CFR; 48 kHz bo'lmagan audio → 48 kHz (soxr).
- [ ] `media/frames.py`: `FrameReader` / `FrameWriter` (rawvideo pipe, yuv420p, aniq seek, rang teglari) — Eye Contact'dagi `video_io.py` tajribasi asosida, lekin Studio'ning o'z moduli.
- [ ] `media/proxy.py`: 960×540, GOP 12, NVENC (bo'lmasa libx264), AAC 128k, faststart.
- [ ] `media/timemap.py`: TZ 9.5 — `TimeMap`, audio namuna aniqligi; hypothesis testlari.
- [ ] `project/model.py`: TZ 8.2 modellari + invariant validatorlari; `project/store.py` (atomik yozish, schema_version, migratsiya skeleti); `project/commands.py` (buyruq naqshi, undo/redo, tarix faylga).
- [ ] `FR-01` import funksiyasi (CLI: `python -m darsstudio.cli import <video> <pptx> --template <id>`).

**DoD**
- Sintetik media to'plamidagi barcha holatlar to'g'ri probe qilinadi; VFR klip CFR'dan keyin ±1 kadr.
- TimeMap property testlari (≥ 500 misol) o'tadi.
- Loyiha yaratish → saqlash → qayta ochish → bir xil holat; 100 ta buyruqdan keyin undo/redo to'g'ri.

**Prompt**
```
B2 ni bajar: TZ FR-01, FR-02, 8-bo'lim (ma'lumot modeli), 9.5 (TimeMap). fps hamma joyda Fraction,
vaqt oraliqlari asl kadr indekslarida [start, end). Eye Contact'dagi video_io.py ni namuna sifatida o'qi,
lekin darsstudio/media ichida o'z modulingni yoz. TimeMap uchun hypothesis property testlari majburiy.
Loyiha holati Pydantic JSON, atomik yozish, buyruqlar tarixi bilan undo/redo.
Oxirida testlar va CLI import namunasini ko'rsat.
```

---

## B3. Vertikal kesim: birinchi haqiqiy MP4

**Maqsad:** qo'lda berilgan slayd vaqtlari (CSV) bilan to'liq kompozit MP4. ASR va AI hali yo'q.

**Vazifalar**
- [ ] `slides/render_pptx.py` (PowerPoint COM, `windows` testi) va `slides/render_pdf.py` (LibreOffice → PDF → pypdfium2); `slides/extract.py` (python-pptx: sarlavha, matn, jadval, eslatmalar, animatsiya/video ogohlantirishlari).
- [ ] `render/templates.py`: shablon JSON (TZ 8.3) yuklash/validatsiya; `templates/demo/` sintetik shablon.
- [ ] `slides/warp.py`: TZ 9.2 (supersampling, kesh, ramkadan chiqmaslik testi).
- [ ] `render/keyer.py`: TZ 9.1 qadamlari 1–8 (PyTorch, batch); CPU zaxira (testlar uchun, sekin).
- [ ] `render/placement.py`: TZ 9.3.
- [ ] `render/compositor.py`: A va B sahnalar, crossfade o'tishlar, logo.
- [ ] `render/renderer.py`: dekod (yuv420p pipe) → GPU (batch 8) → keyer → kompozit → yuv420p → NVENC pipe; chunk + checkpoint + concat; audio hozircha manbadan (`-c:a aac`), A/V siljish saqlanadi.
- [ ] CLI: `python -m darsstudio.cli render <loyiha> --slides-csv times.csv --out out.mp4`.
- [ ] Kalibrlash uchun vaqtinchalik CLI: `calibrate-key` (kadr raqami → key rangi taklifi, oldin/keyin PNG), `calibrate-screen` (4 nuqtani JSON'dan).
- [ ] `tools/render_bench.py`: kadr/s, VRAM pik, CPU.

**DoD**
- Sintetik yashil fon klipida: garbage hududida alfa = 0; slayd ramkadan chiqmaydi; A→B→A o'tishlari to'g'ri uzunlikda.
- Haqiqiy darsdan 2–3 daqiqalik bo'lak: MP4 chiqadi, `render_bench` ≥ 80 kadr/s (yetmasa — sababini o'lchab QAROR_JURNALI'ga).
- A/V siljish testi (sintetik 52 ms klip) o'tadi.

**Qaror nuqtasi G1:** montajchi haqiqiy bo'lakni ko'radi: keyer (soch, qo'l, ko'zoynak, devor cheti), slayd o'qilishi,
o'qituvchi joyi. Qabul qilinmasa — keyer sozlamalari/qo'shimcha usullar (guided filter, AI matting) bo'yicha qaror.

**Prompt**
```
B3 ni bajar — vertikal kesim. TZ FR-03, FR-11, FR-12, FR-13 (faqat o'tishlar va logo), FR-16 (soddalashtirilgan),
9.1–9.3, 9.8. Slayd vaqtlari hozircha CSV'dan. Renderer bitta o'tishda: yuv420p dekod → PyTorch GPU
(keyer + kompozit, batch) → NVENC. Chunk + checkpoint + concat, A/V start_time farqi saqlansin.
Sintetik yashil fon klipi bilan testlar yoz, render_bench bilan tezlikni o'lcha va QAROR_JURNALI.md ga yoz.
Oxirida haqiqiy bo'lakni qanday render qilishni (buyruqlar) ko'rsat — men o'zim ko'rib baholayman.
```

---

## B4. Audio, ASR, so'z vaqtlari, o'zbek matni

**Maqsad:** ishonchli transkript va aniq so'z chegaralari; ASR modeli benchmark bilan tanlanadi.

**Vazifalar**
- [ ] `audio/extract.py`, `audio/denoise.py` (DeepFilterNet3; zaxira `afftdn`), `audio/loudness.py` (EBU R128 o'lchov, ikki o'tishli loudnorm), `audio/vad.py` (Silero).
- [ ] `asr/uz_text.py` (TZ FR-06, ≥ 60 test misoli), `asr/glossary.py`.
- [ ] `asr/engines/base.py` interfeysi; `whisper_ct2.py` (faster-whisper, VAD filtri, hotwords/initial_prompt); `ctc.py` (CTC model, transformers yoki onnxruntime).
- [ ] `asr/word_align.py`: CTC forced alignment (torchaudio `forced_align` yoki model o'zi), so'z vaqtlari.
- [ ] `tools/asr_bench.py`: WER, CER, atamalar aniqligi (lug'at bo'yicha), RTF, VRAM; Markdown jadval chiqaradi.
- [ ] `tools/vram_probe.py`: har model uchun VRAM pik → `models/manifest.json`.
- [ ] Har GPU ishi alohida jarayonda (`jobs/worker.py` minimal versiyasi) — model xotiradan to'liq chiqishi uchun.

**DoD**
- `uz_text` testlari o'tadi.
- `asr_bench` 3 ta 5 daqiqalik namunada (buyurtmachi bergan referens matn bilan) jadval chiqaradi.
- So'z chegarasi xatosi median ≤ 60 ms (100 ta qo'lda belgilangan so'z).

**Qaror nuqtasi G2:** benchmark jadvali bo'yicha model tanlanadi (sifat, tezlik, VRAM, litsenziya).

**Prompt**
```
B4 ni bajar: TZ FR-04, FR-05, FR-06, 9.9 (faqat denoise va o'lchov qismi), 3.4 (VRAM budjeti).
ASR dvigatellari umumiy interfeys orqali; har nomzod modelni models/manifest.json ga litsenziyasi bilan yoz,
litsenziyasi noma'lum modelni ishlatma — menga xabar ber. So'z vaqtlari CTC forced alignment bilan.
asr_bench va vram_probe vositalarini yoz. Har GPU ishi alohida jarayonda.
Oxirida benchmark jadvalini va tavsiyangni ko'rsat — tanlovni men qilaman.
```

---

## B5. Slayd sinxroni

**Maqsad:** jurnal rejimi (aniq) va AI rejimi (zaxira), baholash vositasi bilan.

**Vazifalar**
- [ ] `tools/slide_logger.py` (Windows, pywin32): PowerPoint hodisalari + `perf_counter_ns` + sync beep; CSV (TZ 4.4).
- [ ] `sync/beep.py` (TZ 9.6), `sync/slide_log.py` (CSV → SlideSpan, source="log").
- [ ] `sync/ai_align.py` (TZ 9.4): embedding (manifest'dagi tanlangan model), char n-gram TF-IDF, kalit so'zlar, Viterbi, forward-backward, minimal turish, chegarani pauzaga surish, qisqa qaytishlarni belgilash.
- [ ] `sync/metrics.py` + `tools/align_eval.py`: ±1/±2/±5 s ulushlari, median xato, shubhali ulushi, xato chegaralar shubhali ro'yxatda bo'lish ulushi.
- [ ] Ground truth belgilash uchun oddiy CLI (yoki keyin UI'da): video vaqti + slayd raqami CSV.
- [ ] Parametrlarni (a, b, c, λ, τ) `align_eval` bilan grid search; natija QAROR_JURNALI'ga.

**DoD**
- Sintetik matnli testlarda (ma'lum chegaralar) Viterbi to'g'ri chegaralarni topadi; beep testi ≤ 10 ms.
- 3 ta haqiqiy darsda `align_eval` jadvali.

**Qaror nuqtasi G3:** AI rejimi AC-03 ga yetadimi? Yetmasa — yangi yozuvlar uchun jurnal rejimi majburiy qilinadi,
AI esa faqat eski videolar uchun "taklif" sifatida qoladi.

**Prompt**
```
B5 ni bajar: TZ FR-07, FR-08, 9.4, 9.6. slide_logger PowerPoint COM hodisalarini (SlideShowNextSlide,
SlideShowNextBuild, Begin, End) perf_counter_ns bilan yozsin va boshida 1 kHz 300 ms beep chalsin.
AI moslashtirish: embedding + char n-gram TF-IDF + kalit so'zlar, Viterbi (qolish/keyingi/o'tkazib yuborish/
bitta orqaga), forward-backward ishonchlilik, chegarani pauzaga surish. align_eval bilan parametrlarni tanla.
Oxirida 3 dars bo'yicha natijalar jadvalini ko'rsat.
```

---

## B6. Pauza kesish, Eye Contact, brending, subtitr

**Vazifalar**
- [ ] `FR-09`: pauza nomzodlari (VAD ∩ so'z bo'shliqlari), CutProposal, TimeMap bilan render; audio crossfade 10 ms; `prefer_fullscreen` va `crossfade` variantlari.
- [ ] `FR-10`: Eye Contact worker (submodule CLI, `--patches-out`, `--progress`), `render/eyepatch.py` (qo'llash, rampa), hash bo'yicha kesh yaroqliligi.
- [ ] `FR-13`: lower-third, intro/outro, [T] subtitr overlay.
- [ ] `FR-04/9.9`: to'liq audio zanjiri (denoise → kesish → loudnorm → AAC).
- [ ] `FR-17` SRT (TimeMap orqali).

**DoD**
- Sintetik testlar: kesishdan keyin kadr soni = TimeMap.out_total; A/V siljish ≤ 1 kadr; SRT monoton.
- Haqiqiy darsda: Eye Contact patchlari qo'llangan render; Eye Contact o'chiq oraliqda rampa ko'zga tashlanmaydi.
- Loudness AC-08.

**Prompt**
```
B6 ni bajar: TZ FR-09, FR-10, FR-13, FR-17 (SRT), 9.5, 9.7, 9.9. Eye Contact'ni engines/eye-contact CLI'si orqali
--patches-out rejimida alohida jarayonda chaqir, patchlarni rendererda YUV fazosida qo'lla (rampa bilan).
Kesishlar faqat TimeMap orqali. Audio: denoise → kesish (10 ms crossfade) → ikki o'tishli loudnorm → AAC.
Har qism uchun sintetik testlar; oxirida haqiqiy darsda to'liq render buyrug'ini ko'rsat.
```

---

## B7. Backend API, navbat, rejalashtiruvchi

**Vazifalar**
- [ ] `jobs/resources.py` (TZ FR-20 qabul qoidasi), `jobs/queue_db.py` (SQLite, WAL), `jobs/scheduler.py`, `jobs/worker.py` (alohida jarayon, `PROGRESS`/`OUTPUT`/`LOG` protokoli, `power.py` bilan uyquni bloklash).
- [ ] To'xtatish (jarayon daraxti), resume, 1 marta qayta urinish, VRAM xatosida kutish.
- [ ] `api/app.py`: FastAPI, faqat `127.0.0.1`; loyihalar, assetlar, vazifalar, buyruqlar (undo/redo), preview so'rovlari, eksport; WebSocket progress; statik UI'ni berish.
- [ ] "Tekshiruvgacha tayyorlash" vazifa zanjiri: import → (slaydlar ‖ audio ‖ ASR ‖ Eye Contact) → sinxron → kesish takliflari → proxy.

**DoD**
- Bir vaqtda 3 loyiha navbatga qo'yilganda resurs qoidalari buzilmaydi (log va test bilan).
- Worker o'ldirilsa vazifa `toʻxtatildi`, qayta boshlansa checkpoint'dan davom etadi.
- API uchun pytest (httpx) testlari.

**Prompt**
```
B7 ni bajar: TZ FR-20, FR-21 (to'liq doctor), FR-22, D-04, D-10. Har vazifa alohida jarayon,
resurs e'loni (vram_mb, nvenc, nvdec, cpu_heavy, pptx, exclusive), SQLite navbat, to'xtatish va resume.
FastAPI faqat 127.0.0.1 da, WebSocket progress. Rejalashtiruvchi qoidalari uchun testlar majburiy.
```

---

## B8. UI (React + TypeScript)

**Vazifalar**
- [ ] Dizayn tokenlari: Eye Contact `design-system/tokens.json` dan CSS o'zgaruvchilari (dark birinchi), o'zbekcha matnlar (`oʻ`, `gʻ` U+02BB), ovoz uslubi Eye Contact `design-system/README.md` dagidek.
- [ ] Ekranlar: Bosh sahifa (loyihalar, navbat, doctor banner), Yangi loyiha (sehrgar), Shablon kalibrlash (4 nuqta, anchor), Key kalibrlash (pipetka, slayderlar, oldin/keyin, matte), **Tekshirish** (preview, slayd, transkript, timeline yo'laklari, Shubhali joylar), Eksport (profil, QA), Sozlamalar.
- [ ] Timeline: virtualizatsiya (1 000+ element), klaviatura (TZ FR-14), undo/redo server buyruqlari orqali.
- [ ] Preview: Tez ko'rinish (proxy + slayd) va Haqiqiy ko'rinish (oraliq render), kadr raqami ko'rsatkichi.
- [ ] pywebview oynasi (`DarsStudio.bat`).

**DoD**
- Vitest komponent testlari; [T] Playwright: loyiha ochish → chegarani surish → undo → saqlash → qayta ochish.
- 25 daqiqalik loyihada timeline silliq.

**Prompt**
```
B8 ni bajar: TZ FR-14, FR-15, D-09. ui/ papkasida React + TS + Vite. Dizayn tokenlarini
engines/eye-contact/design-system/tokens.json dan ol, matn uslubi uning README.md dagidek (qisqa, o'zbekcha).
Avval Tekshirish ekranini qur (eng muhimi), keyin qolganlarini. Barcha o'zgarishlar backend buyruqlari orqali
(undo/redo serverda). Oxirida UI'ni ishga tushirish buyrug'i va skrinshotlar.
```

---

## B9. Eksportlar va QA

**Vazifalar**
- [ ] `export/mp4.py` (profillar), `export/tables.py` (CSV/JSON), `export/qa.py` (TZ FR-19).
- [ ] `export/fcp7xml.py` + `export/premiere_pkg.py` (TZ FR-18, D-11): o'qituvchi qatlami ProRes 4444 (alfa, kesilmagan, kanvasdagi joyida), warp qilingan slaydlar, fon, audio; kesishlar klip in/out sifatida.
- [ ] Fayl nomlash va versiyalash.

**DoD**
- XML tuzilma testlari; sintetik loyiha paketi Premiere va DaVinci'da ochiladi (inson tekshiradi, skrinshot).
- QA hisobotdagi barcha tekshiruvlar sintetik "buzilgan" holatlarda xato beradi (negativ testlar).

**Prompt**
```
B9 ni bajar: TZ FR-17, FR-18, FR-19, D-11. FCP7 XML (xmeml v5): V1 fon, V2 slaydlar, V3 o'qituvchi (ProRes 4444,
alfa, kanvasda joylashgan, kesilmagan), A1 audio; kesishlar klip in/out bilan, effekt va transform yo'q.
QA tekshiruvlari uchun negativ testlar yoz. Oxirida paketni Premiere'da qanday ochishni ko'rsat.
```

---

## B10. Paketlash, offline, qo'llanma

**Vazifalar**
- [ ] `tools/package.py`: portativ papka (runtime/python + kutubxonalar, ffmpeg 7.1.1, maxine, models, ui build, `DarsStudio.bat`, ish stoli yorlig'i).
- [ ] `requirements.lock` (hash'lar bilan), modellar manifest bo'yicha tekshiriladi.
- [ ] Offline sinov: tarmoq o'chirilgan holda import → eksport → qayta ochish.
- [ ] README (o'zbekcha): o'rnatish, birinchi shablonni sozlash, kundalik ish, kechki navbat, muammolar.
- [ ] Barqarorlik: 3 × 25 daqiqalik loyiha ketma-ket, render o'rtasida o'ldirish va davom ettirish.

**DoD:** AC-10, AC-11, AC-13.

**Prompt**
```
B10 ni bajar: TZ NFR-11, FR-22, AC-10/11/13. Eye Contact'dagi portativ paket tajribasini qo'lla.
Paket yaratish skripti, lock fayl, offline sinov ssenariysi va o'zbekcha README. Barqarorlik sinovi
uchun skript (3 loyiha ketma-ket, o'rtada worker'ni o'ldirish) va natijalarni QAROR_JURNALI'ga yoz.
```

---

## B11. Pilot va qabul

**Vazifalar**
- [ ] 3–10 haqiqiy dars to'liq sikldan o'tadi; montajchi vaqti o'lchanadi (AC-14).
- [ ] align/asr/keyer parametrlari pilot natijalari bo'yicha sozlanadi; QAROR_JURNALI.
- [ ] TZ 14-bo'limdagi barcha AC jadval ko'rinishida: holat, o'lchov, dalil (fayl/skrinshot).

**Qaror nuqtasi G4:** qabul yoki tuzatishlar ro'yxati.

**Prompt**
```
B11: pilot natijalarini yig'. DARS_PILOT_DIR dagi darslar uchun pytest -m pilot va barcha benchmark vositalarini
ishga tushir, TZ 14-bo'limdagi har AC uchun holat/o'lchov/dalil jadvalini docs/QABUL.md ga yoz.
Bajarilmagan mezonlar uchun sabab va taklif.
```
