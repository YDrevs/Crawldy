"""Приватність калібрувального корпусу: ворота, а не разове прибирання.

Корпус — це докази з ЧУЖИХ сайтів, і в нього раз за разом потрапляє те,
чого там бути не повинно. Один знімок ресторану приніс понад пʼятдесят
тисяч справжніх адрес зі спам-коментарів зламаного сайту; інші знімки
несли сесійні cookie й ключі браузерних API, які належать не нам.
Прибрати це один раз недостатньо: наступний прогін `calibrate.py`
запише все те саме знову.

Тому перевірка постійна й дивиться в сам корпус, включно з вкладеними
архівами. Вона НЕ дивиться на решту продукту: юридичні сторінки й
контакти компанії містять адреси законно, і ворота, які їх відкидають,
швидко вимикають.

Заміна адрес детермінована й однобічна: `user<хеш>@d<хеш>.invalid`, із
збереженням рольової частини (`info`, `contact`, …). Зворотної таблиці
не існує, бо її ніхто не будує — не «видалили», а не створювали.
"""

from __future__ import annotations

import re
import tarfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
BENCH = BACKEND / "benchmark"

REMOVED_SNAPSHOT = "https-myfriendlythai-ca.json"

# Assembled, not written out.
#
# A guard that contains the string it forbids fails on itself, and the
# obvious fix - excluding the guard from its own scan - creates the one
# file where the address may legally sit. Building it from parts keeps
# the repository-wide check honest: nothing anywhere is exempt.
OWNER_EMAIL = "serhii" + "." + "popel" + "@" + "gmail" + "." + "com"

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Домени, які не є нічиєю справжньою адресою: зарезервовані стандартом
# або наші синтетичні.
ALLOWED_SUFFIXES = (".invalid",)
ALLOWED_DOMAINS = {"example.com", "example.org", "example.net"}
ALLOWED_PREFIXES = ("example.", "test.", "localhost")

COOKIE = re.compile(r'"set-cookie"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', re.I)
KEY_PATTERNS = {
    "google api key": re.compile(r"AIza(?!REDACTED)[0-9A-Za-z_\-]{30,}"),
    "stripe live key": re.compile(r"pk_live_(?!REDACTED)[0-9A-Za-z]{10,}"),
    "stripe test key": re.compile(r"pk_test_(?!REDACTED)[0-9A-Za-z]{10,}"),
    "stripe secret test key": re.compile(r"sk_test_(?!REDACTED)[0-9A-Za-z]{10,}"),
    "turnstile site key": re.compile(r"0x4(?!REDACTED)[0-9A-Za-z_\-]{20,}"),
}
MACHINE_PATH = re.compile(
    r"[A-Za-z]:\\{1,2}Users\\{1,2}[A-Za-z0-9_.\-]+"
    r"|[A-Za-z]:/Users/[A-Za-z0-9_.\-]+"
    r"|E:\\{1,2}[A-Za-z0-9_\-]+"
    r"|E:/[A-Za-z0-9_\-]+"
    r"|crawldy-(?:work|stage|extract|exec|benchmark)[A-Za-z0-9_\-]*"
)

BINARY = {".gz", ".zip", ".png", ".pdf", ".eps", ".woff2", ".ico"}


def _is_real_address(address: str) -> bool:
    domain = address.lower().rpartition("@")[2]
    if domain.endswith(ALLOWED_SUFFIXES) or domain in ALLOWED_DOMAINS:
        return False
    return not domain.startswith(ALLOWED_PREFIXES)


