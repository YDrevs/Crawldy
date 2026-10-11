"""Події платіжних провайдерів.

Другий роутер без `X-API-Key` — і, як `/r/{token}`, свідомо
параноїдальний. Автентифікація тут не наша: її робить підпис провайдера,
який перевіряє адаптер. Запит без дійсного підпису не доходить до
домену взагалі.

## Чому маршрут такий тонкий

Уся робота — в `application.billing.ingest`: журнал події, ідемпотентність
за `(provider, external_event_id)`, доменний перехід, повтор невдалих.
Маршрут лише дістає адаптер, віддає йому сирі байти й перекладає відмову
на код відповіді.

## Чому 200 на вже оброблену подію

Провайдери повторюють доставку, поки не отримають успіх. Повторна
доставка тієї самої події — нормальний стан, а не помилка: рядок уже є,
перехід уже стався, і відповідати помилкою означало б просити провайдера
надсилати її ще, вічно.

## Чому 200 на подію, якої ми не слухаємо

Провайдер надсилає те, на що його підписали, і не знає, які з подій ми
переклали на домен. Відмова змусила б його повторювати `subscription.*`
вічно; підтвердження закриває доставку, нічого при цьому не змінюючи.
Це не те саме, що невірний підпис, і код відповіді має їх розрізняти.

## Чому 500 на невдалу обробку

Навпаки: якщо подія прийнята, але доменний перехід не вдався, повторити
доставку **треба**. Мовчазний успіх тут — це рівно та тиша, у якій
оплата проходить, а доступу немає.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import SessionDep
from app.application import billing as billing_app
from app.billing.registry import InvalidWebhook, UnhandledEvent, provider_for

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

# Подія — не сторінка. Ні кешу, ні індексації, ні реферера.
PRIVATE_HEADERS = {
    "Cache-Control": "no-store, private",
    "X-Robots-Tag": "noindex, nofollow",
}


@router.post("/{provider}", status_code=status.HTTP_200_OK)
async def receive(provider: str, request: Request, session: SessionDep) -> Response:
    """Прийняти подію провайдера.

    Тіло читається сирими байтами: підпис рахується від них, і будь-яке
    перекодування — розбір у JSON і зворотна збірка — його ламає.
    """
    adapter = provider_for(provider)
    if adapter is None:
        # Невідомий провайдер відповідає так само, як невірний підпис:
        # перебором імен не має зʼясовуватися, кого ми підключили.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="подію відхилено")

    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        event = adapter.verify_webhook(headers=headers, body=body)
    except UnhandledEvent:
        # Підпис дійсний, подія не наша. 200 — щоб провайдер перестав
        # її повторювати: він не має способу дізнатися, на що ми
        # підписані, крім нашої відповіді.
        return Response(
            content=_json({"outcome": "ignored"}),
            media_type="application/json",
            headers=PRIVATE_HEADERS,
        )
    except InvalidWebhook as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="подію відхилено"
        ) from exc

    result = await billing_app.ingest(session, event)
    await session.commit()

    if result.outcome == "failed":
        # Провайдер має надіслати ще раз. Подія вже в журналі зі своєю
        # причиною, тож повтор не втратить нічого.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="подію не оброблено"
        )

    payload: dict[str, Any] = {"outcome": result.outcome}
    return Response(
        content=_json(payload),
        media_type="application/json",
        headers=PRIVATE_HEADERS,
    )


def _json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)
