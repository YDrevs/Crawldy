"""Платформна роль людині, яка ВЖЕ зареєструвалась у продукті.

Перший адміністратор нової інсталяції з'являється саме так, і навмисно
не інакше.

Що цей скрипт НЕ робить, і чому.

**Не створює користувача й не задає пароля.** Пароль знає тільки його
власник: людина реєструється звичайною формою, обирає пароль сама, а
скрипт лише піднімає їй платформну роль. Скрипт, який заводить
«адміністратора за замовчуванням» із відомим паролем, — це не зручність,
а бекдор, що переживе розгортання й потрапить у резервні копії.

**Не має маршруту в API.** Підвищення до персоналу через HTTP було б
поверхнею атаки, яка потрібна рівно один раз за життя інсталяції.
Доступ до бази вже означає повний контроль, тож нічого нового цей
скрипт не відкриває.

**Не вигадує адреси.** Якщо такої людини немає, він відмовляє й каже
зареєструватися — а не створює її мовчки.

Запуск ідемпотентний: та сама роль удруге нічого не міняє й каже про це.

    python scripts/grant_platform_role.py --email you@example.com --role admin
    python scripts/grant_platform_role.py --email you@example.com --show
    python scripts/grant_platform_role.py --email you@example.com --revoke

`staff` дивиться й допомагає, `admin` ще й міняє умови та повторює події
білінгу; `admin` покриває `staff`. Порожня роль — звичайний клієнт, і це
стан за замовчуванням для всіх.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

# Хости compose-мережі з хоста не видно; локальний запуск дивиться на
# опубліковані порти. Явне значення в оточенні лишається головним.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://seo:seo@localhost:5432/seo")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.core.db import SessionLocal  # noqa: E402
from app.identity.enums import PlatformRole  # noqa: E402
from app.identity.service import find_user_by_email, normalize_email  # noqa: E402

MISSING = (
    "Такої людини в базі немає.\n"
    "Спершу зареєструйтеся у продукті звичайною формою — пароль обираєте ви,\n"
    "і скрипт його не бачить, — а потім запустіть цю команду ще раз."
)


async def run(email: str, role: PlatformRole | None, show: bool) -> int:
    async with SessionLocal() as db:
        user = await find_user_by_email(db, email)
        if user is None:
            print(MISSING)
            return 1

        current = user.platform_role
        shown = current.value if current else "(звичайний клієнт)"
        if show:
            print(f"{normalize_email(email)}: {shown}")
            return 0

        wanted = role.value if role else "(звичайний клієнт)"
        if current == role:
            print(f"{normalize_email(email)}: вже {shown} — нічого не змінено")
            return 0

        user.platform_role = role
        await db.commit()
        print(f"{normalize_email(email)}: {shown} → {wanted}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--email", required=True, help="адреса вже зареєстрованої людини")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--role", choices=[r.value for r in PlatformRole], help="яку роль дати")
    group.add_argument("--revoke", action="store_true", help="зняти платформну роль")
    group.add_argument("--show", action="store_true", help="показати поточну роль")
    args = parser.parse_args()

    role = PlatformRole(args.role) if args.role else None
    return asyncio.run(run(args.email, role, args.show))


if __name__ == "__main__":
    raise SystemExit(main())
