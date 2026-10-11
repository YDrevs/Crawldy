"""Документований перелік чеків звіряється з реальним реєстром (E-04).

`CLAUDE.md` називав 79 чеків, а перелік по модулях у тому самому файлі давав
82. Реєстр на той момент мав інше число, ніж обидва, і нічого їх не
порівнювало: обидва числа писала рука, і жоден тест не читав жодного з них.

Тут єдине джерело істини — **робочий реєстр**, той самий `REGISTRY`, з якого
оркестратор бере чеки. Документ ПАРСИТЬСЯ, а не переписується у словник
очікувань: другий рукописний перелік був би тією самою хворобою під іншим
іменем.

Твердження розділені навмисно. Загальний зсув, зсув одного модуля, зниклий
модуль, дубль коду й внутрішня суперечність документа — різні дефекти, і
кожен має падати своїм рядком, а не спільним «щось не збігається».

Тест не робить аудиту, не ходить у мережу, не потребує бази чи сервісів:
він імпортує реєстр і читає файл.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from app.audit.checks import REGISTRY
from app.audit.enums import Module

CLAUDE_MD = Path(__file__).resolve().parents[2] / "CLAUDE.md"

#: Рядок 22: «… 80 чеків у шести модулях.»
TOTAL_RE = re.compile(r"(\d+)\s+чеків\s+у\s+шести\s+модулях")
#: Рядки 245–246: «реєстр: seo (32), ai_ready (12), …» — можуть переноситись.
INVENTORY_RE = re.compile(r"реєстр:\s*(.+?)\n\s*(?:standards/|\Z)", re.S)
PAIR_RE = re.compile(r"([a-z_]+)\s*\((\d+)\)")


def _document() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.fixture(scope="module")
def documented() -> tuple[int, dict[str, int]]:
    """Те, що документ СТВЕРДЖУЄ зараз: загальне число й перелік по модулях."""
    text = _document()

    totals = TOTAL_RE.findall(text)
    assert totals, "CLAUDE.md більше не називає загального числа чеків"
    assert len(totals) == 1, f"загальне число названо {len(totals)} разів: {totals}"

    block = INVENTORY_RE.search(text)
    assert block, "у CLAUDE.md не знайдено переліку `реєстр: …` по модулях"
    pairs = PAIR_RE.findall(block.group(1))
    assert pairs, "перелік модулів порожній"
    per_module = {name: int(count) for name, count in pairs}
    assert len(per_module) == len(pairs), f"модуль названо двічі: {pairs}"
    return int(totals[0]), per_module


@pytest.fixture(scope="module")
def runtime() -> tuple[int, dict[str, int]]:
    """Те, що реєстр МАЄ насправді. Рахується з самого реєстру, не з тексту."""
    counts = Counter(check.module for check in REGISTRY)
    return len(REGISTRY), {module.value: counts[module] for module in Module}


# ── реєстр сам по собі ────────────────────────────────────────────────────────

def test_кожен_зареєстрований_код_непорожній() -> None:
    empty = [c.__name__ for c in REGISTRY if not getattr(c, "code", None)]
    assert not empty, f"чеки без коду: {empty}"


def test_коди_чеків_унікальні() -> None:
    codes = [check.code for check in REGISTRY]
    duplicates = sorted({code for code, n in Counter(codes).items() if n > 1})
    assert not duplicates, f"дубльовані коди: {duplicates}"


# ── документ проти реєстру ────────────────────────────────────────────────────

def test_документований_загальний_збігається_з_реєстром(documented, runtime) -> None:
    doc_total, _ = documented
    run_total, _ = runtime
    assert doc_total == run_total, (
        f"CLAUDE.md каже {doc_total} чеків, реєстр має {run_total}. "
        "Оновіть рядок у CLAUDE.md, а не це число тут."
    )


def test_документований_загальний_дорівнює_сумі_підсумків(documented) -> None:
    doc_total, per_module = documented
    assert doc_total == sum(per_module.values()), (
        f"документ суперечить сам собі: загальне {doc_total}, "
        f"сума по модулях {sum(per_module.values())} ({per_module})"
    )


def test_перелік_модулів_збігається_з_продуктовим_enum(documented, runtime) -> None:
    _, per_module = documented
    _, run_module = runtime
    assert set(per_module) == set(run_module), (
        f"перелік модулів розійшовся: у документі {sorted(per_module)}, "
        f"у Module {sorted(run_module)}"
    )


def test_кожен_підсумок_модуля_збігається_з_реєстром(documented, runtime) -> None:
    _, per_module = documented
    _, run_module = runtime
    drift = {
        name: (per_module[name], run_module[name])
        for name in sorted(set(per_module) & set(run_module))
        if per_module[name] != run_module[name]
    }
    assert not drift, f"підсумки модулів розійшлися (документ, реєстр): {drift}"


# ── зліпок цієї бази ──────────────────────────────────────────────────────────
#
# Числа нижче — не друге джерело істини: вище кожне з них уже звірене з
# реєстром. Вони фіксують САМУ БАЗУ, щоб узгоджена зміна документа й реєстру
# одночасно не пройшла мовчки: додати чек можна, але це видно в діфі тут.

def test_реєстр_цієї_бази_має_вісімдесят_чеків(runtime) -> None:
    run_total, _ = runtime
    assert run_total == 80


def test_модулі_цієї_бази_мають_очікувані_розміри(runtime) -> None:
    _, run_module = runtime
    assert run_module == {
        "seo": 32,
        "tech": 14,
        "ai_ready": 12,
        "performance": 11,
        "llm_visibility": 9,
        "accessibility": 2,
    }


# ── поточний стан проти сталого числа ─────────────────────────────────────────
#
# `CLAUDE.md` називав «1648 тестів» — число, яке застаріває з кожним доданим
# тестом і яке не звіряв жоден тест. На момент прибирання суїта мала 3191 тест
# у чистому дереві й 3267 із шаром власника, тобто документ помилявся вдвічі.
# Підставити свіже число означало б завести той самий дефект із новою датою:
# правильна відповідь — не називати числа взагалі, а сказати, що набір
# проходить.
#
# Сторож дивиться РІВНО на абзац поточного стану. Історичні свідчення в
# «Пастках» («Усі 1494 тести були зелені») називають числа правомірно: вони
# описують конкретний минулий прогін, а не теперішній стан, і їх не можна
# ані читати тут, ані вимагати стерти.

#: Розділ «## Поточний стан» до наступного заголовка того ж рівня.
CURRENT_STATE_RE = re.compile(r"^## Поточний стан$\n(.*?)(?=^## )", re.S | re.M)

#: Затверджене власником формулювання. Числа в ньому немає навмисно.
APPROVED_SENTENCE = "Повний набір backend-тестів проходить без помилок."

#: Число, приліплене до слова про тести: «1648 тестів», «1 648 тестів»,
#: «1,648 тестів», і зворотний порядок «тестів: 1648». Роздільниками всередині
#: числа бувають звичайний пробіл, нерозривний пробіл і кома.
TEST_TOTAL_RE = re.compile(
    r"\d[\d\u00a0 ,]*[\u00a0 ]?тест\w*"
    r"|тест\w*[\u00a0 ,]*:?[\u00a0 ]*\d",
    re.IGNORECASE,
)


def test_поточний_стан_не_називає_числа_тестів() -> None:
    """Абзац про теперішній стан не має права називати кількість тестів."""
    text = _document()

    section = CURRENT_STATE_RE.search(text)
    assert section, "у CLAUDE.md не знайдено розділу «## Поточний стан»"
    body = section.group(1)

    named = body.count(APPROVED_SENTENCE)
    assert named == 1, (
        f"затверджене речення про backend-тести трапляється {named} разів "
        "у розділі «Поточний стан», очікувалось рівно одне"
    )

    paragraphs = [p for p in body.split("\n\n") if APPROVED_SENTENCE in p]
    assert len(paragraphs) == 1, f"речення розійшлося по {len(paragraphs)} абзацах"
    paragraph = paragraphs[0]

    stale = TEST_TOTAL_RE.findall(paragraph)
    assert not stale, (
        f"абзац поточного стану знову називає число тестів: {stale}. "
        "Воно застаріває з кожним доданим тестом, і не звіряє його ніщо. "
        "Не підставляйте свіже число — саме тому тут його немає."
    )

    # Межу треба довести, а не пообіцяти. Якби взірець не спрацьовував ніде,
    # перевірка вище проходила б і на порожньому правилі.
    outside = TEST_TOTAL_RE.findall(text.replace(paragraph, ""))
    assert outside, (
        "у CLAUDE.md не лишилось жодного числа тестів поза абзацом поточного "
        "стану — тоді цей сторож нічого не обмежує й проходив би вхолосту"
    )
