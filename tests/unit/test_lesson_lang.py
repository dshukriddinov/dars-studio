"""Dars tili: nutqni tanish modeli va VRAM e'loni meta["til"] bo'yicha."""
from darsstudio.jobs.tasks import DEFAULT_ALIGN, DEFAULT_ASR, EN_ASR, asr_models, lesson_lang, resources_for


def test_lesson_lang_defaults_to_uzbek() -> None:
    assert lesson_lang({}) == "uz"
    assert lesson_lang({"til": "uz"}) == "uz"
    assert lesson_lang({"til": "en"}) == lesson_lang({"til": "Ingliz tili"}) == "en"


def test_english_uses_whisper_without_uzbek_aligner() -> None:
    assert asr_models("uz", {}) == (DEFAULT_ASR, DEFAULT_ALIGN)
    assert asr_models("en", {}) == (EN_ASR, None)
    assert resources_for("asr", {"lang": "en"}).vram_mb > resources_for("asr", {"lang": "uz"}).vram_mb


def test_whisper_words_clipped_to_speech() -> None:
    from darsstudio.asr.word_align import clip_to_speech
    from darsstudio.project.model import Word
    w = [Word(text="everyone,", start_ms=920, end_ms=4300, conf=0.9),   # pauzaga cho'zilgan (DSBA8915)
         Word(text="hm", start_ms=3000, end_ms=3200, conf=0.9)]          # VAD o'tkazib yuborgan — o'zgarmaydi
    out = clip_to_speech(w, [(740, 2588), (3940, 4860)])
    assert (out[0].start_ms, out[0].end_ms) == (920, 2588) and out[1] == w[1]


def test_guess_lang_from_slides() -> None:
    from darsstudio.jobs.tasks import guess_lang
    en = "Match the word to its definition. What is the role of the headquarters? How do you work in your team? " * 3
    uz = "Mahalliy byudjet va transfertlar bilan ishlash uchun hududlarning daromadlari bo'yicha tahlil. " * 3
    assert guess_lang(en) == "en" and guess_lang(uz) == "uz" and guess_lang("") == "uz"
