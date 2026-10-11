"""Знаменник доступності: скільки перевірок Lighthouse справді зробив.

Бал категорії — середнє по ЗАСТОСОВНИХ перевірках, тож без їх кількості
він не читається. Ці тести тримають межу між двома різними питаннями:
«скільки Lighthouse перевірив і скільки з того впало» (лічильники) і
«про що з цього ми розповідаємо клієнту» (`accessibility_failures`).
"""

import copy
import json
from collections.abc import Callable
from typing import Any

import pytest

from app.audit.performance import psi as psi_module
from app.audit.performance.psi import _A11Y_NOISE, _parse_accessibility
from app.audit.types import PerformanceResult, Strategy


def _result() -> PerformanceResult:
    return PerformanceResult(provider="psi", strategy=Strategy.MOBILE, url="https://e.com/")

def _payload(score: float, audits: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Відповідь PSI у тій формі, у якій її віддає Google.

    `auditRefs` живуть у категорії, самі перевірки — в `audits` поруч із
    перевірками швидкості. Саме тому парсер звіряється з категорією.
    """
    return {
        "lighthouseResult": {
            "categories": {
                "accessibility": {
                    "score": score,
                    "auditRefs": [{"id": key} for key in audits],
                }
            },
            "audits": audits,
        }
    }

def _binary(score: float, title: str = "") -> dict[str, Any]:
    return {"score": score, "scoreDisplayMode": "binary", "title": title}

def _assert_unmeasured(result: PerformanceResult) -> None:
    """Невиміряно — це ВСІ поля доступності в стані за замовчуванням.

    Частково заповнений результат гірший за порожній: бал без лічильників
    чи лічильники без бала однаково читаються як вимір.
    """
    assert result.accessibility_score is None
    assert result.accessibility_failures == []
    assert result.accessibility_failures_all == []
    assert result.accessibility_audits_total is None
    assert result.accessibility_applicable is None
    assert result.accessibility_passed is None
    assert result.accessibility_failed is None

def test_applicable_splits_into_passed_and_failed() -> None:
    result = _result()
    _parse_accessibility(
        _payload(0.5, {"button-name": _binary(0), "link-name": _binary(1)}), result
    )
    assert result.accessibility_audits_total == 2
    assert result.accessibility_applicable == 2
    assert result.accessibility_passed == 1
    assert result.accessibility_failed == 1

def test_not_applicable_manual_and_informative_leave_the_denominator() -> None:
    """Три режими, у яких Lighthouse нічого не перевіряв.

    Вони не свідчать ані за сайт, ані проти нього. Якби вони входили в
    знаменник, сторінка виглядала б перевіреною там, де перевірка навіть
    не запускалась.
    """
    result = _result()
    _parse_accessibility(
        _payload(
            1.0,
            {
                "button-name": _binary(1),
                "video-caption": {"score": None, "scoreDisplayMode": "notApplicable"},
                "focus-traps": {"score": None, "scoreDisplayMode": "manual"},
                "tap-targets": {"score": 1, "scoreDisplayMode": "informative"},
            },
        ),
        result,
    )
    assert result.accessibility_audits_total == 4
    assert result.accessibility_applicable == 1
    assert result.accessibility_passed == 1
    assert result.accessibility_failed == 0

def test_a_noise_filtered_audit_still_counts_as_applicable_and_failed() -> None:
    """Фільтр шуму — рішення про ЗВІТ, а не про вимірювання.

    `image-alt` прибирається з клієнтського переліку, бо його вже
    повідомляє наш власний чек. Але Lighthouse його запустив і він
    впав — інакше знаменник описував би нашу редакційну політику, а не
    те, що сталося на сторінці.
    """
    assert "image-alt" in _A11Y_NOISE
    result = _result()
    _parse_accessibility(
        _payload(0.5, {"image-alt": _binary(0), "link-name": _binary(1)}), result
    )
    assert result.accessibility_applicable == 2
    assert result.accessibility_failed == 1
    assert result.accessibility_failures == []

def test_the_customer_facing_list_keeps_its_contents_and_order() -> None:
    """Перелік для клієнта не змінився ані складом, ані порядком."""
    result = _result()
    _parse_accessibility(
        _payload(
            0.2,
            {
                "button-name": _binary(0, "Buttons have no name"),
                "image-alt": _binary(0, "шум"),
                "link-name": _binary(0, "Links have no name"),
                "html-has-lang": _binary(0, "шум"),
            },
        ),
        result,
    )
    assert [f["id"] for f in result.accessibility_failures] == ["button-name", "link-name"]
    assert result.accessibility_failures[0]["title"] == "Buttons have no name"
    assert result.accessibility_failed == 4

def test_no_accessibility_category_leaves_every_counter_unset() -> None:
    """Немає даних — немає й нуля. Нуль тут був би твердженням."""
    result = _result()
    _parse_accessibility({"lighthouseResult": {"categories": {}}}, result)
    assert result.accessibility_score is None
    assert result.accessibility_audits_total is None
    assert result.accessibility_applicable is None
    assert result.accessibility_passed is None
    assert result.accessibility_failed is None

def test_a_reference_without_a_record_leaves_the_category_unmeasured() -> None:
    """Посилання є, самої перевірки у відповіді немає.

    Цей тест раніше вимагав зворотного: розрив рахувався в оголошені, мовчки
    не входив у застосовні, і категорія отримувала бал, який неможливо
    звірити з тим, з чого він складений. Категорія оголосила перевірку, а
    результату її немає — вірити такому балу не можна, тож невиміряна вся.
    """
    result = _result()
    payload = _payload(1.0, {"button-name": _binary(1)})
    payload["lighthouseResult"]["categories"]["accessibility"]["auditRefs"].append(
        {"id": "ghost-audit"}
    )
    _parse_accessibility(payload, result)
    _assert_unmeasured(result)

def test_performance_audits_never_enter_the_accessibility_denominator() -> None:
    """`audits` містить і швидкість. Знаменник береться з категорії."""
    result = _result()
    payload = _payload(1.0, {"button-name": _binary(1)})
    payload["lighthouseResult"]["audits"]["unminified-css"] = _binary(0)
    _parse_accessibility(payload, result)
    assert result.accessibility_audits_total == 1
    assert result.accessibility_applicable == 1
    assert result.accessibility_failed == 0

def test_a_snapshot_taken_before_the_counters_existed_does_not_testify() -> None:
    """Знімок, знятий до появи полів, не сміє свідчити нулем.

    Той самий клас, що й `hreflang_observed`: порожнеча в старому
    форматі описує НАС, а не сайт. `_load` мовчки відкидає незнайомі
    ключі, тож сумісність тримається саме на дефолті `None`.
    """
    from app.audit.snapshot import _load_performance

    stored = {
        "provider": "psi",
        "strategy": "mobile",
        "url": "https://e.com/",
        "accessibility_score": 37.0,
        "accessibility_failures": [{"id": "button-name", "title": "", "impact": ""}],
    }
    loaded = _load_performance(stored)
    assert loaded.accessibility_score == 37.0
    assert len(loaded.accessibility_failures) == 1
    assert loaded.accessibility_applicable is None
    assert loaded.accessibility_passed is None
    assert loaded.accessibility_failed is None
    assert loaded.accessibility_audits_total is None


def test_the_unfiltered_list_keeps_what_the_noise_filter_removes() -> None:
    """Два переліки з одного проходу: клієнтові все, чекам без дублів.

    `accessibility_failures` тримає бал модуля й міняти його склад не
    можна. `accessibility_failures_all` — те, що бачить клієнт у знімку
    доступності: на 948 сайтах фільтр ховав щонайменше одну справжню
    ваду на 542 з них.
    """
    result = _result()
    _parse_accessibility(
        _payload(
            0.4,
            {
                "button-name": _binary(0, "No accessible name"),
                "image-alt": _binary(0, "No alt"),
                "link-name": _binary(1),
            },
        ),
        result,
    )
    assert [f["id"] for f in result.accessibility_failures] == ["button-name"]
    assert [f["id"] for f in result.accessibility_failures_all] == [
        "button-name",
        "image-alt",
    ]
    assert result.accessibility_failed == 2


def test_a_page_whose_only_failure_is_filtered_still_reports_it() -> None:
    """Найгірший випадок: усе придушено, і клієнт бачив «проблем немає»."""
    result = _result()
    _parse_accessibility(_payload(0.9, {"heading-order": _binary(0, "Skipped")}), result)
    assert result.accessibility_failures == []
    assert len(result.accessibility_failures_all) == 1
    assert result.accessibility_failed == 1


# ── E-08: один парсер на обидва провайдери ────────────────────────────
#
# Сайдкар Lighthouse віддає ту саму структуру, що й PSI, і до 9 вересня
# 2026 движок її мовчки викидав. Тести нижче тримають дві межі: придатна
# категорія дає ті самі поля незалежно від провайдера, а непридатна не
# перетворюється ні на нуль, ні на сто.


def test_a_zero_score_is_a_measurement_not_a_gap() -> None:
    """Нуль тут — вимір. Саме тому `None` не можна ним підміняти."""
    result = _result()
    _parse_accessibility(_payload(0, {"button-name": _binary(0)}), result)
    assert result.accessibility_score == 0.0
    assert result.accessibility_applicable == 1
    assert result.accessibility_failed == 1


def test_a_fractional_score_survives_the_existing_rounding() -> None:
    result = _result()
    _parse_accessibility(
        _payload(0.37, {"button-name": _binary(0), "link-name": _binary(1), "label": _binary(0)}),
        result,
    )
    assert result.accessibility_score == 37.0
    assert (result.accessibility_applicable, result.accessibility_passed) == (3, 1)


def test_a_perfect_score_is_a_hundred_and_lists_nothing() -> None:
    result = _result()
    _parse_accessibility(_payload(1, {"button-name": _binary(1)}), result)
    assert result.accessibility_score == 100.0
    assert result.accessibility_failures == []
    assert result.accessibility_failed == 0


def test_a_string_score_is_not_a_measurement() -> None:
    """`"n/a"` замість бала трапляється в урізаних відповідях.

    Раніше на ньому падав `float()`, і разом із доступністю зникало все
    вимірювання швидкості. Тепер напрям просто лишається невиміряним.
    """
    result = _result()
    _parse_accessibility(_payload("n/a", {"button-name": _binary(0)}), result)
    assert result.accessibility_score is None
    assert result.accessibility_applicable is None


def test_a_null_score_leaves_the_direction_unmeasured() -> None:
    result = _result()
    _parse_accessibility(_payload(None, {"button-name": _binary(0)}), result)
    assert result.accessibility_score is None
    assert result.accessibility_audits_total is None


def test_a_non_finite_score_from_the_decoder_is_not_a_measurement() -> None:
    """`json` за замовчуванням приймає `NaN` і `Infinity`.

    Обидва пройшли б `float()` і стали б балом, який неможливо ані
    показати, ані порівняти.
    """
    import json

    for literal in ("NaN", "Infinity", "-Infinity"):
        payload = json.loads(
            '{"lighthouseResult": {"categories": {"accessibility": '
            '{"score": ' + literal + ', "auditRefs": [{"id": "button-name"}]}},'
            ' "audits": {"button-name": {"score": 0, "scoreDisplayMode": "binary"}}}}'
        )
        result = _result()
        _parse_accessibility(payload, result)
        assert result.accessibility_score is None, literal
        assert result.accessibility_failed is None, literal


def test_a_boolean_score_is_not_silently_read_as_one() -> None:
    """`bool` — підклас `int`, тож `True` мовчки став би сотнею."""
    result = _result()
    _parse_accessibility(_payload(True, {"button-name": _binary(1)}), result)
    assert result.accessibility_score is None


def test_a_category_without_audit_refs_is_unmeasured_not_perfect() -> None:
    """Бал без переліку перевірок — це бал без знаменника.

    Раніше він давав «0 провалів з 0 застосовних», тобто знімок, який
    стверджує, що ми перевірили сторінку й нічого не знайшли.
    """
    result = _result()
    _parse_accessibility(
        {
            "lighthouseResult": {
                "categories": {"accessibility": {"score": 0.5}},
                "audits": {"button-name": _binary(0)},
            }
        },
        result,
    )
    assert result.accessibility_score is None
    assert result.accessibility_applicable is None


def test_malformed_audit_refs_do_not_crash_the_whole_measurement() -> None:
    result = _result()
    _parse_accessibility(
        {
            "lighthouseResult": {
                "categories": {"accessibility": {"score": 0.5, "auditRefs": "nope"}},
                "audits": {"button-name": _binary(0)},
            }
        },
        result,
    )
    assert result.accessibility_score is None


def test_a_single_unusable_audit_ref_does_not_discard_the_rest() -> None:
    """Зіпсований елемент переліку — не зіпсований перелік."""
    result = _result()
    payload = _payload(0.5, {"button-name": _binary(0), "link-name": _binary(1)})
    payload["lighthouseResult"]["categories"]["accessibility"]["auditRefs"].append("junk")
    _parse_accessibility(payload, result)
    assert result.accessibility_score == 50.0
    assert result.accessibility_applicable == 2


def test_a_category_without_audits_is_unmeasured() -> None:
    result = _result()
    _parse_accessibility(
        {
            "lighthouseResult": {
                "categories": {
                    "accessibility": {"score": 0.5, "auditRefs": [{"id": "button-name"}]}
                }
            }
        },
        result,
    )
    assert result.accessibility_score is None
    assert result.accessibility_audits_total is None


def test_a_referenced_record_that_is_not_an_object_leaves_the_category_unmeasured() -> None:
    """Раніше цей тест вимагав пропустити такий запис і порахувати решту."""
    result = _result()
    payload = _payload(0.5, {"button-name": _binary(0)})
    payload["lighthouseResult"]["audits"]["broken"] = "not an object"
    payload["lighthouseResult"]["categories"]["accessibility"]["auditRefs"].append(
        {"id": "broken"}
    )
    _parse_accessibility(payload, result)
    _assert_unmeasured(result)


def test_repeated_audit_references_do_not_double_anything() -> None:
    """Той самий `id` двічі в переліку — це одна перевірка, не дві."""
    result = _result()
    payload = _payload(0.5, {"button-name": _binary(0), "link-name": _binary(1)})
    payload["lighthouseResult"]["categories"]["accessibility"]["auditRefs"] += [
        {"id": "button-name"},
        {"id": "button-name"},
    ]
    _parse_accessibility(payload, result)
    assert result.accessibility_audits_total == 2
    assert result.accessibility_applicable == 2
    assert [f["id"] for f in result.accessibility_failures] == ["button-name"]
    assert [f["id"] for f in result.accessibility_failures_all] == ["button-name"]


def test_a_failure_whose_details_are_not_an_object_still_parses() -> None:
    result = _result()
    payload = _payload(0.5, {"button-name": _binary(0)})
    payload["lighthouseResult"]["audits"]["button-name"]["details"] = ["not", "an", "object"]
    _parse_accessibility(payload, result)
    assert result.accessibility_failures[0]["impact"] == ""


def test_the_parser_never_edits_the_response_it_was_given() -> None:
    """Після нас цю саму відповідь читають інші парсери."""
    import copy

    payload = _payload(0.5, {"button-name": _binary(0), "link-name": _binary(1)})
    untouched = copy.deepcopy(payload)
    _parse_accessibility(payload, _result())
    assert payload == untouched


def test_the_sidecar_shape_and_the_psi_shape_parse_identically() -> None:
    """Той самий звіт, два провайдери, однакові поля.

    PSI загортає звіт у `lighthouseResult`, сайдкар віддає його як є.
    Якби парсери розійшлися, бал доступності залежав би від того, хто
    відповів, — а це той самий сайт і та сама сторінка.
    """
    audits = {
        "button-name": _binary(0, "Buttons have no name"),
        "image-alt": _binary(0, "No alt"),
        "link-name": _binary(1),
    }
    psi_payload = _payload(0.66, audits)
    sidecar_report = psi_payload["lighthouseResult"]

    from_psi = _result()
    _parse_accessibility(psi_payload, from_psi)

    from_sidecar = PerformanceResult(
        provider="lighthouse", strategy=Strategy.MOBILE, url="https://e.com/"
    )
    _parse_accessibility({"lighthouseResult": sidecar_report}, from_sidecar)

    for field in (
        "accessibility_score",
        "accessibility_failures",
        "accessibility_failures_all",
        "accessibility_audits_total",
        "accessibility_applicable",
        "accessibility_passed",
        "accessibility_failed",
    ):
        assert getattr(from_psi, field) == getattr(from_sidecar, field), field


# ── Придатна лише вся категорія ───────────────────────────────────────
#
# Бал доступності можна публікувати лише тоді, коли його можна звірити з
# тим, з чого він складений. Порожній чи сміттєвий перелік посилань,
# посилання в нікуди, бал поза 0…1 — це не «виміряно частково», а
# відповідь, якій не можна вірити. Жоден із цих випадків не має дати ні
# бала, ні лічильника, ні провалу, і жоден не має записати в результат
# бодай одне поле до того, як уся категорія перевірена.


class _LogRecorder:
    """Стоїть замість журналу парсера: що саме й скільки разів сказано."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def _record(self, level: str, event: str, **fields: Any) -> None:
        self.events.append((level, event, fields))

    def warning(self, event: str, **fields: Any) -> None:
        self._record("warning", event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._record("info", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._record("error", event, **fields)

    def debug(self, event: str, **fields: Any) -> None:
        self._record("debug", event, **fields)


def _refs(category_score: Any, audits: dict[str, Any], refs: list[Any]) -> dict[str, Any]:
    return {
        "lighthouseResult": {
            "categories": {"accessibility": {"score": category_score, "auditRefs": refs}},
            "audits": audits,
        }
    }


def _decoded(literal: str) -> dict[str, Any]:
    """Бал так, як його видає `json`: `NaN` і `Infinity` декодер приймає."""
    decoded: dict[str, Any] = json.loads(
        '{"lighthouseResult": {"categories": {"accessibility": '
        '{"score": ' + literal + ', "auditRefs": [{"id": "button-name"}]}},'
        ' "audits": {"button-name": {"score": 0, "scoreDisplayMode": "binary"}}}}'
    )
    return decoded


UNVERIFIABLE: list[Any] = [
    pytest.param(
        lambda: _refs(0.5, {"button-name": _binary(0)}, []),
        "no_valid_audit_refs",
        id="empty-audit-refs",
    ),
    pytest.param(
        lambda: _refs(
            0.5,
            {"button-name": _binary(0)},
            ["junk", 5, None, {"noid": "x"}, {"id": ""}, {"id": "   "}, {"id": 7}],
        ),
        "no_valid_audit_refs",
        id="only-malformed-audit-refs",
    ),
    pytest.param(
        lambda: _refs(0.5, {"link-name": _binary(1)}, [{"id": "button-name"}, {"id": "label"}]),
        "audit_ref_unresolved",
        id="only-dangling-refs",
    ),
    pytest.param(
        lambda: _refs(
            0.5, {"button-name": _binary(0)}, [{"id": "button-name"}, {"id": "ghost-audit"}]
        ),
        "audit_ref_unresolved",
        id="valid-plus-dangling-ref",
    ),
    pytest.param(
        lambda: _refs(0.5, {"button-name": "not an object"}, [{"id": "button-name"}]),
        "audit_record_not_an_object",
        id="referenced-non-object-audit",
    ),
    pytest.param(
        lambda: _refs(
            0.5,
            {"button-name": _binary(0), "broken": ["not", "an", "object"]},
            [{"id": "button-name"}, {"id": "broken"}],
        ),
        "audit_record_not_an_object",
        id="valid-plus-non-object-audit",
    ),
    pytest.param(
        lambda: _payload(
            1.0,
            {
                "video-caption": {"score": None, "scoreDisplayMode": "notApplicable"},
                "focus-traps": {"score": None, "scoreDisplayMode": "manual"},
                "tap-targets": {"score": 1, "scoreDisplayMode": "informative"},
            },
        ),
        "no_applicable_audits",
        id="no-applicable-automated-audit",
    ),
    pytest.param(
        lambda: _payload(-0.1, {"button-name": _binary(0)}),
        "score_out_of_range",
        id="category-score-below-zero",
    ),
    pytest.param(
        lambda: _payload(1.1, {"button-name": _binary(1)}),
        "score_out_of_range",
        id="category-score-above-one",
    ),
    pytest.param(
        lambda: _payload(0.5, {"button-name": _binary(-0.1), "link-name": _binary(1)}),
        "audit_score_invalid",
        id="audit-score-below-zero",
    ),
    pytest.param(
        lambda: _payload(0.5, {"button-name": _binary(1.1), "link-name": _binary(0)}),
        "audit_score_invalid",
        id="audit-score-above-one",
    ),
    pytest.param(
        lambda: _payload(
            0.5,
            {"button-name": {"score": None, "scoreDisplayMode": "binary"}, "link-name": _binary(1)},
        ),
        "audit_score_invalid",
        id="automated-audit-without-a-score",
    ),
    pytest.param(
        lambda: _payload(
            0.5,
            {"button-name": {"score": None, "scoreDisplayMode": "error"}, "link-name": _binary(1)},
        ),
        "audit_score_invalid",
        id="automated-audit-in-error-mode",
    ),
    pytest.param(
        lambda: _payload(
            0.5,
            {"button-name": {"score": "0", "scoreDisplayMode": "binary"}, "link-name": _binary(1)},
        ),
        "audit_score_invalid",
        id="automated-audit-string-score",
    ),
    pytest.param(
        lambda: _payload("n/a", {"button-name": _binary(0)}),
        "score_not_a_finite_number",
        id="string-score",
    ),
    pytest.param(
        lambda: _payload(None, {"button-name": _binary(0)}),
        "score_not_a_finite_number",
        id="null-score",
    ),
    pytest.param(
        lambda: _payload(True, {"button-name": _binary(1)}),
        "score_not_a_finite_number",
        id="boolean-score",
    ),
    pytest.param(lambda: _decoded("NaN"), "score_not_a_finite_number", id="nan-score"),
    pytest.param(lambda: _decoded("Infinity"), "score_not_a_finite_number", id="infinite-score"),
    pytest.param(
        lambda: {
            "lighthouseResult": {
                "categories": {"accessibility": {"score": 0.5}},
                "audits": {"button-name": _binary(0)},
            }
        },
        "audit_refs_not_a_list",
        id="missing-audit-refs",
    ),
    pytest.param(
        lambda: {
            "lighthouseResult": {
                "categories": {"accessibility": {"score": 0.5, "auditRefs": "nope"}},
                "audits": {"button-name": _binary(0)},
            }
        },
        "audit_refs_not_a_list",
        id="malformed-audit-refs",
    ),
    pytest.param(
        lambda: {
            "lighthouseResult": {
                "categories": {
                    "accessibility": {"score": 0.5, "auditRefs": [{"id": "button-name"}]}
                }
            }
        },
        "audits_not_an_object",
        id="missing-audits",
    ),
    pytest.param(
        lambda: {
            "lighthouseResult": {
                "categories": {
                    "accessibility": {"score": 0.5, "auditRefs": [{"id": "button-name"}]}
                },
                "audits": ["button-name"],
            }
        },
        "audits_not_an_object",
        id="audits-not-an-object",
    ),
    pytest.param(
        lambda: {"lighthouseResult": {"categories": {"accessibility": "nope"}, "audits": {}}},
        "category_not_an_object",
        id="category-not-an-object",
    ),
    pytest.param(
        lambda: {"lighthouseResult": {"categories": {"accessibility": {}}, "audits": {}}},
        "score_not_a_finite_number",
        id="empty-category-object",
    ),
]

ACCEPTED: list[Any] = [
    pytest.param(lambda: _payload(0, {"button-name": _binary(0)}), id="category-score-zero"),
    pytest.param(lambda: _payload(1, {"button-name": _binary(1)}), id="category-score-one"),
    pytest.param(
        lambda: _payload(0.37, {"button-name": _binary(0), "link-name": _binary(1)}),
        id="fractional-category-score",
    ),
    pytest.param(
        lambda: _payload(0.5, {"button-name": _binary(0.0), "link-name": _binary(1.0)}),
        id="audit-scores-at-the-boundaries",
    ),
    pytest.param(
        lambda: _payload(0.6, {"button-name": _binary(0.5), "link-name": _binary(1)}),
        id="fractional-audit-score",
    ),
    pytest.param(
        lambda: _refs(
            0.5,
            {"button-name": _binary(0), "link-name": _binary(1)},
            [{"id": "button-name"}, {"id": "button-name"}, {"id": "link-name"}],
        ),
        id="duplicate-references",
    ),
    pytest.param(
        lambda: _refs(
            0.5,
            {"button-name": _binary(0), "link-name": _binary(1)},
            ["junk", {"id": "button-name"}, 7, None, {"noid": 1}, {"id": ""}, {"id": "link-name"}],
        ),
        id="valid-references-with-isolated-junk",
    ),
    pytest.param(
        lambda: _payload(
            0.8,
            {
                "button-name": _binary(1),
                "video-caption": {"score": None, "scoreDisplayMode": "notApplicable"},
                "focus-traps": {"score": None, "scoreDisplayMode": "manual"},
            },
        ),
        id="automated-audit-beside-non-automated-ones",
    ),
]


@pytest.mark.parametrize(("build", "reason"), UNVERIFIABLE)
def test_an_unverifiable_category_is_rejected_whole(
    build: Callable[[], dict[str, Any]], reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Жодного поля, одне попередження, і причина названа кодом."""
    recorder = _LogRecorder()
    monkeypatch.setattr(psi_module, "log", recorder)
    result = _result()
    _parse_accessibility(build(), result)

    _assert_unmeasured(result)
    warnings = [e for e in recorder.events if e[0] == "warning"]
    assert len(warnings) == 1
    assert warnings[0][1] == "accessibility_category_unusable"
    assert warnings[0][2]["reason"] == reason


@pytest.mark.parametrize(("build", "reason"), UNVERIFIABLE)
def test_rejection_writes_nothing_even_into_a_result_that_already_held_values(
    build: Callable[[], dict[str, Any]], reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Атомарність: відмова не торкається результату взагалі.

    Якби бал записувався до завершення перевірки, частина полів тут
    змінилася б. Сторожові значення роблять будь-який запис видимим.
    """
    monkeypatch.setattr(psi_module, "log", _LogRecorder())
    result = _result()
    sentinel_failure = {"id": "sentinel", "title": "", "impact": ""}
    result.accessibility_score = 12.3
    result.accessibility_failures = [sentinel_failure]
    result.accessibility_failures_all = [sentinel_failure]
    result.accessibility_audits_total = 99
    result.accessibility_applicable = 98
    result.accessibility_passed = 97
    result.accessibility_failed = 1

    _parse_accessibility(build(), result)

    assert result.accessibility_score == 12.3
    assert result.accessibility_failures == [sentinel_failure]
    assert result.accessibility_failures_all == [sentinel_failure]
    assert (
        result.accessibility_audits_total,
        result.accessibility_applicable,
        result.accessibility_passed,
        result.accessibility_failed,
    ) == (99, 98, 97, 1)


@pytest.mark.parametrize(("build", "reason"), UNVERIFIABLE)
def test_rejection_does_not_edit_the_response(
    build: Callable[[], dict[str, Any]], reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(psi_module, "log", _LogRecorder())
    payload = build()
    untouched = json.dumps(payload, sort_keys=True, default=repr)
    _parse_accessibility(payload, _result())
    assert json.dumps(payload, sort_keys=True, default=repr) == untouched


@pytest.mark.parametrize("build", ACCEPTED)
def test_a_verifiable_category_is_measured_with_a_real_denominator(
    build: Callable[[], dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _LogRecorder()
    monkeypatch.setattr(psi_module, "log", recorder)
    payload = build()
    untouched = copy.deepcopy(payload)
    result = _result()
    _parse_accessibility(payload, result)

    assert result.accessibility_score is not None
    assert result.accessibility_applicable is not None
    assert result.accessibility_applicable >= 1
    assert recorder.events == []
    assert payload == untouched


def test_no_score_is_ever_published_without_a_denominator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Інваріант над усіма формами: бал існує лише разом зі знаменником."""
    monkeypatch.setattr(psi_module, "log", _LogRecorder())
    for param in [*UNVERIFIABLE, *ACCEPTED]:
        build = param.values[0]
        result = _result()
        _parse_accessibility(build(), result)
        if result.accessibility_score is None:
            _assert_unmeasured(result)
            continue
        assert 0.0 <= result.accessibility_score <= 100.0, param.id
        assert result.accessibility_applicable is not None, param.id
        assert result.accessibility_applicable >= 1, param.id
        assert result.accessibility_audits_total is not None, param.id
        assert result.accessibility_audits_total >= result.accessibility_applicable, param.id
        assert (
            (result.accessibility_passed or 0) + (result.accessibility_failed or 0)
            == result.accessibility_applicable
        ), param.id


def test_isolated_junk_is_ignored_while_the_real_references_resolve() -> None:
    result = _result()
    payload = _refs(
        0.5,
        {"button-name": _binary(0, "No name"), "link-name": _binary(1)},
        ["junk", {"id": "button-name"}, 7, None, {"noid": 1}, {"id": ""}, {"id": "link-name"}],
    )
    _parse_accessibility(payload, result)
    assert result.accessibility_score == 50.0
    assert result.accessibility_audits_total == 2
    assert (result.accessibility_applicable, result.accessibility_passed) == (2, 1)
    assert [f["id"] for f in result.accessibility_failures] == ["button-name"]


def test_audit_scores_exactly_at_zero_and_one_are_accepted() -> None:
    result = _result()
    _parse_accessibility(
        _payload(0.5, {"button-name": _binary(0.0), "link-name": _binary(1.0)}), result
    )
    assert (result.accessibility_applicable, result.accessibility_passed) == (2, 1)
    assert result.accessibility_failed == 1


def test_a_fractional_audit_score_still_counts_as_a_failure() -> None:
    """Успадкована поведінка: усе, що нижче одиниці, — провал."""
    result = _result()
    _parse_accessibility(
        _payload(0.6, {"button-name": _binary(0.5, "Partial"), "link-name": _binary(1)}), result
    )
    assert result.accessibility_failed == 1
    assert [f["id"] for f in result.accessibility_failures] == ["button-name"]


def test_an_absent_or_null_category_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Категорію могли не запитувати — це звичайний стан, а не аномалія."""
    recorder = _LogRecorder()
    monkeypatch.setattr(psi_module, "log", recorder)
    for payload in (
        {},
        {"lighthouseResult": {}},
        {"lighthouseResult": {"categories": {}}},
        {"lighthouseResult": {"categories": {"accessibility": None}}},
    ):
        result = _result()
        _parse_accessibility(payload, result)
        _assert_unmeasured(result)
    assert recorder.events == []


def test_the_rejection_log_carries_no_payload_ids_or_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """У журнал — код причини й безпечна адреса, і більше нічого.

    Ні ідентифікаторів перевірок, ні їхніх назв, ні запиту, ні фрагмента,
    ні облікових даних з адреси.
    """
    recorder = _LogRecorder()
    monkeypatch.setattr(psi_module, "log", recorder)
    result = PerformanceResult(
        provider="lighthouse",
        strategy=Strategy.MOBILE,
        url="https://user:secret@example.com:8443/about/team?session=abc123&x=1#section-2",
    )
    payload = _refs(
        0.5,
        {"button-name": _binary(0, "Buttons have no accessible name")},
        [{"id": "button-name"}, {"id": "ghost-audit-id"}],
    )
    _parse_accessibility(payload, result)

    assert len(recorder.events) == 1
    level, event, fields = recorder.events[0]
    assert (level, event) == ("warning", "accessibility_category_unusable")
    assert fields["url"] == "https://example.com:8443/about/team"
    assert fields["reason"] == "audit_ref_unresolved"
    logged = json.dumps(fields)
    for forbidden in ("ghost-audit-id", "button-name", "Buttons have no", "session", "abc123",
                      "section-2", "secret", "user:"):
        assert forbidden not in logged, forbidden

