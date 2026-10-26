"""glossary testlari (TZ FR-06)."""

import json
from pathlib import Path

from darsstudio.asr.glossary import Term, correct, hotwords, load


def write(path: Path, terms: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"terms": terms}, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_override_and_missing(tmp_path: Path) -> None:
    g = write(tmp_path / "global.json", [{"term": "Python", "variants": ["paiton"]}, {"term": "fotosintez"}])
    p = write(tmp_path / "project.json", [{"term": "python", "variants": ["payton"], "lang": "en"}])
    terms = load(g, tmp_path / "yoq.json", p)
    assert terms == [Term("python", ["payton"], "en"), Term("fotosintez", [], "uz")]


def test_hotwords() -> None:
    assert hotwords([Term("fotosintez", []), Term("Nyuton qonuni", [])]) == "fotosintez Nyuton qonuni"


def test_correct_near_miss() -> None:
    terms = [Term("fotosintez", ["fotosintes"])]
    assert correct("bu fotosintiz jarayoni".split(), terms, threshold=85) == ["bu", "fotosintez", "jarayoni"]
    assert correct("bu fotosintes".split(), terms) == ["bu", "fotosintez"]


def test_correct_multiword_and_variant_count() -> None:
    terms = [Term("Nyuton qonuni", []), Term("kompyuter", ["kom pyuter"])]
    assert correct("ikkinchi nyuton qonun".split(), terms, threshold=85) == ["ikkinchi", "Nyuton", "qonuni"]
    assert correct("yangi kom pyuter".split(), terms) == ["yangi", "kompyuter"]


def test_correct_no_match_keeps_words() -> None:
    words = ["salom", "dunyo"]
    assert correct(words, [Term("fotosintez", [])]) == words
    assert correct([], [Term("fotosintez", [])]) == []
