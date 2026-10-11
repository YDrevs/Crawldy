"""Контракти /v1 — заморожені сигнатури.

Цей файл — гальмо, і гальмом він і задуманий. Поля нижче — опублікований
контракт: фронтенд, мобільний клієнт і чужі скрипти читають саме їх.
Перейменувати поле, змінити тип, зробити необовʼязкове обовʼязковим чи
прибрати ендпойнт — означає зламати клієнтів, яких ми не бачимо.

Правила, які перевіряє тест:

- **заморожене поле мусить існувати** з тим самим типом і тією самою
  обовʼязковістю — ловиться перейменування, видалення, зміна типу;
- **нові поля дозволені** — додавання зворотно сумісне; додавши поле,
  допиши його сюди (інакше воно не захищене);
- **заморожені шляхи мусять існувати** — нові можна, прибирати не можна.

Якщо тест упав — це не «полагодь тест». Варіанти два: відкотити зміну
контракту або свідомо провести міграцію (deprecation-період, шар
сумісності або /v2) і лише тоді оновити заморозку. «Поправити рядок тут,
щоб стало зелене» — рівно той мовчазний злам, від якого тест існує.

Сигнатури згенеровані з openapi і вставлені літералами навмисно: якби
тест будував «очікуване» з коду, він порівнював би код сам із собою.
"""

from __future__ import annotations

from app.main import app

