# Деплой Crawldy на VPS

Один сервер, Docker Compose, Caddy з автоматичним HTTPS. Назовні відкриті лише
порти 22 (SSH), 80 і 443.

```
інтернет ──443──▶ Caddy ──▶ frontend:3000   (SITE_DOMAIN)
                       └──▶ api:8000        (API_DOMAIN)
                               │
               мережа data (без виходу назовні): postgres, redis, api, worker
                               │
               worker ──▶ мережа crawl ──▶ лише публічний інтернет (egress-firewall.sh)
```

## 1. Сервер

Ubuntu 24.04 LTS або Debian 12, від 4 ГБ RAM (Chromium воркера їсть памʼять).

```bash
# вхід лише за ключем, root — без пароля
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# автоматичні оновлення безпеки
sudo apt update && sudo apt install -y unattended-upgrades && sudo dpkg-reconfigure -plow unattended-upgrades

# фаєрвол хоста
sudo apt install -y ufw
sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
sudo ufw enable

# Docker (офіційний репозиторій)
curl -fsSL https://get.docker.com | sudo sh
```

> **Docker обходить ufw.** Опублікований порт контейнера (`ports:`) відкритий в
> інтернет незалежно від правил ufw. Тому в `docker-compose.prod.yml` порти
> публікує лише Caddy. Не додавайте `ports:` до postgres, redis чи api.

## 2. DNS

Дві A-записи на IP сервера, наприклад `crawldy.ai` і `api.crawldy.ai`. Без них
Caddy не отримає сертифікати.

## 3. Код і секрети

```bash
sudo mkdir -p /opt/crawldy && sudo chown $USER /opt/crawldy
git clone https://github.com/YDrevs/Crawldy.git /opt/crawldy
cd /opt/crawldy/source

cp deploy/.env.example deploy/.env
cp backend/.env.example backend/.env
chmod 600 deploy/.env backend/.env
```

**`deploy/.env`**: домени, пошта для Let's Encrypt, паролі бази й Redis
(`openssl rand -hex 32` для кожного).

**`backend/.env`**: обовʼязково заповнити

| Змінна | Значення |
|---|---|
| `API_KEYS` | порожньо (службовий ключ не потрібен) або `openssl rand -hex 32`. Ключ із прикладу прод не прийме. |
| `SECRETS_KEY` | `openssl rand -hex 32`. Втратите — не розшифруєте збережені в адмінці ключі. |
| `IP_HASH_SALT` | `openssl rand -hex 32` |
| `MAIL_SMTP_HOST`, `MAIL_SENDER`, `MAIL_SMTP_*` | пошта клієнтам; без них прод не стартує |
| `PADDLE_*`, `TURNSTILE_*`, `CONTACT_*` | за потребою, див. HANDOFF.md §11 |
| `ALLOW_PRIVATE_HOSTS` | `false`. На ньому тримається SSRF-захист. |

`APP_ENV`, `DATABASE_URL`, `REDIS_URL`, `PUBLIC_APP_URL`, `CORS_ORIGINS`,
`TRUST_PROXY_HEADERS` і `TRUSTED_PROXY_HOPS` задає compose. Значення в
`backend/.env` для них ігноруються.

## 4. Запуск

```bash
cd /opt/crawldy/source/deploy
docker compose -f docker-compose.prod.yml --env-file .env up -d --build

# фільтр вихідного трафіку воркера + автозапуск після reboot
sudo chmod +x egress-firewall.sh
sudo cp crawldy-egress.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now crawldy-egress
sudo ./egress-firewall.sh --check
```

Перший адміністратор: зареєструйтесь на сайті, потім

```bash
docker compose -f docker-compose.prod.yml exec api \
  python scripts/grant_platform_role.py --email you@example.com --role admin
```

## 5. Перевірка після запуску

```bash
# HTTPS і заголовки
curl -sI https://$SITE_DOMAIN | grep -iE "strict-transport|content-security|x-frame"
curl -s -o /dev/null -w "%{http_code}\n" https://$API_DOMAIN/docs      # 404: документації в проді немає

# Назовні не видно ні бази, ні Redis, ні API напряму (запускати з ІНШОЇ машини)
nc -zv <IP> 5432 6379 8000      # усі три мають відмовити

# Воркер не дістається до метаданих і приватних мереж, але бачить інтернет
docker compose -f docker-compose.prod.yml exec worker python -c "import httpx; print(httpx.get('https://example.com').status_code)"
docker compose -f docker-compose.prod.yml exec worker python -c "import httpx; httpx.get('http://169.254.169.254/', timeout=3)"   # має впасти
```

## 6. Оновлення

```bash
cd /opt/crawldy && git pull
cd source/deploy && docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

Міграції виконує сервіс `migrate` перед стартом API. Черга при оновленні має
бути порожньою: завдання з попереднього формату воркер не прочитає.

Оновлення Python-залежностей — лише через lockfile:

```bash
cd source/backend
uv pip compile pyproject.toml --universal --python-version 3.12 --generate-hashes --no-header -o requirements.lock
pytest -q    # і лише потім коміт
```

## 7. Резервні копії

PostgreSQL — єдине сховище даних. Щоденний дамп поза сервер:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U crawldy -Fc crawldy > crawldy-$(date +%F).dump
```

Копію `backend/.env` (особливо `SECRETS_KEY`) тримайте окремо від дампів.

## Що цей конфіг не робить

- **Не перевірений на справжньому VPS.** Стек піднімався локально; правила
  `egress-firewall.sh` на реальному сервері перевірте командами з розділу 5.
- **IPv6:** у мережі `crawl` вимкнений; увімкнете — додайте правила `ip6tables`.
- **Воркер бачить базу й Redis** через мережу `data` — без цього він не
  працює. Їх захищають паролі й SSRF-перевірка в коді, не фільтр.
- **Моніторинг, алерти, ротація логів** — поза цим конфігом.
