# Продакшн-образ сайту: збірка окремо, у фінальному образі лише те, що
# потрібно `next start`. Для розробки й далі `docker-compose.yml` з `next dev`.

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Адреса API вшивається в клієнтський бандл під час збірки — змінити її
# потім змінною оточення не можна, лише перезбіркою.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN test -n "$NEXT_PUBLIC_API_URL" || (echo "NEXT_PUBLIC_API_URL is required" >&2 && exit 1)
RUN npm run build


FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

COPY --from=build /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/next.config.mjs ./

# Не root: сервер рендерить сторінки, і вразливість у ньому не має давати
# root у контейнері.
USER node
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-p", "3000", "-H", "0.0.0.0"]
