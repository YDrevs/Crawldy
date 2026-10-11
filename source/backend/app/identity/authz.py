"""Авторизація: чи має цей актор доступ до цього ресурсу.

Окремо від автентифікації («хто це») і окремо від прав тарифу («що
дозволяє план»). Порядок завжди такий: спершу знаємо, хто; потім — чи
його це взагалі; і аж потім — чи дозволяє тариф. Активна підписка не дає
доступу до чужого аудиту; членство не дає права на функцію поза тарифом.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from app.identity.enums import PlatformRole, Role

AuthMethod = Literal["session", "api_key"]


class NotAuthenticated(Exception):
    """Хто це — невідомо."""


class Forbidden(Exception):
    """Відомо хто, але цього йому не можна."""


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Хто діє й від чийого імені.

    Організація тут — не параметр запиту, а частина контексту
    автентифікації. Це не деталь реалізації: щойно `organization_id`
    почне приходити з тіла запиту, будь-хто зможе підставити чужу, і
    перевірка власності перетвориться на формальність.

    `user_id` порожній для ключа API: ключ належить організації, а не
    людині, і дія від його імені не має автора.
    """

    organization_id: uuid.UUID
    role: Role
    auth: AuthMethod
    user_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None

    # Мовні налаштування читача. Рядки, а не локалі: сюди вони приходять
    # із бази, і невідоме значення має прозоро нічого не значити, а не
    # валити запит. Розбирає їх `application.locale.resolve`.
    #
    # Порожньо в обох — нормальний стан для ключа API: у ключа немає
    # людини, а мова організації читається тоді, коли вона є.
    user_locale: str = ""
    organization_locale: str = ""

    # Роль у платформі. Порожньо в переважної більшості акторів — і в
    # усіх ключів API: ключ належить організації, а персонал — це людина.
    platform_role: PlatformRole | None = None

    @property
    def is_human(self) -> bool:
        return self.user_id is not None

    @property
    def is_staff(self) -> bool:
        return self.platform_role is not None

    def require_platform(self, needed: PlatformRole) -> None:
        """Права команди Crawldy. Відмова однакова для всіх, хто їх не має.

        Ключ API сюди не проходить ніколи: у нього немає людини, а
        платформні дії робить людина й відповідає за них.
        """
        if self.user_id is None or self.platform_role is None:
            raise Forbidden("потрібні права команди Crawldy")
        if not self.platform_role.covers(needed):
            raise Forbidden(f"потрібна платформна роль не нижча за {needed.value}")

    def require(self, role: Role) -> None:
        """Роль не нижча за задану, інакше — відмова.

        Ключ API отримує роль організації, з якою його створено, тож
        перевірка одна для обох способів входу.
        """
        if not self.role.at_least(role):
            raise Forbidden(f"потрібна роль не нижча за {role.value}, є {self.role.value}")

    def require_human(self) -> uuid.UUID:
        """Дія, у якої мусить бути автор: запрошення, зміна пароля, білінг.

        Ключ API сюди не пускається навмисно. Не тому, що він менш
        довірений, а тому, що такі дії потім пояснюють людині — і
        «зроблено ключем integration-1» не є відповіддю на питання, хто
        передав володіння організацією.
        """
        if self.user_id is None:
            raise Forbidden("дія потребує входу користувача, а не ключа API")
        return self.user_id


def owns(actor: ActorContext, organization_id: uuid.UUID) -> bool:
    return actor.organization_id == organization_id


def assert_owns(actor: ActorContext, organization_id: uuid.UUID) -> None:
    """Ресурс належить організації актора.

    Викидає `Forbidden`, але шар API перетворює це на 404, а не 403:
    відповідь «доступ заборонено» підтверджує, що ресурс існує, і дає
    сторонньому спосіб перевіряти чужі ідентифікатори.
    """
    if not owns(actor, organization_id):
        raise Forbidden("ресурс належить іншій організації")
