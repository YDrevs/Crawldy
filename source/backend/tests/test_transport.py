"""Транспорт: що видно з відповіді й чого з неї не випливає.

Найважливіші випадки тут — не спрацювання, а межі. Ми бачимо ВІДПОВІДЬ,
а не сервер: «віддано без стиснення» і «сервер не вміє стискати» — різні
твердження, і друге з першого не випливає ніколи.
"""

from __future__ import annotations

import json

import pytest

from app.audit import snapshot, transport
from app.audit.checks.tech import SUBSTANTIAL_TEXT_BYTES, TransportCheck
from app.audit.extractor import extract
from app.audit.fetcher import FetchResult
from app.audit.transport import Coding, Compressibility
from tests.factories import context

SITE = "https://example.com"
HTML = "<html lang='en'><head><title>T</title></head><body><h1>H</h1><p>text</p></body></html>"


def page(url: str = f"{SITE}/", *, content_type: str = "text/html",
         encoding: str | None = None, length: str | None = None,
         chunked: bool = False, protocol: str = "HTTP/2",
         advertised: str = "gzip, deflate", decoded: int = 60_000):
    headers: dict[str, str] = {}
    if encoding:
        headers["content-encoding"] = encoding
    if length is not None:
        headers["content-length"] = length
    if chunked:
        headers["transfer-encoding"] = "chunked"
    signals = extract(
        FetchResult(url=url, final_url=url, status_code=200, content_type=content_type,
                    text=HTML, body_bytes=decoded, elapsed_ms=10, headers=headers,
                    http_version=protocol, accept_encoding=advertised),
        origin=SITE,
    )
    return signals


def finding(ctx, variant: str):
    return next(
        (i for i in TransportCheck().run(ctx) if i.issue_key.endswith(variant)), None
    )


# ── 1–5. Стиснення ────────────────────────────────────────────────────────


@pytest.mark.parametrize("coding", ["gzip", "br", "zstd", "deflate"])
def test_a_compressed_text_response_is_not_a_finding(coding):
    """1–3. gzip, Brotli, Zstandard — усі робочі, і жоден не привід.

    Радити заміну gzip на щось інше без вимірювання було б порожньою
    порадою: стиснення вже є.
    """
    ctx = context(page(encoding=coding))
    assert transport.analyse(ctx).unencoded == []
    assert finding(ctx, "uncompressed") is None


def test_a_substantial_text_response_without_encoding_is_reported():
    """4. Ми просили стиснення, а відповідь прийшла без нього."""
    ctx = context(page(length="60000"))
    found = transport.analyse(ctx).unencoded
    assert len(found) == 1 and found[0].coding is Coding.IDENTITY
    assert finding(ctx, "uncompressed") is not None


def test_a_tiny_uncompressed_response_is_below_the_noise_floor():
    """5. Дрібний текст без стиснення нікому не шкодить.

    Поріг — наш запобіжник від шуму, а не вимога пошуку.
    """
    ctx = context(page(decoded=SUBSTANTIAL_TEXT_BYTES - 1, length="1000"))
    assert transport.analyse(ctx).unencoded  # факт лишається фактом
    assert finding(ctx, "uncompressed") is None  # але знахідкою не стає


@pytest.mark.parametrize("content_type", [
    "image/jpeg", "image/webp", "image/avif", "font/woff2",
    "application/zip", "video/mp4", "audio/mpeg", "application/pdf",
])
def test_already_compressed_formats_are_never_flagged(content_type):
    """6–7. Стиснути вже стиснене — марна робота, і радити її не треба."""
    ctx = context(page(content_type=content_type))
    assert transport.analyse(ctx).unencoded == []


@pytest.mark.parametrize("content_type", [
    "application/json", "application/xml", "image/svg+xml", "text/css",
    "application/javascript", "text/plain",
])
def test_textual_formats_are_recognised_as_compressible(content_type):
    """8. Текстові представлення, а не лише HTML."""
    assert transport.compressibility_of(content_type) is Compressibility.TEXTUAL


def test_an_unknown_content_type_stays_unknown():
    """9. Невідомий тип не судимо: обережність дешевша за хибну пораду."""
    assert transport.compressibility_of("application/x-made-up") is Compressibility.UNKNOWN
    assert transport.compressibility_of(None) is Compressibility.UNKNOWN
    ctx = context(page(content_type="application/x-made-up"))
    assert transport.analyse(ctx).unencoded == []


