"""FR-03: PPTX matni, eslatmalar, ogohlantirishlar (python-pptx, GPU/PowerPoint'siz)."""

from typing import Any

from darsstudio.slides import extract


def test_extract_lesson(test_media: dict[str, Any]) -> None:
    exp = test_media["lesson.pptx"]["slides"]
    slides, general = extract.extract_pptx(test_media["lesson.pptx"]["path"])
    assert general == []                                   # 16:9
    assert [s.title for s in slides] == [e["title"] for e in exp]
    assert [s.body for s in slides] == [e["body"] for e in exp]
    assert [s.notes for s in slides] == [e["notes"] for e in exp]
    anim = [s.index for s in slides if any(w.startswith("animatsiya") for w in s.warnings)]
    assert anim == [e["index"] for e in exp if e["animated"]]
    for s, e in zip(slides, exp, strict=True):   # bosishda chiqadigan matn (javob o'qituvchi aytganda ko'rinadi)
        assert s.anim == ([e["body"]] if e["animated"] else [])