FROZEN_SCHEMAS = {
    "AuditOut": {
        "id": "!string:uuid",
        "site_id": "null|string:uuid",
        "url": "!string",
        "origin": "!string",
        "status": "!ref:AuditStatus",
        "score_overall": "!integer|null",
        "scores": "!null|object",
        "error": "!null|string",
        "created_at": "!string:date-time",
        "started_at": "!null|string:date-time",
        "finished_at": "!null|string:date-time",
        "option_adjustments": "array[object]",
        "quota_state": "ref:QuotaState",
        "failure_class": "null|ref:FailureClass",
        "attempts": "integer",
    },
    "AuditDetailOut": {
        "id": "!string:uuid",
        "site_id": "null|string:uuid",
        "url": "!string",
        "origin": "!string",
        "status": "!ref:AuditStatus",
        "score_overall": "!integer|null",
        "scores": "!null|object",
        "error": "!null|string",
        "created_at": "!string:date-time",
        "started_at": "!null|string:date-time",
        "finished_at": "!null|string:date-time",
        "option_adjustments": "array[object]",
        "quota_state": "ref:QuotaState",
        "failure_class": "null|ref:FailureClass",
        "attempts": "integer",
        "locale": "string",
        "options": "object",
        "targets": "array[ref:TargetOut]",
        "pages_count": "integer",
        "issues_count": "integer",
        "issues_by_severity": "object",
        "issues": "array[ref:IssueOut]",
        "pages": "array[ref:PageOut]",
        "attempt_log": "array[ref:AttemptOut]",
    },
    "IssueOut": {
        "id": "!string:uuid",
        "module": "!ref:Module",
        "code": "!string",
        "severity": "!ref:Severity",
        "title": "!string",
        "description": "!string",
        "recommendation": "!string",
        "evidence": "!object",
        "page_url": "null|string",
        "msg": "string",
        "verdict": "null|ref:Verdict",
        "verdict_note": "string",
        "text_locale": "string",
    },
    "TargetOut": {
        "id": "!string:uuid",
        "position": "!integer",
        "url": "!string",
        "origin": "!string",
        "status": "!ref:AuditStatus",
        "score_overall": "!integer|null",
        "scores": "!null|object",
        "error": "!null|string",
        "failure_class": "null|ref:FailureClass",
    },
    "AttemptOut": {
        "number": "!integer",
        "status": "!ref:AuditStatus",
        "failure_class": "!null|ref:FailureClass",
        "error": "!string",
        "retry_decision": "!string",
        "started_at": "!string:date-time",
        "finished_at": "!null|string:date-time",
    },
    "ShareLinkOut": {
        "id": "!string:uuid",
        "target_id": "!null|string:uuid",
        "lang": "!string",
        "created_at": "!string:date-time",
        "expires_at": "!string:date-time",
        "revoked_at": "!null|string:date-time",
        "views": "!integer",
    },
    "SiteOut": {
        "id": "!string:uuid",
        "origin": "!string",
        "display_name": "!string",
        "resolved_origin": "!null|string",
        "redirects_elsewhere": "!boolean",
        "created_at": "!string",
        "archived_at": "!null|string",
    },
    "ScheduleOut": {
        "id": "!string:uuid",
        "site_id": "!string:uuid",
        "cadence": "!ref:Cadence",
        "timezone": "!string",
        "hour_local": "!integer",
        "minute_local": "!integer",
        "day_of_week": "!integer|null",
        "day_of_month": "!integer|null",
        "enabled": "!boolean",
        "next_run_at": "!null|string",
        "last_run_at": "!null|string",
        "consecutive_failures": "!integer",
        "last_failure_reason": "!string",
        "needs_attention": "!boolean",
    },
    "MeOut": {
        "user": "!null|ref:UserOut",
        "organization": "!ref:OrganizationOut",
        "auth": "!string",
    },
    "HistoryOut": {
        "origin": "!string",
        "visible_days": "integer|null",
        "points": "array[ref:ScorePointOut]",
        "steps": "array[ref:HistoryStepOut]",
        "incomparable_steps": "integer",
        "fixable_by_recompute": "integer",
    },
    "SiteHistoryOut": {
        "site": "!ref:SiteRefOut",
        "visible_days": "integer|null",
        "points": "array[ref:ScorePointOut]",
        "steps": "array[ref:HistoryStepOut]",
        "incomparable_steps": "integer",
        "fixable_by_recompute": "integer",
    },
    "ScorePointOut": {
        "audit_id": "!string",
        "at": "!string",
        "overall": "!integer|null",
        "scores": "object",
        "versions": "object",
        "can_be_recomputed": "boolean",
    },
    "HistoryStepOut": {
        "before": "!ref:ScorePointOut",
        "after": "!ref:ScorePointOut",
        "days_between": "!integer",
        "overall_delta": "!integer|null",
        "by_module": "object",
        "comparable": "!boolean",
        "changed_in_us": "array[string]",
        "rebased": "boolean",
    },
    "AccountOut": {
        "organization": "!ref:AccountOrganizationOut",
        "role": "!string",
        "plan": "!ref:PlanOut",
        "subscription": "null|ref:SubscriptionOut",
        "entitlements": "object",
        "usage": "!ref:UsageOut",
    },
    "SubscriptionOut": {
        "status": "!ref:SubscriptionStatus",
        "cancel_at_period_end": "!boolean",
        "current_period_start": "!null|string:date-time",
        "current_period_end": "!null|string:date-time",
        "trial_end": "!null|string:date-time",
        "grace_until": "!null|string:date-time",
    },
    "PlanOut": {
        "code": "!string",
        "name": "!string",
    },
    "UsageOut": {
        "audits_used": "!integer",
        "audits_limit": "!integer|null",
        # Залишок рахує бекенд. «Ліміт мінус використано» виглядає
        # тривіальним доти, доки не зʼявиться безлімітний тариф або
        # перевитрата після зміни плану.
        "audits_remaining": "!integer|null",
        "period_start": "!string:date-time",
        "period_end": "!string:date-time",
        "renews_at": "null|string:date-time",
        # Куплені окремо аудити — власним числом, а не доданням до квоти
        # періоду. Квота згорає при поновленні, кредити ні; одна сума
        # приховала б від клієнта, що частина числа зникне сама собою.
        "one_off_available": "integer",
    },
    "AuditResultResponse": {
        "contract_version": "integer",
        "audit_id": "!string:uuid",
        "site_id": "null|string:uuid",
        "url": "!string",
        "origin": "!string",
        "status": "!ref:AuditStatus",
        "generated_at": "!string:date-time",
        "finished_at": "null|string:date-time",
        "overall_score": "!integer|null",
        "overall_band": "!string",
        "potential_score": "integer|null",
        "modules": "array[ref:ModuleScoreOut]",
        "summary": "!ref:ResultSummaryOut",
        "priorities": "array[ref:PriorityOut]",
        "next_actions": "array[ref:NextActionOut]",
        "findings": "array[ref:FindingOut]",
        "missing_data": "array[ref:MissingDataOut]",
        "engine_versions": "object",
        "localization": "!ref:LocalizationOut",
    },
    "ModuleScoreOut": {
        "module": "!ref:Module",
        "score": "!integer|null",
        "band": "!string",
        "weight": "!number",
        "issues_count": "!integer",
        "excluded": "!boolean",
        "partial": "!boolean",
        # G2 (E-01): чому бала немає. Сигнатура бачить лише «рядок або null»;
        # межу значень тримає окремий тест наприкінці файла.
        "withheld_reason": "null|string",
    },
    # Знімок доступності заморожено рівно на полі G2: решту його полів ця
    # заморозка поки не охоплює.
    "AccessibilitySnapshotOut": {
        "withheld_reason": "null|string",
    },
    "PriorityOut": {
        "rank": "!integer",
        "issue_key": "!string",
        "module": "!ref:Module",
        "severity": "!ref:Severity",
        "title": "!string",
        "problem": "!string",
        "action": "!string",
        "consequence": "!string",
        "scope": "!string",
        "affected_pages": "!integer",
        "affected_examples": "array[string]",
        "evidence": "object",
        "impact_points": "!integer",
        "impact_by_module": "object",
        "effort": "!ref:Effort",
        "confidence": "!ref:Confidence",
    },
    "NextActionOut": {
        "rank": "!integer",
        "issue_key": "!string",
        "module": "!ref:Module",
        "action": "!string",
        "why": "!string",
        "expected_gain_points": "!integer",
        "expected_gain": "!string",
        "effort": "!ref:Effort",
        "affected_pages": "!integer",
    },
    "FindingOut": {
        "id": "null|string:uuid",
        "code": "!string",
        "issue_key": "!string",
        "module": "!ref:Module",
        "severity": "!ref:Severity",
        "title": "!string",
        "description": "!string",
        "recommendation": "!string",
        "page_url": "!null|string",
        "evidence": "object",
        "verdict": "null|ref:Verdict",
        "verdict_note": "string",
    },
    "MissingDataOut": {
        "scope": "!string",
        "kind": "!string",
        "reason": "!string",
        "affects": "array[string]",
        "note": "string",
    },
    "CoverageOut": {
        "pages_read": "integer",
        "pages_fetched": "integer",
        "pages_failed": "integer",
        "urls_known": "integer",
    },
    "ResultSummaryOut": {
        "issues_total": "!integer",
        "by_severity": "object",
        "by_module": "object",
        "coverage": "!ref:CoverageOut",
        "impact_is_independent": "boolean",
    },
    "LocalizationOut": {
        "locale": "!string",
        "fallback_locale": "!string",
        "fell_back_strings": "integer",
    },
    "UserOut": {
        "id": "!string:uuid",
        "email": "!string",
        "display_name": "!string",
        "status": "!string",
        "locale": "string",
    },
    "PlanCatalogOut": {
        "locale": "!string",
        "plans": "array[ref:PublicPlanOut]",
    },
    "PublicPlanOut": {
        "code": "!string",
        "name": "!string",
        "description": "string",
        "sort_order": "integer",
        "highlighted": "boolean",
        "prices": "array[ref:PlanPriceOut]",
        "limits": "array[ref:PlanFeatureOut]",
        "features": "array[ref:PlanFeatureOut]",
        "cta_key": "!string",
        "cta_label": "!string",
        "available": "boolean",
    },
    "PlanPriceOut": {
        "currency": "!string",
        "interval": "!string",
        "amount_minor": "integer|null",
        "exponent": "integer",
    },
    "PlanFeatureOut": {
        "label_key": "!string",
        "label": "!string",
        "included": "boolean",
    },
}

