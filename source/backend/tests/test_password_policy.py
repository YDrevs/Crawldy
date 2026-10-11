"""Мінімальна довжина пароля: одне число на продукт.

До 25 вересня 2026 їх було два. Сервер приймав від десяти символів,
форма просила дванадцять, і розбіжність вважалася безпечною: усе, що
проходило форму, проходило й сервер. Безпечна вона рівно доти, доки
хтось не звернеться до API повз форму — тоді правило продукту оголошує
слабша сторона, а напис на екрані стає побажанням.

Тут перевіряються три різні твердження, і плутати їх не можна:

* **межа** — які саме довжини сервер приймає для НОВОГО пароля;
* **паритет** — що інтерфейс називає те саме число, і шістьма мовами;
* **сумісність** — що підняття межі нікого не замкнуло.

Третє найтихіше й найдорожче. Воно не про те, що написано в політиці, а
про те, що станеться з людиною, яка зареєструвалась до її зміни.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.identity import passwords
from app.identity.passwords import WeakPassword

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "app" / "lib"
POLICY_TS = FRONTEND / "password-policy.ts"
CATALOG_TS = FRONTEND / "i18n.ts"


def _frontend_minimum() -> int:
    """Число, яке оголошує інтерфейс. Відсутній файл — теж розходження."""
    source = POLICY_TS.read_text(encoding="utf-8")
    found = re.search(r"export const MIN_PASSWORD_LENGTH = (\d+);", source)
    assert found is not None, f"у {POLICY_TS.name} немає оголошення мінімуму"
    return int(found.group(1))


# ── межа ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("length", [0, 1, 8, 9, 10, 11])
def test_a_new_password_shorter_than_the_minimum_is_refused(length: int) -> None:
    """Десять і одинадцять — теж «закоротко», і саме це змінилось.

    Раніше десять проходило. Тест перелічує обидва граничні значення
    явно, бо «менше за межу» в коді легко зробити «менше або дорівнює».
    """
    with pytest.raises(WeakPassword):
        passwords.validate("x" * length)


@pytest.mark.parametrize("length", [12, 13, 40, 255, 256])
def test_a_long_enough_new_password_is_accepted(length: int) -> None:
    passwords.validate("x" * length)


def test_the_minimum_is_twelve() -> None:
    assert passwords.MIN_LENGTH == 12


def test_a_password_longer_than_the_maximum_is_refused() -> None:
    """Верхня межа лишилась на місці: мегабайтний «пароль» — це спосіб
    завантажити процесор хешуванням, а не пароль."""
    with pytest.raises(WeakPassword):
        passwords.validate("x" * (passwords.MAX_LENGTH + 1))


def test_hashing_a_new_password_enforces_the_policy() -> None:
    """`hash_password` — єдині двері, у яких стоїть перевірка."""
    with pytest.raises(WeakPassword):
        passwords.hash_password("x" * (passwords.MIN_LENGTH - 1))


# ── сумісність: підняття межі нікого не замкнуло ───────────────────────


def test_an_old_short_password_still_verifies() -> None:
    """Наявний хеш не знецінюється. Пароль, прийнятий торік, чинний.

    Це і є зміст «межа стосується лише НОВИХ паролів»: `verify` політики
    не знає й знати не повинен.
    """
    legacy = passwords.rehash_existing("short-pass")  # рівно 10 символів
    assert passwords.verify(legacy, "short-pass") is True


def test_rehashing_an_accepted_password_does_not_enforce_the_policy() -> None:
    """Пастка, заради якої `rehash_existing` і зʼявився.

    Вхід перехешовує пароль, коли параметри argon2 підняли. Поки це
    робилось через `hash_password`, перехешування ще й ПЕРЕВІРЯЛО
    довжину — і в день зміни параметрів людина з десятисимвольним
    паролем, ввівши його ПРАВИЛЬНО, дістала б `WeakPassword` із глибини
    входу. Не «оновіть пароль», а помилка сервера на коректних даних.

    Дефект не спрацював би одразу: він чекав би на не повʼязану з ним
    зміну, і до того моменту причину вже ніхто б не згадав.
    """
    rehashed = passwords.rehash_existing("short-pass")
    assert passwords.verify(rehashed, "short-pass") is True


def test_the_two_hashing_doors_are_not_the_same_door() -> None:
    """Якби `rehash_existing` був псевдонімом `hash_password`, тест вище
    проходив би лише випадково — до першого рефакторингу."""
    short = "x" * (passwords.MIN_LENGTH - 1)
    passwords.rehash_existing(short)
    with pytest.raises(WeakPassword):
        passwords.hash_password(short)


# ── паритет із інтерфейсом ─────────────────────────────────────────────


def test_the_interface_declares_the_same_minimum() -> None:
    """Число живе у двох мовах програмування, тож мусить бути звірене.

    Та сама межа, що стереже знімок ваг скорингу для публічної сторінки
    методології: якщо число переписане рукою там, де перевірка не
    дивиться, воно розійдеться — питання лише коли.
    """
    assert _frontend_minimum() == passwords.MIN_LENGTH


def test_every_locale_states_the_real_minimum() -> None:
    """Правило пароля клієнт читає шістьма мовами, і в кожній — число.

    Мовчазний фолбек тут не спіймати порівнянням мов між собою: ключа
    бракувало б усім шістьом однаково. Тому перевіряється наявність
    самого числа в кожному рядку.
    """
    catalog = CATALOG_TS.read_text(encoding="utf-8")
    hints = re.findall(r'^ {2}"auth\.passwordHint": "([^"]+)",$', catalog, re.M)
    assert len(hints) == 6, f"правило пароля не в усіх шести мовах: {len(hints)}"
    for hint in hints:
        assert str(passwords.MIN_LENGTH) in hint, hint
    # Старе число не сміє лишитися в жодній мові: саме так локалізація
    # і переживає зміну правила — одна мова оновлена, пʼять ні.
    for hint in hints:
        assert "10" not in hint, f"у правилі лишилось старе число: {hint}"


def test_no_screen_declares_its_own_minimum() -> None:
    """Джерело одне. Копія, яка сьогодні збігається, завтра розійдеться."""
    screens = [
        FRONTEND.parent / "(product)" / "login" / "page.tsx",
        FRONTEND.parent / "(product)" / "reset" / "page.tsx",
        FRONTEND.parent / "components" / "ChangePasswordDialog.tsx",
    ]
    for screen in screens:
        source = screen.read_text(encoding="utf-8")
        assert "MIN_PASSWORD_LENGTH" in source, screen.name
        assert not re.search(r"\.length\s*<\s*\d+", source), (
            f"{screen.name} порівнює довжину з літералом замість константи"
        )
