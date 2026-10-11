"""Legacy-шар семантики не має шляху в жоден продуктовий потік.

`app/audit/llm/` стоїть ДО скора й уміє створити знахідку, тобто змінити
бал. Він вимкнений (`LLM_ENABLED=false`), але «вимкнений налаштуванням» і
«не може запуститися» — різні гарантії. Тут перевіряється друга.

Мережі немає: усе — читання коду й дефолтів.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _imports_of(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_enrichment_layer_shares_no_code_with_the_legacy_semantic_layer():
    """Новий шлюз не має способу випадково активувати старий шлях.

    Спільний код був би саме таким способом: один імпорт — і задача
    збагачення тягне за собою аналітика, який уміє створювати знахідки.
    """
    for path in (APP / "enrich").rglob("*.py"):
        for module in _imports_of(path):
            assert "audit.llm" not in module, f"{path.name} тягне legacy: {module}"


def test_report_rendering_route_cannot_ask_for_a_live_model_call():
    """`?enrich=true` не купує виклик під час рендеру — структурно.

    Раніше кожне повторне завантаження того самого файлу коштувало
    нового платного виклику, бо результат ніде не зберігався. Тепер
    маршрут просить розширення з `enabled=False`, і це не наслідок
    вимкненого `llm_enabled`, а окрема межа.
    """
    source = (APP / "api" / "routes" / "audits.py").read_text(encoding="utf-8")
    calls = [
        line.strip()
        for line in source.splitlines()
        if "build_owner_extras(" in line and "import" not in line
    ]
    assert calls, "виклик розширення зник — інваріант більше нічим не тримається"
    for call in calls:
        assert "enabled=False" in call, f"маршрут може піти в мережу: {call}"


def test_public_guest_routes_never_mention_the_semantic_or_enrichment_layers():
    """Безкоштовна анонімна воронка лишається детерміністичною."""
    source = (APP / "api" / "routes" / "public.py").read_text(encoding="utf-8").lower()
    for word in ("get_analyst", "llm_enabled", "enrich", "site_understanding"):
        assert word not in source, f"гостьовий маршрут згадує «{word}»"


def test_both_ai_layers_stay_disabled_by_default():
    """Дефолти класу налаштувань, а не значення з .env розробника."""
    from app.core.config import Settings

    assert Settings.model_fields["llm_enabled"].default is False
    assert Settings.model_fields["enrich_enabled"].default is False


def test_legacy_analyst_is_reachable_only_through_its_historical_gate():
    """Викликів legacy-аналітика рівно два, і обидва під власним прапорцем."""
    callers = sorted(
        path.relative_to(APP).as_posix()
        for path in APP.rglob("*.py")
        if "get_analyst" in path.read_text(encoding="utf-8")
        and "audit/llm" not in path.relative_to(APP).as_posix()
    )
    assert callers == ["audit/orchestrator.py", "report/owner_enrich.py"], (
        f"зʼявився новий шлях до legacy-аналітика: {callers}"
    )
