"""Dars boshi/oxirini kesish (salomlashish / xayrlashish signallari)."""

import math
from fractions import Fraction

from darsstudio.project import cuts
from darsstudio.project.model import CutProposal, Word


def test_trim_head_and_tail() -> None:
    """Salomdan oldingi va xayrlashishdan keyingi qism kesiladi; so'z invarianti ularga tegmaydi."""
    fps = Fraction(25)
    ws = [Word(text=t, start_ms=s, end_ms=s + 400, conf=0.9) for t, s in
          [("boshlasangiz", 800), ("bo'ladi.", 1400), ("Assalomu", 4100), ("alaykum,", 4600), ("ma'ruza", 10000),
           ("rahmat.", 90000), ("keyingi", 91000), ("darsda", 91500), ("ko'rishguncha.", 92000), ("musiqa", 92500)]]
    total = 95 * 25
    c = cuts.trim_cuts(ws, fps, total)
    assert [(x.start, x.end, x.reason, x.status) for x in c] == [
        (0, 95, "bosh", "tasdiqlangan"), (math.ceil(93.0 * 25), total, "oxir", "tasdiqlangan")]
    assert cuts.check_no_word_cut(c, ws, fps) == []
    assert cuts.trim_cuts(ws[2:5], fps, 11 * 25) == []     # salom boshida, xayr yo'q


def _w(items: list[tuple[str, int]]) -> list[Word]:
    return [Word(text=t, start_ms=s, end_ms=s + 300, conf=0.9) for t, s in items]


def test_event_cuts_only_in_word_gaps() -> None:
    fps = Fraction(25)
    ws = _w([("bir", 0), ("ikki", 1000), ("uch", 4000), ("tort", 4400)])
    ev = [{"start_ms": 2000, "end_ms": 2800, "kind": "yo'tal", "prob": 0.9},     # 1300..4000 bo'shliqda
          {"start_ms": 4100, "end_ms": 4300, "kind": "aksa", "prob": 0.9},       # so'zlar orasi 100 ms — yo'q
          {"start_ms": 2000, "end_ms": 2800, "kind": "yo'tal", "prob": 0.3}]     # past ehtimol
    c = cuts.event_cuts(ev, ws, fps, 200)
    assert [(x.start, x.end, x.reason, x.status) for x in c] == [
        (math.ceil(1.475 * 25), math.floor(3.825 * 25), "yo'tal", "taklif")]
    assert cuts.check_no_word_cut([x.model_copy(update={"status": "tasdiqlangan"}) for x in c], ws, fps) == []


def test_stutter_cuts_first_repeat() -> None:
    fps = Fraction(25)
    ws = _w([("demak", 0), ("yaʼni", 1000), ("yaʼni,", 1500), ("saylov", 2000), ("saylov", 5000)])
    c = cuts.stutter_cuts(ws, fps)
    assert [(x.start, x.end, x.reason) for x in c] == [(math.ceil(0.3 * 25), math.floor(1.5 * 25), "takror")]


def test_stutter_false_positives_skipped() -> None:
    fps = Fraction(25)
    ws = [Word(text=x, start_ms=s, end_ms=e, conf=0.9) for x, s, e in
          [("uch", 0, 150), (".uch", 500, 620), ("rais,", 1000, 1300), ("rais", 1400, 1600),
           ("saylov", 2000, 2000), ("saylov", 2000, 2300)]]
    assert cuts.stutter_cuts(ws, fps) == []


def _seq(text: str, t0: int = 0, step: int = 400, gaps: dict[int, int] | None = None) -> list[Word]:
    out, t = [], t0
    for i, x in enumerate(text.split()):
        t += (gaps or {}).get(i, 0)
        out.append(Word(text=x, start_ms=t, end_ms=t + 300, conf=0.9))
        t += step
    return out


def test_retake_restart_chain() -> None:
    # "…etardi. saylov komissiyaning xatti harakatlari ustidan | saylov komissiyaning xatti … qarorlar |
    #  saylov komissiyaning harakatlari va qarorlar ustidan qilingan."  -> ikki urinish kesiladi
    ws = _seq("ishtirok etardi. saylov komissiyaning xatti harakatlari ustidan saylov komissiyaning xatti harakatlari "
              "ustidan qarorlar saylov komissiyaning harakatlari va qarorlar ustidan qilingan.",
              gaps={7: 1200, 13: 2000})
    c = cuts.retake_cuts(ws, Fraction(25))
    assert len(c) == 1
    kept = [w.text for w in ws if not (c[0].start / 25 * 1000 <= w.start_ms < c[0].end / 25 * 1000)]
    assert " ".join(kept) == "ishtirok etardi. saylov komissiyaning harakatlari va qarorlar ustidan qilingan."


