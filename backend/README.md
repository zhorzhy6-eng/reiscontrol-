# backend

**Назначение:** Серверные приложения и слои Python.

**Документы:** Архитектура §4, §10.4; ADR-0001, ADR-0006.

## Локальный запуск API

Поднимите PostgreSQL и MinIO по [корневой инструкции](../README.md), установите
`python -m pip install -r backend/requirements.txt` и загрузите переменные из
[корневого `.env.example`](../.env.example), затем выполните:

```powershell
python -m alembic -c backend/migrations/alembic.ini upgrade head
python -m backend.infrastructure.postgres.seed
python -m uvicorn backend.apps.api.main:app --host 127.0.0.1 --port 8000
```

Загрузки через `attachments:init` пишутся в Object Storage с S3-совместимым API.
При `commit` сервер копирует файл в отдельный ключ и вычисляет SHA-256 по
скопированным байтам. Для локальной разработки секреты находятся только в
неотслеживаемом `.env`; при переносе на сервер — в его секретном хранилище.
Команду seed нужно повторить после создания новых сочетаний клиента, типа груза
и типа рейса, чтобы опубликовать начальный чек-лист для этих заявок.