# Свідомо прибрано з клієнтського API, а не втрачено:
#
#   GET /v1/audits/checks/feedback → GET /v1/admin/checks/feedback
#
# Зведення йшло по **всіх** організаціях (`feedback_by_check` не приймає
# organization_id), тобто будь-який автентифікований клієнт бачив, скільки
# чужих людей і як відповіли на кожен чек. Це внутрішній інструмент якості
# детекції, а не продуктова функція. Той рідкісний випадок, коли злам
# контракту правильний: лишити витік заради сумісності — гірше.
FROZEN_PATHS = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("GET", "/r/{token}"),
    ("GET", "/v1/account"),
    ("GET", "/v1/admin/checks/feedback"),
    ("GET", "/v1/audits"),
    ("POST", "/v1/audits"),
    ("GET", "/v1/audits/history/by-origin"),
    ("PUT", "/v1/audits/issues/{issue_id}/verdict"),
    ("GET", "/v1/audits/llm-models"),
    ("POST", "/v1/audits/targets/{target_id}/rescore"),
    ("GET", "/v1/audits/{audit_id}"),
    ("GET", "/v1/audits/{audit_id}/benchmark"),
    ("GET", "/v1/audits/{audit_id}/issues"),
    ("GET", "/v1/audits/{audit_id}/links"),
    ("POST", "/v1/audits/{audit_id}/links"),
    ("DELETE", "/v1/audits/{audit_id}/links/{link_id}"),
    ("GET", "/v1/audits/{audit_id}/report"),
    ("GET", "/v1/audits/{audit_id}/result"),
    ("GET", "/v1/auth/api-keys"),
    ("POST", "/v1/auth/api-keys"),
    ("DELETE", "/v1/auth/api-keys/{key_id}"),
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/auth/logout"),
    ("GET", "/v1/auth/me"),
    ("PATCH", "/v1/auth/me"),
    ("POST", "/v1/auth/register"),
    ("GET", "/v1/plans"),
    ("GET", "/v1/schedules"),
    ("POST", "/v1/schedules"),
    ("DELETE", "/v1/schedules/{schedule_id}"),
    ("POST", "/v1/schedules/{schedule_id}/disable"),
    ("POST", "/v1/schedules/{schedule_id}/enable"),
    ("GET", "/v1/sites"),
    ("POST", "/v1/sites"),
    ("DELETE", "/v1/sites/{site_id}"),
    ("GET", "/v1/sites/{site_id}"),
    ("PATCH", "/v1/sites/{site_id}"),
    ("GET", "/v1/sites/{site_id}/history"),
}


def _actual_type(prop: dict) -> str:
    if "$ref" in prop:
        return "ref:" + prop["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in prop:
        return "|".join(sorted(_actual_type(p) for p in prop["anyOf"]))
    kind = prop.get("type", "any")
    if kind == "array":
        return f"array[{_actual_type(prop.get('items', {}))}]"
    fmt = prop.get("format")
    return f"{kind}:{fmt}" if fmt else kind


def _schemas() -> dict:
    return app.openapi()["components"]["schemas"]


def test_frozen_fields_exist_with_the_same_type_and_requiredness():
    schemas = _schemas()
    broken: list[str] = []
    for name, frozen in FROZEN_SCHEMAS.items():
        actual = schemas.get(name)
        if actual is None:
            broken.append(f"{name}: схема зникла з openapi")
            continue
        required = set(actual.get("required", []))
        properties = actual.get("properties", {})
        for field, signature in frozen.items():
            must = signature.startswith("!")
            expected = signature.lstrip("!")
            if field not in properties:
                broken.append(f"{name}.{field}: поле зникло (перейменоване?)")
                continue
            got = _actual_type(properties[field])
            if got != expected:
                broken.append(f"{name}.{field}: тип {expected!r} → {got!r}")
            if must and field not in required:
                broken.append(f"{name}.{field}: було обовʼязковим, стало ні")
    assert not broken, "зламано контракт:\n" + "\n".join(broken)


def test_frozen_paths_still_exist():
    actual = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }
    gone = FROZEN_PATHS - actual
    assert not gone, f"ендпойнти зникли: {sorted(gone)}"


def _declares_a_model(schema: dict) -> bool:
    """Чи оголошує ця схема відповіді конкретну модель.

    Три форми, і всі три — контракт: прямий `$ref`, масив моделей, і
    обʼєднання, кожна гілка якого — модель. Останнє знадобилося E-13:
    гостьовий маршрут віддає або стан аудиту, або коротку проєкцію, і це
    дві різні моделі, а не одна розмита. Перевірка навмисно вимагає, щоб
    модель була в КОЖНІЙ гілці — `anyOf` із голим `object` усередині
    лишається дірою й далі.
    """
    if "$ref" in schema:
        return True
    if schema.get("type") == "array":
        return "$ref" in str(schema.get("items") or {})
    branches = schema.get("anyOf") or schema.get("oneOf") or []
    return bool(branches) and all("$ref" in branch for branch in branches)


def test_every_route_declares_a_response_contract():
    """Новий клієнтський маршрут без схеми відповіді — дірка в контракті.

    Винятки перелічені явно й мають підстави: у 204 тіла немає, `report`
    віддає файл, `health` — службовий, `share` — публічний рендер звіту,
    контракт якого і є JSON-звіт.
    """
    allowed_without_model = {
        ("GET", "/health"),
        ("GET", "/health/ready"),
        ("GET", "/r/{token}"),
        ("GET", "/v1/audits/{audit_id}/report"),
        # Word-експорт присутності — файл, як і report: тіло бінарне.
        ("GET", "/v1/presence/runs/{run_id}/export.docx"),
        ("GET", "/v1/public/presence/{run_id}/export.docx"),
        ("POST", "/v1/audits/targets/{target_id}/rescore"),
        ("PUT", "/v1/audits/issues/{issue_id}/verdict"),
        ("GET", "/v1/audits/{audit_id}/benchmark"),
        # Службовий API. Не публічний контракт: його читає лише наша
        # адмінка, і міняється він разом із нею, одним комітом. Виняток
        # свідомо поширений на весь префікс службової конфігурації,
        # аналітики й тестування: там відповідь — діагностичний зріз
        # наявних таблиць, і фіксувати його схемою означало б заморозити
        # внутрішній інструмент замість продукту.
        ("GET", "/v1/admin/checks/feedback"),
        ("GET", "/v1/admin/config/payment"),
        ("PUT", "/v1/admin/config/payment"),
        ("POST", "/v1/admin/config/payment/test"),
        ("GET", "/v1/admin/config/ai"),
        ("PUT", "/v1/admin/config/ai"),
        ("POST", "/v1/admin/config/ai/{provider}/test"),
        ("GET", "/v1/admin/analytics"),
        ("GET", "/v1/admin/payments/pending"),
        ("POST", "/v1/admin/payments/sweep"),
        ("POST", "/v1/admin/payments/verify"),
        ("POST", "/v1/admin/payments/{purchase_id}/verify"),
        ("POST", "/v1/admin/payments/{purchase_id}/credit"),
        ("GET", "/v1/admin/testing/audits"),
        ("POST", "/v1/admin/testing/audits"),
        ("GET", "/v1/admin/testing/audits/{audit_id}"),
        # Звіт службового прогону — той самий файл, що й клієнтський.
        ("GET", "/v1/admin/testing/audits/{audit_id}/report"),
        ("GET", "/v1/admin/testing/presence"),
        ("POST", "/v1/admin/testing/presence"),
        ("GET", "/v1/admin/testing/presence/{run_id}"),
        # Word-експорт присутності зі службового екрана — той самий файл.
        ("GET", "/v1/admin/testing/presence/{run_id}/report"),
        # Гостьовий перегляд: до завершення — статус, після — короткий
        # звіт. Обидві форми тепер оголошені моделями (E-13), тож у списку
        # лишається сам повний звіт нижче — його контракт і є JSON-звіт.
        # Повний звіт гостя — той самий JSON-звіт, що й /r/{token}.
        ("GET", "/v1/public/audits/{audit_id}/full"),
        # Відповідь вебхука читає провайдер, а не наш клієнт: йому
        # важливий код відповіді, не тіло.
        ("POST", "/v1/webhooks/{provider}"),
        ("POST", "/v1/auth/logout"),
        ("DELETE", "/v1/auth/api-keys/{key_id}"),
        ("DELETE", "/v1/sites/{site_id}"),
        ("DELETE", "/v1/schedules/{schedule_id}"),
    }
    missing: list[str] = []
    for path, methods in app.openapi()["paths"].items():
        for method, spec in methods.items():
            key = (method.upper(), path)
            responses = spec.get("responses", {})
            ok = responses.get("200") or responses.get("201") or responses.get("202")
            if ok is None:
                continue  # 204 та інші без тіла
            content = ok.get("content", {})
            schema = content.get("application/json", {}).get("schema", {})
            declared = _declares_a_model(schema)
            if not declared and key not in allowed_without_model:
                missing.append(f"{key[0]} {key[1]}")
    assert not missing, (
        "маршрути без оголошеної схеми відповіді (додай response_model або "
        "явний виняток із підставою):\n" + "\n".join(missing)
    )


