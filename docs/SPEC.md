# SkillQuest — Technical Specification

## 1. Стек и обоснование
| Слой | Выбор | Почему |
|---|---|---|
| Backend | Python 3 (stdlib: `http.server`, `sqlite3`, `json`) | Нулевые зависимости, ничего не надо устанавливать |
| БД | SQLite (WAL, foreign keys) | Локально, надёжно, один файл `data/skillquest.db` |
| Frontend | Vanilla JS (ES modules), CSS custom properties, SVG-графики | Без сборки и node_modules, быстро |
| Тесты | `unittest` (интеграционные, реальный HTTP-сервер + временная БД) | Входит в stdlib |

## 2. Архитектура
```
SkillQuest/
├── run.py                 # точка входа: python3 run.py
├── backend/
│   ├── config.py          # пути, порт, лимиты
│   ├── clock.py           # today()/now() (подменяемо в тестах)
│   ├── db.py              # подключение, схема, сидирование навыков
│   ├── errors.py          # ApiError (HTTP-код + код + поля)
│   ├── validation.py      # валидация входных данных
│   ├── xp.py              # формулы уровней, сложность, streak-множитель, тиры
│   ├── achievements.py    # определения и проверка достижений
│   ├── services/          # бизнес-логика (missions, stats, profile)
│   ├── router.py          # маршрутизатор regex → handler
│   ├── routes.py          # HTTP-слой (тонкие хендлеры)
│   ├── server.py          # ThreadingHTTPServer + статика + JSON/ошибки
│   └── seed_demo.py       # демо-данные (опционально)
├── frontend/              # SPA: index.html, css/, js/ (api, ui, charts, views/)
├── tests/test_api.py
├── data/                  # SQLite-файл (создаётся автоматически)
└── docs/                  # PRD, SPEC, DESIGN
```
Слои: **routes → services → db**. Бизнес-логика (XP, streak, достижения) только в services/xp/achievements; хендлеры лишь разбирают запрос.

## 3. База данных
```sql
users(id PK CHECK(id=1), name, avatar, avatar_hue, created_at)
skills(slug PK, name, description, icon, color, sort_order)
missions(id PK, title, description, category FK→skills.slug, difficulty,
         xp, due_date NULL, status CHECK IN('pending','completed'),
         created_at, updated_at, completed_at NULL)
xp_events(id PK, mission_id FK→missions ON DELETE SET NULL, skill_slug FK NULL (NULL у достижений),
          source CHECK IN('mission','achievement'), label, difficulty NULL,
          base_xp, bonus_xp, amount, day 'YYYY-MM-DD', created_at)
user_achievements(code PK, unlocked_at)
```
Индексы: `missions(status)`, `missions(due_date)`, `xp_events(day)`, `xp_events(skill_slug)`.
Леджер `xp_events` — единственный источник правды: общий XP, XP навыков, streak и история считаются из него. Это упрощает откат (reopen = удалить событие) и аналитику.

## 4. Игровая логика
### 4.1 Уровни
XP для достижения уровня `L`: **T(L) = 50·L·(L−1)**  → L2=100, L3=300, L4=600, L5=1000, L10=4500, L20=19000.
Шаг между уровнями растёт линейно (+100 на уровень): быстрые первые уровни, затем плавное замедление.

### 4.2 Навыки
**S(L) = 25·L·(L−1)** → L2=50, L3=150, L5=500, L10=2250 (навыки растут вдвое быстрее общего уровня). Максимум — 50.
Тиры: Novice (ур.1), Apprentice (2), Adept (4), Expert (6), Master (8).

### 4.3 Награда за миссию
| Сложность | XP по умолчанию |
|---|---|
| Easy | 20 |
| Medium | 50 |
| Hard | 100 |
| Epic | 200 |

Пользователь может задать любой XP 1…1000. **Бонус за серию** (множитель к базовому XP, округление):
streak ≥3 → ×1.05, ≥7 → ×1.10, ≥14 → ×1.15, ≥30 → ×1.20.
`streak` для расчёта — серия *после* текущего выполнения. Награда целиком идёт и в общий XP, и в XP навыка (категории миссии).

