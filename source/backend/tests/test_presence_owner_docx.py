"""Загальний документ присутності: шість мов, і жодного слова понад доказ.

Перевіряється РЕНДЕР, а не словник — той самий урок, що й у решти
звітності: ключ, якого бракує всім локалям одразу, проходить будь-яке
порівняння словників і випливає лише в згенерованому документі.
"""

from __future__ import annotations

import re
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from app.report.presence_docx import filename_for as technical_filename
from app.report.presence_docx import render_presence_docx
from app.report.presence_owner_docx import (
    _STRINGS,
    filename_for,
    render_presence_owner_docx,
)

LOCALES = ("en", "uk", "de", "es", "fr", "ru")

RAW_KEY = re.compile(r"\b[a-z_]{3,}\.[a-z_.]{3,}\b")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")

# Маркери англійського фолбека: у de/es/fr/ru їх бути не сміє.
EN_MARKERS = ("answers named your brand", "What we asked", "Who we asked")

# Слова технічного документа. У загальному вони не мають зʼявлятися
# ніде: він адресований власнику, і саме цим відрізняється від сусіда.
# Слово «API» сюди не входить свідомо: воно живе в офіційних назвах
# провайдерів («ChatGPT / OpenAI API»), і саме ці назви кажуть правду про
# те, що ми міряли. Замінити їх на назви застосунків для людей означало б
# приписати вимірюванню чужу поверхню — рівно те, що заперечує блок
# застережень.
JARGON = (
    "denominator", "numerator", "prompt", "unbranded", "branded",
    "mention_presence", "citation_presence", "gpt-", "claude-", "p0-",
)


def _metric(numerator: int, denominator: int, rate: float | None = None) -> dict[str, Any]:
    return {
        "numerator": numerator, "denominator": denominator,
        "rate": rate, "unavailable": 0,
    }


def _combined(mention: tuple[int, int, float | None],
              citation: tuple[int, int, float | None]) -> dict[str, Any]:
    return {
        "mention_presence": _metric(*mention),
        "citation_presence": _metric(*citation),
    }


def _mode(providers: dict[str, tuple[int, int]],
          mention: tuple[int, int, float | None],
          citation: tuple[int, int, float | None]) -> dict[str, Any]:
    return {
        "per_provider": {
            name: {
                "mention_presence": _metric(hits, denom),
                "citation_presence": _metric(min(hits, 1), denom),
            }
            for name, (hits, denom) in providers.items()
        },
        "combined": _combined(mention, citation),
    }


def _scenario(kind: str) -> dict[str, Any]:
    """Стани, що справді трапляються: повний, без цитат, без згадок, порожній."""
    providers = {"anthropic": (2, 6), "openai": (1, 6),
                 "perplexity": (0, 6), "google": (1, 6)}
    deliverable: bool | None = True
    if kind == "full":
        # 24 спостереження — вище за поріг двигуна, тож частка є.
        modes = {
            "natural": _mode(providers, (4, 24, 0.17), (2, 24, 0.08)),
            "explicit": _mode(providers, (6, 24, 0.25), (3, 24, 0.13)),
        }
    elif kind == "few":
        # Нижче порога: двигун частки не порахував, документ її не вигадує.
        modes = {"natural": _mode(providers, (1, 6, None), (0, 6, None))}
    elif kind == "no_mention":
        modes = {"natural": _mode(providers, (0, 24, 0.0), (0, 24, 0.0))}
    else:  # empty: жодного придатного спостереження
        modes = {
            "natural": _mode(
                {name: (0, 0) for name in providers}, (0, 0, None), (0, 0, None)
            )
        }
        deliverable = False
    return {
        "run": {
            "url": "https://example.com", "brand": "Acme Dental",
            "status": "completed",
            "created_at": datetime(2026, 9, 1, tzinfo=UTC),
            "finished_at": datetime(2026, 9, 1, 12, 30, tzinfo=UTC),
            "observations_total": 24, "observations_ok": 24,
            "deliverable": deliverable, "prompt_set_version": "p0-1:en",
            "languages": ["en"],
        },
        "metrics": {
            "providers": ["anthropic", "google", "openai", "perplexity"],
            "modes": modes,
            "observed_domains": [
                {"domain": "clinic.example", "citations": 4},
                {"domain": "reviews.example", "citations": 2},
            ],
        },
        "coverage": {
            "prompts_declared": 12, "observations_total": 24,
            "observations_ok": 24,
        },
        "observations": [
            {"provider": "openai", "model": "gpt-5.1", "mode": "natural",
             "prompt_text": "Best clinics in town?", "status": "ok",
             "searched": True, "brand_mentioned": True,
             "domain_cited": False, "answer_excerpt": "Acme Dental is..."},
        ],
    }


