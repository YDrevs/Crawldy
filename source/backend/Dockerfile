# ── збірка залежностей ─────────────────────────────────────────────────
# Компілятор потрібен лише тут, на випадок пакета без готового wheel. У
# runtime-образ потрапляє тільки готове оточення /opt/venv: ні gcc, ні curl
# у контейнері, що ходить на чужі сайти, не потрібні.
FROM python:3.12-slim AS deps

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Спершу лише залежності: цей шар кешується й не перезбирається на кожну
# правку коду. Версії й хеші — з requirements.lock: `pyproject` має лише
# нижні межі, і без lock кожна збірка тягла б найсвіжіше (так selectolax
# 1.0 мовчки зламав імпорт). Пакет, чий хеш не збігся, не встановиться.
WORKDIR /build
COPY requirements.lock ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-deps --require-hashes -r requirements.lock


# ── API ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH \
    # Браузер ставиться в спільний каталог, а не в ~ користувача, який
    # його встановлює (root): інакше `app` його не знайде.
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Непривілейований користувач: процес, що розбирає чужий HTML і запускає
# чужий JS у браузері, не має бути root у своєму контейнері.
RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app

COPY --from=deps /opt/venv /opt/venv

WORKDIR /app
COPY . .
RUN pip install -e . --no-deps

USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Браузер ставиться лише воркеру: рендерить він, а API за інваріантом у
# мережу для аудиту не ходить узагалі. Chromium із системними залежностями
# важить близько 400 МБ, і тягнути їх в образ API немає підстав.
#
# Без цього шару пакет playwright у контейнері є, а виконуваного файла
# немає — рендер падає з «Executable doesn't exist», аудит стає partial, і
# SSR-дельта, вплив third-party, mobile-gap та llm.client_rendered не
# виконуються ніколи. Локально в CLI це непомітно, бо браузер стоїть у
# системі розробника: саме тому дефект прожив усю фазу 2.
FROM base AS worker
USER root
RUN playwright install --with-deps chromium && \
    chmod -R a+rX /ms-playwright
USER app
CMD ["arq", "app.worker.main.WorkerSettings"]
