"""O'zbek matnini normallashtirish (TZ FR-06): apostroflar, kirill -> lotin, raqamlar -> so'z.

Qoidalar:
- Apostrof o/g dan keyin -> U+02BB (oʻ, gʻ); boshqa harflar orasida -> U+02BC (tutuq: taʼlim).
  Harfdan keyin kelmagan yoki o/g bo'lmagan harfdan keyin harfsiz turgan apostrof qo'shtirnoq hisoblanadi:
  asl belgisi qoladi (faqat ʻ/ʼ oddiy ' ga aylanadi), normalize() uni olib tashlaydi.
- Kirill ц: unlidan keyin "ts", aks holda (so'z boshi, undoshdan keyin) "s".
- Kirill е: so'z boshida va unli/ъ/ь dan keyin "ye", aks holda "e".
"""

import re

OKINA = "ʻ"
TUTUQ = "ʼ"
APOSTROPHES = frozenset("'‘’`ʻʼ´")

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": TUTUQ, "ы": "i", "ь": "", "э": "e",
    "ю": "yu", "я": "ya", "ў": "o" + OKINA, "қ": "q", "ғ": "g" + OKINA, "ҳ": "h",
}  # fmt: skip
_CYR_VOWELS = frozenset("аеёиоуэюяў")

_ONES = ["", "bir", "ikki", "uch", "toʻrt", "besh", "olti", "yetti", "sakkiz", "toʻqqiz"]
_TENS = ["", "oʻn", "yigirma", "oʻttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "toʻqson"]
_SCALES = [(10**9, "milliard"), (10**6, "million"), (1000, "ming")]
_VOWELS = frozenset("aeiou")


def fix_apostrophes(text: str) -> str:
    """Apostrof variantlarini oʻ/gʻ uchun U+02BB, tutuq uchun U+02BC ga keltiradi."""
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch not in APOSTROPHES:
            out.append(ch)
            continue
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if prev and prev in "oOgG":
            out.append(OKINA)
        elif prev.isalpha() and nxt.isalpha():
            out.append(TUTUQ)
        else:  # qo'shtirnoq
            out.append("'" if ch in (OKINA, TUTUQ) else ch)
    return "".join(out)


def cyr_to_lat(text: str) -> str:
    """Rasmiy o'zbek kirill -> lotin jadvali (1995). Katta harf: butun so'z katta bo'lsa SH, aks holda Sh."""
    out: list[str] = []
    for i, ch in enumerate(text):
        low = ch.lower()
        prev = text[i - 1].lower() if i else ""
        if low == "е":
            lat = "ye" if not prev.isalpha() or prev in _CYR_VOWELS or prev in "ъь" else "e"
        elif low == "ц":
            lat = "ts" if prev in _CYR_VOWELS else "s"
        elif low in _CYR:
            lat = _CYR[low]
        else:
            out.append(ch)
            continue
        if ch != low and lat:
            nxt = text[i + 1] if i + 1 < len(text) else ""
            whole_upper = nxt.isupper() or (not nxt.isalpha() and text[i - 1 : i].isupper())
            lat = lat.upper() if whole_upper else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


def _below_thousand(n: int) -> list[str]:
    words: list[str] = []
    h, rest = divmod(n, 100)
    if h:
        words += ["yuz"] if h == 1 else [_ONES[h], "yuz"]
    t, u = divmod(rest, 10)
    words += [w for w in (_TENS[t], _ONES[u]) if w]
    return words


def number_to_words(n: int) -> str:
    """Butun son -> o'zbekcha sanoq son (2010 -> "ikki ming oʻn")."""
    if n < 0:
        return "minus " + number_to_words(-n)
    if n == 0:
        return "nol"
    words: list[str] = []
    for scale, name in _SCALES:
        q, n = divmod(n, scale)
        if q:
            words += [name] if q == 1 and name == "ming" else [number_to_words(q), name]
    words += _below_thousand(n)
    return " ".join(words)


def ordinal_to_words(n: int) -> str:
    """Tartib son: unli bilan tugasa +nchi, aks holda +inchi (ikkinchi, birinchi)."""
    w = number_to_words(n)
    return w + ("nchi" if w[-1] in _VOWELS else "inchi")


def _digits_to_words(digits: str) -> str:
    # kasr qismidagi boshlang'ich nollar alohida o'qiladi: 3.05 -> "uch butun nol besh"
    zeros = len(digits) - len(digits.lstrip("0"))
    rest = digits[zeros:]
    return " ".join(["nol"] * zeros + ([number_to_words(int(rest))] if rest else []))


_NUM = re.compile(r"(\d+)(?:[.,](\d+))?(\s*%|-(?=[^\W\d_]))?")


def _num_repl(m: re.Match[str]) -> str:
    whole, frac, suffix = m.group(1), m.group(2), m.group(3) or ""
    if frac is not None:
        words = number_to_words(int(whole)) + " butun " + _digits_to_words(frac)
    elif suffix == "-":
        return ordinal_to_words(int(whole)) + " "
    else:
        words = number_to_words(int(whole))
    if suffix.endswith("%"):
        return words + " foiz"
    return words + (" " if suffix == "-" else "")


def expand_numbers(text: str) -> str:
    """Raqamlarni so'zga aylantiradi (faqat moslashtirish uchun): "5-sinf" -> "beshinchi sinf", "15%" -> foiz."""
    return _NUM.sub(_num_repl, text)


_PUNCT = re.compile(r"[^\w\sʻʼ]|_")


def normalize(text: str) -> str:
    """ASR/moslashtirish uchun: lotin, to'g'ri apostroflar, raqamlar so'zda, kichik harf, tinish belgilarisiz."""
    text = expand_numbers(fix_apostrophes(cyr_to_lat(text))).lower()
    return " ".join(_PUNCT.sub(" ", text).split())


def normalize_display(text: str) -> str:
    """Subtitr uchun: lotin + to'g'ri apostroflar; raqamlar, katta harflar va tinish belgilari saqlanadi."""
    return " ".join(fix_apostrophes(cyr_to_lat(text)).split())


def tokenize(text: str) -> list[str]:
    """normalize() natijasini so'zlarga bo'ladi."""
    return normalize(text).split()