def test_without_advertising_a_coding_we_conclude_nothing():
    """10. Найважливіша межа стиснення.

    Сервер, який уміє лише Brotli, віддасть identity клієнту, який
    Brotli не просив. Не питали — не стверджуємо.
    """
    ctx = context(page(advertised=""))
    assert transport.analyse(ctx).unencoded == []
    assert finding(ctx, "uncompressed") is None


# ── 11–13. Розміри ────────────────────────────────────────────────────────


def test_decoded_size_is_never_mistaken_for_transfer_size():
    """11. httpx розпаковує сам, тож довжина тіла — це РОЗПАКОВАНИЙ розмір.

    `Content-Length` при цьому описує те, що справді їхало. Ділити одне
    на одне без розуміння семантики — саме те, чого робити не можна.
    """
    observation = transport.observe(page(encoding="gzip", length="9000", decoded=60_000))
    assert observation.encoded_bytes == 9000
    assert observation.decoded_bytes == 60_000


def test_a_missing_content_length_yields_no_invented_number():
    """12. Немає заголовка — немає числа, а не нуль і не здогад."""
    assert transport.observe(page()).encoded_bytes is None


def test_chunked_transfer_is_handled_honestly():
    """13. При `chunked` `Content-Length` означає інше або відсутній."""
    observation = transport.observe(page(chunked=True, length="123"))
    assert observation.encoded_bytes is None


def test_the_finding_never_promises_measured_savings():
    """13b. Скільки зекономить стиснення, ми не міряли — і не кажемо."""
    evidence = finding(context(page(length="60000")), "uncompressed").evidence
    assert evidence["savings_measured"] is False


# ── 14–19. Протокол ───────────────────────────────────────────────────────


def test_the_observed_protocol_is_preserved_verbatim():
    """14–15. HTTP/2 і HTTP/1.1 зберігаються такими, як були."""
    assert transport.observe(page(protocol="HTTP/2")).protocol == "HTTP/2"
    assert transport.observe(page(protocol="HTTP/1.1")).protocol == "HTTP/1.1"


def test_our_client_is_actually_capable_of_http2():
    """16. Без цього знахідка про HTTP/1.1 не мала б права існувати.

    Вона була б твердженням про нашу вимірювальну установку, а не про
    сайт. Тому здатність перевіряється явно, а не припускається.
    """
    assert transport.client_offers_http2() is True


def test_http1_is_reported_only_because_we_offered_more():
    """17. Спостереження, а не вирок серверу.

    Умова — можливості клієнта, а не контраст усередині аудиту: сайт,
    який усюди віддає HTTP/1.1, інакше ніколи б не потрапив у знахідку,
    хоча саме він і є випадком.
    """
    ctx = context(page(protocol="HTTP/1.1", encoding="gzip"))
    issue = finding(ctx, "http1")
    assert issue is not None
    assert issue.evidence["client_offers_http2"] is True


def test_no_finding_when_the_client_cannot_offer_http2(monkeypatch):
    """18. Якби наш клієнт не вмів HTTP/2, знахідка була б неправдою."""
    monkeypatch.setattr(transport, "client_offers_http2", lambda: False)
    ctx = context(page(protocol="HTTP/1.1", encoding="gzip"))
    assert finding(ctx, "http1") is None


def test_http3_absence_is_never_reported():
    """19. Наш стек HTTP/3 не погоджує, тож його відсутність — невідомість."""
    ctx = context(page(protocol="HTTP/2", encoding="gzip"))
    assert transport.analyse(ctx).coverage()["client_offers_http3"] is False
    assert list(TransportCheck().run(ctx)) == []


def test_no_wording_demands_http3_or_brotli():
    """19b. Ані HTTP/3, ані Brotli не є обовʼязковими."""
    from app.audit.i18n import CATALOGS

    offenders = []
    for locale, catalog in CATALOGS.items():
        for key, entry in catalog.items():
            if not key.startswith("tech.transport"):
                continue
            for field, text in entry.items():
                if field == "recommendation" and "brotli" in text.lower():
                    # Згадка дозволена лише як «не потрібно переходити».
                    if not any(w in text.lower() for w in
                               ("не потрібно", "no need", "nicht nötig", "no hace falta",
                                "nul besoin", "не нужно")):
                        offenders.append(f"{locale}/{key}")
                if "http/3" in text.lower() and field == "recommendation":
                    offenders.append(f"{locale}/{key}: http/3 у пораді")
    assert not offenders, offenders


# ── 20–27. Знімки, агрегація, мова, скоринг ───────────────────────────────


