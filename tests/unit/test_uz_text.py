"""uz_text testlari (TZ FR-06)."""

import pytest

from darsstudio.asr.uz_text import (
    OKINA,
    TUTUQ,
    cyr_to_lat,
    expand_numbers,
    fix_apostrophes,
    normalize,
    normalize_display,
    number_to_words,
    ordinal_to_words,
    tokenize,
)

OO = "o" + OKINA
G = "g" + OKINA


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("o'qituvchi", f"{OO}qituvchi"),
        ("O'zbekiston", f"O{OKINA}zbekiston"),
        ("o`zbek", f"{OO}zbek"),
        ("o‘zbek", f"{OO}zbek"),
        ("o’zbek", f"{OO}zbek"),
        ("o´zbek", f"{OO}zbek"),
        (f"o{TUTUQ}zbek", f"{OO}zbek"),
        ("g'oya", f"{G}oya"),
        ("G‘alaba", f"G{OKINA}alaba"),
        ("bog'", f"bo{G}"),
        ("to'g'ri", f"t{OO}{G}ri"),
        ("ta'lim", f"ta{TUTUQ}lim"),
        ("ma'no", f"ma{TUTUQ}no"),
        ("san`at", f"san{TUTUQ}at"),
        (f"mas{OKINA}uliyat", f"mas{TUTUQ}uliyat"),
        ("'salom'", "'salom'"),
        ("‘salom’", "‘salom’"),
        (f"{OKINA}salom{TUTUQ}", "'salom'"),
        ("'o'qituvchi'", f"'{OO}qituvchi'"),
        ("it ' s", "it ' s"),
    ],
)
def test_fix_apostrophes(src: str, expected: str) -> None:
    assert fix_apostrophes(src) == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("салом", "salom"),
        ("Шаҳар", "Shahar"),
        ("ШАҲАР", "SHAHAR"),
        ("Ш", "Sh"),
        ("Чиройли", "Chiroyli"),
        ("Ўзбекистон", f"O{OKINA}zbekiston"),
        ("ғалаба", f"{G}alaba"),
        ("қўғирчоқ", f"q{OO}{G}irchoq"),
        ("ер", "yer"),
        ("Ерга", "Yerga"),
        ("поезд", "poyezd"),
        ("келди", "keldi"),
        ("съезд", f"s{TUTUQ}yezd"),
        ("мактаб", "maktab"),
        ("ёз", "yoz"),
        ("юлдуз", "yulduz"),
        ("ярим", "yarim"),
        ("цирк", "sirk"),
        ("станция", "stansiya"),
        ("милиция", "militsiya"),
        ("Щука", "Shchuka"),
        ("мыло", "milo"),
        ("мебель", "mebel"),
        ("эшик", "eshik"),
        ("ҳаво", "havo"),
        ("Хат", "Xat"),
        ("Hello, мир!", "Hello, mir!"),
    ],
)
def test_cyr_to_lat(src: str, expected: str) -> None:
    assert cyr_to_lat(src) == expected


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "nol"),
        (1, "bir"),
        (4, f"t{OO}rt"),
        (9, f"t{OO}qqiz"),
        (10, f"{OO}n"),
        (11, f"{OO}n bir"),
        (20, "yigirma"),
        (30, f"{OO}ttiz"),
        (47, "qirq yetti"),
        (58, "ellik sakkiz"),
        (66, "oltmish olti"),
        (73, "yetmish uch"),
        (85, "sakson besh"),
        (90, f"t{OO}qson"),
        (100, "yuz"),
        (101, "yuz bir"),
        (200, "ikki yuz"),
        (999, f"t{OO}qqiz yuz t{OO}qson t{OO}qqiz"),
        (1000, "ming"),
        (1001, "ming bir"),
        (2010, f"ikki ming {OO}n"),
        (2024, "ikki ming yigirma t" + OO + "rt"),
        (12345, f"{OO}n ikki ming uch yuz qirq besh"),
        (100000, "yuz ming"),
        (1_000_000, "bir million"),
        (2_500_000, "ikki million besh yuz ming"),
        (3_000_000_000, "uch milliard"),
        (-7, "minus yetti"),
    ],
)
def test_number_to_words(n: int, expected: str) -> None:
    assert number_to_words(n) == expected


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "birinchi"),
        (2, "ikkinchi"),
        (3, "uchinchi"),
        (4, f"t{OO}rtinchi"),
        (6, "oltinchi"),
        (7, "yettinchi"),
        (10, f"{OO}ninchi"),
        (20, "yigirmanchi"),
        (40, "qirqinchi"),
        (100, "yuzinchi"),
        (1000, "minginchi"),
        (2010, f"ikki ming {OO}ninchi"),
    ],
)
def test_ordinal_to_words(n: int, expected: str) -> None:
    assert ordinal_to_words(n) == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("2010-yilda", f"ikki ming {OO}ninchi yilda"),
        ("5-sinf", "beshinchi sinf"),
        ("25 ta", "yigirma besh ta"),
        ("3,5", "uch butun besh"),
        ("3.5", "uch butun besh"),
        ("3.05", "uch butun nol besh"),
        ("15%", f"{OO}n besh foiz"),
        ("15 %", f"{OO}n besh foiz"),
        ("2,5%", "ikki butun besh foiz"),
        ("2010-2015", f"ikki ming {OO}n-ikki ming {OO}n besh"),
        ("Men 5. Keyin", "Men besh. Keyin"),
        ("raqamsiz", "raqamsiz"),
    ],
)
def test_expand_numbers(src: str, expected: str) -> None:
    assert expand_numbers(src) == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("O'zbekiston, 2010-yilda!", f"{OO}zbekiston ikki ming {OO}ninchi yilda"),
        ("Ассалому алайкум, 2-дарсга хуш келибсиз!", "assalomu alaykum ikkinchi darsga xush kelibsiz"),
        ('Ta\'lim   va  "tarbiya"', f"ta{TUTUQ}lim va tarbiya"),
        ("'salom', dedi.", "salom dedi"),
        ("O‘QITUVCHI", f"{OO}qituvchi"),
        ("Bugun 15% chegirma", f"bugun {OO}n besh foiz chegirma"),
        ("Ўқитувчи ва ўқувчи", f"{OO}qituvchi va {OO}quvchi"),
        ("a-b_c", "a b c"),
        ("", ""),
    ],
)
def test_normalize(src: str, expected: str) -> None:
    assert normalize(src) == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("  O'zbekiston   2010-yilda!  ", f"O{OKINA}zbekiston 2010-yilda!"),
        ("Ассалому алайкум, дўстлар!", f"Assalomu alaykum, d{OO}stlar!"),
        ("Ta'lim 3,5 %", f"Ta{TUTUQ}lim 3,5 %"),
        ("'Salom'\n dedi", "'Salom' dedi"),
    ],
)
def test_normalize_display(src: str, expected: str) -> None:
    assert normalize_display(src) == expected


def test_tokenize() -> None:
    assert tokenize("O'qituvchi: 5-dars.") == [f"{OO}qituvchi", "beshinchi", "dars"]


def test_normalize_idempotent() -> None:
    s = "Ўзбекистон 2010-йилда мустақил бўлди, ta'lim o'zgardi."
    assert normalize(normalize(s)) == normalize(s)
