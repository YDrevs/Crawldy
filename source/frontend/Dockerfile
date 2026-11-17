# Фронт для хостингу (Railway). Локально фронт іде через compose з
# `npm run dev`, цей файл його не стосується.

# ── збірка ─────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Next вшиває ці значення під час `next build`: адресу API — у бандл і в
# connect-src CSP, HSTS — у заголовки. Railway передає змінні сервісу як
# build-arg лише тоді, коли вони оголошені тут.
ARG NEXT_PUBLIC_API_URL
ARG HSTS_ENABLED=false
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} HSTS_ENABLED=${HSTS_ENABLED}
RUN test -n "$NEXT_PUBLIC_API_URL" || (echo "NEXT_PUBLIC_API_URL не задано" >&2; exit 1)
RUN npm run build && npm prune --omit=dev

# ── запуск ─────────────────────────────────────────────────────────────
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

COPY --from=build /app/package.json /app/next.config.mjs /app/security-headers.mjs ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/public ./public
COPY --from=build --chown=node:node /app/.next ./.next

# Непривілейований користувач з образу node.
USER node
# PORT задає хостинг; без нього — 3000.
CMD ["sh", "-c", "exec node_modules/.bin/next start -H 0.0.0.0 -p ${PORT:-3000}"]