# ── G2: чому модуля немає в балі ──────────────────────────────────────────
#
# `withheld_reason` зʼявився адитивно (E-01) у двох моделях відповіді. Для
# машинного стану сигнатура «рядок або null» — ще не контракт: споживач
# розгалужується за значенням, і нове значення без міграції зламало б його так
# само тихо, як перейменоване поле. Тому заморожено й межу значень.

WITHHELD_REASONS = {"excluded_by_request", "withheld_not_measured"}
WITHHELD_REASON_MODELS = ("ModuleScoreOut", "AccessibilitySnapshotOut")


def test_withheld_reason_is_a_bounded_nullable_optional_field_in_both_models():
    """Поле є в обох схемах, приймає null, не вимагається, а його рядок
    обмежений рівно двома значеннями — довільного рядка схема не допускає."""
    schemas = _schemas()
    for name in WITHHELD_REASON_MODELS:
        schema = schemas[name]
        prop = schema["properties"].get("withheld_reason")
        assert prop is not None, f"{name}.withheld_reason зникло"
        assert "withheld_reason" not in schema.get("required", []), (
            f"{name}: поле стало обовʼязковим"
        )
        branches = prop.get("anyOf", [])
        assert {"type": "null"} in branches, f"{name}: null більше не допускається"
        values = [branch for branch in branches if branch != {"type": "null"}]
        assert len(values) == 1, f"{name}: зʼявилась інша форма значення: {prop}"
        assert values[0].get("type") == "string", f"{name}: значення не рядок: {prop}"
        assert "enum" in values[0], f"{name}: рядок став необмеженим: {prop}"
        assert sorted(values[0]["enum"]) == sorted(WITHHELD_REASONS), (
            f"{name}: змінились значення: {prop}"
        )


def test_withheld_reason_accepts_exactly_the_frozen_values_and_old_payloads():
    """Тіло без поля — від старого сервера чи зі старих даних — читається, як
    до G2. Будь-який рядок поза переліком валідацію не проходить."""
    import pytest
    from pydantic import ValidationError

    from app.schemas.result import AccessibilitySnapshotOut, ModuleScoreOut

    module = {
        "module": "seo",
        "score": 42,
        "band": "poor",
        "weight": 0.26,
        "issues_count": 3,
        "excluded": False,
        "partial": False,
    }
    for model, old in ((ModuleScoreOut, module), (AccessibilitySnapshotOut, {"available": False})):
        name = model.__name__
        assert model.model_validate(old).withheld_reason is None, f"{name}: старе тіло не читається"
        assert model.model_validate({**old, "withheld_reason": None}).withheld_reason is None
        for value in sorted(WITHHELD_REASONS):
            dumped = model.model_validate({**old, "withheld_reason": value}).model_dump(mode="json")
            assert dumped["withheld_reason"] == value, name
        for foreign in ("", "excluded", "not_measured", "EXCLUDED_BY_REQUEST", "withheld_not_measured "):
            with pytest.raises(ValidationError):
                model.model_validate({**old, "withheld_reason": foreign})


def test_measured_modules_and_accessibility_serialize_withheld_reason_as_null():
    """Виміряне віддається з явним null: ключ присутній, значення порожнє.
    Перевірка йде справжнім шляхом відповіді — білдером звіту й `to_web`."""
    import uuid
    from datetime import UTC, datetime

    from app.audit.enums import AuditStatus, Module
    from app.audit.i18n import Locale
    from app.report.builder import build_report
    from app.report.types import ReportSource
    from app.report.web import to_web

    source = ReportSource(
        url="https://example.com",
        entry_url="https://example.com/",
        origin="https://example.com",
        overall=50,
        scores={m.value: 50 for m in Module},
        issues=[],
        degraded=[],
        skipped_modules=set(),
        evidence={},
        pages_crawled=1,
        status=AuditStatus.COMPLETED,
    )
    payload = to_web(
        build_report(source, Locale.EN),
        audit_id=uuid.UUID(int=1),
        site_id=None,
        status="completed",
        finished_at=datetime(2026, 9, 11, tzinfo=UTC),
        fallback_locale="en",
    ).model_dump(mode="json")

    assert payload["modules"], "немає жодного модуля"
    for module in payload["modules"]:
        assert "withheld_reason" in module, module
        assert module["withheld_reason"] is None, module
    assert "withheld_reason" in payload["accessibility"]
    assert payload["accessibility"]["withheld_reason"] is None
    assert payload["accessibility"]["counts_toward_overall"] is True, "знімок справді виміряний"


def test_the_result_contract_version_stays_2():
    """`withheld_reason` адитивний: версія контракту не росте."""
    from app.schemas.result import RESULT_CONTRACT_VERSION

    assert RESULT_CONTRACT_VERSION == 2
    assert _schemas()["AuditResultResponse"]["properties"]["contract_version"].get("default") == 2


