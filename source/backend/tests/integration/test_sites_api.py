"""Сайти через HTTP: володіння, ізоляція, незмінність ідентичності.

Головне тут — не CRUD, а те, що організації не бачать сайтів одна одної
й що `origin` не можна змінити після створення.
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import register as _register
from tests.integration.conftest import sign_in_as as _as


@pytest.mark.asyncio
async def test_a_site_needs_authentication(client):
    assert (await client.post("/v1/sites", json={"url": "example.com"})).status_code == 401
    assert (await client.get("/v1/sites")).status_code == 401


@pytest.mark.asyncio
async def test_creating_a_site_normalizes_the_address(client):
    await _register(client, "a@example.com")

    response = await client.post(
        "/v1/sites", json={"url": "HTTPS://Example.com/pricing?utm=1"}
    )

    assert response.status_code == 201
    assert response.json()["origin"] == "https://example.com"
    assert response.json()["display_name"] == "example.com"


@pytest.mark.asyncio
async def test_a_nonsense_address_is_refused_with_a_reason(client):
    await _register(client, "a@example.com")

    response = await client.post("/v1/sites", json={"url": "not a url at all"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_same_site_twice_is_a_conflict(client):
    await _register(client, "a@example.com")
    await client.post("/v1/sites", json={"url": "example.com"})

    second = await client.post("/v1/sites", json={"url": "https://example.com/"})

    assert second.status_code == 409


@pytest.mark.asyncio
async def test_http_and_https_are_two_sites(client):
    """Незручно навмисно: тихе злиття зробило б одну криву з двох історій."""
    await _register(client, "a@example.com")

    first = await client.post("/v1/sites", json={"url": "http://example.com"})
    second = await client.post("/v1/sites", json={"url": "https://example.com"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert len((await client.get("/v1/sites")).json()) == 2


@pytest.mark.asyncio
async def test_the_same_origin_in_two_organizations_is_two_sites(client):
    """Унікальність — у межах організації, а не глобальна.

    Інакше перший, хто додав example.com, забрав би його в усіх.
    """
    await _register(client, "a@example.com")
    first = await client.post("/v1/sites", json={"url": "example.com"})

    await _as(client, "b@example.com")
    second = await client.post("/v1/sites", json={"url": "example.com"})

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


@pytest.mark.asyncio
async def test_one_organization_does_not_see_the_sites_of_another(client):
    await _register(client, "a@example.com")
    await client.post("/v1/sites", json={"url": "secret.example.com"})

    await _as(client, "b@example.com")

    assert (await client.get("/v1/sites")).json() == []


@pytest.mark.asyncio
async def test_a_foreign_site_does_not_exist_for_the_asker(client):
    """404, а не 403: «доступ заборонено» підтвердило б, що ресурс є, і
    дало б спосіб перевіряти чужі ідентифікатори перебором."""
    await _register(client, "a@example.com")
    victim = (await client.post("/v1/sites", json={"url": "secret.example.com"})).json()

    await _as(client, "b@example.com")

    assert (await client.get(f"/v1/sites/{victim['id']}")).status_code == 404
    assert (await client.delete(f"/v1/sites/{victim['id']}")).status_code == 404
    assert (
        await client.patch(f"/v1/sites/{victim['id']}", json={"display_name": "чуже"})
    ).status_code == 404


@pytest.mark.asyncio
async def test_only_the_label_can_be_changed(client):
    """`origin` не редагується взагалі — його немає в схемі зміни.

    Дозволити зміну означало б переписати минуле: криву, зібрану для
    одного сайту, видати за криву іншого.
    """
    await _register(client, "a@example.com")
    site = (await client.post("/v1/sites", json={"url": "example.com"})).json()

    renamed = await client.patch(
        f"/v1/sites/{site['id']}",
        json={"display_name": "Головний сайт", "origin": "https://other.com"},
    )

    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Головний сайт"
    assert renamed.json()["origin"] == "https://example.com", "ідентичність незмінна"


@pytest.mark.asyncio
async def test_archiving_hides_the_site_but_keeps_it(client):
    await _register(client, "a@example.com")
    site = (await client.post("/v1/sites", json={"url": "example.com"})).json()

    assert (await client.delete(f"/v1/sites/{site['id']}")).status_code == 204
    assert (await client.get("/v1/sites")).json() == []

    with_archived = (await client.get("/v1/sites?include_archived=true")).json()
    assert len(with_archived) == 1
    assert with_archived[0]["archived_at"] is not None


@pytest.mark.asyncio
async def test_an_archived_origin_can_be_added_again(client):
    """Архів не має тримати адресу в заручниках.

    Наразі повторне додавання конфліктує з архівним записом — і це
    зафіксовано як відома поведінка, а не як задум: розблокувати адресу
    можна буде розархівуванням, коли воно з'явиться в інтерфейсі.
    """
    await _register(client, "a@example.com")
    site = (await client.post("/v1/sites", json={"url": "example.com"})).json()
    await client.delete(f"/v1/sites/{site['id']}")

    again = await client.post("/v1/sites", json={"url": "example.com"})

    assert again.status_code == 409


@pytest.mark.asyncio
async def test_a_fresh_site_has_not_resolved_anywhere_yet(client):
    """`resolved_origin` заповнює воркер після першого аудиту.

    До того ми не знаємо, куди адреса веде, і не вигадуємо.
    """
    await _register(client, "a@example.com")

    body = (await client.post("/v1/sites", json={"url": "example.com"})).json()

    assert body["resolved_origin"] is None
    assert body["redirects_elsewhere"] is False