### 4.4 Streak
Серия — число подряд идущих дней (локальная дата), в каждый из которых выполнена ≥1 миссия. Текущая серия жива, если активность была сегодня или вчера. Бонусный XP достижений активность не засчитывает.

### 4.5 Достижения (награда = бонусный XP)
| Код | Название | Условие | XP |
|---|---|---|---|
| first_mission | First Blood | 1 миссия | 25 |
| ten_missions | Getting Serious | 10 миссий | 100 |
| fifty_missions | Quest Machine | 50 миссий | 300 |
| streak_7 | Week Warrior | серия 7 дней | 150 |
| streak_30 | Unstoppable | серия 30 дней | 500 |
| xp_1000 | Thousand Club | 1000 XP | 200 |
| skill_level_2 | New Skill Unlocked | любой навык ур.2 | 50 |
| skill_level_5 | Skill Master | любой навык ур.5 | 300 |
| polymath | Polymath | XP во всех 6 навыках | 150 |
| level_5 | Rising Star | общий уровень 5 | 200 |
| epic_mission | Epic Deed | выполнена Epic-миссия | 100 |

Проверка выполняется в той же транзакции после выполнения миссии, циклом до стабилизации (бонус может открыть следующее достижение). Достижение открывается один раз.

## 5. REST API (JSON, префикс `/api`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/dashboard` | Сводка главной панели |
| GET | `/missions?status=&category=&difficulty=&q=&sort=` | Список (`status`: all/active/completed/overdue; `sort`: due/newest/xp) |
| POST | `/missions` | Создать |
| GET | `/missions/{id}` | Одна миссия |
| PUT | `/missions/{id}` | Изменить |
| DELETE | `/missions/{id}` | Удалить |
| POST | `/missions/{id}/complete` | Выполнить → результат награды |
| POST | `/missions/{id}/reopen` | Вернуть в работу (снимает XP) |
| GET | `/skills` | Навыки с уровнями и тирами |
| GET | `/achievements` | Достижения с прогрессом |
| GET | `/analytics?range=week\|month` | Аналитика |
| GET | `/xp-history?limit=&offset=` | Лента XP |
| GET / PUT | `/profile` | Профиль |
| POST | `/profile/reset` | Сброс прогресса (`{"confirm": true}`) |

**Ошибки:** `{"error": {"code": "validation_error", "message": "...", "fields": {"title": "..."}}}`; коды HTTP: 400, 404, 405, 409 (миссия уже выполнена / не выполнена), 413, 500.

**Ответ `complete`:**
```json
{"mission": {...}, "reward": {"base_xp":50,"bonus_xp":5,"total_xp":55,"skill":"programming"},
 "level": {"before":1,"after":2,"leveled_up":true}, "skill_level": {"before":1,"after":2,"leveled_up":true},
 "streak": 3, "new_achievements": [{"code":"first_mission","title":"...","reward_xp":25}], "user": {...}}
```

## 6. Валидация
Сервер (источник правды) и клиент: title 1–120 символов; description ≤1000; category ∈ навыки; difficulty ∈ easy/medium/hard/epic; xp — целое 1–1000; due_date — валидная дата `YYYY-MM-DD` или null; имя профиля 1–40; avatar ≤8 символов; hue 0–360. Тело запроса ≤1 МБ, должно быть JSON-объектом.

## 7. Frontend
SPA с hash-роутингом: `#/dashboard`, `#/missions`, `#/skills`, `#/achievements`, `#/analytics`, `#/profile`. Модули: `api.js` (fetch + ошибки), `ui.js` (h(), иконки, toast, modal, confirm), `charts.js` (SVG), `views/*`. Весь пользовательский текст вставляется через `textContent` (защита от XSS). Каждое представление: skeleton → данные | empty | error с кнопкой Retry.

## 8. Запуск и тестирование
`python3 run.py` → http://127.0.0.1:8000. Переменные: `PORT`, `HOST`, `SKILLQUEST_DB`. Тесты: `python3 -m unittest discover -s tests -v`.