# ── E-13: чому гостьовий аудит не дав звіту ───────────────────────────────
#
# Гість бачив тільки «не вийшло». Пʼять нормалізованих класів давали одну
# й ту саму відповідь, і людина не могла відрізнити «сайт не відкрився»
# від «сайт заблокував доступ» від «сервіс аналізу впав» — тобто не могла
# зрозуміти, чи є сенс пробувати ще раз.
#
# Тепер клас віддається машинним переліком, а причина — готовим реченням
# мовою сторінки. Сире `error` лишається там, де було: у кабінеті.

import json  # noqa: E402
import uuid as _uuid  # noqa: E402

import pytest  # noqa: E402

from app.audit.enums import AuditStatus as _AuditStatus  # noqa: E402
from app.audit.i18n import Locale as _Locale  # noqa: E402
from app.core.run_enums import FailureClass as _FailureClass  # noqa: E402
from app.schemas.result import FAILURE_REASONS as _FAILURE_REASONS  # noqa: E402

#: Сире технічне повідомлення, яке зберігає воркер. Воно не має зʼявитися
#: у гостьовій відповіді ЖОДНОЮ своєю частиною.
_RAW_ERROR = (
    "ConnectionError in app/audit/fetcher.py:88 -> PSIProvider gave 502 for "
    "https://10.0.0.5/robots.txt (upstream lighthouse-worker-3)"
)
_RAW_FRAGMENTS = (
    "ConnectionError", "fetcher.py", "PSIProvider", "10.0.0.5", "lighthouse",
    "502", "app/audit", "upstream", "Traceback",
)


class _Row:
    """Рядок аудиту з тими полями, які читає маршрут."""

    def __init__(self, status, failure_class=None, error=_RAW_ERROR, progress=None):
        self.id = _uuid.UUID("11111111-2222-3333-4444-555555555555")
        self.status = status.value if hasattr(status, "value") else status
        self.failure_class = failure_class
        self.error = error
        self.progress = progress or {}
        self.site_id = None
        self.finished_at = None


@pytest.fixture()
def guest(monkeypatch):
    """Гостьовий маршрут із підміненими залежностями сесії та власності.

    Підміняється тільки те, що ходить у базу. Сам маршрут, його схема
    відповіді й локалізація — справжні: тест саме про них.
    """
    from fastapi.testclient import TestClient

    from app.api.routes import public as public_routes
    from app.application import guest as guest_app
    from app.services import audit_service

    state = {"row": None, "unlocked": False}

    async def _owns(*_a, **_k):
        return True

    async def _unlocked(*_a, **_k):
        return state["unlocked"]

    async def _get(*_a, **_k):
        return state["row"]

    monkeypatch.setattr(guest_app, "owns_audit", _owns)
    monkeypatch.setattr(guest_app, "is_unlocked", _unlocked)
    monkeypatch.setattr(audit_service, "get_audit", _get)

    def _dep(annotated):
        return annotated.__metadata__[0].dependency

    app.dependency_overrides[_dep(public_routes.CapabilityDep)] = lambda: object()
    app.dependency_overrides[_dep(public_routes.SessionDep)] = lambda: object()
    client = TestClient(app)

    def call(row, *, lang="en", unlocked=False, raw=False):
        state["row"], state["unlocked"] = row, unlocked
        response = client.get(f"/v1/public/audits/{row.id}", params={"lang": lang})
        # `raw` віддає ТІЛО як рядок. Розібраний словник не розрізняє
        # «ключа немає» і «ключ є, значення null» так, щоб різницю було
        # видно в самому твердженні, а саме на цій різниці тримається
        # контракт: фронт оголошує `string | undefined`, і `null` там —
        # інший тип.
        return response.text if raw else response.json()

    yield call
    app.dependency_overrides.clear()


def test_every_failure_class_reaches_the_guest_with_its_own_class(guest):
    """Пʼять класів — пʼять різних відповідей, а не одна на всіх."""
    seen = {}
    for failure in _FailureClass:
        body = guest(_Row(_AuditStatus.FAILED, failure))
        assert body["failure_class"] == failure.value
        seen[failure.value] = body["failure_reason"]
    assert len(seen) == 5
    assert len(set(seen.values())) == 5, "різні класи не можуть мати одне речення"


def test_every_reason_comes_from_the_catalogue(guest):
    """Речення не складається на місці: воно є в каталозі, слово в слово."""
    for failure in _FailureClass:
        body = guest(_Row(_AuditStatus.FAILED, failure))
        assert body["failure_reason"] == _FAILURE_REASONS[failure][_Locale.EN]


def test_all_six_launch_locales_render_a_localized_reason(guest):
    """Шість мов — шість текстів, і жоден не падає на англійську."""
    for failure in _FailureClass:
        rendered = {}
        for locale in (_Locale.UK, _Locale.EN, _Locale.DE, _Locale.ES, _Locale.FR, _Locale.RU):
            body = guest(_Row(_AuditStatus.FAILED, failure), lang=locale.value)
            assert body["failure_reason"] == _FAILURE_REASONS[failure][locale]
            rendered[locale] = body["failure_reason"]
        english = rendered[_Locale.EN]
        leaked = [loc.value for loc, text in rendered.items()
                  if loc is not _Locale.EN and text == english]
        assert not leaked, f"{failure.value}: англійський текст протік у {leaked}"


def test_no_raw_technical_detail_reaches_the_anonymous_guest(guest):
    """Сире `error` живе в кабінеті. Тут його немає жодним фрагментом."""
    for failure in _FailureClass:
        for locale in (_Locale.UK, _Locale.EN, _Locale.DE, _Locale.ES, _Locale.FR, _Locale.RU):
            body = guest(_Row(_AuditStatus.FAILED, failure), lang=locale.value)
            blob = json.dumps(body, ensure_ascii=False)
            assert "error" not in body
            for fragment in _RAW_FRAGMENTS:
                assert fragment not in blob, f"{fragment!r} протік у {locale.value}"


def test_provider_failed_never_names_a_provider(guest):
    """«Сервіс аналізу» — і крапка. Назва постачальника — наша кухня."""
    vendors = ("psi", "pagespeed", "lighthouse", "google", "anthropic", "openai",
               "playwright", "paddle", "moz", "ahrefs")
    for locale in (_Locale.UK, _Locale.EN, _Locale.DE, _Locale.ES, _Locale.FR, _Locale.RU):
        body = guest(_Row(_AuditStatus.FAILED, _FailureClass.PROVIDER_FAILED),
                     lang=locale.value)
        text = body["failure_reason"].lower()
        assert not [v for v in vendors if v in text]


