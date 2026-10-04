# Сквозная проверка этапа 1

`test_stage1_live.py` проверяет реальные PostgreSQL и MinIO через HTTP API: вход
водителя и логиста, согласия, снимок конфигурации рейса, три обязательных фото
`LOADING` (камера и галерея), двухфазную загрузку, ленту в веб-кабинете, outbox
и выбор получателя Telegram через реальные таблицы и подставной транспорт,
повтор события и трека без дублей, а также `409` при изменённом повторе.

Тест запускается только при наличии `STAGE1_E2E_DATABASE_URL`. Имя БД обязано
заканчиваться на `_test`; тест создаёт в ней данные, поэтому нужна отдельная
одноразовая база. PostgreSQL и MinIO должны работать по адресам из `.env`.

Из корня репозитория в PowerShell:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}
$dbName = 'reiscontrol_stage1_' + [Guid]::NewGuid().ToString('N').Substring(0, 8) + '_test'
docker compose exec -T postgres createdb -U $env:POSTGRES_USER $dbName
$env:STAGE1_E2E_DATABASE_URL = $env:DATABASE_URL -replace '/[^/]+$', "/$dbName"
$env:DATABASE_URL = $env:STAGE1_E2E_DATABASE_URL
.\.venv\Scripts\python.exe -m alembic -c backend/migrations/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/migrations/alembic.ini check
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_stage1_live.py -q
$env:REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE = '1'
.\.venv\Scripts\python.exe -m alembic -c backend/migrations/alembic.ini downgrade base
Remove-Item Env:REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE
```

`downgrade base` выше удаляет таблицы **только созданной здесь тестовой БД**.
В обычной базе этот флаг не устанавливайте.
