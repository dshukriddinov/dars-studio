# Dars Studio — videodarslarni yarim avtomatik montaj qilish

Yashil fonda yozilgan oʻqituvchi videosi va PPTX slaydlardan tayyor dars videosini yigʻadi: slaydlarni nutqqa
moslaydi, oʻqituvchini fondan ajratadi, nigohini kameraga qaratadi (Eye Contact), ovozni tozalaydi, uzun pauzalarni
qisqartirishni taklif qiladi. Natija: MP4, SRT subtitr, slayd vaqtlari jadvali va Premiere/DaVinci uchun paket.
Hammasi kompyuterning oʻzida, internetsiz ishlaydi.

Talablar: Windows 11, NVIDIA RTX (16 GB tavsiya), drayver 570 yoki yangiroq, 32 GB RAM, ishchi diskda 500 GB boʻsh joy.
PPTX uchun PowerPoint yoki LibreOffice.

## Oʻrnatish

**Tayyor paketdan (tavsiya):** `DarsStudio` papkasini NVMe diskka nusxalang va `DarsStudio.bat` ni ikki marta bosing.
Oʻrnatish va administrator huquqi kerak emas. Ish stoliga yorliq: `Ish_stoliga_yorliq.bat`.

Birinchi ishga tushishda dastur muhitni tekshiradi (Doctor). Qizil banner chiqsa, undagi yechimni bajaring.
Ikki muhim tekshiruv:

- **BIOS / CPU mikrokod.** 13/14-avlod Intel protsessorlarda mikrokod 0x12B dan eski boʻlsa uzun renderlarda
  crash boʻlishi mumkin. ASUS saytidan eng soʻnggi BIOS ni oʻrnating va "Intel Default Settings" ni yoqing.
- **Drayver pin.** Sinalgan NVIDIA drayver versiyasini `driver_pin.txt` ga yozing. Drayver oʻzgarsa Doctor ogohlantiradi.

