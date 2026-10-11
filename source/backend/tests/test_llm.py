"""Семантичний шар: межі, бюджет і чесність про власне мовчання.

Жоден тест не звертається до API. Аналітик — протокол саме для того,
щоб перевірка поведінки не коштувала грошей.
"""

from __future__ import annotations

import pytest

from app.audit.llm import NullAnalyst, get_analyst
from app.audit.llm.base import PageInsight, SiteBrief


class FakeAnalyst:
    """Рахує звернення: бюджет перевіряється кількістю, а не наміром."""

    name = "fake"

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.seen: list[str] = []

    async def read_page(self, url: str, title: str, text: str) -> PageInsight:
        self.seen.append(url)
        if self.error:
            return PageInsight(url=url, analysed=False, error=self.error)
        return PageInsight(url=url, analysed=True, summary=f"про {title}", main_query="що це")

    async def brief(self, origin: str, pages: list[tuple[str, str]]) -> SiteBrief:
        if self.error:
            return SiteBrief(analysed=False, error=self.error)
        return SiteBrief(analysed=True, name="Acme", tagline="робимо штуки")


@pytest.mark.asyncio
async def test_null_analyst_states_the_reason_instead_of_pretending():
    """«Аналізу не було» без причини читається як збій продукту."""
    analyst = NullAnalyst("не заданий ключ ANTHROPIC_API_KEY")

    page = await analyst.read_page("https://example.com/", "Головна", "текст")
    brief = await analyst.brief("https://example.com", [])

    assert page.analysed is False
    assert page.error == "не заданий ключ ANTHROPIC_API_KEY"
    assert page.summary == "", "порожній переказ не можна сплутати зі справжнім"
    assert brief.analysed is False


def test_disabled_by_default():
    """Єдина частина аудиту, що коштує грошей за виклик. Вмикати її
    мовчки за клієнта не можна.

    Перевіряємо саме дефолт класу налаштувань, а не поточне значення:
    воно береться з .env розробника, і тест, який на нього спирається,
    червонів би на одній машині й зеленів на іншій.
    """
    from app.core.config import Settings

    assert Settings.model_fields["llm_enabled"].default is False


def test_explicitly_disabled_says_so():
    analyst = get_analyst(enabled=False)

    assert analyst.name == "null"
    assert "вимкнено" in analyst.reason  # type: ignore[attr-defined]


def test_enabled_without_a_key_still_refuses_and_says_why(monkeypatch):
    monkeypatch.setattr("app.audit.llm.factory.settings.anthropic_api_key", None)

    analyst = get_analyst(enabled=True)

    assert analyst.name == "null"
    assert "ключ" in analyst.reason  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_page_insight_defaults_do_not_accuse_the_site():
    """answers_query за замовчуванням True: поки не перевірили — не звинувачуємо."""
    insight = PageInsight(url="https://example.com/")

    assert insight.answers_query is True
    assert insight.missing == []


# ── форма запиту й розбір відповіді, без мережі ────────────────────────────


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str = "", stop_reason: str = "end_turn") -> None:
        self.stop_reason = stop_reason
        self.content = [_Block(text)] if text else []


class _Messages:
    def __init__(self, response: _Response) -> None:
        self._response = response
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class _Client:
    def __init__(self, response: _Response) -> None:
        self.messages = _Messages(response)

    async def close(self) -> None:
        return None


def _analyst_with(response: _Response):
    from app.audit.llm.anthropic_analyst import AnthropicAnalyst

    analyst = AnthropicAnalyst(model="claude-opus-5")
    analyst._client = _Client(response)
    return analyst


VALID = (
    '{"summary": "сторінка про доставку", "main_query": "скільки коштує доставка",'
    ' "answers_query": true, "missing": [], "entities": ["Нова пошта"]}'
)


@pytest.mark.asyncio
async def test_request_asks_for_a_schema_not_free_text():
    """Без json_schema модель повертає прозу, і розбір ламається на першій
    сторінці, де вона вирішить відповісти інакше."""
    analyst = _analyst_with(_Response(VALID))
    await analyst.read_page("https://example.com/", "Доставка", "текст сторінки")

    sent = analyst._client.messages.calls[0]
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert "summary" in sent["output_config"]["format"]["schema"]["properties"]
    assert sent["model"] == "claude-opus-5"


