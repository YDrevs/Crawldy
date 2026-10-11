"""Коди мов, письма й регіонів — і те, що з них приймає Google у hreflang.

## Дві різні відповіді на схоже питання

`en-Latn-US` структурно коректний за BCP 47. Чи означає це, що Google
прийме його в `hreflang`? Не обовʼязково: Google описує власну, вужчу
граматику, і саме її треба перевіряти, коли пишеш клієнту, що значення
недійсне. Тому тут дві функції, а не одна: `parse` розбирає форму,
`google_verdict` каже, чи підтримує її Google.

Плутати їх — означає або пропускати справжні помилки, або називати
помилкою те, що нею не є.

## Граматика Google, з його ж документації

    language[-script][-region]  |  x-default

- **language** — ISO 639-1: «the language code (in ISO 639-1 format)»;
- **script** — ISO 15924, необовʼязково: «You can also specify the
  script itself explicitly using ISO 15924, like this: zh-Hant, zh-Hans»;
- **region** — ISO 3166-1 Alpha 2, необовʼязково: «followed by an
  optional second code that represents the region code»;
- порядок саме такий: приклад Google `zh-Hans-US` ставить письмо між
  мовою і регіоном;
- `x-default` — зарезервоване значення для випадку, коли жодна мова не
  збіглася.

## Чому списки лежать тут, а не приходять пакетом

Готового реєстру в оточенні немає (`langcodes`, `babel`, `pycountry` не
встановлені), а брати повний реєстр IANA було б неточно з іншого боку:
Google приймає не весь BCP 47, а перелічені вище три стандарти. Тож
списки — це довідкові дані з джерелом і датою звірки, як і реєстр
AI-краулерів поруч.

Від друкарських помилок стереже тест: кожен дволітерний код мови зі
стандартної бібліотеки Python (`locale.locale_alias`) мусить бути тут.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

SOURCES = {
    "language": "https://www.loc.gov/standards/iso639-2/php/code_list.php",
    "script": "https://www.unicode.org/iso15924/iso15924.txt",
    "iana_subtags": (
        "https://www.iana.org/assignments/language-subtag-registry/"
        "language-subtag-registry"
    ),
    "region": "https://www.iso.org/iso-3166-country-codes.html",
    "google_hreflang": (
        "https://developers.google.com/search/docs/specialty/international/"
        "localized-versions"
    ),
}
LAST_VERIFIED_AT = date(2026, 8, 25)

# Зарезервоване значення. Не мова й не регіон — окремий випадок граматики.
X_DEFAULT = "x-default"

# ISO 639-1, дволітерні коди мов.
ISO_639_1: frozenset[str] = frozenset("""
aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr
cs cu cv cy da de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu
gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is it iu ja jv ka kg ki kj kk
kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms
mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro
ru rw sa sc sd se sg si sk sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl
tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi yo za zh zu
""".split())

# ── ISO 15924: письмо ──────────────────────────────────────────────────────
#
# Вендорований знімок реєстру, а не добірка «тих, що трапляються». Добірка
# тут уже була, і вона була помилкою: 39 кодів на око означали, що
# правильні `ks-Aran`, `ber-Tfng`, `syr-Syrc` ми називали клієнтові
# недійсними. Реєстр каже 226 — стільки й лежить нижче.
#
# Незалежне підтвердження: реєстр підтегів IANA (File-Date 2026-08-08)
# несе 224 підтегів письма плюс діапазон приватного вжитку
# `Qaaa..Qabx`, кінці якого файл RA перелічує окремими рядками:
# 224 + 2 = 226. Два незалежні джерела сходяться.
ISO_15924_SOURCE = "https://www.unicode.org/iso15924/iso15924.txt"
# Найпізніша правка всередині знімка — версія самих даних.
ISO_15924_AMENDED = date(2025, 4, 24)
ISO_15924_RETRIEVED = date(2026, 8, 25)
# Розмір знімка. Мовчазне усічення списку — саме той дефект, який тут
# виправляють, тож він мусить валити самоперевірку, а не проходити тихо.
ISO_15924_COUNT = 226
ISO_15924: frozenset[str] = frozenset("""
Adlm Afak Aghb Ahom Arab Aran Armi Armn Avst Bali Bamu Bass Batk Beng Berf
Bhks Blis Bopo Brah Brai Bugi Buhd Cakm Cans Cari Cham Cher Chis Chrs Cirt
Copt Cpmn Cprt Cyrl Cyrs Deva Diak Dogr Dsrt Dupl Egyd Egyh Egyp Elba Elym
Ethi Gara Geok Geor Glag Gong Gonm Goth Gran Grek Gujr Gukh Guru Hanb Hang
Hani Hano Hans Hant Hatr Hebr Hira Hluw Hmng Hmnp Hntl Hrkt Hung Inds Ital
Jamo Java Jpan Jurc Kali Kana Kawi Khar Khmr Khoj Kitl Kits Knda Kore Kpel
Krai Kthi Lana Laoo Latf Latg Latn Leke Lepc Limb Lina Linb Lisu Loma Lyci
Lydi Mahj Maka Mand Mani Marc Maya Medf Mend Merc Mero Mlym Modi Mong Moon
Mroo Mtei Mult Mymr Nagm Nand Narb Nbat Newa Nkdb Nkgb Nkoo Nshu Ogam Olck
Onao Orkh Orya Osge Osma Ougr Palm Pauc Pcun Pelm Perm Phag Phli Phlp Phlv
Phnx Piqd Plrd Prti Psin Qaaa Qabx Ranj Rjng Rohg Roro Runr Samr Sara Sarb
Saur Seal Sgnw Shaw Shrd Shui Sidd Sidt Sind Sinh Sogd Sogo Sora Soyo Sund
Sunu Sylo Syrc Syre Syrj Syrn Tagb Takr Tale Talu Taml Tang Tavt Tayo Telu
Teng Tfng Tglg Thaa Thai Tibt Tirh Tnsa Todr Tols Toto Tutg Ugar Vaii Visp
Vith Wara Wcho Wole Xpeo Xsux Yezi Yiii Zanb Zinh Zmth Zsye Zsym Zxxx Zyyy
Zzzz
""".split())

# Шість кодів, які ISO 639-1 позначив застарілими, а реєстр IANA досі
# тримає: `in`→`id`, `iw`→`he`, `ji`→`yi`, `jw`→`jv`, `mo`→`ro`, `sh`→`sr`.
# Вони приймаються. Сказати клієнтові, що його `iw` недійсний, було б
# хибним спрацюванням: код справжній, просто старий, і споживачі мовних
# тегів його розуміють. Факт застарілості йде в доказ, а не в текст.
ISO_639_1_DEPRECATED: frozenset[str] = frozenset("in iw ji jw mo sh".split())

# ISO 3166-1 alpha-2: **офіційно призначені** дволітерні коди країн і
# територій, усі 249. Правило тут детерміноване й свідоме, на відміну від
# добірки письма, яку воно замінює: реєстр IANA несе ще 12 винятково
# зарезервованих (`EU`, `UN`, `AC`, `DG`, `EA`, `IC`, `TA`, `CP`, `EZ`…),
# діапазони для приватного вжитку та 11 вилучених (`AN`, `SU`, `YU`…).
# Google пише «region code in ISO 3166-1 Alpha 2 format» і націлює на
# країни; `en-EU` країною не є. Розширювати цей перелік — рішення про
# продукт, а не звірка з джерелом, тож воно записане в §K.4 звірки
# покриття, а не зроблене тут мовчки.
ISO_3166_1: frozenset[str] = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM
BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX
CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG
GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR
IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV
LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE
NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO
RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF
TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF
WS YE YT ZA ZM ZW
""".split())

