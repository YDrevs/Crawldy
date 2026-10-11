"""Word-експорт присутності: шість локалей, чотири стани, без сирих ключів.

Перевіряється РЕНДЕР, а не словник: урок паритету мов у звітах — ключ,
якого бракує всім локалям одразу, проходить будь-яке порівняння словників
і випливає лише в згенерованому документі.
"""

from __future__ import annotations

import re
import zipfile
from datetime import UTC, datetime
from io import BytesIO

from app.report.presence_docx import _STRINGS, PROVIDER_NAMES, render_presence_docx

LOCALES = ("en", "uk", "de", "es", "fr", "ru")

# Ключ каталогу, що втік у текст (слово.слово без пробілів), і
# нерозвʼязаний плейсхолдер {name}.
RAW_KEY = re.compile(r"\b[a-z_]{3,}\.[a-z_.]{3,}\b")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")

# Маркери англійського фолбека, яких не сміє бути в de/es/fr/ru.
EN_MARKERS = ("valid observations", "brand mentioned",
              "cited as a source", "searched the web")


def _metric(numerator: int, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "rate": None, "unavailable": 0}


def _mode_block(providers: dict[str, tuple[int, int]]) -> dict:
    return {
        "per_provider": {
            name: {
                "mention_presence": _metric(hits, denom),
                "citation_presence": _metric(min(hits, 1), denom),
            }
            for name, (hits, denom) in providers.items()
        },
        "combined": {},
    }


def _scenario(kind: str) -> dict:
    """Чотири стани: повний, частковий, непридатний, історичний (P0)."""
    full = {"anthropic": (2, 3), "openai": (1, 3),
            "perplexity": (0, 3), "google": (1, 3)}
    if kind == "full":
        modes = {"natural": _mode_block(full), "explicit": _mode_block(full)}
        deliverable = True
    elif kind == "partial":
        partial = dict(full)
        partial["google"] = (0, 0)  # провайдер без жодного спостереження
        modes = {"natural": _mode_block(partial),
                 "explicit": _mode_block(partial)}
        deliverable = True
    elif kind == "undeliverable":
        empty = {name: (0, 0) for name in full}
        modes = {"natural": _mode_block(empty)}
        deliverable = False
    else:  # historical: P0-рядки без режимів — лише natural
        modes = {"natural": _mode_block(
            {"anthropic": (1, 2), "openai": (1, 2), "perplexity": (0, 2)})}
        deliverable = True
    return {
        "run": {
            "url": "https://example.com", "brand": "Acme Dental",
            "status": "completed",
            "created_at": datetime(2026, 9, 1, tzinfo=UTC),
            "finished_at": datetime(2026, 9, 1, 12, 30, tzinfo=UTC),
            "observations_total": 240, "observations_ok": 237,
            "deliverable": deliverable, "prompt_set_version": "p0-1:en",
        },
        "metrics": {
            "modes": modes,
            "observed_domains": [{"domain": "clinic.example", "citations": 4}],
        },
        "coverage": {},
        "observations": [
            {"provider": "openai", "model": "gpt-5.1", "mode": "natural",
             "prompt_text": "Best clinics?", "status": "ok",
             "searched": True, "brand_mentioned": True,
             "domain_cited": False, "answer_excerpt": "Acme Dental is..."},
        ],
    }


def _docx_text(payload: bytes) -> str:
    with zipfile.ZipFile(BytesIO(payload)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return re.sub(r"<[^>]+>", " ", xml)


def test_all_six_locales_share_the_same_string_keys() -> None:
    keys = {name: set(cat) for name, cat in _STRINGS.items()}
    assert set(keys) == set(LOCALES)
    reference = keys["en"]
    for name, own in keys.items():
        assert own == reference, f"{name}: розійшовся набір ключів"


def test_every_locale_renders_every_scenario_cleanly() -> None:
    for kind in ("full", "partial", "undeliverable", "historical"):
        for locale in LOCALES:
            payload = render_presence_docx(lang=locale, **_scenario(kind))
            assert payload[:2] == b"PK"
            text = _docx_text(payload)
            # сирі ключі: дозволяємо лише домени/версії з фікстури
            leaked = [
                m for m in RAW_KEY.findall(text)
                if m not in ("example.com", "clinic.example")
                and not m.startswith("p0-1")
            ]
            assert not leaked, f"{locale}/{kind}: сирі ключі {leaked[:3]}"
            assert not PLACEHOLDER.findall(text), f"{locale}/{kind}"
            # знак незалежності присутній у кожному документі
            assert _STRINGS[locale]["marks"][:25] in text, f"{locale}/{kind}"


def test_non_english_exports_carry_no_english_fallback() -> None:
    for locale in ("de", "es", "fr", "ru"):
        text = _docx_text(render_presence_docx(lang=locale, **_scenario("full")))
        for marker in EN_MARKERS:
            assert marker not in text, f"{locale}: англійський фолбек: {marker}"


def test_provider_names_stay_official_in_every_locale() -> None:
    for locale in LOCALES:
        text = _docx_text(render_presence_docx(lang=locale, **_scenario("full")))
        for name in ("OpenAI", "Anthropic", "Perplexity", "Gemini"):
            assert name in text, f"{locale}: немає назви {name}"


def test_a_provider_without_observations_is_unavailable_not_zero() -> None:
    text = _docx_text(render_presence_docx(lang="de", **_scenario("partial")))
    assert _STRINGS["de"]["no_observations"][:30] in text
    # і жодного «0 з 0» поруч із назвою Gemini
    google_pos = text.find(PROVIDER_NAMES["google"])
    assert "0/0" not in text[google_pos:google_pos + 200]


def test_undeliverable_run_says_no_check_was_charged() -> None:
    for locale in LOCALES:
        text = _docx_text(
            render_presence_docx(lang=locale, **_scenario("undeliverable")))
        assert _STRINGS[locale]["deliverable_no"][:30] in text


def test_unknown_locale_falls_back_to_english() -> None:
    payload = render_presence_docx(lang="xx", **_scenario("full"))
    assert _STRINGS["en"]["coverage"] in _docx_text(payload)
