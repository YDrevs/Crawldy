"""Публікація каталогу у провайдера каси.

Два моменти, коли вона відбувається, і обидва — дії адміністратора:

1. **Збереження ціни** на закладці «Ціни»: прайс публікується ДО запису в
   базу, і відмова провайдера зупиняє збереження. Сайт не сміє показати
   суму, за якою каса не візьме гроші.
2. **Збереження провайдера** (інший провайдер, інше оточення, інший
   ключ): увесь каталог публікується наново. Тут відмова не зупиняє
   збереження налаштувань — людина мусить мати змогу виправити ключ, —
   але жоден запис, що не опублікувався, не переписується, і кабінет
   показує, що саме не вдалося.

У каталозі одна ціна на продукт. Провайдер — властивість запису, а не
частина його ідентичності: після зміни провайдера той самий запис несе
нового провайдера і новий прайс. Дублікат «на кожного провайдера свій
рядок» після повернення до попереднього відкривав би касу старою сумою.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import catalog
from app.billing.publishing import PriceSpec, PublishedPrice, PublishFailed
from app.billing.registry import publisher_for
from app.models.billing import Plan, PlanPrice
from app.models.commerce import CommercialOffer

_KIND_WORDS = {"single": "single check", "pack": "check pack"}

# Назва, яку покупець побачить у касі й у квитанції. Англійська й та сама
# для всіх шести мов сайту: у провайдера одна назва на прайс, а квитанція
# — комерційний документ, і німець не має отримувати український рядок.
# `display_name` каталогу для цього не годиться: публічна сторінка його не
# показує взагалі (у неї власні підписи), тобто це внутрішня мітка.
# Перекрити можна англійською назвою в каталозі — вона головніша за все.
_OFFER_NAMES = {"single": "Crawldy Full Audit", "pack": "Crawldy Audit Pack"}
_PLAN_NAMES = {"month": "Crawldy Monthly Plan", "year": "Crawldy Annual Plan"}


def _customer_name(default: str, i18n: dict[str, Any] | None, standard: str | None) -> str:
    chosen = str((i18n or {}).get("en") or "").strip() or standard or default
    return chosen.strip() or default


def offer_spec(
    *,
    code: str,
    offer_type: str,
    display_name: str,
    display_name_i18n: dict[str, Any] | None,
    amount_minor: int,
    currency: str,
) -> PriceSpec:
    return PriceSpec(
        code=code,
        name=_customer_name(display_name, display_name_i18n, _OFFER_NAMES.get(offer_type)),
        amount_minor=int(amount_minor),
        currency=currency.upper(),
        interval=None,
        description=f"Crawldy {_KIND_WORDS.get(offer_type, offer_type)} · {code}",
    )


def plan_spec(
    *,
    code: str,
    name: str,
    name_i18n: dict[str, Any] | None,
    interval: str,
    amount_minor: int,
    currency: str,
) -> PriceSpec:
    return PriceSpec(
        code=f"{code}_{interval}",
        name=_customer_name(name, name_i18n, _PLAN_NAMES.get(interval)),
        amount_minor=int(amount_minor),
        currency=currency.upper(),
        interval=interval,
        description=f"Crawldy plan · {code} · {interval}",
    )


def remembered(
    provider: str,
    *,
    refs: dict[str, Any] | None,
    row_provider: str | None = None,
    price_ref: str | None = None,
    product_ref: str | None = None,
) -> tuple[str | None, str | None]:
    """Що цей запис має В ЦЬОГО провайдера — прайс і продукт, або нічого.

    Джерело — мапа памʼяті по провайдерах; чинна привʼязка враховується
    теж, бо записи, створені до появи мапи, мають лише її.

    Прайс ІНШОГО провайдера тут не годиться: для цієї каси він нічого не
    означає. А памʼять саме тому й існує: без неї перемикання каси туди
    й назад створювало б у провайдера нові продукти щоразу.
    """
    known = (refs or {}).get(provider) or {}
    price = str(known.get("price") or "") or None
    product = str(known.get("product") or "") or None
    if price is None and row_provider == provider:
        price = price_ref or None
        product = product_ref or None
    return price, product


def with_ref(refs: dict[str, Any] | None, published: PublishedPrice) -> dict[str, Any]:
    """Мапа памʼяті з дописаним свіжим записом цього провайдера."""
    updated = dict(refs or {})
    updated[published.provider] = {
        "price": published.price_ref,
        "product": published.product_ref,
    }
    return updated


async def publish(
    spec: PriceSpec,
    *,
    provider: str | None = None,
    price_ref: str | None,
    product_ref: str | None,
) -> PublishedPrice:
    name = provider or catalog.current_provider()
    publisher = publisher_for(name)
    if publisher is None:
        raise PublishFailed("not_registered", f"провайдер {name} не зареєстрований")
    published = await publisher.publish(spec, price_ref=price_ref, product_ref=product_ref)
    problem = catalog.ref_format_problem(name, "price", published.price_ref)
    if problem:  # pragma: no cover — провайдер повернув не свій ідентифікатор
        raise PublishFailed("http_error", problem)
    return published


def _entry(
    kind: str, code: str, name: str, amount_minor: int | None, currency: str, **rest: Any
) -> dict[str, Any]:
    return {
        "kind": kind, "code": code, "name": name,
        "amount_minor": amount_minor, "currency": currency, **rest,
    }


async def republish_catalogue(db: AsyncSession) -> list[dict[str, Any]]:
    """Усі неархівовані пропозиції й ціни тарифів → чинний провайдер.

    Повертає стан кожного запису; збій публікації не кидається, а
    записується у відповідь (кабінет показує його людині), і запис, що не
    опублікувався, лишається як був — з попереднім провайдером.
    """
    provider = catalog.current_provider()
    report: list[dict[str, Any]] = []

    offers = (
        await db.execute(
            select(CommercialOffer)
            .where(CommercialOffer.archived_at.is_(None))
            .order_by(CommercialOffer.sort_order, CommercialOffer.code)
        )
    ).scalars().all()
    for offer in offers:
        name = offer.display_name
        if offer.display_amount_minor is None:
            report.append(_entry("offer", offer.code, name, None, offer.currency,
                                 outcome="no_price"))
            continue
        spec = offer_spec(
            code=offer.code, offer_type=offer.offer_type.value,
            display_name=offer.display_name, display_name_i18n=offer.display_name_i18n,
            amount_minor=offer.display_amount_minor, currency=offer.currency,
        )
        price_ref, product_ref = remembered(
            provider, refs=offer.provider_refs, row_provider=offer.provider,
            price_ref=offer.provider_price_ref, product_ref=offer.provider_product_ref,
        )
        try:
            published = await publish(
                spec, provider=provider, price_ref=price_ref, product_ref=product_ref
            )
        except PublishFailed as exc:
            report.append(_entry("offer", offer.code, name, offer.display_amount_minor,
                                 offer.currency, outcome=exc.outcome, detail=exc.detail))
            continue
        offer.provider = published.provider
        offer.provider_price_ref = published.price_ref
        offer.provider_product_ref = published.product_ref
        offer.provider_refs = with_ref(offer.provider_refs, published)
        report.append(_entry("offer", offer.code, name, published.amount_minor,
                             published.currency, outcome="published",
                             price_ref=published.price_ref))

    plans = (
        await db.execute(
            select(Plan).where(Plan.archived_at.is_(None)).order_by(Plan.sort_order, Plan.code)
        )
    ).scalars().all()
    for plan in plans:
        prices = (
            await db.execute(
                select(PlanPrice).where(PlanPrice.plan_id == plan.id).order_by(PlanPrice.interval)
            )
        ).scalars().all()
        name = plan.name
        for price in prices:
            code = f"{plan.code}_{price.interval}"
            if price.display_amount_minor is None:
                report.append(_entry("plan", code, name, None, price.currency,
                                     outcome="no_price"))
                continue
            spec = plan_spec(
                code=plan.code, name=plan.name, name_i18n=plan.name_i18n,
                interval=price.interval, amount_minor=price.display_amount_minor,
                currency=price.currency,
            )
            price_ref, product_ref = remembered(
                provider, refs=price.provider_refs, row_provider=price.provider,
                price_ref=price.provider_price_id, product_ref=price.provider_product_ref,
            )
            try:
                published = await publish(
                    spec, provider=provider, price_ref=price_ref, product_ref=product_ref
                )
            except PublishFailed as exc:
                report.append(_entry("plan", code, name, price.display_amount_minor,
                                     price.currency, outcome=exc.outcome, detail=exc.detail))
                continue
            price.provider = published.provider
            price.provider_price_id = published.price_ref
            price.provider_product_ref = published.product_ref
            price.provider_refs = with_ref(price.provider_refs, published)
            report.append(_entry("plan", code, name, published.amount_minor,
                                 published.currency, outcome="published",
                                 price_ref=published.price_ref))
    await db.flush()
    return report


async def catalogue_status(db: AsyncSession) -> list[dict[str, Any]]:
    """Що продається і чи опубліковано це в чинного провайдера — без мережі."""
    provider = catalog.current_provider()
    rows: list[dict[str, Any]] = []
    offers = (
        await db.execute(
            select(CommercialOffer)
            .where(CommercialOffer.archived_at.is_(None))
            .order_by(CommercialOffer.sort_order, CommercialOffer.code)
        )
    ).scalars().all()
    for offer in offers:
        published = offer.provider == provider and bool(offer.provider_price_ref)
        rows.append(_entry(
            "offer", offer.code, offer.display_name,
            offer.display_amount_minor, offer.currency, provider=offer.provider,
            price_ref=offer.provider_price_ref if published else "", published=published,
        ))
    plans = (
        await db.execute(
            select(Plan).where(Plan.archived_at.is_(None)).order_by(Plan.sort_order, Plan.code)
        )
    ).scalars().all()
    for plan in plans:
        prices = (
            await db.execute(
                select(PlanPrice).where(PlanPrice.plan_id == plan.id).order_by(PlanPrice.interval)
            )
        ).scalars().all()
        for price in prices:
            published = price.provider == provider and bool(price.provider_price_id)
            rows.append(_entry(
                "plan", f"{plan.code}_{price.interval}", plan.name,
                price.display_amount_minor, price.currency, provider=price.provider,
                price_ref=price.provider_price_id if published else "", published=published,
                interval=price.interval,
            ))
    return rows


async def verify_catalogue(db: AsyncSession) -> list[dict[str, Any]]:
    """Жива звірка: що провайдер має під нашими ідентифікаторами зараз.

    Читання, не запис: суму з провайдера ми не беремо за джерело, а лише
    порівнюємо з кабінетом. Розбіжність — хтось правив у провайдера
    руками; наступне збереження ціни її прибере.
    """
    provider = catalog.current_provider()
    publisher = publisher_for(provider)
    rows = await catalogue_status(db)
    for row in rows:
        if not row["published"] or publisher is None:
            row["provider_has"] = False
            row["matches"] = False
            continue
        try:
            found = await publisher.read(str(row["price_ref"]))
        except PublishFailed as exc:
            row["provider_has"] = False
            row["matches"] = False
            row["detail"] = f"{exc.outcome}: {exc.detail}"
            continue
        row["provider_has"] = found is not None and found.status == "active"
        row["matches"] = bool(
            found is not None
            and found.status == "active"
            and found.amount_minor == row["amount_minor"]
            and found.currency == row["currency"]
        )
        if found is not None:
            row["provider_amount_minor"] = found.amount_minor
            row["provider_currency"] = found.currency
    return rows


__all__ = [
    "catalogue_status",
    "offer_spec",
    "plan_spec",
    "publish",
    "remembered",
    "republish_catalogue",
    "verify_catalogue",
    "with_ref",
]
