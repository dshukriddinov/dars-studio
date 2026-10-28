# Qarorlar jurnali

Har yozuv: sana, bosqich, qaror yoki o'lchov, sabab, dalil (commit, fayl, buyruq). Yangi yozuvlar yuqoriga.

---

## 2026-10-28 — DSBA9600 (inson tahriri) bo'yicha: eksport xatosi, takror aniqligi, sahnalar slaydga ergashishi

- **Eksport xatosi** ("4 ta kesish o'qituvchi so'zining ustiga tushadi, 19:57"): matndan qo'lda kesish; ASR'da
  "etaman." 1197.18 s da tugaydi va "musiqa" shu zahoti boshlanadi (bo'shliq 0) — kadrga yaxlitlangan chegara so'zga
  20 ms kirib qolardi. Qo'lda kesish chegarasi uchun 1 kadr chidam (avtomatik kesishlar qat'iy qoldi). Bir xil
  kesish 3 marta qo'shilgan edi — endi takror qo'shilmaydi.
- **Takror/qayta boshlash (etalon — foydalanuvchi qo'lda kesgan 22 joy):** topiladi 4 -> **13**.
  - `retake_cuts`: boshidagi >= 3 so'z qayta aytilsa (orasida mazmunli so'z bo'lishi shart) — tashlab ketilgan
    urinish 18 so'zgacha va oxirgi so'zida nuqta bo'lishi mumkin (ASR chala urinishga ham qo'yadi: "qiziltepada.",
    "ikki."); ichidagi gap oxiri qayta aytilgan qismda va undan keyin >= 2 so'z davom etsa ham; aynan 3 so'z
    qaytsa pauzasiz ham ("tizimga byudjetdan tashqari element tizimga…").
  - `stutter_cuts`: >= 6 harfli so'z uchun vergul to'siq emas va pauza 1.2 s gacha ("byudjet, byudjet",
    "avstraliyada avstraliyada" 0.76 s).
  - Yolg'on topilmalar qo'lda tekshirildi va qoidaga aylandi (testlar bilan): "undan keyin esa X… undan keyin esa Y"
    (sanash, DSBA8971), "ikki ming yigirma to'rtinchi… ikki ming yigirma oltinchi" (yillar, DSBA9359),
    "nima muammolar bor? <tushuntirish> nima muammolar bor va…" (DSBA8971), "mana shu manbalarni… mana shu,
    masalan" (o'xshash, lekin davomi). Boshqa darslarda yangi takliflar: DSBA9359 +9, DSBA9607 +7, DSBA8971 +1 —
    ko'rib chiqilganlari haqiqiy takror (bittasi dars boshidan oldingi gap).
  - Topilmay qoldi (9): bitta so'zli qayta boshlash ("poytaxtda eto, poytaxtda esa"), boshiga so'z qo'shilgan qayta
    boshlash ("mavzu nima uchun… | ushbu mavzu nima uchun…"), son takrori ("o'n to'qqiz. o'n to'qqiz.").
- **Sahnalar slaydga ergashmasdi:** sahna tavsiyasi (slayd almashganda A, 10 s dan keyin B) slayd chegarasi
  qo'lda surilganda eski joyda qolardi (DSBA9600: 36/37 oraliq, 7 s gacha farq). Endi chegara surilganda unga
  bog'langan tavsiya sahnalari ham suriladi (bitta buyruq); "Slaydlarga moslash" tugmasi
  (`POST /relayout`) tavsiyani qayta joylaydi, qo'lda o'zgartirilganlar saqlanadi. Topilgan xato: bir xil sahnali
  qo'shnilar birlashganda qo'lda belgisi yo'qolardi (moslash uni qaytarardi) — tuzatildi.
- **Slayd chegaralari (DSBA9600, AI vs inson):** ±2 s 16/25, AI 9 marta erta (2–20 s), kech 0. Sinab ko'rildi:
  yangi slayd sarlavhasi so'zlari tilga olingan gapga ko'chirish — jami 5 darsda ±2 s 58/85 -> 52–54/85
  (yomonlashdi: erta holatlarda o'qituvchi sarlavhani aytmaydi), **qaytarildi**. Ochiq masala.
- Batafsil tahrir: kesish chetlarini sudrash (so'z ichiga tushsa bo'shliqqa), sahna chegarasini sudrash va ikki
  bosish A <-> B, C — kesish asbobi, transkript ijroda o'zi suriladi.

---

## 2026-10-28 — Slayd animatsiyasi: javob o'qituvchi aytganda chiqadi; ingliz tili 3 unit bo'yicha o'lchov

**Talab (foydalanuvchi):** topshiriq slaydlarida javoblar PowerPoint animatsiyasi bilan chiqadi — topshiriqni
tushuntirayotganda javob ko'rinmasligi kerak. Avval slayd doim yakuniy holatda (barcha javoblar ko'rinib) edi.

- PPTX: `extract.anim_clicks` — asosiy ketma-ketlik (`mainSeq`) bosish guruhlari, paydo bo'ladigan/yo'qoladigan
  shakl id'lari; `Slide.anim` — har bosishda chiqadigan matn. Matnsiz moslashtirish chizig'i (prstGeom line)
  — uchiga eng yaqin matnli shakl (ta'rif); javob qutisi foni (matnsiz to'rtburchak) hisobga olinmaydi.
- Render: PowerPoint COM'da har holat uchun hali chiqmagan shakllar xotirada yashirilib eksport (`NNN_k.png`,
  manba faqat o'qish uchun ochiladi, saqlanmaydi). Unit 1 (15 slayd, 22 qadam): 12.6 s. LibreOffice/PDF —
  qadamsiz (yakuniy holat). Eski kesh (stamp'da "steps" yo'q) qayta render qilinadi.
