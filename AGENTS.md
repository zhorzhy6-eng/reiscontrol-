# AGENTS.md — правила для Codex в проекте «Рейс-Контроль»

Я не программист. Объясняй простыми словами. Кратко, по делу. Не додумывай — спрашивай.
Перед записью в файлы — показывай diff и жди команды «запиши».

## Экономия токенов (критично)

Ограничивай вывод любой команды: `КОМАНДА 2>&1 | head -c 4000`.
Не читай `docs/01-requirements/`, `docs/02-architecture/`, `docs/06-schemas/` целиком без нужды.
Читай только файлы, названные в задаче.
Для архитектуры сначала смотри `ARCHITECTURE.md` (сжатая версия), не `docs/02-architecture/*.docx`.
Для правил кода смотри `CONVENTIONS.md`, не `docs/`.
Для ТЗ не открывай `.docx`/`.pdf` без явной необходимости — если нужно, бери только конкретный раздел.

## Где что лежит

- Код и репозиторий: `F:\Driver App\`
- Источник правды: `F:\Driver App\Project\` (Codex читает отсюда, пишет в корень)
- Сжатая архитектура: `ARCHITECTURE.md`
- Правила кода: `CONVENTIONS.md`
- Рабочие docs: `docs/` | ADR: `docs/03-adr/` | Схема БД: `docs/04-db/schema.md`
- API: `docs/05-api/openapi.yaml` | JSON Schema: `docs/06-schemas/`
- Конфиги: `config/` | Миграции: `backend/migrations/`
- GitHub: https://github.com/zhorzhy6-eng/reiscontrol-

## Архитектурные решения — в ADR (читай по требованию)

Все 12 ADR лежат в `docs/03-adr/`. Читай только тот, который нужен для задачи.

| Тема | ADR |
|---|---|
| PostgreSQL (не YDB) | `docs/03-adr/ADR-0001-postgresql.md` |
| Append-only события + проекции | `docs/03-adr/ADR-0002-event-log.md` |
| Config-as-data + snapshot на рейс | `docs/03-adr/ADR-0003-config-as-data.md` |
| Офлайн-first, идемпотентность | `docs/03-adr/ADR-0004-offline-first.md` |
| Время как набор атрибутов | `docs/03-adr/ADR-0005-time-attributes.md` |
| Порты и адаптеры | `docs/03-adr/ADR-0006-ports-and-adapters.md` |
| Двухфазная загрузка | `docs/03-adr/ADR-0007-two-phase-upload.md` |
| Версионирование, expand/contract | `docs/03-adr/ADR-0008-versioning.md` |
| JWT + refresh, PIN | `docs/03-adr/ADR-0009-auth.md` |
| Оператор ПДн | `docs/03-adr/ADR-0010-pd-operator.md` |
| Логирование | `docs/03-adr/ADR-0011-logging.md` |
| Партиционирование отложено | `docs/03-adr/ADR-0012-deferred-partitioning.md` |

Если задача касается архитектуры, БД, API, безопасности или логирования,
но неясно какой ADR применим — остановись и спроси. Не додумывай.

## Запреты

❌ YDB | ❌ хардкод типов событий | ❌ `UPDATE` поверх accepted-событий
❌ big bang миграции | ❌ логировать ПДн, координаты, токены
❌ секреты в коде и выводе | ❌ `print()` вместо логирования
❌ `except Exception: pass` | ❌ смешивать слои | ❌ RuStore

## Стек и запуск

Python (ruff+black), Kotlin (ktlint), TypeScript (eslint+prettier).
Локально: `docker-compose.yml` + `scripts/Start-Local.ps1`. Переезд: `docs/migration-to-server.md`.
`@reiscontrol_main_bot` — логист, отвечает на `/start`. `@reiscontrol_devbot` — worker, не отвечает.

## Тесты

Новый код — новый тест. Идемпотентность: `(client_event_id, device_id)`, UUIDv7.
Миграции — только expand/contract. Downgrade — только с `REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE=1`.