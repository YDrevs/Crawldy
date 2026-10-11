"""robots.txt за RFC 9309: розбір груп і рішення про конкретний шлях.

## Чому не «чи є Disallow: /»

Попередня перевірка вважала краулер заблокованим лише тоді, коли для
нього стояло рівно `Disallow: /`. Усе інше було невидимим: заборона на
`/blog/`, `Allow`, який її знімає, зірочка в шаблоні, група `*` як
запасний варіант. Сайт, що закрив від пошукового бота половину розділів,
для нас виглядав відкритим.

Тут реалізовано те, що описує RFC 9309, і рівно в тому обсязі, який
потрібен для відповіді на питання «чи дозволено цьому агенту цей шлях»:

- вибір групи регістронезалежний, найдовший збіг product-token виграє;
- кілька груп з однаковим агентом зливаються в одну;
- немає збігу — діє група `*`; немає і її — дозволено все;
- у шляхах підтримуються `*` (будь-яка послідовність) і `$` (кінець);
- виграє найдовше правило; за однакової довжини — `allow`.

## Чого тут навмисно немає

Ми не змінюємо поведінку власного краулера. Цей модуль відповідає на
питання **про сайт клієнта** — що його robots.txt каже чужим ботам.
Політика власного обходу — окреме рішення, і змішувати їх в одному
місці означало б, що зміна звіту тихо змінює те, як ми ходимо.

`crawl-delay` і `sitemap` до RFC не належать; перший ігнорується при
оцінці доступу, другий читається окремо як розширення.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

# Директиви, що визначають доступ. Решта рядків групи не впливає на
# рішення й потрібна іншим споживачам.
_ACCESS_FIELDS = ("allow", "disallow")


@dataclass(frozen=True, slots=True)
class Rule:
    """Одне правило доступу з групи."""

    allow: bool
    # Шлях як його написав власник — саме він показується у доказі.
    pattern: str

    @property
    def directive(self) -> str:
        return "Allow" if self.allow else "Disallow"

    def as_line(self) -> str:
        return f"{self.directive}: {self.pattern}"


@dataclass(frozen=True, slots=True)
class Decision:
    """Чи дозволено шлях — і чим саме це вирішено.

    `rule` порожнє, коли жодне правило не збіглося: RFC у цьому випадку
    дозволяє доступ, і доказ має показувати саме відсутність заборони, а
    не вигадане правило.
    """

    allowed: bool
    # Токен групи, яка застосувалася: сам агент або `*`.
    matched_group: str | None
    rule: Rule | None

    @property
    def reason(self) -> str:
        if self.rule is None:
            return "no matching rule"
        return self.rule.as_line()


@dataclass(slots=True)
class Group:
    """Група записів robots.txt: агенти та їхні правила."""

    agents: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)


@dataclass(slots=True)
class RobotsFile:
    """Розібраний robots.txt, готовий відповідати про будь-який шлях."""

    groups: list[Group] = field(default_factory=list)
    sitemaps: list[str] = field(default_factory=list)
    crawl_delay: float | None = None
    # Не було чого розбирати: файлу немає, він порожній або віддав не той
    # тип. Тоді заборон не існує, і це не те саме, що «дозволено явно».
    empty: bool = True

    def rules_for(self, token: str) -> tuple[str | None, list[Rule]]:
        """Правила, що діють для цього агента, і назва групи.

        Вибір за RFC: регістронезалежно, найдовший збіг product-token, усі
        групи з цим агентом зливаються. Немає збігу — група `*`.
        """
        wanted = token.strip().lower()

        best: str | None = None
        for group in self.groups:
            for agent in group.agents:
                if agent == "*":
                    continue
                if wanted.startswith(agent) and (best is None or len(agent) > len(best)):
                    best = agent

        if best is None and any("*" in g.agents for g in self.groups):
            best = "*"
        if best is None:
            return None, []

        merged: list[Rule] = []
        for group in self.groups:
            if best in group.agents:
                merged.extend(group.rules)
        return best, merged

    def evaluate(self, token: str, path: str) -> Decision:
        """Чи можна цьому агенту цей шлях.

        Найдовший збіг виграє; за рівної довжини перемагає `allow` —
        обидва правила прямо в RFC, і обидва легко втратити, якщо писати
        перевірку «на око».
        """
        group, rules = self.rules_for(token)
        target = _normalise_path(path)

        winner: Rule | None = None
        winning_length = -1
        for rule in rules:
            if not _matches(rule.pattern, target):
                continue
            length = len(rule.pattern)
            if length > winning_length or (
                length == winning_length and rule.allow and winner is not None
            ):
                winner, winning_length = rule, length

        if winner is None:
            return Decision(allowed=True, matched_group=group, rule=None)
        return Decision(allowed=winner.allow, matched_group=group, rule=winner)


def parse(content: str) -> RobotsFile:
    """Текст robots.txt → структура. Нерозбірливі рядки ігноруються.

    RFC вимагає саме терпимості: файл із помилкою в одному рядку не стає
    недійсним цілком, інакше друкарська помилка закривала б сайт.
    """
    parsed = RobotsFile()
    current: Group | None = None
    # Порожній рядок або директива доступу закриває набір агентів: далі
    # `User-agent` починає вже нову групу.
    accepting_agents = False

    for raw in content.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()

        if field_name == "user-agent":
            if current is None or not accepting_agents:
                current = Group()
                parsed.groups.append(current)
                accepting_agents = True
            if value:
                current.agents.append(value.lower())
            continue

        if field_name in _ACCESS_FIELDS:
            accepting_agents = False
            if current is None:
                # Правило без групи ні до кого не належить.
                continue
            # `Disallow:` з порожнім значенням не забороняє нічого — це
            # спосіб сказати «дозволено все», і правилом він не стає.
            if field_name == "disallow" and not value:
                continue
            current.rules.append(Rule(allow=field_name == "allow", pattern=value))
            continue

        accepting_agents = False
        if field_name == "sitemap" and value:
            parsed.sitemaps.append(value)
        elif field_name == "crawl-delay":
            try:
                parsed.crawl_delay = float(value)
            except ValueError:
                pass

    parsed.empty = not parsed.groups and not parsed.sitemaps
    return parsed


def _normalise_path(path: str) -> str:
    """Адреса або шлях → шлях із запитом, як його зіставляє RFC."""
    if path.startswith(("http://", "https://")):
        split = urlparse(path)
        path = split.path or "/"
        if split.query:
            path = f"{path}?{split.query}"
    if not path.startswith("/"):
        path = "/" + path
    return unquote(path)


def _matches(pattern: str, path: str) -> bool:
    """Чи накриває шаблон цей шлях. Підтримуються `*` і кінцевий `$`."""
    if pattern == "":
        return False
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    if "*" not in body:
        return path == body if anchored else path.startswith(body)

    expression = "".join(
        ".*" if part == "*" else re.escape(part)
        for part in re.split(r"(\*)", body)
    )
    return re.match(expression + ("$" if anchored else ""), path) is not None


__all__ = ["Decision", "Group", "RobotsFile", "Rule", "parse"]
