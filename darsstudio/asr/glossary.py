"""Atamalar lug'ati (TZ FR-06): glossary.json (global + loyiha), Whisper hotwords, ASR'dan keyin noaniq almashtirish."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

from darsstudio.asr.uz_text import normalize

MAX_WINDOW = 3


@dataclass
class Term:
    term: str
    variants: list[str] = field(default_factory=list)
    lang: str = "uz"


def load(*paths: Path) -> list[Term]:
    """JSON lug'atlar: keyingi fayl bir xil (normallashtirilgan) atamani almashtiradi; yo'q fayl o'tkaziladi."""
    terms: dict[str, Term] = {}
    for path in paths:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("terms", []):
            t = Term(str(item["term"]), [str(v) for v in item.get("variants", [])], str(item.get("lang", "uz")))
            terms[normalize(t.term)] = t
    return list(terms.values())


def hotwords(terms: list[Term]) -> str:
    """Whisper `hotwords` uchun atamalar bo'sh joy bilan."""
    return " ".join(t.term for t in terms)


def correct(words: list[str], terms: list[Term], threshold: int = 90) -> list[str]:
    """ASR so'zlarini lug'at atamasiga almashtiradi (1..3 so'zli sirpanuvchi oyna, rapidfuzz.fuzz.ratio >= threshold).

    Oyna faqat so'z soni bir xil bo'lgan atama/variant bilan solishtiriladi; avval uzunroq oyna sinanadi.
    Mos kelgan oyna atamaning so'zlariga almashadi, shuning uchun variant so'z soni atamanikidan farq qilsa
    natija uzunligi o'zgaradi. Oynadagi tinish belgilari almashtirishda yo'qoladi.
    """
    forms: dict[int, list[tuple[str, Term]]] = {}
    for t in terms:
        for form in [t.term, *t.variants]:
            nf = normalize(form)
            n = len(nf.split())
            if 0 < n <= MAX_WINDOW:
                forms.setdefault(n, []).append((nf, t))
    out: list[str] = []
    i = 0
    while i < len(words):
        for size in range(min(MAX_WINDOW, len(words) - i), 0, -1):
            window = normalize(" ".join(words[i : i + size]))
            if len(window.split()) != size:
                continue
            best: tuple[float, Term] | None = None
            for nf, t in forms.get(size, []):
                score = fuzz.ratio(window, nf)
                if score >= threshold and (best is None or score > best[0]):
                    best = (score, t)
            if best:
                out += best[1].term.split()
                i += size
                break
        else:
            out.append(words[i])
            i += 1
    return out
