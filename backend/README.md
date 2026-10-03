# backend

**Назначение:** Серверные приложения и слои Python.

**Документы:** Архитектура §4, §10.4; ADR-0001, ADR-0006.

## Локальный запуск API

Установите `python -m pip install -r backend/requirements.txt`, задайте переменные
из [`.env.example`](.env.example), затем выполните:

```powershell
python -m alembic -c backend/migrations/alembic.ini upgrade head
python -m backend.infrastructure.postgres.seed
python -m uvicorn backend.apps.api.main:app --host 127.0.0.1 --port 8000
```

Загрузки через `attachments:init` пишутся в Object Storage с S3-совместимым API.
При `commit` сервер копирует файл в отдельный ключ и вычисляет SHA-256 по
скопированным байтам. Секреты передаются окружением из Lockbox в рабочей среде.
Команду seed нужно повторить после создания новых сочетаний клиента, типа груза
и типа рейса, чтобы опубликовать начальный чек-лист для этих заявок.
