FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Процеси не працюють від root. Воркер відкриває чужі сайти в Chromium,
# а той у контейнері живе без власної пісочниці: вразливість рендерера
# не має ставати root у контейнері, поруч із доступом до бази й черги.
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Спершу лише залежності: цей шар кешується й не перезбирається на кожну
# правку коду. Сам пакет поставити тут не можна — app/ ще не скопійований,
# а pyproject оголошує його явно.
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt && \
    pip install -r /tmp/requirements.txt

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
#
# Ставить системні пакети, тож root лише на цей крок. Браузер лягає в
# PLAYWRIGHT_BROWSERS_PATH, а не в домашню теку root, — інакше
# користувач `app` його не побачить.
FROM base AS worker
USER root
RUN playwright install --with-deps chromium
USER app
CMD ["arq", "app.worker.main.WorkerSettings"]