# Форма підтегів за BCP 47. Це саме форма, не належність до реєстру:
# `xx-Yyyy-ZZ` пройде тут і не пройде далі.
_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}$")
_SCRIPT = re.compile(r"^[A-Za-z]{4}$")
_REGION = re.compile(r"^([A-Za-z]{2}|[0-9]{3})$")


class TagProblem(StrEnum):
    """Чому значення не годиться. Кожен випадок — окрема порада клієнту."""

    EMPTY = "empty"
    # Підкреслення замість дефіса: `en_US`. Найчастіша механічна помилка.
    SEPARATOR = "separator"
    # Забагато підтегів або невпізнанна форма.
    MALFORMED = "malformed"
    # Перший підтег не є мовою за ISO 639-1 — часто туди кладуть країну.
    NOT_A_LANGUAGE = "not_a_language"
    # Перший підтег — код країни, а не мови: класичне `hreflang="uk"`
    # в значенні «Велика Британія» або `hreflang="gb"`.
    REGION_AS_LANGUAGE = "region_as_language"
    UNKNOWN_SCRIPT = "unknown_script"
    # `en-UK` замість `en-GB`: UK не є кодом ISO 3166-1.
    UNKNOWN_REGION = "unknown_region"
    # Правильні підтеги в неправильному порядку: `en-US-Latn`.
    ORDER = "order"


