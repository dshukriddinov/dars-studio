# CLAUDE.md — Dars Studio

Lokal, yarim avtomatik videodars montaj tizimi: yashil fondagi o'qituvchi videosi + PPTX → slayd sinxroni,
keying, Eye Contact, ovoz tozalash, pauza kesish → MP4/SRT/Premiere paketi. Windows 11, RTX 5070 Ti 16 GB, 64 GB RAM.

**To'liq talablar:** `docs/TEXNIK_TOPSHIRIQ.md`. **Ish tartibi va joriy bosqich:** `docs/BOSQICHLAR.md`.
**Qarorlar va o'lchovlar tarixi:** `docs/QAROR_JURNALI.md`. Sessiya boshida shu uchtasini o'qi.

## Buyruqlar

```
python -m pytest -m "unit or media"        # GPU'siz, Linux va Windows
python -m pytest -m gpu                     # CUDA kerak (RTX 5070 Ti)
python -m pytest -m windows                 # PowerPoint COM, pywebview
python -m darsstudio.doctor                 # muhit tekshiruvi
python tools/make_test_media.py             # sintetik test media (conftest avtomatik chaqiradi)
python tools/render_bench.py                # render tezligi, VRAM
ruff check . && mypy darsstudio
npm --prefix ui run build && npm --prefix ui test
```
Windows'da portativ Python: `runtime\python\python.exe` (yuqoridagi `python` o'rniga).

## Oltin qoidalar

1. **Vaqt.** fps hamma joyda `fractions.Fraction`. Vaqt oraliqlari asl videoning kadr indekslarida, `[start, end)`.
   Chiqish vaqti faqat `media/timemap.py` orqali. Float soniyalarni yig'ish taqiqlanadi.
2. **ffmpeg.** Faqat `darsstudio/media/ffmpeg.py` orqali chaqiriladi. Versiya 7.1.1. `subprocess` ni to'g'ridan
   chaqirma. Har chaqiruvda `encoding="utf-8", errors="replace"`, Windows'da `CREATE_NO_WINDOW`.
3. **Rang.** Manba diapazoni va matritsasi probe'dan olinadi; rawvideo pipe'larda kirish/chiqish teglari aniq
   beriladi (aks holda ffmpeg yashirin konvertatsiya qo'shadi). Chiqish: BT.709, limited range.
4. **A/V sinxron.** Video va audio `start_time` farqi har eksportda saqlanadi va testda tekshiriladi.
5. **GPU.** Har GPU ishi `jobs/worker.py` orqali alohida jarayonda, resurs e'loni bilan (`vram_mb`, `nvenc`, `nvdec`).
   Server jarayoni CUDA'ni yuklamaydi. Jami VRAM ≤ 13 GB.
6. **Oraliq videolar yo'q.** Yakuniy video bitta render o'tishida quriladi. Tahlil natijalari yon fayllarda (`cache/`).
7. **Eye Contact** — `engines/eye-contact` papkasi (2026-10-29 dan submodule emas, repo ichida), lekin chegara
   saqlanadi: faqat CLI orqali (`--patches-out`), ichki kodini Studio'dan import qilma.
8. **Offline.** Ish vaqtida tarmoqqa murojaat yo'q. Modellar faqat `tools/fetch_models.py` orqali, manifest + sha256.
9. **Litsenziya.** Yangi kutubxona yoki model qo'shishdan oldin litsenziyani tekshir (TZ 10.2). AGPL va
   "non-commercial" taqiqlangan. Noma'lum bo'lsa — to'xta va so'ra.
10. **Til.** UI matnlari, xato xabarlari, foydalanuvchi jurnali, README — o'zbek (lotin). UI'da `oʻ`, `gʻ` uchun U+02BB.
    Identifikatorlar ingliz tilida. Kod izohlari o'zbek yoki ingliz tilida, qisqa.
11. **Xatolar.** Foydalanuvchiga: sabab + nima qilish kerak, o'zbekcha, bitta jumla. Texnik tafsilot — jurnalga.
12. **Saqlash.** Loyiha holati faqat `project/store.py` orqali (atomik yozish). Har o'zgarish `project/commands.py`
    buyrug'i (undo/redo).

## Har vazifada

- Avval reja (qaysi fayllar, interfeyslar, testlar), keyin kod.
- Har funksional o'zgarishga test. Media testlari sintetik media bilan (`tests/conftest.py`), haqiqiy videolar repo'ga
  qo'shilmaydi. GPU/Windows testlari tegishli belgi bilan.
- O'lchov talab qilinadigan joyda (tezlik, VRAM, aniqlik) — o'lcha va `docs/QAROR_JURNALI.md` ga sana, commit va
  raqamlar bilan yoz. Taxminiy raqamni o'lchangan deb yozma.
- Bosqich oxirida: DoD (`docs/BOSQICHLAR.md`) bandma-band tekshiriladi, `CHANGELOG.md`, commit.

## Qilma

- `runtime/`, `models/`, media fayllar, `cache/`, foydalanuvchi loyihalarini commit qilma.
- TZ'dagi qarorlarni (D-01..D-13) jimgina o'zgartirma — kerak bo'lsa asoslab taklif qil va QAROR_JURNALI'ga yoz.
- Testni o'tkazish uchun testni yumshatma; sababini top.
- Uzoq ishni (render, ASR) bloklovchi tarzda server jarayonida bajarma.
- `print` bilan debug qoldirma; `logging_setup.py` dagi logger.

## Tuzilma (qisqa)

`darsstudio/` — backend paketi (media, project, slides, audio, asr, sync, render, export, jobs, api).
`ui/` — React + TS. `engines/eye-contact/` — submodule. `templates/` — studiya shablonlari. `tools/` — benchmark va
yordamchi skriptlar. `tests/` — unit, media, gpu, windows. Batafsil: TZ 11-bo'lim.