def test_missing_failure_detail_gives_the_safe_generic_reason(guest):
    """Невідомий клас — внутрішня помилка, і КЛАСОМ теж, не лише текстом.

    Попередня версія цього тесту закріплювала розходження: вона вимагала
    `failure_class is None` поруч із реченням про внутрішню помилку,
    тобто два твердження про одну невдачу, які суперечать одне одному.
    Нормалізація тепер спільна, і клас поруч із реченням той самий.
    """
    body = guest(_Row(_AuditStatus.FAILED, None))
    assert body["failure_class"] == _FailureClass.INTERNAL_ERROR.value
    assert body["failure_reason"] == _FAILURE_REASONS[_FailureClass.INTERNAL_ERROR][_Locale.EN]
    for fragment in _RAW_FRAGMENTS:
        assert fragment not in json.dumps(body, ensure_ascii=False)


def test_an_unrecognised_stored_class_becomes_internal_error(guest):
    """Чужий рядок у колонці — внутрішня помилка, а не 500 і не сирий рядок."""
    body = guest(_Row(_AuditStatus.FAILED, "something_we_never_declared"))
    assert body["failure_class"] == _FailureClass.INTERNAL_ERROR.value
    assert body["failure_reason"] == _FAILURE_REASONS[_FailureClass.INTERNAL_ERROR][_Locale.EN]


def test_every_terminal_failure_names_one_of_the_five_classes(guest):
    """Клас завжди з переліку — інакше машинний читач не має на що спертися."""
    known = {c.value for c in _FailureClass}
    for state in (_AuditStatus.FAILED, _AuditStatus.SKIPPED):
        for stored in [*_FailureClass, None, "not_a_class"]:
            body = guest(_Row(state, stored))
            assert body["failure_class"] in known
            assert isinstance(body["failure_reason"], str) and body["failure_reason"]


def test_running_and_queued_audits_get_no_failure_fields(guest):
    """Полів про невдачу в нетермінальній відповіді НЕМАЄ — не `null`.

    Назва цього тесту завжди казала «no failure fields», а твердження
    перевіряли `is None`, тобто закріплювали рівно протилежне: ключ на
    місці, значення порожнє. Фронт оголошує `failure_reason?: string`,
    і `null` там — інший тип; ключ, якого немає, читається як
    «невідомо», а ключ зі значенням `null` — як «відомо, що нічого».
    Про аудит, який ще виконується, правдиве перше.
    """
    for state in (_AuditStatus.QUEUED, _AuditStatus.RUNNING):
        body = guest(_Row(state, _FailureClass.INTERNAL_ERROR))
        assert "failure_class" not in body
        assert "failure_reason" not in body
        assert body["status"] == state.value


def test_absence_is_not_the_same_as_null_on_the_wire(guest):
    """Різниця видима в САМОМУ тілі, а не лише в розібраному словнику.

    Розібраний словник показав би `None` і для відсутнього ключа, якби
    твердження було написане через `.get()`. Тут читається текст
    відповіді: імені поля в ньому немає взагалі.
    """
    for state in (_AuditStatus.QUEUED, _AuditStatus.RUNNING):
        text = guest(_Row(state, _FailureClass.SITE_BLOCKED), raw=True)
        assert "failure_class" not in text
        assert "failure_reason" not in text
        assert "null" not in text.replace('"progress": {}', "")
    # А на термінальній невдачі обидва імені в тілі Є, і жодне не `null`.
    text = guest(_Row(_AuditStatus.FAILED, _FailureClass.SITE_BLOCKED), raw=True)
    assert '"failure_class"' in text and '"failure_reason"' in text
    assert '"failure_class": null' not in text and '"failure_class":null' not in text


def test_a_completed_audit_carries_no_failure_fields(guest, monkeypatch):
    """Готовий аудит віддає коротку проєкцію — і в ній невдачі немає."""
    from app.application import guest as guest_app

    monkeypatch.setattr(
        guest_app, "short_view",
        lambda audit, **_k: {"audit_id": str(audit.id), "url": "https://x", "origin": "https://x",
                             "status": "completed", "generated_at": "2026-01-01T00:00:00",
                             "overall_score": 71, "overall_band": "medium", "issues_total": 0,
                             "severity": {}, "coverage": {"pages_read": 1, "pages_known": 1,
                                                          "level": "full", "pages_failed": 0},
                             "problems": [], "unlocked": False})
    body = guest(_Row(_AuditStatus.COMPLETED, None))
    assert "failure_class" not in body
    assert "failure_reason" not in body


def test_the_guest_audit_route_is_no_longer_exempt_from_the_response_contract():
    """Виняток знято: маршрут оголошує обидві свої форми моделями."""
    spec = app.openapi()["paths"]["/v1/public/audits/{audit_id}"]["get"]
    schema = spec["responses"]["200"]["content"]["application/json"]["schema"]
    assert _declares_a_model(schema)
    branches = schema.get("anyOf") or schema.get("oneOf") or []
    assert {b["$ref"].rsplit("/", 1)[-1] for b in branches} == {
        "GuestAuditStatusOut", "GuestShortReportOut"}


def test_a_union_of_a_model_and_a_bare_object_is_still_a_hole():
    """Послаблення не сталося: гілка без моделі лишається дірою."""
    assert not _declares_a_model({"anyOf": [{"$ref": "#/components/schemas/X"},
                                            {"type": "object"}]})
    assert not _declares_a_model({})
    assert not _declares_a_model({"type": "object"})


def test_an_old_client_reading_only_the_four_original_keys_still_works(guest):
    """Адитивність: старі ключі на місці, з тими самими типами."""
    body = guest(_Row(_AuditStatus.FAILED, _FailureClass.SITE_BLOCKED))
    assert set(body) >= {"audit_id", "status", "unlocked", "progress"}
    assert isinstance(body["audit_id"], str)
    assert isinstance(body["status"], str)
    assert isinstance(body["unlocked"], bool)
    assert isinstance(body["progress"], dict)


def test_the_cabinet_still_exposes_the_raw_error_and_class():
    """Кабінет не звужено: E-13 додає гостю, а не забирає в автентифікованого."""
    from app.schemas.audit import AttemptOut, AuditDetailOut, AuditOut, TargetOut

    for model in (AuditOut, TargetOut, AttemptOut, AuditDetailOut):
        assert "error" in model.model_fields
        assert "failure_class" in model.model_fields