- Model: `Project.anim_steps` (slayd, click, kadr, ai/manual). Bo'sh — yakuniy holat (eski loyihalar o'zgarmaydi).
- Vaqt (`slides/anim.py`): bosish matni slayd oralig'idagi nutqdan tartib bilan, faqat mazmunli so'zlar bo'yicha
  ("He is the CEO" -> "ceo"; avval yordamchi so'zlar savol gapiga mos kelib 12/22 qadam erta chiqardi). Ibora
  chetidan slaydning o'z matni davom etsa ("true or false", "simple or continuous") — topshiriq o'qilmoqda, o'tkaziladi.
  "Answers: 1→e 2→h…" kabi bitta qutida hamma javob — yorliq so'zi ("now answers"). Topilmagan bosish kechroq
  (keyingi topilgandan yoki slayd oxiridan 1.5 s qadam bilan orqaga) — javob hech qachon erta chiqmaydi.
- Kompozitor: rasm id = slayd + 1000 * holat (animatsiyasiz slayd — o'z raqami, eski xatti-harakat va testlar
  o'zgarmadi); slayd ichida qadam — 4 kadr crossfade (clock wipe emas). Premiere paketi ham qadam rasmlari bilan.
- UI: Batafsil tahrirda "Javoblar (animatsiya)" yo'lagi (sudrab surish, qo'shni qadamlar orasida, `manual`),
  slayd ekrani playhead'dagi holatni ko'rsatadi ("2 ta javob ko'rinadi").
- **O'lchov — qadam vaqti, Unit 1, montajchi (english1.prproj, Slide06_0…_5 kliplari) bilan:** 22 qadam,
  ±1 s 20/22, o'rtacha |farq| 0.57 s, **1 s dan erta 0**, kech 1 (14.5 "Disagreeing (politely)": so'zlar orasida
  10 so'z, +4.8 s). Render tekshiruvi: 550 s javobsiz, 560 s 1-javob, 570 s 2 javob (3-chisi 572.5 s da).
  Unit 2/3 da animatsiya yo'q. Unit 4 (etalonsiz): 5- va 11-slaydda "Answers:" qutisi "answer for…" / "now
  answers" da — qo'lda tekshirildi.
- **Slayd chegaralari (3 unit, montajchi etaloni):** Unit 1 ±2 s 8/15, Unit 2 7/14 -> **8/14** (o'rtacha 9.3 ->
  5.9 s), Unit 3 9/13. Yangi `drop_premature`: A->B, <= 20 s da B->A va B keyinroq yana — birinchi borish
  olib tashlanadi (Unit 2: reja slaydida keyingi bosqich mazmuni aytilgan). O'zbekcha namuna o'zgarmadi
  (±2 s 94%, median 1.26 s). Qolgan xatolar: o'qituvchi slaydni tushuntirayotganda keyingi slayd mazmunini aytadi
  (Unit 2 12-slayd -33 s), qisqa (<= 10 s) slaydlar topilmaydi. Unit 4 (36 slayd, etalonsiz) yomon: 17 slayd
  topildi, 3<->4 qayta-qayta — ochiq masala.
- Topilgan va tuzatilgan xato (avvaldan): `project_lock` — Windows'da o'chirilayotgan qulf faylini ochish
  `PermissionError` beradi (FileExistsError emas) -> parallel buyruqlardan biri yo'qolardi
  (`test_concurrent_stacks_no_lost_update` 31 urinishda 1 marta yiqildi). Endi band deb kutadi (40/40 o'tdi);
  doimiy PermissionError timeout bilan tugaydi.

---

## 2026-10-28 — Ingliz tili darslari (dars tili `meta.til`)

- Foydalanuvchi: ingliz tili darsi deyarli to'liq inglizcha, orada o'zbekcha so'zlar bo'lishi mumkin. Yangi dars
  formasida "Dars tili" (O'zbek / Ingliz); `meta["til"] = "en"` (sxema o'zgarmadi, `meta` da "til" ko'zda tutilgan).
  Keyin o'zgartirilmaydi (qayta tayyorlash qo'lda tahrirlarni yo'qotadi), 1-qadamda faqat ko'rsatiladi.
- ASR: inglizcha — `whisper-large-v3-ct2` (manifestda bor, MIT), `language="en"`, so'z vaqtlari Whisper'dan (o'zbek CTC
  inglizcha so'zlarni tekislay olmaydi); lug'atdan faqat shu tildagi atamalar. VRAM e'loni tilga qarab (3.6 GB).
  `cli asr` ham dars tiliga qaraydi.
- Signal so'zlar bitta ro'yxatda (aralash nutq uchun): qayta o'qish "sorry/again/restart", slayd o'tishi
  "next/following slide/page" (+ "so, okay, for the" kirish so'zlari), xayrlashuv "thank you / goodbye".
- So'z takrori ("brand brand") kesish taklifi inglizchada o'chirilgan: Whisper ikki so'zga 0.2 s beradi — kesish
  so'zni qirqadi. Gap darajasidagi takror va qayta o'qish qoladi.
- Qayta o'qish qoidasi: pauzadan oldingi gap chala qolgan bo'lsa (nuqtasiz) signal so'zsiz ham 5 mos so'z yetarli
  (avval 7). O'zbekcha darslarda eski/yangi taqqoslandi: DSBA9359 +1 (1218 s), DSBA9607 +2 (238 s, 1184 s) — uchalasi
  qo'lda tekshirildi, haqiqiy qayta o'qish; DSBA8971, namuna o'zgarmadi.
- **O'lchov (haqiqiy dars):** "Unit 1 Understanding Brands" (DSBA8969.MOV, 11:49, 15 slayd) — montajchining Premiere
  loyihasi (english1.prproj) etalon: video yo'laklaridagi klip In/Out'laridan saqlangan oraliqlar va slayd PNG'lari
  boshlanishi asl video vaqtiga o'girildi. Tayyorlash (import+proxy, audio, ASR, sinxron, kesish) 258 s; ASR RTF 0.10,
  1753 so'z, matn sifati yuqori (ism, Dior, CEO to'g'ri).
  - Slayd chegaralari (13 ta, montajchi kesgan oraliq ichiga tushsa farq 0): signal so'zlarsiz ±2 s 4/13, o'rtacha
    3.8 s; "next slide" bilan **±2 s 8/13, ±5 s 10/13, o'rtacha 2.4 s**. Qoldi: 2-slayd (10 s, reja) topilmadi;
    10/12/14 4–6 s erta (12: 11-slayddagi misol gap 12-slayd mashqida ham bor). O'zbekcha namuna o'zgarmadi
    (±2 s 94%, median 1.26 s — avvalgi kod bilan aynan shu).
  - Kesishlar: montajchi 11 joy (35.9 s) — 9/11 topildi (264–274 s qayta boshlash ham); takliflar 18 ta, 9 tasi
    montajchida yo'q (10.8 s: 1–1.6 s pauzalar, 2 "mmm") — taklif, inson hal qiladi. Topilmadi: 31–34 s ("let's get
    started" ikkinchi marta), 85–87 s (gap ichidagi 1.6 s pauza).

---

## 2026-10-28 — Batafsil tahrir: 3-ekran "Tayyor video", ekranlarni yoqish/o'chirish

- Ekranlar: "Asl video", "Slayd", "Tayyor video" — har biri alohida yoqiladi (kamida bittasi qoladi), tanlov
  brauzerda saqlanadi. Asl video yashirilsa ham pleyer va ovoz undan (proxy) ishlaydi.
- Tayyor video: butun dars `render` vazifasi bilan (alohida GPU jarayoni) `cache/preview/final_<xesh>.mp4` ga,
  intro/outro va SRT'siz (asl kadr bilan 1:1 moslash uchun). Render boshlanganidagi saqlangan oraliqlar va
  project.json xeshi `final_<xesh>.json` ga; loyiha o'zgarsa "eskirgan — Yangilash". UI asl kadrni shu oraliqlar
  bo'yicha chiqish kadriga o'giradi (`srcToOut`); kesilgan joyda "Bu joy kesiladi". Eski final_* fayllar yangisi
  tayyor bo'lganda o'chiriladi.
- Yangi kodlash profili `korish` (2 Mbit/s VBR, preset p1), faqat ko'rish uchun. O'lchov (DSBA8971, 60 s bo'lak,
  1500 kadr, ishga tushish bilan): web/p7 81.5 s, 35.7 MB; korish/p1 78.3 s, 14.8 MB — tezlikni enkoder
  belgilamaydi, hajm 2.4x kichik. Butun dars (23 878 chiqish kadri): web/p7 435 s, 592 MB; korish/p1 **319 s,
  232 MB** (~75 kadr/s; 144.8 kadr/s benchmarkdan sekin — sababi o'rganilmagan). UI matnida "~7 daqiqa".
- Sinxron tekshiruvi (headless Chrome, uch nuqta): asl 2446/11010/19574 -> chiqish 2373/10765/19155, tayyor video
  aynan shu kadrlarda; uzunlik 23 878 kadr = kutilgan.
- Topilgan xato: "Haqiqiy ko'rinish" asl video vaqtini chiqish vaqti deb yuborardi — kesishlar bo'lsa boshqa joy
  render qilinardi (DSBA8971 oxirida ~420 kadr, 17 s siljish). Endi server asl kadrni TimeMap orqali o'giradi.

---

## 2026-10-28 — Batafsil tahrir: timeline qayta qurildi

- Boshqaruv: Alt (yoki Ctrl) + g'ildirak — kursor ostidagi kadr atrofida masshtab (oldinga — yaqin, orqaga — uzoq);
  oddiy g'ildirak va o'rta tugma bilan sudrash — gorizontal surish; `=`/`-` masshtab, `\` butun dars, Home/End;
  masshtab slayderi; "Kuzatish" (ijroda playhead ortidan yurish) o'chirib-yoqiladi.
- Ko'rinish: o'lchov chizig'i soniyalardan kadrlargacha (eng yaqinda 1 kadr = 24 px, 25 fps'da 5 kadr qadam),
  sichqoncha ostidagi vaqt, o'lchovda sudrab ko'rish (scrub); slayd yo'lagida kichik rasm va raqam (chapga
  yopishadi); slayd chegarasini sudrab surish (playhead'dan 8 px ichida unga yopishadi, undo bilan);
  audio to'lqin yo'lagi; butun dars minimap'i (kesishlar belgilangan, ko'rinib turgan oyna sudraladi).
- Audio to'lqin: `GET /api/projects/{name}/waveform` — har kadrga RMS (uint8, 99.5-persentil bo'yicha
  normallangan), `cache/audio/rms.u8` da keshlanadi. DSBA8971 (24420 kadr): birinchi hisob 2.2 s, keyin 2 ms,
  24 KB. Cho'qqi (max) bilan to'lqin deyarli bir tekis to'la chiqdi — RMS tanlandi.
- Topilgan xato (eski timeline'da ham bo'lgan): flex/grid zanjirida `min-width: 0` yo'qligi sababli yaqinlashganda
  konteyner kontent kengligigacha cho'zilib, surish ishlamasdi va "butun dars" masshtabi noto'g'ri hisoblanardi.
- Tekshiruv: haqiqiy loyiha bilan headless Chrome (CDP orqali Alt+g'ildirak hodisalari) — 3 masshtabda skrinshot.
  Batafsil tahrirga to'g'ridan havola: `?dars=NOM&batafsil`.

---

## 2026-10-28 — Matn orqali kesish (transkriptdan so'zlarni belgilab)

- Foydalanuvchi: transkriptdagi so'zni bosib tanlasa, o'sha qism videodan kesilsin. 3-qadamda "Takliflar | Matn"
  yorlig'i (`components/TextEdit.tsx`): so'zni bosish yoki sudrash, Shift + bosish — kengaytirish; "Kesish" yoki
  Delete — qo'lda kesish (`reason: manual`, darhol tasdiqlangan), chegaralari so'zlar orasidagi bo'shliq o'rtasida;
  kesilgan so'z bosilsa "Tiklash" (rad etiladi). Bosilgan so'zga video o'tadi, o'ynayotgan so'z belgilanadi;
  xatboshilar >= 1.5 s pauzada, vaqt belgisi bilan.
- TZ 8.2 invarianti aniqlashtirildi (`check_no_word_cut`): avtomatik kesishlar (pauza, "mmm", yo'tal) hech bir
  so'zga tegmasligi kerak (avvalgidek); qo'lda kesish butun so'zlarni kesishi mumkin, faqat chegarasi so'z yarmiga
  tushmasin (avval qo'lda kesish so'z ustida bo'lsa eksport to'xtardi).
- Sinov (haqiqiy brauzer, uitest loyihasi): 5 so'z Shift bilan belgilandi -> kesish qo'shildi (681–764 kadr),
  so'zlar ustidan chizildi -> "Tiklash" -> rad etildi. Topilgan xatolar: tez bosishlarda tanlov boshi eski holatda
  qolardi (ref bilan tuzatildi), `.cut` CSS sinfi takliflar ro'yxati bilan to'qnashib so'zlarni alohida qatorga
  cho'zardi.

---

## 2026-10-28 — Foydalanuvchi sinovidagi xatolar (DSBA8971)

- Eksport ikki marta to'xtadi: "1 ta tasdiqlangan kesish so'z ichiga tushadi (18163-kadr)". Sabab: `cuts.union`
  "mmm" (726.52–726.76 s) va takror ("progress formulasi va | progress formulasi") takliflarini birlashtirib "mmm"
  sababini qoldirgan — so'zni kesishga ruxsatsiz sabab, xavfsizlik tekshiruvi to'xtatgan. Tuzatish: sabab ustunligi
  so'z kesuvchi (takror/bosh/oxir/qism) > boshqa > pauza; loyihadagi bitta kesish sababi tuzatildi (buyruq, undo
  bilan); eksport v6 o'tdi (965.84 s, A/V 0 ms). Xabar endi vaqt bilan va nima qilish kerakligi bilan.
- Proxy vazifasi PermissionError (fayl band): ikkita ilova nusxasi (12:20 va 23:32 da ochilgan) bitta navbatdan bir
  vazifani bir vaqtda bajargan. `app_window`: bitta nusxa (`workdir/app_instance.txt` + health) — ikkinchi ishga
  tushirish mavjud serverga oyna ochadi. Muvaffaqiyatda eski xato matni tozalanadi.
- UI: 3-qadamda "Tasdiqlash va eksportga o'tish" (video ostida, doim ko'rinadi); vazifa xatolari traceback emas,
  oxirgi xabar qatori; `index.html` no-store (yangilangan UI eski keshdan ko'rinardi — headless sinovda aniqlandi).

---

## 2026-10-27 — UI qayta qurildi: och mavzu, chap panel, 4 qadam, matnli ko'rib chiqish

- Foydalanuvchi: GUI eski/xira, ish tartibi tushunarsiz, tekshirish ekrani noqulay; tanlov — bosqichma-bosqich,
  och mavzu.
- Tuzilish: chap panel (darslar holati bilan, "Yangi dars", navbat qatori, Sozlamalar) + dars sahifasi 4 qadamda:
  1) Fayllar va o'qituvchi (lower-third jonli ko'rinish, video qismlari, slaydlar — ko'rsatilmaganlari belgilanadi),
  2) Tayyorlash (6 bosqich holati, xatoda "Qayta urinish"), 3) Ko'rib chiqish, 4) Eksport (versiyalar, "Ko'rish",
  "Papkada ko'rsatish" — `/api/projects/{name}/reveal`). Eski batafsil tahrir ("Batafsil tahrir") va kalibrlash
  ekranlari saqlandi (Sozlamalar ichida).
- Ko'rib chiqish: har taklif o'qituvchi so'zlari bilan — kesiladigan qism ustidan chizilgan qizil, atrofdagi so'zlar
  kulrang; turlar bo'yicha filtr, katakcha (kesish/qoldirish), "Hammasini kesish/qoldirish", butun dars bo'ylab
  kesishlar xaritasi; qatorni bosish — 2 s oldindan o'ynaydi; "Natijani tinglash" — tasdiqlangan kesishlarni
  o'tkazib yuboradi (haqiqiy brauzerda tekshirildi: 3 s takror o'tkazib yuborildi); klaviatura Probel / ↑ ↓ / Enter.
- Dizayn: tokenlar och palitra (akademiya ko'ki #1F4FD8, matn #17223B), shriftlar videodagi bilan bir xil —
  Roboto Slab (sarlavha), Noto Sans (interfeys), `ui/public/fonts` (offline). To'g'ridan havola: `?dars=NOM&qadam=N`,
  `?yangi=1`.
- Topildi: 2-qism CLI orqali qo'shilganda proxy qayta yasalmagan edi (API'dagi "Davomini qo'shish" uni navbatga
  qo'yadi) — DSBA9359 proxy qayta yasaldi (1244 s).

---

## 2026-10-27 — Ortga qaytib qayta aytish ("qaytadan", "boshqatdan", 2–3 gap oldidan)

- `cuts.reread_cuts` (sabab "takror", taklif): qayta boshlash nuqtasi — signal so'zdan ("qaytadan", "boshqatdan",
  "boshidan", "yangidan", "adashdim…", "kechirasiz") keyingi 15 s ichidagi ibora boshi (oraliqda "demak", xodimlar
  bilan gaplashuv bo'lishi mumkin) yoki >= 1.5 s pauzadan keyingi ibora. Undan keyingi 8 so'z oldingi 90 s bilan
  tartibli moslanadi (birinchi so'z + >= 5 mos so'z signal bilan, >= 7 signalsiz); eng yaqin mos joyning gap
  boshidan qayta boshlash nuqtasigacha kesiladi. ASR yangi urinish boshini boshqacha yozgan bo'lsa, nuqta oldingi
  iboraga suriladi (>= 3 son bo'lmagan so'z mos kelsa).
- Sonlar: `_is_number` (ildiz + son qo'shimchasi) — "uchast" (uchastka) son emas; signalsiz moslikda boshqa son —
  takror emas (yillar), signal bilan son farqi tuzatishning o'zi ("birinchi uchastka" -> "uchta").
- Kalibrlash (3 ma'ruza): DSBA 3 (614, 974 — qismlar ulanishi bilan bir xil, 1051), Asadov 1 ("yo'q, adashdim" —
  retake bilan bir xil), Dalmuradova 0. Oraliq xatolar va tuzatishlar: "okrug" gacha cho'zilgan kesish (qisqa so'z
  talabi, ikki so'zli juftlik), "ikki ming," bilan haqiqiy gapni olish (sonlar hisobga olinmaydi).

---

## 2026-10-27 — Oq chiziq (garbage chegarasi) va uzun takrorlar (xulosa, xayrlashuv)

- Foydalanuvchi (DSBA9359 v5): slayd ekrani ostidan pastgacha oq chiziq. Sabab: yashil mato chekkasi qiyshiq —
  ustundagi yashil ulushi 30% bo'yicha garbage chegarasi 348 (+6 = 355), 98% — 370: 355–370 oralig'ida devor
  qatorlari kalitdan o'tib, kanvasda x~855 da vertikal chiziq bo'lardi (faqat 1-qismda). `keyer.suggest`: chegara —
  >= 95% yashil ustun; qatorlar yashil ustunlar oralig'ida o'lchanadi. DSBA 355 -> 376, Asadov 339 -> 348,
  Dalmuradova 227 -> 231.
- Foydalanuvchi: xulosa va xayrlashuv takrorlangan. `cuts.repeat_cuts` (sabab "takror", taklif): 20 s ichida
  1) tashlab ketilgan urinish — ibora boshidan >= 7 so'z tartib bilan qayta aytilgan (1–2 so'z qo'shilishi/tushishiga
     chidamli), birinchi urinishda gap oxiri yo'q; kesish takror ibora boshidan (oldidagi qisqa "xulosa qilamiz." ham,
     agar ikkinchisi shu so'z bilan boshlansa) ikkinchisi boshigacha;
  2) >= 3 so'zli to'liq gap aynan takrorlangan — birinchisi.
  Sonlar aynan teng bo'lishi shart (`_alike`: "to'rtinchi" ~ "oltinchi" yilni almashtirib haqiqiy gapni kesardi;
  qayta aytish/qismlar ulanishiga ham ta'sir qiladi). Kalibrlash (3 ma'ruza): DSBA 8 ta (hammasi haqiqiy takror:
  222, 586, 614, 843, 903, 956, 1218 xulosa, 1235 xayrlashuv), Asadov 0, Dalmuradova 0. Oraliq variantlarda
  rad etilganlar: 6 so'z chegarasida reja bandlari, sonlari boshqa yillar, to'liq gapdagi atamalar takrori,
  gap boshidan kesish (takrorlanmagan qismni ham olardi).
- DSBA9359 v6: takrorlar tasdiqlandi (foydalanuvchi so'rovi bo'yicha), 1160.12 s, A/V 0 ms.

---

## 2026-10-27 — Dars bir nechta video faylda (DSBA9359 + DSBA9629)

- Foydalanuvchi: dars davomi boshqa faylda (13- va 24-oktabr yozuvlari). 2-qismda kamera yaqinroq va o'ngroqda, yashil
  fon chegarasi boshqa.
- `VideoPart` + `importer.join_parts` (concat, -c copy, sifat yo'qolmaydi) / `append_part` (1-qism indekslari, tasdiqlangan
  kesishlar saqlanadi); renderer `TeacherParts` — har qismga o'z keyer va joylashuvi; `prepare.ensure_parts`.
  Natija: 1-qism 0.9548, 2-qism 0.8791 — kanvasda o'qituvchi bir xil o'lcham va joyda.
- **Topilgan xato:** MOV'ga -c copy ulashda edit list 1-qism boshidagi ochiq GOP 2 kadrini yashirdi (31102 paket,
  31100 kadr; framemd5 bilan aniqlandi) -> indekslar va A/V 80 ms siljirdi, Eye Contact xato berdi. Yechim: MKV;
  probe video boshlanishi = eng kichik paket pts (asl MOV/MP4 lar uchun o'zgarmaydi); `join_parts` to'liq dekod bilan
  kadrlar soni aniq tekshiriladi. Eye Contact dvigatelida ham xuddi shu tuzatish (`studio-ec` b86f2aa).
- Ulanish joyi (`cuts.part_join_cuts`, sabab "qism", avtomatik): 1-qism gap o'rtasida uzilgan ("…tartibga soluvchi
  va."), 2-qism xodimlar bilan gaplashuv bilan boshlanib ("boshidan o'qiyveraman… bo'ldimi?"), o'qituvchi slaydni
  boshidan qayta o'qigan. 2-qism boshi 1-qism oxiri bilan so'zma-so'z moslanadi (juftlik + 8 so'zlik oynada >= 4):
  974.56–1002.84 s kesiladi — "…yetishmayotgan hududlar hisoblanadi. Byudjetlararo transfertlarni…". Moslik bo'lmasa
  — "uch, ikki, bir, boshlasangiz bo'ladi" yoki jimlik.
- QA: TP -1.4 dBTP (chegara -1.5). Limiterdan keyin -3.0 dBFS, AAC'dan keyin -1.5 dBTP (o'lchandi) -> limiter
  -4 dBFS (`LIMIT_LIN` 0.631). v5: 1220.92 s, A/V 0 ms, -16.7 LUFS, TP -3.0 dBTP.

---

## 2026-10-27 — Joylashuv masshtabi: bosh va yelka bo'yicha (kaft bo'yicha emas)

- Foydalanuvchi (DSBA9359, UI orqali): o'qituvchi juda yaqin, son yuqori qismi ko'rinishi kerak edi. Sabab: bu
  o'qituvchi qo'llarini deyarli doim beli oldida tutadi — "kaftlar" bel darajasida topildi va kadr pastiga moslandi:
  masshtab 1.31.
- O'lchov (alfa siluet, 30 s qadam): bosh tepasi -> bo'yin (bosh ostidagi eng tor qator) / yelka kengligi:
  Asadov 162 / 370 px, DSBA9359 172 / 378 px — o'qituvchilar kadrda deyarli bir xil.
- `TeacherFit`: masshtab = o'rtacha(head_px / bosh, shoulder_px / yelka), head_px 161, shoulder_px 368 (Asadov
  namunasi x0.9936); bosh tepasi va markaz avvalgidek. Natija: Asadov 0.9936 -> 0.9942 (o'zgarmadi), DSBA9359
  1.3136 -> 0.9548. Kaft (teri rangi) aniqlash olib tashlandi.
- DSBA9359 eksport v3 (14 taklif foydalanuvchi tasdiqlamagan — qo'llanmadi).

---

## 2026-10-27 — UI: yangi loyiha (o'qituvchi ma'lumoti), Loyiha sahifasi, to'liq eksport

- Yangi loyiha: video/PPTX Windows oynasidan tanlanadi (`/api/pick-file`, tkinter — stdlib), shablon default
  `akademiya`; o'qituvchi maydonlari: ism familiya (majburiy), ish joyi, lavozim, ilmiy daraja/unvon (ixtiyoriy) +
  fan, mavzu, dars; lower-third jonli ko'rinishi (`/api/lower-third-preview`, 400 ms kechikish bilan). Kiritishda
  o'/g' dan keyingi apostrof U+02BB ga almashtiriladi. Lower-third: ism; "ish joyi + lavozim"; ilmiy unvon (eski
  `unvon` "a | b" ham ishlaydi).
- "Loyiha" sahifasi: tayyorlash bosqichlari holati (WS), o'qituvchi ma'lumotini tahrirlash (buyruq, undo bilan),
  kesish takliflari turlari bo'yicha ("Hammasini kesish" / "Qoldirish"), slaydlar (ko'rsatilmaganlari qizil).
- Eksport: `export` vazifasi (avval UI faqat `render` qilardi — QA, jadval, intro/outro'siz SRT yo'q edi);
  "Subtitr (SRT)" va "Premiere/DaVinci paketi" katakchalari.
- `DarsStudio.bat`: ishlab chiqish muhitida Maxine yo'li yonidagi "eye contact" loyihasidan (aks holda UI'dan Eye
  Contact yiqilardi).
- Sinov (API, 2 daq klip): import -> 7 vazifa (slides, audio, asr, eyecontact, proxy, sync, cuts) tayyor -> takliflar
  tasdiqlandi -> export v1: 122.0 s, A/V 0 ms, lower-third UI maydonlaridan. Brauzerda: Loyiha, Yangi loyiha (jonli
  ko'rinish, Gʻ almashinuvi), Eksport ekranlari, konsol xatosi yo'q. **Tekshirilmagan:** "Tanlash" tugmasi
  (Windows oynasi) — foydalanuvchi sinab ko'radi.

---

## 2026-10-27 — Offline sinov qayta (yangi qismlar: DeepFilterNet CLI, PANNs, "mmm", qayta aytish)

- `tools/offline_check.py` (Python jarayonlariga socket qo'riqchisi, faqat 127.0.0.1/::1): `0Z1A1253.MP4` 2 daqiqa +
  `yangi35.pptx`: import 22.2 s, audio (DeepFilterNet3 CLI + PANNs) 16.6 s, ASR 26.0 s, sinxron 1.5 s, kesish 1.6 s,
  Eye Contact (Maxine) 34.5 s, eksport 56.6 s — jami 159 s, **tarmoqqa urinishlar: yo'q**.
- `deep-filter.exe` (Rust, qo'riqchi ko'rmaydi) statik tekshirildi: import DLL'lari advapi32, bcrypt, dbghelp,
  kernel32, ntdll, vcruntime140, CRT — ws2_32/winhttp/wininet yo'q (tarmoq API'si yo'q); ichidagi URL'lar faqat
  xato/hujjat matnlari (docs.rs, clap issues).
- Internet faqat bir martalik o'rnatishda: Python paketlari, `tools/fetch_models.py` (manifest + sha256).

---

## 2026-10-27 — Mualliflik matni: oxirgi 5 s, o'ngdan sirg'alib kiradi

- Foydalanuvchi: matn statik turibdi, namunada harakatlanadi; oxirgi 5 s da ko'rinsin (sinov videosi qayta
  ishlanmadi — keyingi eksportlardan).
- O'lchov (tayyor.mp4, 815–824 s, matn chap cheti har 0.2 s): polosa matn bilan birga o'ngdan chapga **chiziqli**
  ~130 px/s, ~640 px, 815.2 -> 820.1 s; x~886 dan o'ngi ko'rinmaydi (niqob); keyin outro'gacha joyida.
- `Copyright.on = "tail"` (default): `seconds` 5, `slide_s` 3 (5 s ichida 2 s o'qish uchun joyida turadi),
  `slide_px` 640. `Overlay.slide_in_px/slide_frames/clip_x`; render keshi kalitida ham.

---

## 2026-10-27 — "mmm/eee" o'ylab turish tovushlari; gapirilmagan slaydlar; chegara tartibi

**O'ylab turish tovushlari.** Foydalanuvchi v4 17:47–17:48 ni ko'rsatdi (manba 1112.1–1114.8 s, "tarqatish, …
tashviqot"). O'lchov (30 ms kadrlar): 1113.56–1114.40 s, -9..-12 dBFS (nutq darajasi), ovozlilik 0.7, F0 110–115 Hz
barqaror, ASR so'zi yo'q; VAD nutq deb hisoblagani uchun pauza kesishi tushmagan.
- `audio/fillers.py` (model yo'q): so'zlar orasidagi bo'shliqda >= 240 ms, ovozlilik >= 0.5, umumiy RMS dan
  18 dB ichida, kadrlarning >= 75% i F0 medianasidan +-8% ichida (std mezoni oktava xatosida 1113.6 ni o'tkazib
  yubordi). Sinov videosi: 22 nomzod, Dalmuradova: 2; ishlash 0.1 s.
- `cuts.filler_cuts` (sabab "to'ldiruvchi"): tovush to'liq + bo'shliqdagi jimlik, so'zlardan 30 ms ichkarida.
  `cuts.union`: ustma-ust takliflar birlashadi (avval yangi taklif pauza bilan kesishsa tashlanardi — "mmm" qolardi).
- Natija (v5): 19 ta "mmm" kesildi; 1112.1–1114.8 dagi 2.66 s bo'shliq chiqishda 0.40 s. Kliplar:
  `workdir/eshankulov/tekshiruv/mmm/` — **aniqlik foydalanuvchi bahosidan keyin o'lchanadi**.

**Gapirilmagan slaydlar.**
- `sync.run.thanks_slide`: oxirgi slayd "rahmat/e'tibor" bo'lsa va ko'rsatilmagan bo'lsa — oxirgi 60 s dagi
  "rahmat/ko'rishguncha" gapi boshidan (0.3 s oldin) oxirigacha. Sinov: 42-slayd endi chiqishda 1101.7 s dan.
- `unshown` (sinxron natijasi) va QA `korsatilmagan_slaydlar` ogohlantirishi. Sinov: 15, 26, 38, 41 (15 va 38 da
  slayd matni yo'q — OCR keyinroq, foydalanuvchi ruxsati bilan).

**AI sinxron xatosi topildi:** aniqlashtirish/signal chegaralarni alohida suradi, tartib buzilardi (37->39 1155.8 s,
39->40 1146.9 s -> 39-slayd 0.1 s miltillardi). Endi vaqtlar o'sish tartibida qayta beriladi. Dalmuradova G3 o'zgarmadi
(+-2 s 94%, median 0.20 s).

Eksport v5: 1109.72 s, A/V 0 ms, jami kesilgan 69.4 s.

---

## 2026-10-27 — Gapni qayta aytish (qayta boshlash, "yo'q, adashdim")

- Foydalanuvchi: v3 da 16:22 (gap 5–6 so'zdan keyin qayta boshlangan) va 17:28 ("yo'q, adashdim shu yerda" deb qayta
  aytilgan) qolib ketgan. Manbada 998.0 s va 1066.7 s.
- `cuts.retake_cuts` (sabab "takror", taklif):
  1) qayta boshlash — ibora boshi (gap oxiri yoki >= 0.5 s pauzadan keyin) <= 10 so'z / 12 s ichida qayta aytilgan,
     ikki so'z aynan bir xil yoki uchta so'z o'xshash (difflib >= 0.7), birinchi urinishda gap oxiri yo'q; zanjir —
     oxirgi urinishgacha;
  2) tuzatish iborasi ("adashdim", "kechirasiz", "noto'g'ri aytdim"…): to'g'ri gapdagi birinchi so'z juftligi
     30 s ichidagi eng yaqin o'xshash juftlikka moslanadi -> xato gap boshi (gap chegarasigacha orqaga); kesish
     to'g'ri gap boshigacha (oraliqdagi oxirgi "demak/ya'ni…" dan keyin). Chegaralar so'zlar orasi o'rtasida.
- Natija: sinov videosida aynan 2 ta (997.3–1005.2 s: ikki tashlab ketilgan urinish; 1051.3–1070.0 s: xato javob +
  "yo'q, adashdim shu yerda. saylov, demak,"), Dalmuradova namunasida 0. Birinchi variant (2 so'z o'xshash) 68 s da
  bitta to'liq gapni ("…eng muhim huquqiy asos, bu O'zbekiston Respublikasining Saylov kodeksi") kesardi — shart
  qattiqlashtirildi. Chiqishda: "…qaysi organlar tomonidan ko'riladi? Bu uchta saylov komissiyasi tomonidan…".
  Eksport v4: 1127.76 s (-40.6 s jami), A/V 0 ms.

---

## 2026-10-27 — O'qituvchi joylashuvi: gavda qoidasi (foydalanuvchi namunasi bo'yicha)

- Foydalanuvchi: o'qituvchi to'liq bo'y-basti bilan ko'rinmasin; slayd o'ng cheti bilan kanvas o'ng cheti o'rtasida;
  pastki chegara yonga tushgan qo'llar darajasida. Namuna skrinshoti (`extra/image.png`, VLC, video maydoni
  3502x1970 -> 1920x1080) dan: bosh tepasi y~250, kaftlar y~1025, markaz x~1473 (= (1026+1920)/2).
- `templates.TeacherFit` + `placement.body_landmarks/fit_body`: manbada bosh tepasi (alfa birinchi qatori), kaftlar
  (alfa ichida yuzdan pastdagi teri rangi, YCrCb, pastki chet), yelka zonasi markazi — 30 s qadam bilan kadrlar
  medianasi. Sinov videosi: bosh 66, kaftlar 848, markaz 1063 (manba px) -> masshtab 0.9936, (417, 184).
  `akademiya` shablonida qat'iy `teacher_placement` (0.929 @ 692,79 — Dalmuradova namunasi) o'rniga `teacher_fit`.
- Lower-third: Roboto Slab'da U+02BB yo'q ("Gʻ" kvadrat chiqdi) — `overlays.glyph_safe` shriftda belgi bo'lmasa
  U+2018/U+2019 ga almashtiradi (montajchi namunasida ham "G‘").
- Sinov loyihasi o'qituvchisi: Asadov Shavkat Gʻaybullayevich (avval Eshankulov deb noto'g'ri berilgan edi).
  Eksport v3: 1153.8 s, A/V 0 ms.

---

## 2026-10-27 — Nutq kamchiliklari (yo'tal, aksa, takror); sinov videosi `0Z1A1253.MP4` (Eshankulov)

**Sinov materiali:** `namuna/0Z1A1253.MP4` (1168.36 s, 1080p25, green screen, yon tomonda oq devor) + `yangi35.pptx`
(42 slayd). tayyor2.mp4 (o'sha o'qituvchi) bu xom videodan **emas**: audio konvert korrelyatsiyasi r ~0.3, joylar
tasodifiy — montajchi ground truth'i yo'q.

**Qarorlar:**
- `audio/events.py`: PANNs Cnn14 16 kHz (og'irliklar Zenodo 3987831 CC-BY-4.0, md5 Zenodo bilan mos; kod MIT —
  arxitektura o'zimizda qayta yozildi, `torchlibrosa`/`panns_inference` yo'q). Checkpoint numpy obyektli: faqat
  numpy turlari ruxsat etilgan `weights_only=True` bilan yuklanadi. 1 s oyna, 0.1 s qadam. Butun video GPU'da **3.6 s**.
  Audio bosqichida (`events.json`), denoise'dan oldingi audio'da.
- Sinflar: Cough, Throat clearing, Sneeze, Hiccup, Burping, Humming. **Sniff/Gasp chiqarildi**: sinov videosida
  0.3+ ehtimolli 74 hodisaning ko'pi shular, kadrlar bo'yicha — gaplar orasidagi oddiy nafas.
- `cuts.event_cuts`: ehtimol >= 0.6; kesish hodisa joylashgan so'zlar orasidagi bo'shliq (har tomonda 0.175 s qoldirib),
  so'zga tegmaydi; bo'shliq < 300 ms bo'lsa taklif yo'q. `cuts.stutter_cuts`: ketma-ket bir xil so'z, birinchisi
  kesiladi. Yolg'on takrorlar filtrlandi (sinovda 8 dan 6 tasi): nol uzunlikli so'z (CTC artefakti), ".uch" (93.3 kasr),
  "rais, rais o'rinbosari" (tinish belgisidan keyin). Hammasi **taklif**, inson tasdiqlaydi.
- QA: freezedetect `n` 0.002 -> 0.0005 — qimirlamay turgan o'qituvchi (kadrning ~1/4 qismi) "muzlagan" chiqardi
  (sinov v1: 4 soxta ogohlantirish -> 0; B oraliqlari baribir chiqarib tashlanadi).
- Model sabablari `CutProposal.reason`: bosh, oxir, yo'tal, aksa, to'ldiruvchi, takror (UI'da yorliqlar).

**Sinov natijasi (barcha takliflar tasdiqlangan, `exports/v1`):** bosh 0–4.44 s ("uch, ikki, bir, boshlasangiz
bo'ladi"), oxir 1168.04 s dan ("e'tiboringiz uchun rahmat" dan keyin); pauza 8, aksa 2 (463.0, 1004.6), yo'tal 2
(774.4–776.9, 1088.9–1090.2), takror 2 (558, 692); 84 s dagi aksa (0.96) pauza kesishi ichida. Jami -25.3 s.
1153.8 s, A/V 0 ms, -16.2 LUFS, QA faqat 4 tasdiqlanmagan sinxron chegarasi bo'yicha.
**Tekshirilmagan:** hodisa kesishlarining to'g'riligi — kadrlarda aniq yo'tal/aksa harakati ko'rinmadi; foydalanuvchi
`workdir/eshankulov/tekshiruv/` kliplarini eshitib baholashi kerak (aniqlik shundan keyin o'lchanadi).
"eee/mmm" to'ldiruvchilar: ASR ularni yozmaydi, PANNs "Humming" sinovda chiqmadi — hali yechim yo'q.

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
