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
