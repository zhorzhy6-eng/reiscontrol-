# Рейс-Контроль

Монорепозиторий Android-приложения водителя, веб-кабинета логиста, Telegram-ботов и backend. Рабочая документация — в `docs/`; исходная схема — в `Project/`.

## Локальный запуск на своём компьютере

Нужны Docker с Compose, Python 3.12 и Node.js. PostgreSQL 16 и MinIO запускаются в Docker; API, воркеры, боты и веб-кабинет — как локальные процессы.

В PowerShell из корня репозитория:

```powershell
Copy-Item .env.example .env
# Задайте свой JWT_SECRET и, если нужны боты, Telegram-токены в .env.
docker compose up -d
docker compose ps
```

Compose создаёт bucket `reiscontrol`. PostgreSQL доступен на `127.0.0.1:5432`, S3 API MinIO — на `http://127.0.0.1:9000`, консоль MinIO — на `http://127.0.0.1:9001`. Учётные данные для разработки указаны в `.env`; файл исключён из Git. Если меняете пароли или bucket, обновите также `DATABASE_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` и `OBJECT_STORAGE_BUCKET`.

Перед запуском каждого локального Python-процесса загрузите `.env` в **его** терминал:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}
python -m pip install -r backend/requirements.txt
python -m alembic -c backend/migrations/alembic.ini upgrade head
python -m backend.infrastructure.postgres.seed
python -m uvicorn backend.apps.api.main:app --host 127.0.0.1 --port 8000
```

В отдельных терминалах с загруженным `.env` запустите `python -m backend.apps.worker.outbox`, `python -m backend.apps.worker.devbot` и `python -m apps.telegram.bot`. Для ботов нужны реальные Telegram-токены и доступ к Telegram API. Связать чат с логистом: `python -m apps.telegram.subscribe <user_uuid> <chat_id>`.

Веб-кабинет запускается отдельно:

```powershell
Set-Location apps/web
npm ci
npm run dev
```

Vite перенаправляет `/api` на локальный backend `127.0.0.1:8000`. Android-эмулятор обращается к API через `10.0.2.2:8000`. Для загрузки вложений по presigned ссылкам MinIO с адресом `127.0.0.1:9000` настройте `adb reverse tcp:9000 tcp:9000` перед запуском приложения. Для физического устройства задайте S3 endpoint с адресом компьютера, доступным устройству, и откройте доступ к MinIO соответственно.

Остановить контейнеры без удаления данных: `docker compose down`. Данные сохраняются в именованных volumes. Перенос на свой сервер описан в [docs/migration-to-server.md](docs/migration-to-server.md).

## Проверки

```powershell
python -m pytest tests
python -m ruff check --config backend/pyproject.toml backend tests
python -m black --check --config backend/pyproject.toml backend tests
```

Android: см. [apps/android/README.md](apps/android/README.md). Веб: см. [apps/web/README.md](apps/web/README.md).

## Документы

- [ТЗ v4.1](docs/01-requirements/), [архитектура v1.1](docs/02-architecture/), [ADR](docs/03-adr/).
- [Схема БД](docs/04-db/schema.md), [OpenAPI](docs/05-api/openapi.yaml), [JSON Schema](docs/06-schemas/).
- [Правила кода](CONVENTIONS.md), [дорожная карта](ROADMAP.md).