def test_the_engine_surface_is_untouched_by_this_phase():
    """Цей етап — контракти API. Рушій не змінюється, і це вимірюється."""
    import hashlib

    import app.audit.checks  # noqa: F401  — заповнює реєстр
    from app.audit import versions
    from app.audit.applicability import CHECK_DECLARATIONS
    from app.audit.checks.base import REGISTRY

    assert len(REGISTRY) == 80
    assert len(CHECK_DECLARATIONS) == 80
    # Константи зберігаються рядками — порівнюємо тим типом, який у коді,
    # а не тим, яким число зручно писати в інструкції.
    assert str(versions.DETECTOR_RULES) == "14"
    assert str(versions.SCORING_RULES) == "5"
    assert str(versions.CRAWLER_VERSION) == "4"
    assert versions.detector_version() == "3b9a556ab798"
    assert versions.scoring_version() == "aa4ecc62a5a3"
    rows = sorted(
        f"{c.code}:{c.module.value}:{c.severity.value}:{c.weight}:{c.effort.value}"
        f":{','.join(c.variants)}"
        for c in REGISTRY
    )
    digest = hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16]
    assert digest == "fa42a134eb827580"


def test_the_result_contract_version_did_not_move():
    """Поля адитивні, отже версія контракту не росте — і це теж перевірка."""
    from app.schemas.result import RESULT_CONTRACT_VERSION

    assert RESULT_CONTRACT_VERSION == 2


# ── Ворота 1: тіло відповіді перевіряється моделлю, а не лише схемою ──────
#
# Маршрут віддає готовий `Response`, щоб зберегти приватні заголовки. При
# цьому FastAPI пропускає валідацію `response_model` — отже, оголошений у
# OpenAPI `anyOf` сам по собі нічого не гарантує. Гарантує рядок у коді,
# який валідує словник перед серіалізацією, і саме він перевіряється тут.


def _guest_models():
    from app.schemas.result import GuestAuditStatusOut, GuestShortReportOut

    return GuestAuditStatusOut, GuestShortReportOut


_SHORT_BODY = {
    "audit_id": "11111111-2222-3333-4444-555555555555",
    "url": "https://example.com",
    "origin": "https://example.com",
    "status": "completed",
    "generated_at": "2026-01-01T00:00:00",
    "overall_score": 71,
    "overall_band": "medium",
    "issues_total": 3,
    "severity": {"high": 1, "medium": 2, "low": 0},
    "coverage": {"pages_read": 4, "pages_known": 9, "level": "partial", "pages_failed": 1},
    "problems": [{"problem": "p", "why": "w", "impact_points": 3, "floored": False}],
    "unlocked": False,
}


def test_each_branch_validates_against_exactly_one_declared_model(guest, monkeypatch):
    """Кожне тіло підходить рівно одній оголошеній моделі, а не обом."""
    from pydantic import ValidationError

    from app.application import guest as guest_app

    status_model, short_model = _guest_models()

    failed = guest(_Row(_AuditStatus.FAILED, _FailureClass.SITE_BLOCKED))
    status_model.model_validate(failed)
    with pytest.raises(ValidationError):
        short_model.model_validate(failed)

    monkeypatch.setattr(guest_app, "short_view", lambda audit, **_k: dict(_SHORT_BODY))
    done = guest(_Row(_AuditStatus.COMPLETED, None))
    short_model.model_validate(done)
    with pytest.raises(ValidationError):
        status_model.model_validate(done)


def test_serialized_output_equals_the_validated_model_output(guest, monkeypatch):
    """Надіслані байти — це дамп перевіреної моделі, а не сирий словник."""
    from app.application import guest as guest_app

    status_model, short_model = _guest_models()

    failed = guest(_Row(_AuditStatus.FAILED, _FailureClass.PROVIDER_FAILED))
    assert failed == status_model.model_validate(failed).model_dump(mode="json")

    monkeypatch.setattr(guest_app, "short_view", lambda audit, **_k: dict(_SHORT_BODY))
    done = guest(_Row(_AuditStatus.COMPLETED, None))
    assert done == short_model.model_validate(done).model_dump(mode="json")
    # І він дорівнює тому, що склав `to_short`: валідація нічого не зсунула.
    assert done == _SHORT_BODY


def test_an_unexpected_field_cannot_reach_the_output(guest, monkeypatch):
    """Зайве поле не просочується: контракт або відхиляє його, або не несе."""
    from app.application import guest as guest_app

    polluted = dict(_SHORT_BODY, internal_debug="psi-worker-3 trace", error=_RAW_ERROR)
    monkeypatch.setattr(guest_app, "short_view", lambda audit, **_k: polluted)
    try:
        body = guest(_Row(_AuditStatus.COMPLETED, None))
    except Exception:  # noqa: BLE001 — обидві відповіді правильні
        # Контракт дозволяє або відхилити зайве поле, або не понести його
        # далі. Перший шлях приходить сюди винятком валідації, другий -
        # тихо відкинутим ключем, і тест приймає рівно ці два.
        return
    assert "internal_debug" not in body
    assert "error" not in body
    assert "psi-worker-3" not in json.dumps(body, ensure_ascii=False)


def test_raw_error_on_the_row_cannot_reach_either_branch(guest, monkeypatch):
    """Сире `error` лежить на рядку в обох випадках і не виходить назовні."""
    from app.application import guest as guest_app

    body = guest(_Row(_AuditStatus.FAILED, _FailureClass.INTERNAL_ERROR, error=_RAW_ERROR))
    assert _RAW_ERROR not in json.dumps(body, ensure_ascii=False)

    monkeypatch.setattr(guest_app, "short_view", lambda audit, **_k: dict(_SHORT_BODY))
    body = guest(_Row(_AuditStatus.COMPLETED, None, error=_RAW_ERROR))
    assert _RAW_ERROR not in json.dumps(body, ensure_ascii=False)


def test_the_runtime_payload_matches_the_declared_openapi_schema(guest, monkeypatch):
    """Оголошене й надіслане збігаються: схема описує саме ці тіла."""
    from app.application import guest as guest_app

    spec = app.openapi()["paths"]["/v1/public/audits/{audit_id}"]["get"]
    branches = spec["responses"]["200"]["content"]["application/json"]["schema"]["anyOf"]
    declared = {b["$ref"].rsplit("/", 1)[-1] for b in branches}
    components = app.openapi()["components"]["schemas"]

    failed = guest(_Row(_AuditStatus.FAILED, _FailureClass.CANCELLED))
    assert set(failed) <= set(components["GuestAuditStatusOut"]["properties"])

    monkeypatch.setattr(guest_app, "short_view", lambda audit, **_k: dict(_SHORT_BODY))
    done = guest(_Row(_AuditStatus.COMPLETED, None))
    assert set(done) <= set(components["GuestShortReportOut"]["properties"])
    assert declared == {"GuestAuditStatusOut", "GuestShortReportOut"}