def test_retake_correction_cue() -> None:
    ws = _seq("qaysi organlar tomonidan koʻriladi? bu demak, birinchi uchast saylov komissiyasini, okrug sudda "
              "koʻrilishi mumkin. yoʻq, adashdim shu yerda. saylov, demak, bu uchta saylov komissiyasi tomonidan okrug")
    c = cuts.retake_cuts(ws, Fraction(25))
    kept = [w.text for w in ws if not any(x.start / 25 * 1000 <= w.start_ms < x.end / 25 * 1000 for x in c)]
    assert " ".join(kept) == "qaysi organlar tomonidan koʻriladi? bu uchta saylov komissiyasi tomonidan okrug"


def test_retake_complete_sentence_not_cut() -> None:
    ws = _seq("oʻzbekiston respublikasida eng muhim bu huquqiy asos, bu oʻzbekiston respublikasining saylov kodeksi "
              "hisoblanadi.", gaps={8: 800})
    assert cuts.retake_cuts(ws, Fraction(25)) == []


def test_part_join_cuts() -> None:
    """2-qism boshidagi "uch ikki bir boshlasangiz bo'ladi" va 1-qism oxiridagi jimlik kesiladi."""
    from darsstudio.project.model import VideoPart
    fps = Fraction(25)
    parts = [VideoPart(path="a", start=0, frames=25 * 100), VideoPart(path="b", start=25 * 100, frames=25 * 60)]
    ws = _seq("demak shu bilan", 90000) + _seq("uch ikki bir boshlsangiz boʻladi demak davom etamiz", 102000, 500)
    c = cuts.part_join_cuts(ws, parts, fps)
    assert len(c) == 1 and c[0].reason == "qism" and c[0].status == "tasdiqlangan"
    kept = [w.text for w in ws if not (c[0].start / 25 * 1000 <= w.start_ms < c[0].end / 25 * 1000)]
    assert kept == ["demak", "shu", "bilan", "demak", "davom", "etamiz"]
    # signal yo'q: faqat jimlik (birinchi so'zgacha)
    c2 = cuts.part_join_cuts(_seq("bir", 90000) + _seq("davom etamiz", 104000), parts, fps)
    assert c2[0].end / 25 * 1000 <= 104000 and c2[0].start / 25 * 1000 >= 90300


def test_part_join_overlap_reread() -> None:
    """Yozuv gap o'rtasida uzilgan, keyingi qismda slayd boshidan qayta o'qilgan: 1-qismdagi takror (uzilgan) gap va
    2-qism boshidagi gaplashuv kesiladi, qayta o'qilgan to'liq variant qoladi."""
    from darsstudio.project.model import VideoPart
    fps = Fraction(25)
    parts = [VideoPart(path="a", start=0, frames=25 * 100), VideoPart(path="b", start=25 * 100, frames=25 * 80)]
    p1 = _seq("hududlar hisoblanadi. byudjet kodeksi transportlariga olti turini belgilaydi. subvensiya aniq "
              "xarajatlar uchun tartibga soluvchi va.", 80000)
    p2 = _seq("boshidan oʻqiyveraman. boʻldimi? byudjetlararo transportlarni byudjet kodeksi asosan oltita turi "
              "belgilangan. subvensiya bu aniq xarajat uchun", 101000, gaps={3: 1500})
    c = cuts.part_join_cuts(p1 + p2, parts, fps)
    kept = [w.text for w in p1 + p2 if not any(x.start / 25 * 1000 <= w.start_ms < x.end / 25 * 1000 for x in c)]
    assert " ".join(kept) == ("hududlar hisoblanadi. byudjetlararo transportlarni byudjet kodeksi asosan oltita turi "
                              "belgilangan. subvensiya bu aniq xarajat uchun")


def _kept(ws: list[Word], cs: list[CutProposal]) -> str:
    return " ".join(w.text for w in ws if not any(c.start * 40 <= w.start_ms < c.end * 40 for c in cs))


