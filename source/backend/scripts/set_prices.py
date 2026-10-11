"""Ціни й кількості сторінки цін — з командного рядка, без адмінки.

Публічної адмінки в продукті немає: каталог редагується службовим API
(`PUT /v1/admin/commerce/...`), а він вимагає входу людини з платформною
роллю. Для локального перегляду це зайвий обряд, тож цей скрипт пише ті
самі значення тим самим шаром сервісів, що й маршрут, — з тими самими
перевірками: SINGLE видає рівно одну перевірку, PACK — щонайменше дві,
права тарифу перевіряються, форма посилання провайдера теж.

Числа беруться з аргументів і НЕ вигадуються: без аргументу значення
лишається таким, яким було. Суми задаються в звичайних одиницях валюти
(19.00), у базу лягають у мінімальних (1900).

    python scripts/set_prices.py --single 19 --pack 149 --pack-count 10 \
        --monthly 49 --monthly-presence 5

    python scripts/set_prices.py --show      # що зараз у каталозі
    python scripts/set_prices.py --clear     # прибрати все, що додав скрипт

Пакет — це набір разових перевірок: `--pack-count N` задає і кількість
повних перевірок, і кількість перевірок Actual AI Presence, бо це те саме
число. Ціна за одну перевірку обчислюється сторінкою з загальної ціни й N.

Прайс у провайдера скрипт не вигадує й не приймає аргументом: він
публікує ціну тим самим шляхом, що й кабінет (створює або оновлює прайс
чинного провайдера каси й записує його ідентифікатор). Раніше тут стояли
`--provider fake` і `--single-ref local_single` за замовчуванням — саме
вони й лишали каталог із посиланнями, за якими каса не відкривається.

Хто саме обслуговує касу, скрипт не питає: провайдера задає кабінет
(«Платіжний провайдер»), і публікація йде до нього.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

# Хости compose-мережі з хоста не видно; локальний запуск дивиться на
# опубліковані порти. Явне значення в оточенні лишається головним.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://seo:seo@localhost:5432/seo")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.application import catalogue_publishing as publishing  # noqa: E402
from app.billing import catalog as billing_catalog  # noqa: E402
from app.billing import entitlements as billing_entitlements  # noqa: E402
from app.billing.publishing import PublishFailed  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.services import commerce_service  # noqa: E402

SINGLE_CODE = "single"
PACK_CODE = "pack"
PLAN_CODE = "monthly"


def minor(amount: str, currency: str) -> int:
    """«19» або «19.90» → сума в мінімальних одиницях валюти."""
    from app.billing import money

    try:
        value = Decimal(amount)
    except InvalidOperation as exc:  # pragma: no cover - помилка вводу
        raise SystemExit(f"не число: {amount!r}") from exc
    if value < 0:
        raise SystemExit("ціна не буває відʼємною")
    exponent = money.exponent(currency)
    scaled = value.scaleb(exponent)
    if scaled != scaled.to_integral_value():
        raise SystemExit(f"{amount} має більше знаків після коми, ніж має {currency}")
    return int(scaled)


async def publish(spec) -> tuple[str, str, str]:
    """Опублікувати ціну в чинного провайдера. Повертає (провайдер, прайс, продукт).

    Відмова провайдера зупиняє скрипт: те саме правило, що в кабінеті —
    сайт не показує суми, за якою каса не візьме гроші.
    """
    provider = billing_catalog.current_provider()
    try:
        published = await publishing.publish(
            spec, provider=provider, price_ref=None, product_ref=None
        )
    except PublishFailed as exc:
        raise SystemExit(f"ціну не опубліковано у провайдера {provider}: {exc}") from exc
    return published.provider, published.price_ref, published.product_ref


async def show() -> None:
    async with SessionLocal() as db:
        offers = await commerce_service.all_offers(db)
        plans = await commerce_service.all_plans(db)
    if not offers and not plans:
        print("каталог порожній — сторінка цін покаже «Ціна за запитом»")
        return
    for offer in offers:
        amount = (
            "—" if offer.display_amount_minor is None
            else f"{offer.display_amount_minor / 100:.2f} {offer.currency}"
        )
        print(
            f"{offer.offer_type.value:7} {offer.code:12} {amount:>14}"
            f"  перевірок: {offer.audit_credits}  Presence: {offer.presence_credits}"
            f"  активна: {offer.active}"
        )
    for plan in plans:
        prices = ", ".join(
            "—" if p["display_amount_minor"] is None
            else f"{p['display_amount_minor'] / 100:.2f} {p['currency']}/{p['interval']}"
            for p in plan["prices"]
        ) or "—"
        presence = plan["entitlements"].get("presence_per_period")
        print(f"plan    {plan['code']:12} {prices:>14}  Presence/міс: {presence}"
              f"  публічний: {plan['is_public']}")


async def clear() -> None:
    from sqlalchemy import delete, select

    from app.models.billing import Plan, PlanPrice, Subscription
    from app.models.commerce import CommercialOffer

    async with SessionLocal() as db:
        await db.execute(
            delete(CommercialOffer).where(CommercialOffer.code.in_([SINGLE_CODE, PACK_CODE]))
        )
        plan = (await db.execute(select(Plan).where(Plan.code == PLAN_CODE))).scalar_one_or_none()
        if plan is not None:
            used = (
                await db.execute(
                    select(Subscription.id).where(Subscription.plan_id == plan.id)
                )
            ).first()
            if used is not None:
                print(f"тариф {PLAN_CODE} має підписку — не видаляю, лише ховаю з вітрини")
                plan.is_public = False
            else:
                await db.execute(delete(PlanPrice).where(PlanPrice.plan_id == plan.id))
                await db.delete(plan)
        await db.commit()
    print("прибрано")
    await show()


async def apply(args: argparse.Namespace) -> None:
    currency = args.currency.upper()
    async with SessionLocal() as db:
        if args.single is not None:
            amount = minor(args.single, currency)
            provider, price_ref, product_ref = await publish(publishing.offer_spec(
                code=SINGLE_CODE, offer_type="single", display_name=args.single_name,
                display_name_i18n={}, amount_minor=amount, currency=currency,
            ))
            await commerce_service.upsert_offer(db, code=SINGLE_CODE, values={
                "offer_type": "single", "active": True,
                "display_name": args.single_name, "description": "",
                "provider": provider, "provider_price_ref": price_ref,
                "provider_product_ref": product_ref,
                "currency": currency, "display_amount_minor": amount,
                # Склад разової фіксований продуктом: одна перевірка й одна
                # перевірка Actual AI Presence.
                "audit_credits": 1, "presence_credits": 1,
                "promo_eligible": False, "sort_order": 1,
                "display_name_i18n": {}, "description_i18n": {},
            })
        if args.pack is not None:
            if args.pack_count is None or args.pack_count < 2:
                raise SystemExit("--pack потребує --pack-count 2 або більше")
            amount = minor(args.pack, currency)
            provider, price_ref, product_ref = await publish(publishing.offer_spec(
                code=PACK_CODE, offer_type="pack", display_name=args.pack_name,
                display_name_i18n={}, amount_minor=amount, currency=currency,
            ))
            await commerce_service.upsert_offer(db, code=PACK_CODE, values={
                "offer_type": "pack", "active": True,
                "display_name": args.pack_name, "description": "",
                "provider": provider, "provider_price_ref": price_ref,
                "provider_product_ref": product_ref,
                "currency": currency, "display_amount_minor": amount,
                # Одне число на обидві величини: пакет — це набір разових.
                "audit_credits": args.pack_count, "presence_credits": args.pack_count,
                "promo_eligible": True, "sort_order": 2,
                "display_name_i18n": {}, "description_i18n": {},
            })
        if args.monthly is not None:
            rights = {
                "sites_limit": args.monthly_sites,
                "report_download": True,
                # Повні перевірки місячного плану необмежені за означенням.
                "audits_per_period": None,
                "max_pages_per_audit": args.monthly_pages,
                "presence_per_period": args.monthly_presence,
            }
            problems = billing_entitlements.validate(rights)
            if problems:
                raise SystemExit("права тарифу: " + "; ".join(problems))
            amount = minor(args.monthly, currency)
            provider, price_ref, product_ref = await publish(publishing.plan_spec(
                code=PLAN_CODE, name=args.monthly_name, name_i18n={},
                interval="month", amount_minor=amount, currency=currency,
            ))
            await commerce_service.upsert_plan(
                db, code=PLAN_CODE, name=args.monthly_name, description="",
                name_i18n={}, description_i18n={}, is_public=True, sort_order=1,
                entitlement_values=rights,
                prices=[{
                    "provider": provider, "provider_price_id": price_ref,
                    "provider_product_ref": product_ref,
                    "currency": currency, "interval": "month",
                    "display_amount_minor": amount,
                }],
            )
        await db.commit()
    print("збережено. Оновіть сторінку цін — числа зʼявляться без перезбирання.\n")
    await show()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--single", help="ціна разової перевірки, напр. 19 або 19.00")
    parser.add_argument("--pack", help="ціна пакета цілком, напр. 149")
    parser.add_argument("--pack-count", type=int,
                        help="скільки перевірок у пакеті (від 2); стільки ж Presence")
    parser.add_argument("--monthly", help="ціна місячного плану")
    parser.add_argument("--monthly-presence", type=int, default=5,
                        help="перевірок Actual AI Presence на місяць")
    parser.add_argument("--monthly-sites", type=int, default=10,
                        help="ліміт сайтів місячного плану")
    parser.add_argument("--monthly-pages", type=int, default=50,
                        help="сторінок на аудит у місячному плані")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--single-name", default="Разова перевірка")
    parser.add_argument("--pack-name", default="Пакет перевірок")
    parser.add_argument("--monthly-name", default="Місячний план")
    parser.add_argument("--show", action="store_true", help="показати поточний каталог і вийти")
    parser.add_argument("--clear", action="store_true",
                        help="прибрати пропозиції й тариф, створені цим скриптом")
    args = parser.parse_args()

    if args.show:
        asyncio.run(show())
        return
    if args.clear:
        asyncio.run(clear())
        return
    if args.single is None and args.pack is None and args.monthly is None:
        parser.error("нічого не задано: додайте --single, --pack (з --pack-count) або --monthly")
    asyncio.run(apply(args))


if __name__ == "__main__":
    main()