@pytest.mark.asyncio
async def test_valid_answer_is_parsed_into_the_insight():
    analyst = _analyst_with(_Response(VALID))

    insight = await analyst.read_page("https://example.com/", "Доставка", "текст")

    assert insight.analysed is True
    assert insight.main_query == "скільки коштує доставка"
    assert insight.entities == ["Нова пошта"]


@pytest.mark.asyncio
async def test_refusal_is_handled_before_reading_content():
    """Відмова приходить успішним HTTP 200 з порожнім content. Код, який
    одразу бере content[0], падає саме тут — і саме тоді, коли клієнт
    аудитує щось незвичне."""
    analyst = _analyst_with(_Response("", stop_reason="refusal"))

    insight = await analyst.read_page("https://example.com/", "Сторінка", "текст")

    assert insight.analysed is False
    assert "відмов" in insight.error


@pytest.mark.asyncio
async def test_unparseable_answer_degrades_instead_of_raising():
    analyst = _analyst_with(_Response("вибачте, не можу"))

    insight = await analyst.read_page("https://example.com/", "Сторінка", "текст")

    assert insight.analysed is False
    assert "JSON" in insight.error


@pytest.mark.asyncio
async def test_long_pages_are_trimmed_before_sending():
    """Довша сторінка коштує більше, а відповідь дає вже перша частина."""
    from app.audit.llm.anthropic_analyst import MAX_PAGE_CHARS

    analyst = _analyst_with(_Response(VALID))
    await analyst.read_page("https://example.com/", "Довга", "слово " * 20000)

    prompt = analyst._client.messages.calls[0]["messages"][0]["content"]
    assert len(prompt) < MAX_PAGE_CHARS + 500


# --- факти рівня сайту --------------------------------------------------

FACTS_JSON = (
    '{"facts": ['
    '{"key": "offering", "stated": true, "quote": "Ремонт ноутбуків", "url": "https://e.com/"},'
    '{"key": "location", "stated": false, "quote": "", "url": ""},'
    '{"key": "contact", "stated": true, "quote": "0671112233", "url": "https://e.com/"},'
    '{"key": "pricing", "stated": false, "quote": "", "url": ""}'
    '], "serves_an_area": true, "sells_listed_items": true}'
)


@pytest.mark.asyncio
async def test_facts_request_carries_the_page_urls():
    """Без URL модель не може сказати, де саме знайшла факт, а твердження
    без адреси сторінки клієнт не перевірить."""
    analyst = _analyst_with(_Response(FACTS_JSON))
    await analyst.facts(
        "https://e.com",
        [("https://e.com/", "Головна", "текст"), ("https://e.com/contacts", "Контакти", "текст")],
    )

    sent = analyst._client.messages.calls[0]
    prompt = sent["messages"][0]["content"]
    assert "https://e.com/contacts" in prompt
    assert sent["output_config"]["format"]["schema"]["required"] == [
        "facts", "serves_an_area", "sells_listed_items"
    ]


@pytest.mark.asyncio
async def test_facts_are_parsed_with_their_evidence():
    analyst = _analyst_with(_Response(FACTS_JSON))
    facts = await analyst.facts("https://e.com", [("https://e.com/", "Головна", "текст")])

    assert facts.analysed
    assert [f.key for f in facts.missing()] == ["location", "pricing"]
    assert facts.serves_an_area and facts.sells_listed_items
    assert facts.read_pages == ["https://e.com/"]
    stated = {f.key: f for f in facts.facts}
    assert stated["offering"].quote == "Ремонт ноутбуків"


@pytest.mark.asyncio
async def test_a_fact_the_model_skipped_is_not_held_against_the_site():
    """Мовчання — не доказ відсутності. Звинуватити сайт у тому, чого ми
    не питали, гірше за пропуск."""
    analyst = _analyst_with(
        _Response('{"facts": [{"key": "pricing", "stated": false, "quote": "", "url": ""}],'
                  ' "serves_an_area": false, "sells_listed_items": false}')
    )
    facts = await analyst.facts("https://e.com", [("https://e.com/", "Головна", "текст")])

    assert [f.key for f in facts.missing()] == ["pricing"]


