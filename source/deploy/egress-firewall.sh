#!/usr/bin/env bash
# Мережевий фільтр для воркера: з підмережі `crawl` не можна в приватні
# мережі, на метадані хмари й на сам сервер.
#
# Навіщо, якщо в коді є SSRF-перевірка: браузер аудиту відкриває чужі
# сторінки, і два шляхи код закрити не може — перенаправлення всередині
# iframe (його браузер проходить сам) і повторний DNS-резолв у Playwright.
# Цей фільтр закриває обидва на рівні ядра, незалежно від коду.
#
# Запуск (root), після `docker compose up`, і після кожного перезавантаження
# — для цього є `crawldy-egress.service`:
#
#   sudo ./egress-firewall.sh          # встановити правила
#   sudo ./egress-firewall.sh --check  # показати, що встановлено
#
# Ідемпотентний: власний ланцюг очищується й наповнюється заново.

set -euo pipefail

CRAWL_SUBNET="${CRAWL_SUBNET:-172.31.250.0/24}"
CHAIN="CRAWLDY-EGRESS"

BLOCKED=(
  0.0.0.0/8
  10.0.0.0/8
  100.64.0.0/10
  127.0.0.0/8
  169.254.0.0/16      # метадані хмари (169.254.169.254) і link-local
  172.16.0.0/12       # сюди ж мережі Docker: data, web, шлюз crawl
  192.0.0.0/24
  192.168.0.0/16
  198.18.0.0/15
  224.0.0.0/4
  240.0.0.0/4
)

if [[ "${1:-}" == "--check" ]]; then
  iptables -S "$CHAIN"
  iptables -S DOCKER-USER | grep -- "-j $CHAIN" || echo "DOCKER-USER: правило переходу ВІДСУТНЄ"
  iptables -S INPUT | grep -- "-s $CRAWL_SUBNET" || echo "INPUT: правило для $CRAWL_SUBNET ВІДСУТНЄ"
  exit 0
fi

iptables -N "$CHAIN" 2>/dev/null || true
iptables -F "$CHAIN"

# Відповіді на вже дозволені зʼєднання не чіпаємо.
iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for net in "${BLOCKED[@]}"; do
  iptables -A "$CHAIN" -d "$net" -j REJECT --reject-with icmp-net-prohibited
done
iptables -A "$CHAIN" -j RETURN

# Трафік контейнерів іде через FORWARD; Docker лишає ланцюг DOCKER-USER
# саме для правил користувача й не перезаписує його.
iptables -C DOCKER-USER -s "$CRAWL_SUBNET" -j "$CHAIN" 2>/dev/null \
  || iptables -I DOCKER-USER 1 -s "$CRAWL_SUBNET" -j "$CHAIN"

# Звернення до самого сервера (шлюз підмережі, публічна IP) іде через
# INPUT, повз DOCKER-USER: SSH та інші служби хоста воркеру не потрібні.
iptables -C INPUT -s "$CRAWL_SUBNET" -m conntrack --ctstate NEW -j REJECT 2>/dev/null \
  || iptables -I INPUT 1 -s "$CRAWL_SUBNET" -m conntrack --ctstate NEW -j REJECT

# IPv6 у мережі crawl не вмикається (compose не задає `enable_ipv6`), тож
# окремих правил ip6tables тут немає. Увімкнете IPv6 — додайте їх.

echo "Фільтр встановлено для $CRAWL_SUBNET. Перевірка: $0 --check"
