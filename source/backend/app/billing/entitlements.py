"""Права: що організація зараз може робити.

Межа між білінгом і поведінкою продукту. Білінг відповідає на питання
«яка підписка активна»; права — на питання «що з цього випливає».

Головне правило тут одне й воно негативне: **назва тарифу не з'являється
в бізнес-логіці жодного разу**. Код питає `can("scheduled_audits")` і
`limit("max_pages_per_audit")`, а не `if plan == "pro"`. Перше переживає
зміну складу тарифів, друге вимагає переписування при кожній.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Ключі прав. Список закритий навмисно: нове право — це свідома зміна
# продукту, і воно має пройти через цей файл, а не з'явитися рядком у
# JSON, який ніхто не перевірить.
#
# Значення `None` означає «без обмеження», і це не те саме, що 0.
KEYS: dict[str, type] = {
    "audits_per_period": int,  # None = без обмеження
    # Перевірки AI-присутності на період підписки. ЗАВЖДИ обмежені:
    # безлімітного варіанта в цього ключа немає навмисно — присутність
    # має реальну провайдерську вартість, і «безліміт краулів» ніколи
    # не означає «безліміт AI».
    "presence_per_period": int,
    "max_pages_per_audit": int,
    "sites_limit": int,  # None = без обмеження
    "scheduled_audits": int,  # скільки активних розкладів
    "schedule_min_interval_hours": int,
    # Що клієнт **бачить** в історії. Не те, що ми зберігаємо: якби
    # тариф керував видаленням, пониження на один місяць знищувало б рік
    # історії безповоротно. Приховане повертається, знищене — ні.
    "history_retention_days": int,  # None = бачити все
    # Скільки живуть сирі дані й знахідки. Тариф може строк подовжити й
    # не може вкоротити нижче продуктової межі — див. retention_policy.
    "raw_retention_days": int,
    "findings_retention_days": int,  # None = зберігати завжди
    "semantic_analysis": bool,
    "report_download": bool,
    "public_reports": bool,
    "api_access": bool,
    "team_members": int,
    "white_label": bool,
}

# Значення за замовчуванням. Вони описують найбіднішу можливу організацію
# і потрібні для того, щоб резолвер ніколи не повертав `None` замість
# набору прав: «немає підписки» має означати «безкоштовний тариф», а не
# «перевірка неможлива». Інакше кожна перевірка в коді мусила б окремо
# обробляти відсутність — і половина забула б.
FALLBACK: dict[str, Any] = {
    "audits_per_period": 0,
    "presence_per_period": 0,
    "max_pages_per_audit": 10,
    "sites_limit": 0,
    "scheduled_audits": 0,
    "schedule_min_interval_hours": 24 * 30,
    "history_retention_days": 30,
    "raw_retention_days": 90,
    "findings_retention_days": 730,
    "semantic_analysis": False,
    "report_download": False,
    "public_reports": False,
    "api_access": False,
    "team_members": 1,
    "white_label": False,
}


# Права, у яких «без обмеження» не буває. Присутність має реальну
# провайдерську вартість на кожну одиницю, і None тут означав би
# необмежені чужі гроші — валідація відкидає його ще в адмінці.
NEVER_UNLIMITED: frozenset[str] = frozenset({"presence_per_period"})

# Ключі, які є КОМЕРЦІЙНИМ НАДІЛОМ періоду підписки. Саме вони
# знімкуються на початок періоду: зміна тарифу адміністратором не має
# переписувати вже виданий наділ, а наступний період бере нові значення.
# Решта прав (сторінки, фічі) — поведінка продукту «зараз», не наділ.
PERIOD_ALLOCATION_KEYS: tuple[str, ...] = (
    "audits_per_period",
    "presence_per_period",
)


class UnknownEntitlement(KeyError):
    """Права з такою назвою не існує."""


@dataclass(frozen=True, slots=True)
class EntitlementSet:
    """Готова відповідь на «що дозволено».

    Незмінна й порахована один раз на запит: право, яке міняється
    посеред обробки, дає стан, у якому перевірка пройшла, а дія
    заборонена.
    """

    values: dict[str, Any]
    # Звідки взявся набір — для пояснення в інтерфейсі й у логах.
    plan_code: str
    source: str  # "fallback" | "plan" | "plan+override"

    def _get(self, key: str) -> Any:
        if key not in KEYS:
            raise UnknownEntitlement(key)
        return self.values.get(key, FALLBACK[key])

    def can(self, key: str) -> bool:
        """Булеве право. Числове право теж «можна», якщо ліміт не нульовий."""
        value = self._get(key)
        if isinstance(value, bool):
            return value
        return value is None or value > 0

    def limit(self, key: str) -> int | None:
        """Числовий ліміт. `None` означає «без обмеження»."""
        value = self._get(key)
        if value is None:
            return None
        if isinstance(value, bool):
            raise UnknownEntitlement(f"{key} — булеве право, а не ліміт")
        return int(value)

    def cap(self, key: str, requested: int) -> int:
        """Обрізати запит до дозволеного.

        Саме так права потрапляють у двигун: він не питає про тариф, він
        отримує вже дозволені опції.
        """
        allowed = self.limit(key)
        return requested if allowed is None else min(requested, allowed)

    def to_json(self) -> dict[str, Any]:
        return {
            "plan": self.plan_code,
            "source": self.source,
            "values": {key: self._get(key) for key in KEYS},
        }


def validate(values: dict[str, Any]) -> list[str]:
    """Що не так із набором прав. Порожній список — усе гаразд.

    Перевірка потрібна, бо права живуть у JSONB, і база типів не
    контролює. Тариф із рядком замість числа не зламається одразу — він
    зламається під час першої перевірки ліміту, тобто у клієнта.
    """
    problems = []
    for key, value in values.items():
        if key not in KEYS:
            problems.append(f"невідоме право: {key}")
            continue
        expected = KEYS[key]
        if value is None:
            if expected is bool:
                problems.append(f"{key}: булеве право не може бути None")
            if key in NEVER_UNLIMITED:
                problems.append(f"{key}: безлімітним не буває — потрібне число")
            continue
        if expected is bool and not isinstance(value, bool):
            problems.append(f"{key}: очікується true/false, а не {value!r}")
        if expected is int and (isinstance(value, bool) or not isinstance(value, int)):
            problems.append(f"{key}: очікується число, а не {value!r}")
        if expected is int and isinstance(value, int) and not isinstance(value, bool) and value < 0:
            problems.append(f"{key}: від'ємний ліміт")
    return problems


def resolve(
    *,
    plan_code: str | None,
    plan_values: dict[str, Any] | None,
    overrides: dict[str, Any] | None = None,
) -> EntitlementSet:
    """Дефолт → тариф → індивідуальні винятки.

    Винятки потрібні з першого дня, а не «коли знадобляться»: перша ж
    нестандартна домовленість — компенсація, дідівські умови, тестовий
    доступ для партнера — інакше ламає модель і робиться хардкодом.
    """
    values = dict(FALLBACK)
    source = "fallback"
    if plan_values:
        values.update({k: v for k, v in plan_values.items() if k in KEYS})
        source = "plan"
    if overrides:
        values.update({k: v for k, v in overrides.items() if k in KEYS})
        source = "plan+override" if plan_values else "override"
    return EntitlementSet(values=values, plan_code=plan_code or "free", source=source)


__all__ = [
    "FALLBACK",
    "KEYS",
    "NEVER_UNLIMITED",
    "PERIOD_ALLOCATION_KEYS",
    "EntitlementSet",
    "UnknownEntitlement",
    "resolve",
    "validate",
]