def _corpus_texts() -> list[tuple[str, str]]:
    """Every readable unit of the corpus, nested archives included.

    A loose file that looks clean proves nothing while a tarball beside
    it carries the same bytes - that is exactly how the first cleanup
    missed a byte-identical copy.
    """
    units: list[tuple[str, str]] = []
    for path in sorted(BENCH.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() == ".gz":
            with tarfile.open(path, "r:gz") as tf:
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    handle = tf.extractfile(member)
                    if handle is None:
                        continue
                    units.append(
                        (
                            f"{path.name}::{member.name}",
                            handle.read().decode("utf-8", "replace"),
                        )
                    )
            continue
        if path.suffix.lower() in BINARY:
            continue
        units.append(
            (
                path.relative_to(BENCH).as_posix(),
                path.read_text(encoding="utf-8", errors="replace"),
            )
        )
    return units


@pytest.fixture(scope="module")
def corpus() -> list[tuple[str, str]]:
    return _corpus_texts()


def test_the_corpus_is_actually_present(corpus: list[tuple[str, str]]) -> None:
    """Ворота, що нічого не читають, проходять завжди."""
    assert len(corpus) > 50, f"корпус не прочитано: {len(corpus)} одиниць"


def test_the_removed_snapshot_is_gone(corpus: list[tuple[str, str]]) -> None:
    """І сам файл, і будь-яка його копія у вкладеному архіві."""
    present = [name for name, _ in corpus if REMOVED_SNAPSHOT in name]
    assert not present, f"видалений знімок повернувся: {present}"
    assert not (BENCH / "snapshots" / REMOVED_SNAPSHOT).exists()


def test_no_real_third_party_address_remains(corpus: list[tuple[str, str]]) -> None:
    """Адреси або синтетичні, або зарезервовані. Третього немає."""
    offenders: dict[str, set[str]] = {}
    for name, text in corpus:
        real = {a.lower() for a in EMAIL.findall(text) if _is_real_address(a)}
        if real:
            offenders[name] = real
    assert not offenders, "справжні адреси в корпусі: " + ", ".join(
        f"{name} ({len(found)})" for name, found in sorted(offenders.items())
    )


def test_synthetic_addresses_kept_their_shape(corpus: list[tuple[str, str]]) -> None:
    """Заміна мусить лишитися адресою, інакше докази зникли разом із PII.

    Перевірки пошуку контактів читають форму, а не особу: якщо синтетика
    перестане бути схожою на пошту, вони мовчатимуть — і корпус більше
    не перевірятиме те, заради чого існує.
    """
    synthetic = {
        a.lower()
        for _, text in corpus
        for a in EMAIL.findall(text)
        if a.lower().endswith(".invalid")
    }
    assert synthetic, "у корпусі не лишилось жодної адреси — доказ втрачено"
    for address in synthetic:
        local, _, domain = address.partition("@")
        assert local, address
        assert domain.endswith(".invalid"), address


def test_no_captured_cookie_value_remains(corpus: list[tuple[str, str]]) -> None:
    """Імена й атрибути лишаються, значення — ні."""
    offenders = []
    for name, text in corpus:
        for raw in COOKIE.findall(text):
            head = raw.split("; ")[0]
            cookie_name, sep, value = head.partition("=")
            if sep and value and value != "REDACTED":
                offenders.append(f"{name}:{cookie_name}")
    assert not offenders, f"нередаговані cookie: {offenders[:5]}"


def test_no_third_party_key_remains(corpus: list[tuple[str, str]]) -> None:
    offenders = []
    for name, text in corpus:
        for label, pattern in KEY_PATTERNS.items():
            if pattern.search(text):
                offenders.append(f"{name} ({label})")
    assert not offenders, f"чужі ключі в корпусі: {offenders[:5]}"


def test_no_machine_specific_path_remains(corpus: list[tuple[str, str]]) -> None:
    offenders = []
    for name, text in corpus:
        found = MACHINE_PATH.search(text)
        if found:
            offenders.append(f"{name} ({found.group(0)[:30]})")
    assert not offenders, f"шляхи цієї машини в корпусі: {offenders[:5]}"


def test_the_owner_address_is_absent_from_the_corpus(
    corpus: list[tuple[str, str]],
) -> None:
    offenders = [name for name, text in corpus if OWNER_EMAIL in text]
    assert not offenders, f"особиста адреса власника в корпусі: {offenders}"


def test_the_owner_address_cannot_return_through_a_default() -> None:
    """Контакт краулера приходить із налаштування, і порожньо за
    замовчуванням.

    Найімовірніший спосіб повернення — не редагування корпусу, а
    «зручний» дефолт у скрипті. Перевіряється і константа, і обидва
    скрипти, які нею користуються.
    """
    from app.core.config import Settings

    assert "crawler_contact" in Settings.model_fields
    assert Settings.model_fields["crawler_contact"].default == ""

    for name in ("harvest_corpus.py", "harvest_tranco.py"):
        source = (BACKEND / "scripts" / "samples" / name).read_text(encoding="utf-8")
        assert OWNER_EMAIL not in source, name
        assert "crawler_contact" in source, name
        for address in EMAIL.findall(source):
            assert not _is_real_address(address), f"{name}: {address}"


def test_the_whole_repository_is_free_of_the_owner_address() -> None:
    """Ширше за корпус, бо адреса — одна, і місце в неї одне: ніде."""
    root = BACKEND.parent
    skip = {".git", "node_modules", ".venv", "__pycache__", ".next", ".pytest_cache"}
    offenders = []
    for path in root.rglob("*"):
        if not path.is_file() or set(path.parts) & skip:
            continue
        if path.suffix.lower() in BINARY:
            continue
        try:
            if OWNER_EMAIL in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(path.relative_to(root).as_posix())
        except OSError:
            continue
    assert not offenders, f"особиста адреса в репозиторії: {offenders}"
