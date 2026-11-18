# SkillQuest ⚔️

Персональная платформа саморазвития с механиками RPG: выполняйте реальные задачи, получайте XP, повышайте уровень, прокачивайте навыки и открывайте достижения.

**Стек:** Python 3 (только стандартная библиотека) · SQLite · Vanilla JS (ES modules) · SVG-графики.
Никаких `pip install`, `npm install`, облаков и платных API.

- [Локальный запуск](#локальный-запуск)
- [Резервные копии и восстановление](#резервные-копии-и-восстановление)
- [Развёртывание на сервере](#развёртывание-на-сервере)
- [Переменные окружения](#переменные-окружения)
- [Возможности](#возможности) · [Структура](#структура-проекта) · [Решения и ограничения](#решения-и-ограничения)

---

## Локальный запуск
Нужен Python **3.10+** (проверено на 3.14). Больше ничего.

```bash
cd SkillQuest
python3 run.py            # → http://127.0.0.1:8000
```
Параметры: `--open` (открыть браузер), `--port 8010`, `--quiet` (без логов). Остановка — `Ctrl+C`.
База — файл `data/skillquest.db`, создаётся автоматически; данные сохраняются между перезапусками.

По умолчанию сервер слушает только `127.0.0.1`, и пароль не нужен. Хотите пароль и локально:
```bash
SKILLQUEST_BASIC_AUTH='me:очень-длинный-пароль-123' python3 run.py
```

**Демо-данные** (только для пустой базы): `python3 -m backend.seed_demo`. Начать с нуля — удалить `data/` или **Profile → Reset progress**.

**Тесты:**
```bash
python3 -m unittest discover -s tests
```
Поднимают реальные серверы на временных базах и **не трогают** `data/`.

---

## Резервные копии и восстановление
Используется онлайн-API резервного копирования SQLite: копия согласована даже при работающем сервере (в том числе содержимое WAL). Каждая копия проходит `integrity_check` и получает итоговое имя только после успешной проверки; права `600`; хранится N последних (по умолчанию 14).

```bash
python3 -m backend.backup                          # → ./backups/skillquest-ГГГГММДД-ЧЧММСС.db
python3 -m backend.backup --dir /mnt/usb --keep 30
python3 -m backend.backup --loop 86400             # демон: раз в сутки
```

**Восстановление** (сначала **остановите сервер**):
```bash
python3 -m backend.restore backups/skillquest-20261118-030000.db          # проверка без изменений
python3 -m backend.restore backups/skillquest-20261118-030000.db --yes    # восстановить
```
Перед заменой копия проверяется (битый или чужой файл отклоняется, ничего не меняется), а текущая база сохраняется рядом как `skillquest.db.before-restore-<время>` — она не уничтожается. Устаревшие `-wal`/`-shm` удаляются.

> Резервные копии на том же диске не защищают от потери диска. Периодически копируйте их на другой носитель/сервер.

---

## Развёртывание на сервере
Схема: **Caddy (HTTPS, единственный публичный порт) → app (закрытая сеть) + backup (ежедневные копии)**. Вход защищён HTTP Basic Auth на уровне приложения.

> ⚠️ Файлы конфигурации (`Dockerfile`, `docker-compose.yml`, `deploy/Caddyfile`, `deploy/nginx.conf`) подготовлены, но **не запускались** — на машине разработки не было Docker, Caddy и Nginx. Автоматически проверены только синтаксис YAML и содержимое файлов (см. тесты). Первый запуск на сервере проведите как приёмочный тест по чек-листу ниже.

### 1. Подготовка сервера (Ubuntu/Debian)
1. **Домен:** создайте DNS-запись `A` (и `AAAA`) `quest.example.com → IP сервера`.
2. **Docker Engine + Compose plugin:** установите по официальной инструкции https://docs.docker.com/engine/install/ (`docker compose version` должен работать).
3. **Файрвол** — открыть только SSH и веб:
   ```bash
   sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443 && sudo ufw enable
   ```
   Порт 8000 наружу **не** открывается: приложение доступно только через Caddy.
4. **Код:** скопируйте проект на сервер (`git clone …` или `rsync -a SkillQuest/ server:~/skillquest/`, без папки `data/`).
5. **Секреты:**
   ```bash
   cd ~/skillquest
   cp .env.example .env && chmod 600 .env
   python3 -c "import secrets; print('me:' + secrets.token_urlsafe(24))"   # → вставьте в SKILLQUEST_BASIC_AUTH
   nano .env                                                                 # SKILLQUEST_DOMAIN, ACME_EMAIL, пароль
   ```
   `.env` в `.gitignore` и `.dockerignore`: ни в репозиторий, ни в образ он не попадает. Приложение **не запустится** с заглушкой из `.env.example` и с паролем короче 12 символов; `docker compose` не стартует без обязательных переменных.
6. **Запуск:**
   ```bash
   docker compose up -d --build
   docker compose ps          # app должен быть healthy
   docker compose logs -f caddy app
   ```
   Caddy сам получит сертификат Let's Encrypt (нужны открытые 80/443 и корректный DNS).

### 2. Приёмочная проверка после первого запуска
```bash
curl -sI https://quest.example.com | head -1                     # ожидается 401
curl -s  https://quest.example.com/api/health                    # {"status": "ok"} без пароля (для мониторинга)
curl -s -u 'me:ВАШ_ПАРОЛЬ' https://quest.example.com/api/dashboard | head -c 200   # данные
curl -sI http://quest.example.com | head -1                      # 308 → https
```
Затем откройте сайт в браузере, создайте и выполните миссию, выполните `docker compose up -d --force-recreate app` и убедитесь, что данные на месте.

### 3. Перенос существующих локальных данных на сервер
```bash
# на своём компьютере (сервер остановить не нужно — копия согласованная)
python3 -m backend.backup --dir ./to-server
scp to-server/skillquest-*.db user@server:~/skillquest/
# на сервере
docker compose stop app backup
docker compose cp skillquest-*.db backup:/backups/        # положить в том резервных копий
docker compose run --rm --no-deps backup python -m backend.restore /backups/skillquest-ГГГГММДД-ЧЧММСС.db --db /data/skillquest.db --yes
docker compose up -d
```

### 4. Резервные копии на сервере
Сервис `backup` делает копию раз в сутки (`BACKUP_INTERVAL_SECONDS`) и хранит `BACKUP_KEEP` последних в томе `skillquest-backups`.
```bash
docker compose logs --tail 5 backup                          # проверить, что копии создаются
docker compose cp backup:/backups/. ./offsite-copy/          # забрать копии с сервера (делайте регулярно, например cron + rsync)
```

### 5. Восстановление на сервере
```bash
docker compose stop app backup
docker compose run --rm --no-deps backup python -m backend.restore /backups/skillquest-ГГГГММДД-ЧЧММСС.db --db /data/skillquest.db --yes
docker compose up -d
```
Текущая база сохранится в томе данных как `skillquest.db.before-restore-<время>`.

### 6. Обновление
```bash
git pull   # или rsync новой версии
docker compose up -d --build
```
Данные лежат в именованном томе `skillquest-data` и переживают пересоздание контейнеров (`down`, `up --force-recreate`, пересборку образа). **Не** используйте `docker compose down -v` — флаг `-v` удаляет тома вместе с данными.

### Nginx вместо Caddy (без Docker или со своим Nginx)
Готовый пример: [`deploy/nginx.conf`](deploy/nginx.conf) (HTTP→HTTPS, TLS 1.2/1.3, HSTS, лимит запросов, перезапись `X-Forwarded-For`). Приложение запускайте на `127.0.0.1:8000` с `SKILLQUEST_TRUST_PROXY=1`, `SKILLQUEST_BASIC_AUTH`, `SKILLQUEST_ALLOWED_HOSTS=quest.example.com`; сертификаты — `certbot`.

### Что защищает приложение
| Мера | Где |
|---|---|
| HTTPS, HSTS, автопродление сертификата | Caddy / Nginx |
| HTTP Basic Auth на весь сайт и API (кроме `/api/health`), сравнение в постоянное время | приложение |
| Блокировка перебора: 10 неудачных входов → 429 на 5 минут (по IP клиента) | приложение |
| Отказ запуска на внешнем адресе без пароля / со слабым или шаблонным паролем | `run.py` |
| Проверка `Host` (DNS-rebinding), `Origin` и `Content-Type: application/json` (CSRF) | приложение |
| CSP, `nosniff`, `X-Frame-Options`, `Referrer-Policy` | приложение |
| Непривилегированный пользователь, `read_only`, `cap_drop: ALL`, `no-new-privileges`, лимиты памяти и процессов | docker-compose |
| Пароль только в `.env` (права 600), не в образе, не в compose-файле, не в логах | проверено тестами |

---

## Переменные окружения
| Переменная | По умолчанию | Назначение |
|---|---|---|
| `HOST` / `PORT` | `127.0.0.1` / `8000` | адрес и порт |
| `SKILLQUEST_DB` | `data/skillquest.db` | путь к SQLite |
| `SKILLQUEST_BASIC_AUTH` | — | `user:password`, мин. 12 символов в пароле |
| `SKILLQUEST_BASIC_AUTH_FILE` | — | то же, но значение читается из файла (Docker/K8s secrets); `…_AUTH` имеет приоритет |
| `SKILLQUEST_ALLOWED_HOSTS` | — | допустимые имена хоста через запятую; `localhost`/`127.0.0.1` разрешены всегда |
| `SKILLQUEST_TRUST_PROXY` | `0` | брать IP клиента из `X-Forwarded-For` (включать **только** за прокси, который его перезаписывает) |
| `SKILLQUEST_ALLOW_NO_AUTH` | `0` | разрешить внешний адрес без пароля (только если аутентификацию делает доверенный прокси) |
| `SKILLQUEST_AUTH_MAX_FAILURES` / `…_LOCKOUT_SECONDS` | `10` / `300` | параметры блокировки перебора |
| `SKILLQUEST_REQUEST_TIMEOUT` | `30` | таймаут сокета, сек |
| `SKILLQUEST_BACKUP_DIR` / `…_KEEP` | `backups` / `14` | параметры `backend.backup` |
| `SKILLQUEST_DOMAIN`, `ACME_EMAIL`, `BACKUP_INTERVAL_SECONDS`, `BACKUP_KEEP` | см. `.env.example` | используются `docker-compose.yml` |

---

## Возможности
| Раздел | Что внутри |
|---|---|
| **Dashboard** | Уровень, XP, прогресс, задания на сегодня, streak, неделя, последние достижения, срез навыков |
| **Missions** | Создание/правка/удаление, категория, сложность, XP, срок, статус; поиск, фильтры, сортировка; выполнить и вернуть в работу |
| **Skill Tree** | Programming, AI, English, Fitness, Finance, Personal Development — уровни, прогресс, тиры |
| **Achievements** | 11 достижений с прогрессом и бонусным XP |
| **Analytics** | Активность за 7/30 дней, категории, прогресс навыков, история XP |
| **Profile** | Имя, аватар, уровень, дата регистрации, статистика; сброс прогресса |

**Баланс:** XP для уровня `L` = `50·L·(L−1)`; навыки `25·L·(L−1)`; Easy/Medium/Hard/Epic = 20/50/100/200 XP; бонус за серию дней +5/10/15/20% (3/7/14/30 дней). Подробнее — [docs/SPEC.md](docs/SPEC.md). REST API описан там же.

## Структура проекта
```
SkillQuest/
├── run.py                       # запуск (с проверкой конфигурации)
├── Dockerfile  docker-compose.yml  .env.example
├── deploy/                      # Caddyfile, nginx.conf
├── backend/                     # server, routes, services, xp, achievements, config, backup, restore
├── frontend/                    # SPA: index.html, css/, js/
├── tests/                       # test_api.py, test_deploy.py
├── data/                        # SQLite (создаётся автоматически; в .gitignore)
└── docs/                        # PRD.md, SPEC.md, DESIGN.md
```

## Решения и ограничения
- Один пользователь (id=1), одна общая пара логин/пароль (Basic Auth). Нет регистрации, ролей, сброса пароля.
- Удаление выполненной миссии не отнимает заработанный XP; «Вернуть в работу» отнимает. Открытые достижения не отзываются. У выполненной миссии нельзя менять категорию, сложность и XP.
- API принимает изменяющие запросы только с `Content-Type: application/json` и same-origin `Origin`.
- Запускайте **один** экземпляр приложения: сервер многопоточный, но рассчитан на личное использование, а SQLite сериализует запись.
- Блокировка перебора хранится в памяти и сбрасывается при перезапуске.
- Basic Auth без HTTPS передаёт пароль открытым текстом — наружу только через Caddy/Nginx с TLS.
- Миграций схемы пока нет (только `PRAGMA user_version = 1`).

## Troubleshooting
- **`Address already in use`** — `python3 run.py --port 8010`.
- **Контейнер `app` перезапускается** — `docker compose logs app`: чаще всего заглушка или короткий пароль в `.env`.
- **403 `forbidden_host`** — домен в адресной строке не совпадает с `SKILLQUEST_DOMAIN`/`SKILLQUEST_ALLOWED_HOSTS`.
- **429 при входе** — сработала блокировка перебора; подождите `Retry-After` секунд.
- **Сбросить всё локально** — остановите сервер и удалите `data/skillquest.db`.