# ── Ворота 2: рядки сторінок не читаються поза оплаченим звітом ───────────
#
# Перелік сторінок коштує запиту. Робити цей запит на безкоштовному екрані
# означало б платити за дані, яких той екран не має права показати, — і
# створювати шлях, яким вони могли б туди потрапити.


class _SpySession:
    """Сесія, яка рахує вибірки `audit_pages` і нічого не виконує."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.statements: list[str] = []

    async def execute(self, statement, *_a, **_k):
        self.statements.append(str(statement))
        rows = self.rows

        class _Result:
            def all(self):
                return rows

            def scalars(self):
                class _Scalars:
                    def all(self_inner):
                        return rows

                return _Scalars()

        return _Result()

    @property
    def page_queries(self) -> int:
        return len([s for s in self.statements if "audit_pages" in s])


@pytest.fixture()
def spy_guest(monkeypatch):
    """Гостьові маршрути з сесією-шпигуном, щоб рахувати вибірки сторінок."""
    from fastapi.testclient import TestClient

    from app.api.routes import public as public_routes
    from app.application import guest as guest_app
    from app.services import audit_service

    state = {"row": None, "unlocked": False, "session": _SpySession()}

    async def _owns(*_a, **_k):
        return True

    async def _unlocked(*_a, **_k):
        return state["unlocked"]

    async def _get(*_a, **_k):
        return state["row"]

    monkeypatch.setattr(guest_app, "owns_audit", _owns)
    monkeypatch.setattr(guest_app, "is_unlocked", _unlocked)
    monkeypatch.setattr(guest_app, "full_view", lambda audit, **_k: dict(_SHORT_BODY))
    monkeypatch.setattr(guest_app, "short_view", lambda audit, **_k: dict(_SHORT_BODY))
    monkeypatch.setattr(audit_service, "get_audit", _get)

    def _dep(annotated):
        return annotated.__metadata__[0].dependency

    app.dependency_overrides[_dep(public_routes.CapabilityDep)] = lambda: object()
    app.dependency_overrides[_dep(public_routes.SessionDep)] = lambda: state["session"]
    client = TestClient(app)

    def call(path_suffix, row, *, unlocked, rows=()):
        state["row"], state["unlocked"] = row, unlocked
        state["session"] = _SpySession(rows)
        reply = client.get(f"/v1/public/audits/{row.id}{path_suffix}")
        return reply, state["session"]

    yield call
    app.dependency_overrides.clear()


def test_the_free_preview_loads_no_page_rows(spy_guest):
    """Безкоштовний перегляд готового аудиту не торкається `audit_pages`."""
    reply, session = spy_guest("", _Row(_AuditStatus.COMPLETED, None), unlocked=False)
    assert reply.status_code == 200
    assert session.page_queries == 0
    assert "inspected_pages" not in reply.text


def test_a_locked_guest_asking_for_the_full_report_loads_no_page_rows(spy_guest):
    """Замкнений повний звіт — 402 і жодної вибірки сторінок."""
    reply, session = spy_guest("/full", _Row(_AuditStatus.COMPLETED, None), unlocked=False)
    assert reply.status_code == 402
    assert session.page_queries == 0
    assert "inspected_pages" not in reply.text


def test_a_failed_audit_loads_no_page_rows(spy_guest):
    """Невдалий і пропущений аудити звіту не мають — і сторінок не читають."""
    for state in (_AuditStatus.FAILED, _AuditStatus.SKIPPED):
        reply, session = spy_guest("", _Row(state, _FailureClass.SITE_UNREACHABLE),
                                   unlocked=False)
        assert reply.status_code == 200
        assert session.page_queries == 0
        assert "inspected_pages" not in reply.text


def test_the_paid_full_report_makes_exactly_one_bounded_page_query(spy_guest):
    """Оплачений звіт читає сторінки один раз, однією обмеженою вибіркою.

    «Обмежена» тут означає три речі в ОДНОМУ запиті: він звужений до
    цього аудиту, впорядкований і має межу. Другий запит по ту саму
    таблицю — хай навіть лише `COUNT(*)` — цей тест завалить.
    """
    rows = [_PageRowForSpy("https://example.com/a", 200, 0, 2),
            _PageRowForSpy("https://example.com/b", 404, 1, 2)]
    reply, session = spy_guest("/full", _Row(_AuditStatus.COMPLETED, None),
                               unlocked=True, rows=rows)
    assert reply.status_code == 200
    assert session.page_queries == 1, "N+1 або зайва вибірка"
    statement = next(s for s in session.statements if "audit_pages" in s)
    assert "WHERE" in statement and "audit_id" in statement
    assert "ORDER BY" in statement and "LIMIT" in statement
    body = reply.json()
    assert body["inspected_pages_total"] == 2
    assert body["inspected_pages_truncated"] is False
    assert [p["url"] for p in body["inspected_pages"]] == ["https://example.com/a",
                                                           "https://example.com/b"]


def test_the_paid_full_report_reports_a_total_larger_than_the_page_it_returns(spy_guest):
    """Повне число приходить із запиту, а не з довжини зрізу.

    Два рядки на руках і 4096 у базі — саме та пара, заради якої існує
    `inspected_pages_truncated`. Якби число бралося з довжини переліку,
    «показано не все» не могло б стати правдою ніколи.
    """
    rows = [_PageRowForSpy("https://example.com/a", 200, 0, 4096),
            _PageRowForSpy("https://example.com/b", 404, 1, 4096)]
    reply, session = spy_guest("/full", _Row(_AuditStatus.COMPLETED, None),
                               unlocked=True, rows=rows)
    assert reply.status_code == 200
    assert session.page_queries == 1
    body = reply.json()
    assert body["inspected_pages_total"] == 4096
    assert body["inspected_pages_truncated"] is True
    assert len(body["inspected_pages"]) == 2


class _PageRowForSpy:
    """Рядок результату запиту сторінок: три колонки плюс віконний рахунок."""

    def __init__(self, url, status_code, depth, total):
        self.url = url
        self.status_code = status_code
        self.depth = depth
        self.total = total
