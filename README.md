# Рейс-Контроль

Монорепозиторий мобильного приложения для водителей автовозов, веб-кабинета и серверной части. Текущий результат — **этап 0: каркас**. Бизнес-логика и запускаемые приложения появятся на следующих этапах.

## Стек

- Android: Kotlin, Compose; iOS: Swift, SwiftUI.
- Web: React, TypeScript, Vite; боты: python-telegram-bot.
- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic; PostgreSQL, Yandex Object Storage и YMQ.
- Инфраструктура: Terraform; CI: GitHub Actions.

## Структура

- `apps/` — клиенты и Telegram-боты.
- `backend/` — API, worker, scheduler, domain, application, infrastructure, integrations, contracts и migrations.
- `infra/` — будущий Terraform.
- `tests/` — unit, integration, contract и e2e.
- `docs/` — рабочие копии документов из `Project/`.
- `config/` — будущие шаблоны чек-листов.

`Project/` — исходная документация только для чтения; в Git не включается. При расхождении рабочих копий сверяйтесь с `Project/` и приоритетом из [AGENTS.md](AGENTS.md).

## Проверка каркаса

Требуется Python 3.12. Из корня репозитория:

```bash
python -m pip install -r backend/requirements.txt
python -m ruff check --config backend/pyproject.toml backend tests
python -m black --check --config backend/pyproject.toml backend tests
python -m pytest tests
```

В `apps/web/` доступны `npm install`, `npm run lint`, `npm run format:check`, `npm test`. Android Gradle пока содержит только корневую конфигурацию ktlint; APK появится с модулем `:app` на этапе 1.

## Документы

- [ТЗ v4.1](docs/01-requirements/), [архитектура v1.1](docs/02-architecture/), [ADR](docs/03-adr/).
- [Схема БД](docs/04-db/schema.md), [OpenAPI](docs/05-api/openapi.yaml), [JSON Schema](docs/06-schemas/).
- [Правила кода](CONVENTIONS.md), [дорожная карта](ROADMAP.md), [краткая архитектура](ARCHITECTURE.md).
