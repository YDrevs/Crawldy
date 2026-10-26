#!/usr/bin/env bash
# Деплой однієї версії на сервері. Викликає GitHub Actions по SSH.
#
# Ключ деплою в ~/.ssh/authorized_keys користувача `deploy` має forced command:
#
#   command="/opt/crawldy/source/deploy/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA… github-actions
#
# Тоді ключ CI не дає shell: усе, що він може, — передати SHA коміту (він
# приходить у SSH_ORIGINAL_COMMAND), і цей скрипт розгорне саме його.
# Вручну на сервері:  ./deploy.sh <40-символьний SHA>
#
# Порядок: код (compose, Caddyfile, скрипти) → образи з GHCR → міграції й
# перезапуск → перевірка здоровʼя → при провалі відкат на попередню версію.

set -euo pipefail

# Скрипт лежить у репозиторії, а `git checkout` нижче переписує його ж.
# Bash читає файл поступово, тож зміна посеред виконання ламала б деплой:
# виконуємося з копії, а шлях до справжньої теки передаємо явно.
if [[ -z "${CRAWLDY_DEPLOY_DIR:-}" ]]; then
  CRAWLDY_DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  copy="$(mktemp)"
  cp "${BASH_SOURCE[0]}" "$copy"
  export CRAWLDY_DEPLOY_DIR
  exec bash "$copy" "$@"
fi
trap 'rm -f "${BASH_SOURCE[0]}"' EXIT

DEPLOY_DIR="$CRAWLDY_DEPLOY_DIR"
REPO_DIR="$(cd "$DEPLOY_DIR/../.." && pwd)"
COMPOSE=(docker compose -f "$DEPLOY_DIR/docker-compose.prod.yml" --env-file "$DEPLOY_DIR/.env")
LAST_GOOD="$DEPLOY_DIR/.last-good"
HEALTH_TIMEOUT_S="${HEALTH_TIMEOUT_S:-90}"

log() { printf '[deploy %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

sha="${SSH_ORIGINAL_COMMAND:-${1:-}}"
# Лише повний SHA: forced command отримує довільний рядок від клієнта, і
# все, що не схоже на коміт, відкидається до будь-якої дії.
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  log "відмова: очікується 40-символьний SHA коміту"
  exit 2
fi

set -a
# shellcheck source=/dev/null
source "$DEPLOY_DIR/.env"
set +a
: "${SITE_DOMAIN:?SITE_DOMAIN не задано в deploy/.env}"
: "${API_DOMAIN:?API_DOMAIN не задано в deploy/.env}"

exec 9>"$DEPLOY_DIR/.deploy.lock"
flock -n 9 || { log "інший деплой уже йде"; exit 3; }

healthy() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT_S))
  while (( SECONDS < deadline )); do
    if curl -fsS -o /dev/null --max-time 5 "https://$API_DOMAIN/health" \
       && curl -fsS -o /dev/null --max-time 5 "https://$SITE_DOMAIN/"; then
      return 0
    fi
    sleep 3
  done
  return 1
}

start() {
  local tag="$1"
  IMAGE_TAG="$tag" "${COMPOSE[@]}" pull --quiet
  IMAGE_TAG="$tag" "${COMPOSE[@]}" up -d --no-build --remove-orphans
}

previous=""
[[ -f "$LAST_GOOD" ]] && previous="$(cat "$LAST_GOOD")"

log "код → $sha"
git -C "$REPO_DIR" fetch --quiet origin
git -C "$REPO_DIR" checkout --quiet --detach "$sha"

log "образи й перезапуск → $sha"
if start "$sha" && healthy; then
  echo "$sha" > "$LAST_GOOD"
  # Фільтр виходу воркера тут не застосовується: правила прив'язані до
  # фіксованої підмережі й переживають перестворення мереж Docker, а
  # відновлює їх після reboot crawldy-egress.service. Дати користувачу
  # deploy sudo на скрипт, який він сам може редагувати, — це шлях до root.
  docker image prune -f >/dev/null
  log "готово: $sha"
  exit 0
fi

log "ПРОВАЛ: $sha не пройшов перевірку здоровʼя"
"${COMPOSE[@]}" logs --tail 40 api worker migrate || true
if [[ -n "$previous" ]]; then
  log "відкат → $previous"
  git -C "$REPO_DIR" checkout --quiet --detach "$previous"
  if start "$previous" && healthy; then
    log "відкат успішний. Увага: міграції нової версії НЕ відкочено — див. README."
  else
    log "відкат теж не пройшов перевірку — потрібне ручне втручання"
  fi
else
  log "попередньої версії немає — відкатувати нікуди"
fi
exit 1
