# Qabul mezonlari holati (TZ 14-bo'lim) — 2026-10-26

Pilot (B11) hali o'tkazilmagan: bitta haqiqiy dars bor (`namuna/video.MOV`, 13 min 46 s, 1080p25, Canon MOV +
`Taqdimot.pptx`, 19 slayd). Qo'lda tuzatilgan transkript, slayd chegaralari ground truth'i, montajchi baholari va
10/15/25 daqiqalik darslar berilmagan (O-06, O-09). Shuning uchun quyida "Bajarildi" faqat o'lchangan yoki test
bilan isbotlanganlar; qolgani "Qisman" yoki "Kutilmoqda" (sababi bilan).

| ID | Mezon | Holat | O'lchov | Dalil |
|---|---|---|---|---|
| AC-01 | Import | Qisman | 13.8 min haqiqiy dars + PPTX: 20 s, 20 664 kadr, 19 slayd mos. Noto'g'ri fayl o'zbekcha xato bilan rad etiladi. 10/15/25 min darslar yo'q | `tests/media/test_import.py`, `QAROR_JURNALI` B2 |
| AC-02 | Chroma key | Qisman (G1) | Garbage hududida alfa aynan 0 (test). Namunada avtomatik key: devorlar garbage bilan, sochda yashil yo'q (vizual, `workdir/b3/`). Montajchi tekshiruv ro'yxati — kutilmoqda | `tests/media/test_render.py::test_keyer_suggest_and_garbage` |
| AC-03 | Slayd sinxroni | Qisman (G3) | Jurnal: beep xatosi <= 10 ms (sintetik), jurnal -> oraliqlar (test). AI: sintetik 5 darsda ±2 s ichida >= 90%; namunada 19 slayd ketma-ket, 2 shubhali (14<->15 qaytish). Haqiqiy darslar GT'si yo'q | `tests/unit/test_ai_align.py`, `workdir/namuna/cache/sync/ai_align.json` |
| AC-04 | Kompozitsiya | Bajarildi | Warp alfasi ekran ko'pburchagidan 1 px dan chiqmaydi; to'liq namuna renderida "anchor tashqarisida" / "bosh yuqori chetda" ogohlantirishlari 0 | `test_render.py::test_warp_stays_inside_quad`, `Namuna_v3.render.json` |
| AC-05 | Sahnalar | Bajarildi | A->B->A: o'tishlar aynan 8 (slayd) / 12 (sahna) kadr, B kadri to'liq ekran slayd | `test_render.py::test_timeline_transition_lengths`, `test_render_scenes_and_resume` |
| AC-06 | ASR CER <= 10% | Kutilmoqda (G2) | Referens matn yo'q. Kuchli ikki fine-tune o'zaro 94% mos (rubaistt / kotib "WER" 0.061), Whisper large-v3 0.73 | `docs/ASR_BENCH_2026-10-26.md`, `QAROR_JURNALI` B4 |
| AC-07 | Lab-sync <= ±1 kadr | Bajarildi | Sintetik: 52 ms siljishli klipda chaqnash va beep 1 kadr ichida (kesishsiz va 30 kadr kesish bilan). Namuna eksporti: A/V 0.0 ms, davomiylik farqi 0 | `test_render.py::test_render_av_sync_with_offset`, `test_b6.py::test_render_with_cuts_av_sync`, `exports/v3/qa.json` |
| AC-08 | Loudness | Bajarildi | Namuna eksporti: -16.1 LUFS, TP -2.4 dBTP (manba +0.5 dBTP clipping bilan). Sintetik: -16 ± 1 | `exports/v3/qa.json`, `test_b6.py::test_final_audio_loudness_ac08` |
| AC-09 | Eye Contact metrikalari | Qisman | Patch rejimi oddiy chiqish bilan bayt-aniq (stub, Y va UV); haqiqiy klipda Y max farq 1. Modul metrikalari (identity, EAR, blink, flicker) pilotda qayta o'lchanmagan (eval modellari yo'q) | `engines/eye-contact` PR #1, `QAROR_JURNALI` B1 |
| AC-10 | Unumdorlik | Bajarildi (ekstrapolyatsiya) | Render 147 kadr/s (>= 80), VRAM pik 2.7 GB (render), ASR 4.3 GB maks; 13.8 min mashina vaqti: import 20 s + audio ~10 s + ASR 53 s + Eye Contact ~3.7 min + render 2.3 min ≈ 7 min -> 25 min ≈ 13 min (<= 30). RAM: 3 parallel loyiha python jarayonlari pik 6.6 GB | `tools/render_bench.py`, `stability_test` |
| AC-11 | Barqarorlik | Qisman | 3 loyiha navbatda (21 vazifa) — hammasi tayyor; render 42% da worker o'ldirildi, avtomatik qayta urinishda tayyor segmentdan davom etdi. **25 min emas, 2 min bo'laklar** bilan | `tools/stability_test.py`, `QAROR_JURNALI` B10 |
| AC-12 | Eksport | Qisman | MP4 ffprobe bilan qayta o'qiladi (H.264 High, BT.709 tv, AAC 48 kHz), QA ok. Premiere/DaVinci'da XML paketini ochish — inson tekshiruvi kutilmoqda | `workdir/namuna_2min/exports/v2/premiere/` |
| AC-13 | Offline | Bajarildi (emulyatsiya) | Import -> audio -> ASR -> sinxron -> kesish -> Eye Contact -> eksport -> qayta ochish, har jarayonda tarmoqqa ulanish taqiqlangan: 117 s, QA ok, urinishlar 0. Haqiqiy tarmoq o'chirilmadi | `tools/offline_check.py` |
| AC-14 | Montajchi vaqti <= 45 min | Kutilmoqda | Pilotda o'lchanadi; hozirgi qo'lda montaj vaqti (O-09) noma'lum | — |
| AC-15 | Tiklanish | Bajarildi | Dastur yopilib ochilganda 100 buyruq va undo/redo tarixi tiklanadi; parallel jarayonlar bir-birining o'zgarishini o'chirmaydi | `tests/unit/test_project.py` |

## Inson qarorlari (G1–G4) va ochiq savollar

- **G1 (keyer/kompozit):** `workdir/b3/namuna_frag.mp4` va `workdir/namuna/exports/v3/Namuna_v3.mp4` ni ko'ring.
- **G2 (ASR modeli):** tavsiya rubaistt-v2-medium + sarahai CTC; CER uchun 3 x 5 min qo'lda tuzatilgan matn kerak.
- **G3 (AI sinxron):** 3 dars uchun qo'lda belgilangan chegaralar (`time,slide` CSV) -> `tools/align_eval.py --grid`.
- **Sahna qoidasi:** TZ ">= 60 so'z -> B" namunada deyarli butun darsni B qiladi; `meta.b_scene_words` (ko'rgazmada 120).
- **HW-1:** CPU mikrokod 0x11F (< 0x12B) — BIOS yangilash zarur. **HW-4:** `driver_pin.txt` (610.88?).
- **O-08:** haqiqiy studiya foni, logo, lower-third uslubi — hozir sintetik `demo` shablon.
