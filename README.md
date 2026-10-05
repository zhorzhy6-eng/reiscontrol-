# Рейс-Контроль

Монорепозиторий Android-приложения водителя, веб-кабинета логиста, Telegram-ботов и backend. Рабочая документация — в `docs/`; исходная схема — в `Project/`.

## Быстрый запуск на этом компьютере

1. Дважды щёлкните ярлык **«Рейс-Контроль — запуск»** на рабочем столе. Дождитесь сообщения «Готово» в открывшемся окне. Скрипт запускает Docker Desktop, PostgreSQL, MinIO, API и веб-кабинет, а также применяет миграции БД.
2. Откройте ярлык **«Рейс-Контроль — кабинет логиста»**. Адрес кабинета: <http://127.0.0.1:5173/>. API: <http://127.0.0.1:8000/health>. Консоль MinIO: <http://127.0.0.1:9001/>.
3. Для остановки используйте ярлык **«Рейс-Контроль — остановка»**. Данные в PostgreSQL и MinIO сохраняются.

Если ярлыки отсутствуют, запустите из корня проекта `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\Install-DesktopShortcuts.ps1`. Для запуска нужны установленный Docker Desktop, настроенный `.env`, зависимости Python в `.venv` и зависимости веб-кабинета в `apps/web/node_modules`; команды первичной установки приведены ниже. Telegram-боты запускаются отдельно после настройки токенов. При ошибке запуска проверьте `.local/logs/`.

## Локальный запуск на своём компьютере

Нужны Docker с Compose, Python 3.12 и Node.js. PostgreSQL 16 и MinIO запускаются в Docker; API, воркеры, боты и веб-кабинет — как локальные процессы.

На Windows перед запуском проверьте `docker version`: ответ должен содержать раздел
`Server`. Если Docker Desktop пишет `WSL needs updating`, выполните в PowerShell
**от имени администратора** `wsl --install --no-distribution`. Если Windows
сообщает, что нужная служба не установлена, включите компоненты вручную:

```powershell
dism.exe /Online /Enable-Feature /FeatureName:Microsoft-Windows-Subsystem-Linux /All /NoRestart
dism.exe /Online /Enable-Feature /FeatureName:VirtualMachinePlatform /All /NoRestart
```

После этого перезагрузите компьютер, выполните `wsl --update` и повторно
запустите Docker Desktop.
См. [инструкцию Microsoft](https://learn.microsoft.com/windows/wsl/install).

В PowerShell из корня репозитория:

```powershell
Copy-Item .env.example .env
# Задайте свой JWT_SECRET и, если нужны боты, Telegram-токены в .env.
docker compose up -d
docker compose ps
```

Compose создаёт bucket `reiscontrol`. PostgreSQL доступен на `127.0.0.1:5432`, S3 API MinIO — на `http://127.0.0.1:9000`, консоль MinIO — на `http://127.0.0.1:9001`. Образ MinIO закреплён по digest и собран сообществом из исходного кода релиза 2025-10-15: официальный образ больше недоступен в прежнем реестре. Учётные данные для разработки указаны в `.env`; файл исключён из Git. Если меняете пароли или bucket, обновите также `DATABASE_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` и `OBJECT_STORAGE_BUCKET`.

Перед запуском каждого локального Python-процесса загрузите `.env` в **его** терминал:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m alembic -c backend/migrations/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m backend.infrastructure.postgres.seed
.\.venv\Scripts\python.exe -m uvicorn backend.apps.api.main:app --host 127.0.0.1 --port 8000
```

В отдельных терминалах с загруженным `.env` запустите `.\.venv\Scripts\python.exe -m backend.apps.worker.outbox`, `.\.venv\Scripts\python.exe -m backend.apps.worker.devbot` и `.\.venv\Scripts\python.exe -m apps.telegram.bot`. Для ботов нужны реальные Telegram-токены и доступ к Telegram API. Связать чат с логистом: `.\.venv\Scripts\python.exe -m apps.telegram.subscribe <user_uuid> <chat_id>`.

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
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend tests
.\.venv\Scripts\python.exe -m black --check --config backend/pyproject.toml backend tests
```

Android: см. [apps/android/README.md](apps/android/README.md). Веб: см. [apps/web/README.md](apps/web/README.md).
Проверка всей цепочки на одноразовой базе и MinIO: [tests/e2e/README.md](tests/e2e/README.md).

## Документы

- [ТЗ v4.1](docs/01-requirements/), [архитектура v1.1](docs/02-architecture/), [ADR](docs/03-adr/).
- [Схема БД](docs/04-db/schema.md), [OpenAPI](docs/05-api/openapi.yaml), [JSON Schema](docs/06-schemas/).
- [Правила кода](CONVENTIONS.md), [дорожная карта](ROADMAP.md).
