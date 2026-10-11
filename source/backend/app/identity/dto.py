"""Що контекст ідентичності віддає назовні.

Не ORM-об'єкти. Різниця не косметична: ORM-модель тягне за собою сесію,
ліниві завантаження й усю схему таблиці, тож маршрут, який її прийняв,
починає залежати від персистентності — і зміна колонки стає зміною
контракту API.

Три різні речі, які легко злити в одну заради зручності:
схема API (що бачить клієнт), DTO (що передається між шарами) і
ORM-модель (як воно лежить у базі). Вони бувають схожі й мусять лишатися
різними.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.identity.enums import Role, UserStatus
from app.models.identity import ApiKey, Membership, Organization, User


@dataclass(frozen=True, slots=True)
class UserView:
    id: uuid.UUID
    email: str
    display_name: str
    status: UserStatus
    # Мова інтерфейсу. Порожньо — не обирав, тобто їде за організацією.
    locale: str = ""
    # Роль у команді Crawldy або нічого. Інтерфейсу вона потрібна рівно
    # для одного: чи пропонувати службові екрани. Права це не дає —
    # їх перевіряє кожен службовий маршрут окремо, і 403 приходить
    # незалежно від того, що намалював фронтенд.
    platform_role: str | None = None

    @classmethod
    def of(cls, record: User) -> UserView:
        return cls(
            id=record.id,
            email=record.email,
            display_name=record.display_name,
            status=record.status,
            locale=record.locale,
            platform_role=record.platform_role.value if record.platform_role else None,
        )


@dataclass(frozen=True, slots=True)
class OrganizationView:
    id: uuid.UUID
    name: str
    slug: str
    is_personal: bool
    # Роль того, хто питає. Належить перегляду, а не організації: та сама
    # організація для різних людей має різні ролі.
    role: Role

    @classmethod
    def of(cls, record: Organization, role: Role) -> OrganizationView:
        return cls(
            id=record.id,
            name=record.name,
            slug=record.slug,
            is_personal=record.is_personal,
            role=role,
        )

    @classmethod
    def of_membership(cls, record: Organization, membership: Membership) -> OrganizationView:
        return cls.of(record, membership.role)


@dataclass(frozen=True, slots=True)
class ApiKeyView:
    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None

    @classmethod
    def of(cls, record: ApiKey) -> ApiKeyView:
        return cls(
            id=record.id,
            name=record.name,
            prefix=record.prefix,
            created_at=record.created_at,
            last_used_at=record.last_used_at,
        )


@dataclass(frozen=True, slots=True)
class IssuedApiKeyView(ApiKeyView):
    """Ключ разом із секретом. Існує рівно один раз — у відповіді на створення."""

    token: str = ""

    @classmethod
    def issued(cls, record: ApiKey, token: str) -> IssuedApiKeyView:
        base = ApiKeyView.of(record)
        return cls(
            id=base.id,
            name=base.name,
            prefix=base.prefix,
            created_at=base.created_at,
            last_used_at=base.last_used_at,
            token=token,
        )


__all__ = ["ApiKeyView", "IssuedApiKeyView", "OrganizationView", "UserView"]