def _text(payload: bytes) -> str:
    with zipfile.ZipFile(BytesIO(payload)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return re.sub(r"<[^>]+>", " ", xml)


def test_all_six_locales_share_the_same_string_keys() -> None:
    keys = {name: set(catalogue) for name, catalogue in _STRINGS.items()}

    assert set(keys) == set(LOCALES)
    for name, own in keys.items():
        assert own == keys["en"], f"{name}: розійшовся набір ключів"


def test_every_locale_renders_every_state_cleanly() -> None:
    for kind in ("full", "few", "no_mention", "empty"):
        for locale in LOCALES:
            payload = render_presence_owner_docx(lang=locale, **_scenario(kind))

            assert payload[:2] == b"PK"
            text = _text(payload)
            assert not RAW_KEY.search(text.replace("clinic.example", "")
                                      .replace("reviews.example", "")
                                      .replace("example.com", "")), (locale, kind)
            assert not PLACEHOLDER.search(text), (locale, kind)
            if locale not in ("en",):
                for marker in EN_MARKERS:
                    assert marker not in text, f"{locale}/{kind}: англійський фолбек"


def test_the_general_document_speaks_without_the_technical_vocabulary() -> None:
    """Два види відрізняються словами, а не лише обкладинкою."""
    for locale in LOCALES:
        text = _text(render_presence_owner_docx(lang=locale, **_scenario("full")))

        for word in JARGON:
            assert word not in text, f"{locale}: жаргон «{word}» у загальному звіті"
        # Фрагменти відповідей і самі запитання — предмет технічного
        # документа: власнику потрібен підсумок, а не журнал.
        assert "Best clinics in town?" not in text
        assert "Acme Dental is..." not in text


def test_a_percentage_appears_only_when_the_engine_calculated_one() -> None:
    """Поріг тримає двигун метрик; документ не має права його обходити."""
    enough = _text(render_presence_owner_docx(lang="uk", **_scenario("full")))
    too_few = _text(render_presence_owner_docx(lang="uk", **_scenario("few")))

    assert "17%" in enough
    assert "%" not in too_few
    assert _STRINGS["uk"]["too_few"][:30] in too_few


def test_no_usable_answers_never_reads_as_zero_presence() -> None:
    """«0 / 0» на обкладинці означало б протилежне до правди."""
    for locale in LOCALES:
        text = _text(render_presence_owner_docx(lang=locale, **_scenario("empty")))

        assert "0 / 0" not in text
        assert _STRINGS[locale]["state_none"][:40] in text
        # Прогін, за який не списано право, каже про це прямо.
        assert _STRINGS[locale]["deliverable_no"][:40] in text


def test_the_document_names_the_language_the_questions_were_asked_in() -> None:
    """Німецький документ може описувати англомовний прогін — і мусить сказати."""
    payload = render_presence_owner_docx(lang="de", **_scenario("full"))
    text = _text(payload)

    assert "English" in text
    assert _STRINGS["de"]["q_language"] in text


def test_zero_mentions_and_zero_citations_are_different_sentences() -> None:
    named_but_not_cited = _text(
        render_presence_owner_docx(lang="uk", **_scenario("few"))
    )
    not_named = _text(render_presence_owner_docx(lang="uk", **_scenario("no_mention")))

    assert _STRINGS["uk"]["state_mention_no_citation"][:40] in named_but_not_cited
    assert _STRINGS["uk"]["state_no_mention"][:40] in not_named


def test_both_kinds_accept_the_same_payload_so_the_numbers_cannot_diverge() -> None:
    """Один збирач даних на два документи — це властивість підпису."""
    payload = _scenario("full")

    general = render_presence_owner_docx(lang="uk", **payload)
    technical = render_presence_docx(lang="uk", **payload)

    assert general[:2] == b"PK" and technical[:2] == b"PK"
    assert general != technical


def test_filenames_name_the_site_and_the_kind() -> None:
    """У теці завантажень читач шукає домен, а не ідентифікатор прогону."""
    general = filename_for("https://example.com/", "uk")
    technical = technical_filename("https://example.com/", "uk")

    assert general == "ai-presence-example.com-general-uk.docx"
    assert technical == "ai-presence-example.com-technical-uk.docx"
    assert general != technical
