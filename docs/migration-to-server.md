# Перенос локальных данных на свой сервер

Эта процедура переносит PostgreSQL 16 и текущие объекты MinIO с прежними S3-ключами. Выполняйте её в окно обслуживания: остановите локальные API, воркеры и ботов, чтобы во время копирования не появлялись новые события или вложения.

## Подготовка

1. На сервере подготовьте PostgreSQL 16, MinIO и пустой bucket с тем же именем, что в локальном `OBJECT_STORAGE_BUCKET`. Храните серверные пароли и токены в серверном `.env`, не в Git.
2. Подготовьте защищённый доступ к серверному MinIO для `mc` (TLS или SSH-туннель). URL сервера для presigned S3-ссылок должен быть доступен клиентам.
3. Проверьте свободное место. Если сервер уже содержит данные, сначала отдельно сохраните его БД и bucket. Восстановление ниже рассчитано на **пустую** серверную БД.

## Экспорт на локальном компьютере

После остановки процессов оставьте `docker compose` с PostgreSQL и MinIO запущенным. В PowerShell из корня проекта:

```powershell
$backupDir = 'C:\reiscontrol-migration'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$pgContainer = docker compose ps -q postgres
if (-not $pgContainer) { throw 'PostgreSQL container is not running' }
docker exec $pgContainer pg_dump -U reiscontrol -d reiscontrol -Fc -f /tmp/reiscontrol.dump
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed' }
docker cp "${pgContainer}:/tmp/reiscontrol.dump" "$backupDir\reiscontrol.dump"
if ($LASTEXITCODE -ne 0) { throw 'docker cp failed' }
Get-FileHash "$backupDir\reiscontrol.dump" -Algorithm SHA256
```

Если `POSTGRES_USER` или `POSTGRES_DB` отличаются от примера, замените их в `pg_dump`. Сохраните SHA-256 сумму отдельно.

## Копирование объектов

Используйте MinIO Client (`mc`) на локальном компьютере. Загрузите переменные из `.env`, как описано в корневом README. Серверные реквизиты задайте через секретный менеджер или безопасный ввод в переменные процесса.

```powershell
$serverS3 = 'https://minio.example.org'
$serverBucket = 'reiscontrol'
mc alias set local http://127.0.0.1:9000 $env:AWS_ACCESS_KEY_ID $env:AWS_SECRET_ACCESS_KEY
mc alias set server $serverS3 $env:SERVER_S3_ACCESS_KEY $env:SERVER_S3_SECRET_KEY
mc mb --ignore-existing "server/$serverBucket"
mc mirror --overwrite "local/$env:OBJECT_STORAGE_BUCKET" "server/$serverBucket"
mc ls --recursive --summarize "local/$env:OBJECT_STORAGE_BUCKET"
mc ls --recursive --summarize "server/$serverBucket"
```

Сравните количество объектов и общий объём. Если bucket использует versioning, этот перенос копирует текущие объекты; историю версий переносите отдельной процедурой.

## Восстановление на сервере

Скопируйте `reiscontrol.dump` на сервер защищённым каналом и сверьте SHA-256. В каталоге серверного развёртывания с запущенным PostgreSQL:

```bash
pg_container="$(docker compose ps -q postgres)"
test -n "$pg_container"
docker cp /srv/reiscontrol/reiscontrol.dump "$pg_container:/tmp/reiscontrol.dump"
docker exec "$pg_container" pg_restore --exit-on-error -U reiscontrol -d reiscontrol --no-owner --no-acl /tmp/reiscontrol.dump
```

Замените имя пользователя и БД, если они отличаются. Не запускайте `pg_restore --clean` на базе с данными. Затем в серверном окружении backend выполните `python -m alembic -c backend/migrations/alembic.ini upgrade head` и `python -m backend.infrastructure.postgres.seed`. Seed идемпотентен.

## Проверка и переключение

- Сравните число строк в `events`, `location_tracks`, `attachments`, `outbox`, `notification_log` и значение `alembic_version` до и после переноса.
- Откройте несколько сохранённых вложений через API, чтобы проверить S3-объекты и presigned URL.
- Запустите серверные API, воркеры и ботов только после проверки БД и bucket. Обновите адрес API в новых сборках клиентов.
- Сохраните локальные данные и архив до окончания приёмки. При сбое остановите серверные процессы и восстановите сервер из резервной копии, сделанной до переноса.