def test_an_old_snapshot_without_transport_fields_means_unknown():
    """20. Порожнє поле — «не знаємо», а не «HTTP/1.1» і не «без стиснення»."""
    import pathlib

    old = next(pathlib.Path("benchmark/snapshots").glob("*.json"))
    ctx = snapshot.load(json.loads(old.read_text(encoding="utf-8")))
    analysis = transport.analyse(ctx)
    assert analysis.known == 0 and analysis.unknown > 0
    assert all(o.protocol is None for o in analysis.observations)
    assert list(TransportCheck().run(ctx)) == []


def test_a_fresh_snapshot_round_trips_the_transport_facts():
    """21. Перерахунок без мережі має давати той самий висновок."""
    ctx = context(page(protocol="HTTP/1.1", length="60000"))
    back = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))
    assert back.pages[0].http_version == "HTTP/1.1"
    assert back.pages[0].accept_encoding == "gzip, deflate"
    assert [i.title for i in TransportCheck().run(back)] == [
        i.title for i in TransportCheck().run(ctx)
    ]


def test_findings_are_grouped_with_accurate_totals():
    """22. Одна знахідка на весь сайт, а не по одній на сторінку."""
    pages = [page(f"{SITE}/p{i}", length="60000") for i in range(12)]
    issue = finding(context(*pages), "uncompressed")
    assert issue.evidence["responses_total"] == 12
    assert len(issue.evidence["responses"]) == 8
    assert issue.evidence["responses_truncated"] is True
    assert len(list(TransportCheck().run(context(*pages)))) == 1


def test_the_coverage_states_what_we_saw():
    """23. Розподіл протоколів і кодувань — поруч із висновком."""
    ctx = context(page(f"{SITE}/a", encoding="gzip"),
                  page(f"{SITE}/b", protocol="HTTP/1.1", encoding="gzip"))
    coverage = transport.analyse(ctx).coverage()
    assert coverage["protocols"] == {"HTTP/1.1": 1, "HTTP/2": 1}
    assert coverage["text_content_encodings"] == {"gzip": 2}


@pytest.mark.parametrize("code", ["en", "uk", "de", "es", "fr", "ru"])
def test_every_locale_carries_both_messages(code):
    """24. Жодного тихого відкоту в англійську."""
    from app.audit.i18n import CATALOGS, Locale

    catalog = CATALOGS[Locale(code)]
    for variant in ("uncompressed", "http1"):
        key = f"tech.transport.{variant}"
        assert key in catalog, f"{code}: бракує {key}"
        for field in ("title", "description", "recommendation", "consequence"):
            assert catalog[key][field].strip()


def test_no_wording_claims_ranking_loss_or_server_incapability():
    """25. Ми не міряли позицій і не бачили сервера — лише відповідь."""
    from app.audit.i18n import CATALOGS

    banned = ("ranking", "rank ", "penalty", "penalis", "penaliz", "позиці",
              "штраф", "ранжув", "Rangfolge", "posicionamiento", "classement",
              "ранжир", "does not support", "не підтримує", "не поддерживает")
    offenders = [
        f"{locale}/{key}: {word}"
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        if key.startswith("tech.transport")
        for text in entry.values()
        for word in banned
        if word.lower() in text.lower()
    ]
    assert not offenders, offenders


def test_the_finding_reaches_the_report_with_its_evidence():
    """26. Доказ мусить пережити шлях до звіту."""
    from app.audit import i18n as audit_i18n
    from app.audit.orchestrator import rescore
    from app.report.builder import build_report
    from app.report.source import source_from_outcome

    ctx = context(page(length="60000"))
    doc = build_report(source_from_outcome(rescore(ctx)), audit_i18n.Locale("uk"))
    hits = [r for r in doc.recommendations if r.issue_key.startswith("tech.transport")]
    assert hits
    assert hits[0].evidence["responses"][0]["content_encoding"] == "identity"
    assert hits[0].action and hits[0].consequence


def test_the_new_capability_moves_no_score_on_the_frozen_corpus():
    """27. Здатність бачити більше не рухає бали, зняті раніше."""
    import pathlib

    from app.audit import scoring
    from app.audit.checks import all_checks

    moved = []
    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json")):
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        every = [i for c in all_checks() for i in c.run(ctx)]
        without = [i for i in every if i.code != "tech.transport"]
        if scoring.overall_raw(every, set()) != scoring.overall_raw(without, set()):
            moved.append(path.stem)
    assert not moved, moved
