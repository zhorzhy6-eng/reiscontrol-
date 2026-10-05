# AGENTS.md — правила для Codex в проекте «Рейс-Контроль»

Я не программист. Объясняй простыми словами. Кратко. Не додумывай — спрашивай.
Работай автономно: читай, пиши, тестируй, коммить сам. Показывай diff и жди
«запиши» только перед опасным: удаление, миграции БД, .env, git push, ADR.

## Экономия токенов (критично)

Любую команду ограничивай: `КОМАНДА 2>&1 | head -c 4000`.
Читай только файлы, названные в задаче.
Архитектура — `ARCHITECTURE.md`, не `docs/02-architecture/*.docx`.
Правила кода — `CONVENTIONS.md`.
ТЗ — не открывать `.docx`/`.pdf` без явной необходимости.

## Где что лежит

- Код: `F:\Driver App\` | Источник правды: `F:\Driver App\Project\`
- Архитектура: `ARCHITECTURE.md` | Правила кода: `CONVENTIONS.md`
- ADR: `docs/03-adr/` | API: `docs/05-api/openapi.yaml`
- Схемы payload: `docs/06-schemas/`
- Конфиги: `config/` | Миграции: `backend/migrations/`

## Схема БД

Описание схемы — `docs/04-db/schema.md`. Читай **только если задача прямо
касается структуры таблиц**: добавить колонку, изменить индекс, написать
миграцию, разобраться со связью между таблицами.
Не читай схему «на всякий случай» и не читай её целиком — только нужный раздел.
Код схемы (источник правды) — `backend/infrastructure/postgres/models.py`.

## ADR

Все 12 ADR — в `docs/03-adr/`, по одному файлу на решение.
Открывай **только тот ADR, который прямо нужен для задачи**. Остальные не читай.
Если задача про архитектуру, БД, API или логирование, но непонятно какой ADR
применим — остановись и спроси.

- 01 PostgreSQL (не YDB) · 02 Event log · 03 Config-as-data
- 04 Offline-first · 05 Time-attributes · 06 Ports-and-adapters
- 07 Two-phase upload · 08 Versioning · 09 Auth
- 10 PD-operator · 11 Logging · 12 Deferred-partitioning

## Запреты

❌ YDB · хардкод типов событий · `UPDATE` поверх accepted-событий
❌ big bang миграции · логировать ПДн/координаты/токены
❌ секреты в коде и выводе · `print()` вместо логирования
❌ `except Exception: pass` · смешивать слои · RuStore

## Стек и запуск

Python (ruff+black), Kotlin (ktlint), TypeScript (eslint+prettier).
Локально: `docker-compose.yml` + `scripts/Start-Local.ps1`.
`@reiscontrol_main_bot` — логист. `@reiscontrol_devbot` — worker, не отвечает.

## Тесты

Новый код — новый тест. Идемпотентность: `(client_event_id, device_id)`, UUIDv7.
Миграции — expand/contract. Downgrade — только с `REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE=1`.