@dataclass(frozen=True, slots=True)
class LanguageTag:
    """Розібране значення hreflang."""

    raw: str
    language: str | None = None
    script: str | None = None
    region: str | None = None
    x_default: bool = False
    problem: TagProblem | None = None
    # Код чинний, але ISO 639-1 замінив його іншим. Значення лишається
    # дійсним — це факт для доказу, а не привід звинуватити клієнта.
    deprecated: bool = False

    @property
    def valid(self) -> bool:
        return self.problem is None

    @property
    def normalized(self) -> str:
        """Канонічний запис: мова в нижньому, письмо Titlecase, регіон у верхньому."""
        if self.x_default:
            return X_DEFAULT
        parts = [p for p in (self.language, self.script, self.region) if p]
        return "-".join(parts)

    def as_evidence(self) -> dict[str, str | bool | None]:
        return {
            "value": self.raw,
            "normalized": self.normalized if self.valid else None,
            "language": self.language,
            "script": self.script,
            "region": self.region,
            "x_default": self.x_default,
            "deprecated": self.deprecated,
            "problem": self.problem.value if self.problem else None,
        }


def parse(value: str) -> LanguageTag:
    """Значення hreflang → розібраний тег за граматикою Google.

    Порядок перевірок повторює порядок, у якому помилки трапляються:
    спершу механічні (порожньо, підкреслення), потім змістовні.
    """
    raw = (value or "").strip()
    if not raw:
        return LanguageTag(raw=raw, problem=TagProblem.EMPTY)

    if raw.lower() == X_DEFAULT:
        return LanguageTag(raw=raw, x_default=True)

    if "_" in raw:
        # Розбираємо далі, щоб сказати, що саме мали на увазі, але
        # значення лишається недійсним: роздільник у BCP 47 — дефіс.
        return LanguageTag(raw=raw, problem=TagProblem.SEPARATOR)

    parts = raw.split("-")
    if not 1 <= len(parts) <= 3:
        return LanguageTag(raw=raw, problem=TagProblem.MALFORMED)

    head, *rest = parts
    if not _LANGUAGE.match(head):
        return LanguageTag(raw=raw, problem=TagProblem.MALFORMED)

    language = head.lower()
    deprecated = language in ISO_639_1_DEPRECATED
    if language not in ISO_639_1 and not deprecated:
        # Код країни на місці мови — окремий випадок: порада інша.
        problem = (
            TagProblem.REGION_AS_LANGUAGE
            if head.upper() in ISO_3166_1
            else TagProblem.NOT_A_LANGUAGE
        )
        return LanguageTag(raw=raw, problem=problem)

    script: str | None = None
    region: str | None = None
    for part in rest:
        if _SCRIPT.match(part):
            if script is not None or region is not None:
                # Письмо після регіону — порушення порядку `zh-Hans-US`.
                return LanguageTag(raw=raw, problem=TagProblem.ORDER)
            if part.title() not in ISO_15924:
                return LanguageTag(raw=raw, problem=TagProblem.UNKNOWN_SCRIPT)
            script = part.title()
        elif _REGION.match(part):
            if region is not None:
                return LanguageTag(raw=raw, problem=TagProblem.MALFORMED)
            if part.upper() not in ISO_3166_1:
                return LanguageTag(raw=raw, problem=TagProblem.UNKNOWN_REGION)
            region = part.upper()
        else:
            return LanguageTag(raw=raw, problem=TagProblem.MALFORMED)

    return LanguageTag(
        raw=raw, language=language, script=script, region=region, deprecated=deprecated
    )


def registry_problems() -> list[str]:
    """Самоперевірка довідкових даних, як у реєстрі AI-краулерів."""
    problems: list[str] = []
    if not all(len(code) == 2 and code.islower() for code in ISO_639_1):
        problems.append("ISO 639-1: очікуються дволітерні коди в нижньому регістрі")
    if not all(len(code) == 4 and code.istitle() for code in ISO_15924):
        problems.append("ISO 15924: очікуються чотирилітерні коди Titlecase")
    if len(ISO_15924) != ISO_15924_COUNT:
        problems.append(
            f"ISO 15924: у знімку {len(ISO_15924)} кодів, а реєстр дав {ISO_15924_COUNT}"
        )
    if ISO_639_1 & ISO_639_1_DEPRECATED:
        problems.append("ISO 639-1: застарілий код продубльовано серед чинних")
    if not all(len(code) == 2 and code.isupper() for code in ISO_3166_1):
        problems.append("ISO 3166-1: очікуються дволітерні коди у верхньому регістрі")
    for name, url in SOURCES.items():
        if not url.startswith("https://"):
            problems.append(f"{name}: джерело не є https-адресою")
    return problems


__all__ = [
    "ISO_639_1",
    "ISO_639_1_DEPRECATED",
    "ISO_3166_1",
    "ISO_15924",
    "ISO_15924_AMENDED",
    "ISO_15924_COUNT",
    "ISO_15924_RETRIEVED",
    "ISO_15924_SOURCE",
    "LAST_VERIFIED_AT",
    "SOURCES",
    "X_DEFAULT",
    "LanguageTag",
    "TagProblem",
    "parse",
    "registry_problems",
]