**Dasturchi uchun (repo'dan):**
```
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv\Scripts\python.exe -e .[dev]
python tools/fetch_models.py          # modellar (bir marta, internet bilan), sha256 tekshiriladi
npm --prefix ui install && npm --prefix ui run build
```
ffmpeg 7.1.1 `runtime\ffmpeg` da yoki PATH da. Maxine SDK `runtime\maxine` da yoki `DARS_MAXINE_DIR` muhit
oʻzgaruvchisida. Eye Contact `engines\eye-contact` submodule.

## Birinchi shablonni sozlash (bir marta)

1. Studiya fon rasmini (1920x1080 yoki 3840x2160 PNG, ekrandagi eski slayd tozalangan) `templates\<nom>\background.png`
   ga qoʻying, `templates\demo\template.json` dan nusxa olib `id` ni oʻzgartiring.
2. Dasturda **Shablon kalibrlash**: ekranning 4 burchagini (yuqori chap, yuqori oʻng, pastki oʻng, pastki chap) va
   oʻqituvchi joyini (anchor) sichqoncha bilan belgilang, saqlang.
3. Birinchi darsda **Key kalibrlash**: oʻqituvchi koʻrinadigan kadrni tanlang, "Avtomatik taklif" ni bosing,
   kerak boʻlsa tolerantlik, yumshoqlik, spill slayderlarini suring. Natija/Matte koʻrinishida soch va qoʻl
   chetlarini tekshiring. Studiya yorugʻligi oʻzgarmasa keyingi darslarda shu sozlama ishlaydi.

## Kundalik ish

1. **Yangi loyiha**: video (`dars05.mov`) va slaydlar (`dars05.pptx`), shablon, fan, mavzu, oʻqituvchi.
   "Tekshiruvgacha tayyorlash" belgilangan boʻlsa navbatga qoʻyiladi: slaydlar, audio, ASR, Eye Contact,
   slayd sinxroni, pauza takliflari.
2. **Tekshirish**: "Shubhali joylar" roʻyxatidan boshlang. Har biri bosilganda oʻsha joyga oʻtadi.
   - Slayd chegarasi: `[` / `]` bilan suring, kerak boʻlsa slayd raqamini almashtiring.
   - Sahna: `1` — studiya (A), `2` — slayd toʻliq ekran (B).
   - Pauza kesish: `Enter` — tasdiqlash, yoki "Hammasini tasdiqlash".
   - Eye Contact oʻchiq: oʻqituvchi ataylab slaydga qaragan joylarni belgilang.
   - `Ctrl+Z` / `Ctrl+Y` — bekor qilish / qaytarish. Har oʻzgarish avtomatik saqlanadi.
   - Navigatsiya: `J/K/L`, `←/→` (1 kadr), `Shift+←/→` (1 s). "Haqiqiy koʻrinish" — ±5 s haqiqiy kompozit.
3. **Eksport**: profil `web` (8 Mbit/s) yoki `arxiv` (yuqori sifat). Natija `exports\v<N>\` da:
   `<fan>_<dars>_<mavzu>_v<N>.mp4`, `.srt`, `.slides.csv`, `qa.json`. QA ogohlantirishlarini koʻrib chiqing.
   Premiere/DaVinci kerak boʻlsa "Premiere paketi" ni belgilang (oʻqituvchi qatlami ProRes 4444, 30–60 GB).

**Premiere/DaVinci'da ochish:** `exports\v<N>\premiere\sequence.xml` ni File → Import qiling. V1 fon, V2 slaydlar,
V3 oʻqituvchi, A1 audio. Kesishlar klip chegaralari bilan — ularni Premiere'da surish mumkin. Qatlamlar allaqachon
joyida, effekt yoʻq.

## Kechki navbat

Bir nechta darsni kechqurun qoʻshing: video va slaydlar bir xil nomli boʻlsin (`dars05.mov` + `dars05.pptx`), papkani
tanlang yoki buyruq qatorida:
```
python -m darsstudio.cli import-dir D:\Darslar\2026-10 --template studio1
```
Navbat har vazifani alohida jarayonda, GPU xotirasi budjeti bilan bajaradi; kompyuter uxlab qolmaydi. Ertalab
faqat tekshirish va eksport qoladi. Vazifa toʻxtatilsa yoki kompyuter qayta yuklansa, "Davom ettirish" bilan
oxirgi checkpoint'dan davom etadi.

## Buyruq qatori

```
python -m darsstudio.cli import VIDEO SLAYDLAR [--template ID] [--meta fan=...] [--name NOM]
python -m darsstudio.cli audio LOYIHA          # WAV, VAD, loudness, shovqin tozalash
python -m darsstudio.cli asr LOYIHA            # transkript + soʻz vaqtlari
python -m darsstudio.cli eyecontact LOYIHA     # koʻz patchlari
python -m darsstudio.cli sync LOYIHA           # slayd vaqtlari (jurnal yoki AI)
python -m darsstudio.cli cuts LOYIHA [--approve-all]
python -m darsstudio.cli export LOYIHA [--profile arxiv] [--premiere]
python -m darsstudio.doctor                    # muhit tekshiruvi
python -m darsstudio.api.app                   # server (127.0.0.1:8765) + UI
```
Suratga olishda slaydlarni noutbukda almashtirsangiz, aniq vaqtlar uchun `python tools\slide_logger.py dars05.csv`
ni ishga tushiring (boshida qisqa "beep" chaladi) va importda `--slide-log dars05.csv` bering.

## Muammolar

| Belgi | Sabab | Yechim |
|---|---|---|
| Doctor: "nvidia-smi ishlamadi" | Drayver yoʻq yoki eski | NVIDIA Studio drayverini oʻrnating (570+) |
| "Faqat 1920x1080 qoʻllanadi" | Video boshqa oʻlchamda | Kamera/eksportni 1080p ga qoʻying |
| "PPTX ni ochish uchun PowerPoint yoki LibreOffice kerak" | Ikkalasi ham yoʻq | Ulardan birini oʻrnating yoki PDF bering |
| Soch atrofida yashil hoshiya | Spill yetarli emas | Key kalibrlashda Spill ni oshiring, Choke 1–2 px |
| Oʻqituvchi qoʻli kesilib qolgan | Garbage hududi juda keng | Key kalibrlashda garbage chegarasini toraytiring |
| Slayd vaqtlari koʻp xato | Nutq slayd matniga yaqin emas | Slayd jurnalidan foydalaning (`slide_logger`) |
| Render oʻrtasida crash | CPU mikrokod/RAM barqarorligi | BIOS yangilash (HW-1), RAM sinovi (HW-3) |
| Vazifa "xato" | Sabab vazifa jurnalida | `workdir\logs\job_<N>.log`; "Davom ettirish" |

Jurnallar: `workdir\logs\` (vazifalar), loyiha papkasidagi `logs\`. Texnik tafsilotlar: `docs\TEXNIK_TOPSHIRIQ.md`,
qarorlar va oʻlchovlar: `docs\QAROR_JURNALI.md`.

## Uchinchi tomon modellari va litsenziyalar

Toʻliq roʻyxat: `models/manifest.json` (har fayl sha256 bilan).

- **PANNs Cnn14 (16 kHz)** — yoʻtal, aksa, tomoq qirish kabi tovushlarni aniqlash. Q. Kong va b., "PANNs: Large-Scale
  Pretrained Audio Neural Networks for Audio Pattern Recognition" (2020). Ogʻirliklar: Zenodo 3987831, CC-BY-4.0.
  AudioSet sinflari roʻyxati: CC-BY-4.0. Arxitektura kodi (MIT) Studio ichida qayta yozilgan.
- **DeepFilterNet3** (`deep-filter` 0.5.6) — shovqin tozalash. H. Schröter va b. MIT / Apache-2.0.
- Shriftlar: Noto Sans, Noto Serif (OFL), Roboto Slab (Apache-2.0) — `templates/fonts/`.