@pytest.mark.asyncio
async def test_facts_failure_says_why_instead_of_claiming_all_is_well():
    analyst = _analyst_with(_Response("", stop_reason="refusal"))
    facts = await analyst.facts("https://e.com", [("https://e.com/", "Головна", "текст")])

    assert not facts.analysed
    assert facts.error
    assert facts.missing() == []


@pytest.mark.asyncio
async def test_null_analyst_reports_facts_as_unanalysed():
    from app.audit.llm.base import NullAnalyst

    facts = await NullAnalyst("ключа немає").facts("https://e.com", [])

    assert not facts.analysed
    assert facts.error == "ключа немає"


@pytest.mark.asyncio
async def test_effort_is_not_sent_to_models_that_reject_it():
    """Haiku 4.5 відповідає на effort помилкою 400. Оскільки збій API аудиту
    не валить, це виглядало як «модель нічого не знайшла»: на дешевій моделі
    чек мовчав на всіх сайтах, зокрема там, де проблеми справжні."""
    from app.audit.llm.anthropic_analyst import AnthropicAnalyst

    analyst = AnthropicAnalyst(model="claude-haiku-4-5")
    analyst._client = _Client(_Response(VALID))
    await analyst.read_page("https://e.com/", "Головна", "текст")

    sent = analyst._client.messages.calls[0]["output_config"]
    assert "effort" not in sent
    assert sent["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_effort_is_still_sent_to_models_that_accept_it():
    analyst = _analyst_with(_Response(VALID))
    await analyst.read_page("https://e.com/", "Головна", "текст")

    assert "effort" in analyst._client.messages.calls[0]["output_config"]


# --- вибір моделі -------------------------------------------------------

def test_catalogue_has_exactly_one_default():
    from app.audit.llm.models import AVAILABLE_MODELS, DEFAULT_MODEL

    defaults = [m.id for m in AVAILABLE_MODELS if m.default]
    assert defaults == [DEFAULT_MODEL]


def test_unknown_model_refuses_loudly_instead_of_falling_back(monkeypatch):
    """Тихий відкат на дефолт дав би звіт, порахований не тією моделлю,
    про яку просили, — а різниця між ними доходить до 13 балів."""
    from app.audit.llm.factory import get_analyst

    monkeypatch.setattr("app.audit.llm.factory.settings.llm_enabled", True)
    monkeypatch.setattr("app.audit.llm.factory.settings.anthropic_api_key", "sk-test")

    analyst = get_analyst(model="gpt-4")

    assert analyst.name == "null"
    assert "gpt-4" in analyst.reason


def test_chosen_model_reaches_the_analyst(monkeypatch):
    from app.audit.llm.factory import get_analyst

    monkeypatch.setattr("app.audit.llm.factory.settings.llm_enabled", True)
    monkeypatch.setattr("app.audit.llm.factory.settings.anthropic_api_key", "sk-test")

    analyst = get_analyst(model="claude-haiku-4-5")

    assert analyst._model == "claude-haiku-4-5"


def test_options_carry_the_model_through_the_queue():
    """Опції їдуть у БД як JSON і повертаються звідти у воркер: вибір
    моделі має пережити цю дорогу, інакше воркер порахує іншою."""
    from app.audit.orchestrator import AuditOptions

    options = AuditOptions.from_dict({"llm_model": "claude-haiku-4-5", "llm": True})

    assert options.llm_model == "claude-haiku-4-5"
    assert options.llm is True


def test_schema_rejects_a_model_that_is_not_in_the_catalogue():
    import pytest as _pytest
    from pydantic import ValidationError

    from app.schemas.audit import AuditOptionsIn

    with _pytest.raises(ValidationError):
        AuditOptionsIn(llm_model="gpt-5")


def test_schema_accepts_every_model_the_interface_offers():
    """UI бере список із того самого каталогу. Якщо валідація його не
    приймає, користувач обирає модель і отримує 422."""
    from app.audit.llm.models import MODEL_IDS
    from app.schemas.audit import AuditOptionsIn

    for model in MODEL_IDS:
        assert AuditOptionsIn(llm_model=model).llm_model == model