def test_repeat_abandoned_and_sentence() -> None:
    """DSBA9359 oxiri: tashlab ketilgan xulosa va ikki marta aytilgan xayrlashuv."""
    ws = _seq("oladi. xulosa qilamiz. byudjet daromadi yalpi ichki mahsulotning bir qismini davlatga qayta "
              "taqsimlash munosabati haqida, e, xulosa qiladigan boʻlsak, byudjet daromadi bu yalpi ichki "
              "mahsulotning bir qismini davlatga qayta taqsimlash munosabatlarini oʻz ichiga oladi. "
              "eʼtiboringiz uchun rahmat. savollaringiz boʻlsa, muhokama qilamiz. eʼtiboringiz uchun rahmat.",
              0, 450, gaps={16: 1500})
    assert _kept(ws, cuts.repeat_cuts(ws, Fraction(25))) == (
        "oladi. xulosa qiladigan boʻlsak, byudjet daromadi bu yalpi ichki mahsulotning bir qismini davlatga qayta "
        "taqsimlash munosabatlarini oʻz ichiga oladi. savollaringiz boʻlsa, muhokama qilamiz. "
        "eʼtiboringiz uchun rahmat.")


def test_repeat_false_positives() -> None:
    # yillar va sonlar boshqa — takror emas; to'liq gapdagi atamalar keyingi gapda — takror emas
    a = _seq("fiskal strategiyaga koʻra ikki ming yigirma oltinchi yilda daromadlar uch yuz yetmish ikki "
             "trillion, ikki ming yigirma sakkizinchi yilda esa toʻrt yuz sakson toʻrt trillion boʻladi.", 0, 350)
    b = _seq("navbatdagi dars mahalliy davlat hokimiyati vakillik organlarini shakllantirishga bagʻishlangan. "
             "demak, biz koʻrib chiqamiz: mahalliy davlat hokimiyati vakillik organlarini shakllantirishning "
             "asoslarini.", 0, 350)
    assert cuts.repeat_cuts(a, Fraction(25)) == [] and cuts.repeat_cuts(b, Fraction(25)) == []


def test_reread_after_cue_two_sentences_back() -> None:
    """"…qaytadan aytaman" deb 2 gap orqaga qaytgan: eski ikki gap + signal kesiladi, yangi o'qish qoladi."""
    ws = _seq("mavzuga oʻtamiz. soliq kodeksi soliqlarning toʻqqiz turini belgilaydi. bular davlat byudjetiga tushadi. "
              "mahalliy byudjetga esa yer soligʻi va mol mulk. yoʻq, qaytadan aytaman. soliq kodeksi soliqlarning "
              "toʻqqiz turini belgilaydi. bular respublika byudjetiga tushadi. mahalliy byudjetga yer soligʻi tushadi.",
              0, 450)
    assert _kept(ws, cuts.reread_cuts(ws, Fraction(25))) == (
        "mavzuga oʻtamiz. soliq kodeksi soliqlarning toʻqqiz turini belgilaydi. bular respublika byudjetiga tushadi. "
        "mahalliy byudjetga yer soligʻi tushadi.")


def test_reread_needs_strong_match_without_cue() -> None:
    # signal yo'q, pauzadan keyin o'xshash mavzu — lekin aynan qayta o'qish emas: kesilmaydi
    ws = _seq("soliq kodeksi soliqlarning toʻqqiz turini belgilaydi.", 0, 450) + \
        _seq("soliq kodeksi mahalliy soliqlarni ham alohida tartibga soladi.", 8000, 450)
    assert cuts.reread_cuts(ws, Fraction(25)) == []


def test_reread_english_cue() -> None:
    """Ingliz tili darsi: "sorry, again" deb gap qayta aytilgan — eski gap va signal kesiladi."""
    ws = _seq("today we talk about brands. a strong brand builds trust with its customers over many years. sorry, "
              "again. a strong brand builds loyalty with its customers over many years.", 0, 450)
    assert _kept(ws, cuts.reread_cuts(ws, Fraction(25))) == (
        "today we talk about brands. a strong brand builds loyalty with its customers over many years.")


def test_reread_after_abandoned_sentence_and_pause() -> None:
    """Ingliz tili darsi (264 s): gap chala qolib pauza, keyin shu boshlanish bilan qayta — 5 mos so'z yetarli."""
    ws = _seq("we saw the title. okay for the next slide we are going to do a short reading. we will do the "
              "summary the some", 0, 450) + _seq("for the next slide we will do the reading part.", 13000, 450)
    assert _kept(ws, cuts.reread_cuts(ws, Fraction(25))) == "we saw the title. for the next slide we will do the reading part."


def test_finished_sentence_still_needs_strong_match() -> None:
    # oldingi gap tugagan: "for the next slide we..." har slaydda aytiladi — yumshoq moslik qo'llanmaydi
    ws = _seq("for the next slide we are going to do a short reading.", 0, 450) + \
        _seq("for the next slide we will learn some grammar.", 9000, 450)
    assert cuts.reread_cuts(ws, Fraction(25)) == []
