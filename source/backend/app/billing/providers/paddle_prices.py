"""Публікація прайсів у Paddle: продукт і ціна за нашим каталогом.

Paddle тримає ціну як окремий обʼєкт (`pri_…`) при продукті (`pro_…`).
Зміну СУМИ ми робимо на місці (`PATCH /prices/{id}`, поле `unit_price`):
ідентифікатор лишається тим самим, і посилання в наших покупках не
старіють. Новий прайс потрібен, коли на місці змінити не можна: старого
прайса в цьому оточенні немає (перший раз або перехід між пісочницею й
бойовим), змінився період або змінилася ВАЛЮТА. Останні дві — не наша
обережність: `billing_cycle` Paddle не редагує взагалі, а зміна валюти
чинного прайса зачіпає підписки, відкриті в старій валюті, і ціна цього
рішення непередбачувана. Новий прайс тут коштує один зайвий `pri_…`.

Три речі, яких тут не буває: обʼєкти Paddle не архівуються (старий
прайс іншого оточення нічому не заважає), сума не читається з Paddle
як джерело (джерело — кабінет), і помилка провайдера не ковтається —
вона зупиняє збереження ціни.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.billing.providers.paddle import (
    NAME,
    PaddleNotConfigured,
    _base_url,
)
from app.billing.publishing import PriceSpec, PublishedPrice, PublishFailed
from app.core import runtime_config as runtime

# Категорія податку Paddle для всіх трьох продуктів: Crawldy — SaaS, і
# разова перевірка, і пакет, і підписка продають доступ до того самого
# сервісу. Змінити можна в самому Paddle — ми її при оновленні не чіпаємо.
TAX_CATEGORY = "saas"


def _reason(response: httpx.Response) -> str:
    """Причина відмови словами Paddle: його ж `code` і `detail`, без тіла.

    Це службовий екран, і тут докладність корисна: «forbidden» саме по собі
    не каже, що робити, а «not authorized to create product» каже. У тіло
    відповіді Paddle кладе ще й `request_id` та наші дані — вони назовні не
    йдуть. Каса клієнта користується вужчим `_safe_error` адаптера: там
    зайве слово провайдера нікому не допомагає.
    """
    code, detail = "", ""
    try:
        error = response.json().get("error") or {}
        code = str(error.get("code") or "")
        detail = str(error.get("detail") or "")
    except ValueError:  # pragma: no cover — тіло помилки не JSON
        pass
    if code and detail:
        return f"HTTP {response.status_code}, {code}: {detail}"
    if code:
        return f"HTTP {response.status_code}, {code}"
    return f"HTTP {response.status_code}"


# Що саме треба увімкнути в Paddle, коли ключ читає, але не пише. Ключ із
# правом лише на читання проходить перевірку зʼєднання (вона читає перелік
# типів подій) і падає рівно на першій публікації — тож без цієї підказки
# людина шукала б проблему в ціні, а не в дозволах ключа.
_WRITE_PERMISSION_HINT = (
    "ключ API має дозволяти запис. У Paddle → Developer tools → Authentication "
    "створіть ключ із правами product.write і price.write (кожне включає "
    "читання) і збережіть його на сторінці «Платіжний провайдер»"
)


def _is_ref(value: str | None, prefix: str) -> bool:
    return bool(value) and str(value).startswith(prefix)


def _published(data: dict[str, Any]) -> PublishedPrice:
    unit = data.get("unit_price") or {}
    cycle = data.get("billing_cycle") or {}
    return PublishedPrice(
        provider=NAME,
        product_ref=str(data.get("product_id") or ""),
        price_ref=str(data["id"]),
        amount_minor=int(str(unit.get("amount") or "0")),
        currency=str(unit.get("currency_code") or ""),
        interval=str(cycle["interval"]) if cycle.get("interval") else None,
        status=str(data.get("status") or ""),
    )


def _same_shape(published: PublishedPrice, spec: PriceSpec) -> bool:
    """Чи можна змінити цей прайс на місці: період і валюта ті самі."""
    return published.interval == spec.interval and published.currency == spec.currency


def _price_body(spec: PriceSpec, product_ref: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "description": spec.description,
        "name": spec.name,
        "product_id": product_ref,
        "unit_price": {"amount": str(spec.amount_minor), "currency_code": spec.currency},
        # Одна позиція на касу: кількість обирає не покупець, а пропозиція
        # (пакет — це один товар на N перевірок, а не N товарів).
        "quantity": {"minimum": 1, "maximum": 1},
        "tax_mode": "account_setting",
    }
    if spec.interval:
        body["billing_cycle"] = {"interval": spec.interval, "frequency": 1}
    return body


def _price_patch(spec: PriceSpec) -> dict[str, Any]:
    return {
        "description": spec.description,
        "name": spec.name,
        "unit_price": {"amount": str(spec.amount_minor), "currency_code": spec.currency},
        "status": "active",
    }


class PaddlePricePublisher:
    name = NAME

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # Транспорт підміняють тести; у продукті — мережа.
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        key = runtime.get("paddle_api_key")
        if not key:
            raise PublishFailed("not_configured", "немає ключа API Paddle")
        try:
            base = _base_url()
        except PaddleNotConfigured as exc:
            raise PublishFailed("inconsistent", str(exc)) from exc
        return httpx.AsyncClient(
            base_url=base,
            headers={"Authorization": f"Bearer {key}"},
            timeout=runtime.get_float("paddle_timeout_s"),
            transport=self._transport,
        )

    async def _request(
        self, client: httpx.AsyncClient, method: str, path: str,
        *, json: dict[str, Any] | None = None, missing_ok: bool = False,
    ) -> dict[str, Any] | None:
        try:
            response = await client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise PublishFailed("network_error", type(exc).__name__) from exc
        if response.status_code == 404 and missing_ok:
            return None
        if response.status_code == 401:
            raise PublishFailed("unauthorized", _reason(response))
        if response.status_code == 403:
            # 403 — не «ключ не той», а «цьому ключу не можна». Різниця
            # практична: перший міняють, другому додають права.
            raise PublishFailed("forbidden", f"{_reason(response)}. {_WRITE_PERMISSION_HINT}")
        if response.status_code >= 400:
            raise PublishFailed("http_error", _reason(response))
        try:
            data = response.json().get("data")
        except ValueError as exc:
            raise PublishFailed("http_error", "Paddle відповів не JSON") from exc
        if not isinstance(data, dict):
            raise PublishFailed("http_error", "Paddle відповів без data")
        return data

    async def publish(
        self, spec: PriceSpec, *, price_ref: str | None, product_ref: str | None
    ) -> PublishedPrice:
        async with self._client() as client:
            existing = None
            if _is_ref(price_ref, "pri_"):
                existing = await self._request(
                    client, "GET", f"/prices/{price_ref}", missing_ok=True
                )
            reusable = existing is not None and _same_shape(_published(existing), spec)
            if reusable:
                data = await self._request(
                    client, "PATCH", f"/prices/{price_ref}", json=_price_patch(spec)
                )
                assert data is not None
                return _published(data)

            product = None
            candidate = product_ref if _is_ref(product_ref, "pro_") else None
            if candidate is None and existing is not None:
                candidate = str(existing.get("product_id") or "") or None
            if candidate is not None:
                found = await self._request(
                    client, "GET", f"/products/{candidate}", missing_ok=True
                )
                product = candidate if found is not None else None
            if product is None:
                created = await self._request(
                    client, "POST", "/products",
                    json={
                        "name": spec.name,
                        "tax_category": TAX_CATEGORY,
                        "description": spec.description,
                    },
                )
                assert created is not None
                product = str(created["id"])
            data = await self._request(
                client, "POST", "/prices", json=_price_body(spec, product)
            )
            assert data is not None
            return _published(data)

    async def read(self, price_ref: str) -> PublishedPrice | None:
        if not _is_ref(price_ref, "pri_"):
            return None
        async with self._client() as client:
            data = await self._request(client, "GET", f"/prices/{price_ref}", missing_ok=True)
        return _published(data) if data is not None else None


__all__ = ["TAX_CATEGORY", "PaddlePricePublisher"]
