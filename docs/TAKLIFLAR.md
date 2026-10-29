# Yaxshilash takliflari

Chuqur tahlil natijasi (2026-10-29). Holat o'zgarganda shu fayl yangilanadi.
Tartib — ustuvorlik bo'yicha. Har bandda: muammo, taklif, kutilgan foyda.

## Loyiha holati (tahlil paytida)

| Ko'rsatkich | Qiymat |
|---|---|
| Bosqichlar (B0–B11) | hammasi qurilgan, B11 (pilot) tugallanmagan |
| Kod | backend 8 900, UI 2 900, testlar 2 700 qator |
| Testlar | 282 Python + 45 UI, hammasi yashil; ruff/mypy toza |
| Qabul (AC-01..15) | 6 bajarildi, 6 qisman, 3 kutilmoqda |
| Slayd sinxroni (±2 s, 5 etalon dars) | 74% (63/85) |
| A→B sahna (±2 s, 7 montajchi loyihasi) | 41% (30/73) |
| Animatsiya qadami (±1 s, Unit 1) | 91% (20/22), erta chiqish 0 |
| Kesish takliflari (DSBA9600 qo'lda etalon) | 59% (13/22) |
| GitHub | remote yo'q — faqat lokal (engines/eye-contact alohida repoda) |

---

## 1. Pilot o'tkazish (B11, AC-14) — eng muhimi

- **Muammo:** bosh maqsad "montajchi vaqti ≤ 45 min" o'lchanmagan; qo'lda montaj
  bazasi (O-09) ham noma'lum — "necha baravar tezlashdi" deyishga asos yo'q.
- **Taklif:** 3 ta haqiqiy dars, haqiqiy foydalanuvchi, sekundomer:
  import → ko'rib chiqish → eksport. Natija `docs/QABUL.md` ga.
- **Foyda:** loyiha maqsadga yetganining isboti; qolgan ishlarning qiymatini belgilaydi.
- **Holat:** kutilmoqda.

## 2. Foydalanuvchi tahriri = bepul etalon (GT yig'ish)

- **Muammo:** aniqlik 7 ta tasodifiy topilgan Premiere loyihasi bilan o'lchanadi.
  Foydalanuvchi UI'da har kuni chegara suradi, taklif tasdiqlaydi/rad etadi — bu
  tayyor etalon, lekin yig'ilmayapti.
- **Taklif:** `tools/collect_gt.py` — tahrirlangan loyihalardan GT to'plash
  (surilgan chegaralar, rad etilgan/qo'shilgan kesishlar) + bitta regression
  benchmark: qoida o'zgarganda "aniqlik oshdimi/tushdimi" bir buyruq bilan.
- **Foyda:** sinxronni 74% dan yuqoriga olib chiqishning yagona ishonchli yo'li.
- **Holat:** kutilmoqda.

## 3. OCR (Tesseract, Apache-2.0 — litsenziya ruxsat etilgan)

- **Muammo:** uchta ochiq masala bitta ildizdan: matnsiz/rasmli slaydlar sinxronda
  ko'rinmaydi; "ko'rsatilmagan slaydlar" sababi noma'lum; noto'g'ri taqdimot
  (Unit 4 holati) faqat bilvosita aniqlanadi.
- **Taklif:** slayd PNG'lariga OCR, natija `Slide.ocr` maydoniga (modelda bor,
  bo'sh turibdi); `ai_align` undan allaqachon foydalanadi.
- **Holat:** kutilmoqda.

## 4. ASR referens transkripti (AC-06, G2)

- **Muammo:** CER o'lchanmagan — modellar bir-biri bilan solishtirilgan, haqiqat
  bilan emas.
- **Taklif:** 5 daqiqalik qo'lda tuzatilgan transkript (O-06 — buyurtmachi).
  UI'da so'zni ikki bosib tahrirlash qo'shilsa: tuzatishlar CER o'lchoviga ham,
  glossariyga ham, 2-banddagi etalonga ham xizmat qiladi.
- **Holat:** kutilmoqda.

## 5. Disk tozaligi

- **Muammo:** `namuna/exports` 4,4 GB, jami eksportlar ~14 GB; har "Tayyor video"
  keshi ~230 MB; loyihani o'chirish umuman yo'q (API'da DELETE yo'q).
- **Taklif:** eksportda oxirgi 2 versiya qoladi, eskilarga "Tozalash" tugmasi;
  loyihani o'chirish — savatchaga (`_trash/` ga ko'chirish, qaytariladigan).
- **Holat:** kutilmoqda.

## 6. Versiya ko'rsatish va "qayta oching" belgisi

- **Muammo:** har tuzatishdan keyin ilovani qayta ochish kerak, lekin foydalanuvchi
  qaysi versiyada ishlayotganini ko'rmaydi.
- **Taklif:** Sozlamalar → Tizim holatiga git hash + sana; server kodi diskdagidan
  eski bo'lsa "Yangilanish bor — qayta oching" belgisi.
- **Holat:** kutilmoqda.

## 7. GPU smoke-testlar

- **Muammo:** `pytest -m gpu` hujjatlarda bor, lekin birorta gpu testi yozilmagan.
  Keyer, NVENC, Eye Contact CLI faqat qo'lda tekshiriladi — drayver yangilanganda
  regressiya sezilmay qoladi.
- **Taklif:** 3–4 tez test: keyer forward (CUDA), NVENC 1 s encode, doctor CUDA,
  eye-contact CLI stub.
- **Holat:** kutilmoqda.

## 8. Mayda, tez yutuqlar

- [ ] O'qituvchi ismlari dublikati ("Pardaev"/"Pardayev") — yaqin ismlarni
      birlashtirish yoki ogohlantirish.
- [ ] `.claude/` va `extra/` ni `.gitignore` ga (har `git status` da chiqib turibdi).
- [ ] AC-11: 25 daqiqalik uzluksiz dars stress-testi (hozir 2 min bo'laklarda).
- [ ] Premiere paketiga intro/outro.
- [ ] GitHub remote: zaxira + tarix uchun private repo (hozir hammasi bitta diskda).

---

Tavsiya etilgan tartib: **1 → 2 → 4** (avval o'lchov, keyin optimallash),
5–6 oraliqlarda. 3 (OCR) — 2-band benchmark'i tayyor bo'lgach, ta'sirini o'lchab.
