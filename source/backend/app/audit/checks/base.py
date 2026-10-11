"""Реєстр чеків. Додати новий чек = підклас + декоратор @register."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from app.audit import i18n
from app.audit.types import Confidence, Effort, Issue, Module, Severity, SiteContext


class Check(ABC):
    code: str
    module: Module
    severity: Severity = Severity.MEDIUM
    weight: int = 2
    title: str = ""

    # Скільки коштує полагодити. Дані декларуються поруч із чеком, а не
    # вгадуються в шарі звіту — так само, як weight.
    effort: Effort = Effort.MEDIUM

    # Наскільки твердо чек стверджує. Дефолт високий: більшість читає
    # розмітку й заголовки. Чеки, що спираються на висновок моделі або на
    # неповне покриття краулу, знижують його явно.
    confidence: Confidence = Confidence.HIGH

    # Усі ключі каталогу, які цей чек може віддати. Дефолт — сам code.
    # test_i18n перевіряє, що кожен ключ є в кожній мові.
    messages: tuple[str, ...] = ()

    # Семантично різні проблеми, які цей чек уміє розрізняти.
    #
    # Порожньо означає «чек знає рівно одну проблему»; тоді `issue_key`
    # дорівнює коду. Непорожнє — кожна знахідка мусить назвати свою
    # проблему явно, і `issue.issue_key` стане `code:variant`.
    #
    # Оголошується тут, а не виводиться з `messages`, навмисно. Ключі
    # каталогу — це presentation layer: їх перейменовують, коли міняють
    # формулювання, і привʼязати до них стелю штрафу означало б зробити
    # так, щоб редагування тексту мовчки зсувало бали. Крім того, два
    # повідомлення інколи описують **одну** проблему в різних ступенях
    # («заголовків безпеки бракує» проти «їх немає жодного»), і ділити
    # для них стелю правильно.
    variants: tuple[str, ...] = ()

    # Чи спирається висновок чека на прочитаний вміст сайту.
    #
    # Коли краул не приніс жодної сторінки, такий чек не мовчить — він
    # стверджує відсутність: «немає сторінки About», «немає sitemap»,
    # «немає розмітки Organization». Це опис нашої відмови, а не сайту:
    # unilever.com віддав нам 403 на все й отримав тринадцять таких
    # тверджень при чесно притриманому балі. Число ми не вигадали, а
    # зміст — вигадали.
    #
    # Дефолт True: більшість чеків судить те, що прочитала. False ставлять
    # ті, чий доказ лежить у самій відповіді сервера — код, заголовки,
    # сертифікат, — і лишається доказом навіть тоді, коли сторінки немає.
    reads_content: bool = True

    @classmethod
    def message_keys(cls) -> tuple[str, ...]:
        return cls.messages or (cls.code,)

    @abstractmethod
    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        """Повертає знайдені проблеми. Порожньо = чек пройдено."""

    def issue(
        self,
        *,
        key: str | None = None,
        msg: str | None = None,
        params: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        severity: Severity | None = None,
        page_url: str | None = None,
        confidence: Confidence | None = None,
    ) -> Issue:
        # Чек, який оголосив, що розрізняє кілька проблем, мусить казати,
        # яку саме знайшов. Мовчазний дефолт злив би їх під одну стелю —
        # рівно той дефект, заради якого variants і зʼявились.
        if self.variants and key is None:
            raise ValueError(f"{self.code}: знахідка без key, хоча чек розрізняє {self.variants}")
        if key is not None and key not in self.variants:
            raise ValueError(f"{self.code}: невідомий key {key!r}, оголошено {self.variants}")

        message = msg or self.code
        text = i18n.render(message, params)
        return Issue(
            code=self.code,
            module=self.module,
            severity=severity or self.severity,
            title=text.title,
            description=text.description,
            recommendation=text.recommendation,
            evidence=evidence or {},
            weight=self.weight,
            page_url=page_url,
            confidence=confidence or self.confidence,
            msg=message,
            params=params or {},
            key=key or "",
        )


REGISTRY: list[type[Check]] = []


def register(cls: type[Check]) -> type[Check]:
    if not getattr(cls, "code", None):
        raise ValueError(f"{cls.__name__} без code")
    if any(existing.code == cls.code for existing in REGISTRY):
        raise ValueError(f"дубль коду чека: {cls.code}")
    REGISTRY.append(cls)
    return cls


def _with_applicability(check: Check) -> Check:
    """Обгорнути `run` фільтром застосовності (E-05).

    Обгортка стоїть ТУТ, а не в кожному чеку, і це вимога контракту:
    «applicability is policy-driven and centralized, not scattered ad hoc
    through checks». Поки кожен чек вирішував сам, ніхто не бачив картини
    цілком — і `/login` роками втрачав бали за відсутній title.

    Обгортається саме екземпляр, а не клас: підміна на класі змінила б
    поведінку й там, де чек створюють напряму (тести, скрипти), а тут
    потрібен рівно один шов — той, через який аудит справді виконує чеки.
    """
    inner = check.run

    def run(ctx: SiteContext) -> Iterable[Issue]:
        from app.audit import applicability

        return applicability.filter_issues(ctx, check.code, inner(ctx))

    check.run = run  # type: ignore[method-assign]
    return check


def all_checks(modules: set[Module] | None = None) -> list[Check]:
    return [
        _with_applicability(cls())
        for cls in REGISTRY
        if modules is None or cls.module in modules
    ]


# Ключі каталогу вилучених із продукції чеків. Рядки шести локалей
# лишаються ЗАРАДИ ЗБЕРЕЖЕНИХ аудитів: старий звіт мусить рендеритися
# тією ж мовою, якою був порахований. Нові аудити цих ключів не
# емітять — самих чеків у реєстрі немає, і саме реєстр є єдиним
# джерелом емісії.
#
# llm.direct_answer вилучено 30.08.2026: предикат міряв не сайт, а нашу
# екстракцію (<main>/меню) і латинську пунктуацію — 27 із 30 спрацювань
# вибірки були навігаційними артефактами (fastapi.tiangolo.com,
# microsoft.com/about), CJK-сторінки не могли пройти структурно, а
# формулювання обіцяло поведінку ChatGPT, якої не документує жоден
# провайдер.
# ai.jsonld.partial вилучено 30.08.2026: часткове покриття — не вада.
# Розмітка не мусить стояти на кожній сторінці (Google: Organization —
# на головній або about), а посторінкову застосовність ми надійно не
# визначаємо.
RETIRED_MESSAGE_KEYS = frozenset({
    "llm.direct_answer",
    "ai.jsonld.partial",
    # Сама назва ключа стверджувала недовідне: «незахищена» форма з
    # HTML не доводиться. Активний спадкоємець — no_visible_marker.
    "tech.form_protection.unprotected",
    # Вилучено зі скорингу 13 вересня 2026 (G6: E-07, рішення власника
    # OD-01). Текст лишається в каталозі шістьма мовами навмисно: звіти,
    # збережені до вилучення, несуть цей ключ і мусять рендеритись далі.
    # Новий аудит його не віддасть — чек більше не зареєстрований.
    "ai.schema.faq",
})


def all_message_keys() -> set[str]:
    """Ключі АКТИВНИХ чеків — те, що нові аудити справді можуть віддати.

    Вилучені ключі сюди не входять навмисно: синтетичні контексти
    мусять чіпляти кожен активний ключ, а вимагати цього від вилучених
    означало б тримати мертві фікстури. Тест каталогу на сиріт натомість
    допускає active ∪ retired.
    """
    return {key for cls in REGISTRY for key in cls.message_keys()}
