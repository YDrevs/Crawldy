"""Google Gemini: один провайдер, два явні бекенди виконання.

Продуктовий бекенд — `vertex_ai`: `generateContent` на глобальному
ендпойнті Vertex AI з `gemini-2.5-flash` і заземленням Google Search.
Заземлення 2.5 білиться ЗА ЗАЗЕМЛЕНИЙ ПРОМПТ: «$35 per 1,000 Grounding
Prompts… Even if multiple Grounding Queries are sent, there is only one
charge», і лише коли промпт успішно повернув джерела
(cloud.google.com/vertex-ai/generative-ai/pricing, звірено 2026-09-01).
Тож один запит — рівно одна одиниця білення, і захисний максимум
спроби рахований. Запит надсилає ТОЧНО ті межі, з яких рахується
максимум: `maxOutputTokens`, `thinkingConfig.thinkingBudget = 0`
(документоване вимкнення thinking на 2.5 Flash) і `candidateCount = 1`.
Автентифікація — Application Default Credentials / workload identity
через google-auth; API-ключі (google_api_key, тим паче psi_api_key)
цим бекендом не бувають ніколи.

Бекенд `developer_api` лишається сумісністю: generateContent з
API-ключем для 2.5-моделей (доступних лише користувачам-ветеранам
Developer API — новим Google віддає 404) та Interactions для
gemini-3.x — WATCHLIST: там білиться кожен пошуковий запит, стелі
кількості API не документує, максимум нерахований, і твердий бюджет
закриває платний шлях ще до виклику. Мовчазного фолбека між бекендами
немає: бекенд обирає політика, і він записаний у знімку прогону.

Пошук model-decided в усіх шляхах: примусити його Google API не вміє,
тож explicit-режим — інструкція в промпті, а чи стався пошук насправді,
кажуть метадані відповіді, не наша віра.

httpx навмисно, як у perplexity: один POST не вартий SDK-залежності;
google-auth дає лише токен, а не транспорт.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from app.core import runtime_config as runtime
from app.presence.budget import REQUEST_CEILINGS
from app.presence.contracts import (
    ObservationStatus,
    PresenceProviderError,
    ProviderAnswer,
    ProviderUsage,
)

API_REVISION = "2026-05-20"
TOOL_VERSION = f"interactions-google_search@{API_REVISION}"
TOOL_VERSION_GENERATE = "generate_content-google_search@v1beta"
TOOL_VERSION_VERTEX = "vertex-generate_content-google_search@v1"
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
_GENERATE_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Моделі за-промптного білення заземлення — у developer_api вони йдуть
# через generateContent. Решта (gemini-3.x) лишається на Interactions і
# закрита бюджетом до появи документованої стелі запитів.
_PER_PROMPT_BILLING_MODELS = ("gemini-2.5-flash",)

_VERTEX_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# Кеш облікових даних google-auth: обʼєкт credentials тримає токен і
# сам знає, коли той протух. Значення токена не логується й не
# зберігається ніде, крім памʼяті процесу.
_vertex_credentials: Any = None


def _vertex_host(location: str) -> str:
    """Глобальний ендпойнт живе без регіонального префікса."""
    if location == "global":
        return "aiplatform.googleapis.com"
    return f"{location}-aiplatform.googleapis.com"


def _refresh_vertex_token() -> str:
    """Синхронна частина google-auth; викликається з to_thread."""
    global _vertex_credentials
    import google.auth
    import google.auth.transport.requests

    if _vertex_credentials is None:
        _vertex_credentials, _project = google.auth.default(
            scopes=[_VERTEX_SCOPE])
    if not _vertex_credentials.valid:
        _vertex_credentials.refresh(
            google.auth.transport.requests.Request())
    token = _vertex_credentials.token
    if not isinstance(token, str) or not token:
        raise RuntimeError("google-auth повернув порожній токен")
    return token


class GooglePresenceProvider:
    name = "google"

    def __init__(
        self, model: str, *, timeout_s: float = 90.0,
        backend: str = "vertex_ai",
    ) -> None:
        self.model = model
        self.timeout_s = timeout_s
        self.backend = backend
        if backend == "vertex_ai":
            self.tool_version = TOOL_VERSION_VERTEX
        elif model in _PER_PROMPT_BILLING_MODELS:
            self.tool_version = TOOL_VERSION_GENERATE
        else:
            self.tool_version = TOOL_VERSION

    async def observe(
        self, prompt_text: str, *, country: str | None,
        require_search: bool = False,
    ) -> ProviderAnswer:
        # `country` свідомо не передається: google_search не приймає
        # локації користувача (каталог каже supports_location=False,
        # політика це валідує до запуску). `require_search` теж не має
        # API-важеля — примус лишається на рівні промпту, і це чесно
        # записано в контракті режимів.
        if self.backend == "vertex_ai":
            return await self._observe_vertex(prompt_text)
        if not runtime.get("google_api_key"):
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED, "GOOGLE_API_KEY відсутній",
                incurred_usd=0.0,  # запит не покидав процесу
            )
        if self.model in _PER_PROMPT_BILLING_MODELS:
            return await self._observe_generate_content(prompt_text)
        return await self._observe_interaction(prompt_text)

    def _generation_payload(self, prompt_text: str) -> dict[str, Any]:
        """Тіло generateContent — спільне для Vertex і Developer API.

        Несе РІВНО ті межі, з яких рахується захисний максимум: стелю
        виходу, вимкнений thinking (thinkingBudget=0 — документований
        спосіб на 2.5 Flash) і одного кандидата. Одиниця білення
        заземлення — цей самий промпт, одна на запит.
        """
        ceilings = REQUEST_CEILINGS["google"]
        return {
            "contents": [
                {"role": "user", "parts": [{"text": prompt_text}]},
            ],
            "tools": [{"google_search": {}}],
            "generationConfig": {
                "maxOutputTokens": ceilings.max_output_tokens,
                "candidateCount": 1,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }

    async def _observe_vertex(self, prompt_text: str) -> ProviderAnswer:
        project = runtime.get("google_vertex_project")
        if not project:
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED,
                "GOOGLE_VERTEX_PROJECT відсутній",
                incurred_usd=0.0,  # запит не покидав процесу
            )
        try:
            token = await asyncio.wait_for(
                asyncio.to_thread(_refresh_vertex_token),
                timeout=min(self.timeout_s, 30.0),
            )
        except TimeoutError as exc:
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED,
                "автентифікація Vertex не вклалась у час",
                incurred_usd=0.0,  # модельного запиту не було
            ) from exc
        except Exception as exc:
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED,
                f"облікові дані Vertex недоступні: {exc!r}"[:300],
                incurred_usd=0.0,  # модельного запиту не було
            ) from exc

        location = runtime.get("google_vertex_location") or "global"
        url = (
            f"https://{_vertex_host(location)}/v1/projects/{project}"
            f"/locations/{location}/publishers/google/models/"
            f"{self.model}:generateContent"
        )
        body = await self._post(
            url,
            self._generation_payload(prompt_text),
            headers={"Authorization": f"Bearer {token}"},
            with_api_key=False,
            # Офіційне правило білення Vertex (прайс, 2026-09-01):
            # «You're charged only for requests that return a 200
            # response code» — будь-який інший статус авторитетно
            # НЕ коштує грошей за вхід/вихід, а заземлення білиться
            # лише за успішний промпт із джерелами.
            non_200_incurs=0.0,
        )
        return parse_generate_content(
            body, fallback_model=self.model,
            # Vertex: одиниця білення заземлення зараховується лише
            # коли промпт успішно повернув джерела.
            bill_grounding_on_sources_only=True,
        )

    async def _observe_generate_content(
        self, prompt_text: str
    ) -> ProviderAnswer:
        body = await self._post(
            f"{_GENERATE_BASE}/{self.model}:generateContent",
            self._generation_payload(prompt_text),
        )
        return parse_generate_content(body, fallback_model=self.model)

    async def _observe_interaction(self, prompt_text: str) -> ProviderAnswer:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": prompt_text,
            "tools": [{"type": "google_search"}],
            "generation_config": {
                "max_output_tokens":
                    REQUEST_CEILINGS["google"].max_output_tokens,
            },
        }
        body = await self._post(
            _ENDPOINT, payload, headers={"Api-Revision": API_REVISION})
        return parse_interaction(body, fallback_model=self.model)

    async def _post(
        self, url: str, payload: dict[str, Any],
        *, headers: dict[str, str] | None = None,
        with_api_key: bool = True,
        non_200_incurs: float | None = None,
    ) -> dict[str, Any]:
        """POST з класифікацією долі грошей.

        `non_200_incurs` — що авторитетно відомо про не-200 відповіді:
        0.0 для Vertex (офіційне «charged only for … 200»), None для
        Developer API (авторитетного правила немає — тримаємо резерв).
        Мережевий обрив/таймаут — завжди None: відповіді ми не бачили,
        і жоден документ не скаже, що сталося на тому боці.
        """
        request_headers = {
            "Content-Type": "application/json",
            **(headers or {}),
        }
        if with_api_key:
            request_headers["x-goog-api-key"] = runtime.get("google_api_key") or ""
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(
                    url, json=payload, headers=request_headers)
        except httpx.HTTPError as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, f"мережа: {exc!r}"[:300],
                incurred_usd=None,
            ) from exc

        if response.status_code != 200:
            raise _classified_http_error(
                response.status_code, response.text,
                incurred_usd=non_200_incurs,
            )
        result = response.json()
        return result if isinstance(result, dict) else {}


def _classified_http_error(
    status_code: int, body_text: str, *, incurred_usd: float | None,
) -> PresenceProviderError:
    """HTTP-статус → статус спостереження з читабельною причиною.

    Розрізнення потрібне адмінці: «API вимкнено», «бракує ролі»,
    «модель недоступна» — різні дії власника, і ховати їх за одним
    «HTTP 403» означає розслідування замість налаштування.
    """
    detail = f"HTTP {status_code}: {body_text[:200]}"
    if status_code == 429:
        return PresenceProviderError(
            ObservationStatus.RATE_LIMITED, detail,
            incurred_usd=incurred_usd)
    if status_code in (401, 403):
        hint = "доступ відхилено (перевірте роль aiplatform.user)"
        if "SERVICE_DISABLED" in body_text or "has not been used" in body_text:
            hint = "Vertex AI API вимкнено в проєкті"
        elif status_code == 401:
            hint = "облікові дані не прийнято"
        return PresenceProviderError(
            ObservationStatus.NOT_CONFIGURED, f"{hint}; {detail}",
            incurred_usd=incurred_usd)
    if status_code == 404:
        return PresenceProviderError(
            ObservationStatus.NOT_CONFIGURED,
            f"модель/проєкт недоступні; {detail}",
            incurred_usd=incurred_usd)
    return PresenceProviderError(
        ObservationStatus.PROVIDER_ERROR, detail,
        incurred_usd=incurred_usd)


# Цитати Gemini приходять обгорнуті редіректом vertexaisearch; справжній
# домен джерела провайдер віддає в `title` (перевірено живим смоком:
# title="whatclinic.com", Location 302 веде саме туди). Розгортати
# редірект мережею — 9 зайвих викликів на спостереження; домен із
# провайдерських метаданих — чесна цитата рівня домену без жодного.
_REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)
_DOMAIN_TITLE = re.compile(r"^[a-z0-9][a-z0-9.-]{2,253}\.[a-z]{2,}$", re.I)


def _unwrap_citation(url: str, title: str | None) -> str:
    if any(host in url for host in _REDIRECT_HOSTS):
        if title and _DOMAIN_TITLE.match(title.strip()):
            return f"https://{title.strip().lower()}/"
    return url


def parse_generate_content(
    body: dict[str, Any], *, fallback_model: str,
    bill_grounding_on_sources_only: bool = False,
) -> ProviderAnswer:
    """Офіційна форма generateContent → канонічна відповідь. Окремо від
    I/O, щоб фікстури тестів проходили рівно цим кодом.

    Форма (одна на Vertex і Developer API): текст у
    `candidates[0].content.parts[].text`; заземлення в
    `candidates[0].groundingMetadata` — `webSearchQueries` (виконані
    запити) і `groundingChunks[].web.{uri,title}` (джерела, uri —
    редірект vertexaisearch, домен у title). Спожите — в
    `usageMetadata`.

    `bill_grounding_on_sources_only` кодує офіційне правило Vertex:
    заземлення білиться лише за промпт, що УСПІШНО ПОВЕРНУВ ДЖЕРЕЛА.
    Для Developer API такого твердження в документації немає, тож там
    одиниця консервативно зараховується і за самі виконані запити —
    переоцінити власну витрату безпечно, недооцінити не можна.
    """
    candidates = body.get("candidates") or []
    candidate = candidates[0] if candidates and isinstance(
        candidates[0], dict) else {}

    texts: list[str] = []
    content = candidate.get("content") or {}
    for part in content.get("parts") or []:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])

    grounding = candidate.get("groundingMetadata") or {}
    queries = [q for q in grounding.get("webSearchQueries") or []
               if isinstance(q, str) and q]
    cited: list[str] = []
    for chunk in grounding.get("groundingChunks") or []:
        if not isinstance(chunk, dict):
            continue
        web = chunk.get("web") or {}
        uri = web.get("uri")
        if isinstance(uri, str) and uri:
            unwrapped = _unwrap_citation(uri, web.get("title"))
            if unwrapped not in cited:
                cited.append(unwrapped)

    searched = bool(queries) or bool(cited)
    usage = body.get("usageMetadata") or {}
    # thoughtsTokenCount мусить бути нулем (thinkingBudget=0), але
    # рахується захисно: thinking-токени білляться як вихідні, і якби
    # провайдер знехтував параметром, факт має це показати — саме
    # проти цього стоїть перевірка «факт ≤ максимум» у книзі.
    output_tokens = (int(usage.get("candidatesTokenCount") or 0)
                     + int(usage.get("thoughtsTokenCount") or 0))
    input_tokens = (int(usage.get("promptTokenCount") or 0)
                    + int(usage.get("toolUsePromptTokenCount") or 0))
    # Одиниця білення 2.5 — заземлений промпт, максимум одна на запит;
    # кількість внутрішніх запитів на білення не впливає. Vertex
    # зараховує її лише за джерела (офіційне правило), Developer API —
    # і за виконані запити без джерел (консервативно).
    billed_grounding = bool(cited) if bill_grounding_on_sources_only \
        else searched
    response_id = body.get("responseId")
    return ProviderAnswer(
        text="".join(texts),
        cited_urls=cited,
        searched=searched,
        search_queries=queries,
        model=str(body.get("modelVersion") or fallback_model),
        usage=ProviderUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            searches=1 if billed_grounding else 0,
        ),
        provider_request_id=(
            str(response_id) if isinstance(response_id, str) else None
        ),
        raw=body,
    )


def parse_interaction(body: dict[str, Any], *, fallback_model: str) -> ProviderAnswer:
    """Офіційна форма Interactions → канонічна відповідь. Окремо від I/O,
    щоб фікстури тестів проходили рівно цим кодом."""
    texts: list[str] = []
    cited: list[str] = []
    queries: list[str] = []
    search_calls = 0
    for step in body.get("steps") or []:
        if not isinstance(step, dict):
            continue
        kind = step.get("type")
        if kind == "google_search_call":
            search_calls += 1
            for q in step.get("queries") or []:
                if isinstance(q, str) and q and q not in queries:
                    queries.append(q)
        elif kind == "model_output":
            for block in step.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                texts.append(str(block.get("text") or ""))
                for note in block.get("annotations") or []:
                    if (isinstance(note, dict)
                            and note.get("type") == "url_citation"):
                        url = note.get("url")
                        if isinstance(url, str) and url:
                            unwrapped = _unwrap_citation(
                                url, note.get("title"))
                            if unwrapped not in cited:
                                cited.append(unwrapped)

    usage = body.get("usage") or {}
    interaction_id = body.get("id")
    return ProviderAnswer(
        text="".join(texts),
        cited_urls=cited,
        searched=search_calls > 0,
        search_queries=queries,
        model=str(body.get("model") or fallback_model),
        usage=ProviderUsage(
            input_tokens=int(usage.get("total_input_tokens") or 0),
            output_tokens=int(usage.get("total_output_tokens") or 0),
            searches=search_calls,
        ),
        provider_request_id=(
            str(interaction_id) if isinstance(interaction_id, str) else None
        ),
        raw=body,
    )
