param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $root

$envFile = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Нет .env. Скопируйте .env.example в .env и задайте JWT_SECRET.'
}
Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}

$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$docker = if ($dockerCommand) { $dockerCommand.Source } else {
    Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
}
if (-not (Test-Path -LiteralPath $docker)) { throw 'Docker CLI не найден. Установите Docker Desktop.' }

& $docker version --format '{{.Server.Version}}' *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $dockerDesktop)) { throw 'Docker Desktop не найден.' }
    Write-Host 'Запускаю Docker Desktop…'
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 2
        & $docker version --format '{{.Server.Version}}' *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    }
    if (-not $ready) { throw 'Docker Engine не запустился. Проверьте Docker Desktop.' }
}

Write-Host 'Запускаю PostgreSQL и MinIO…'
& $docker compose up -d
if ($LASTEXITCODE -ne 0) { throw 'Не удалось запустить контейнеры.' }
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    & $docker compose exec -T postgres pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
}
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL не готов к миграции.' }
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $storageReady = (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:9000/minio/health/live' -TimeoutSec 2).StatusCode -eq 200
    } catch { $storageReady = $false }
    if ($storageReady) { break }
    Start-Sleep -Seconds 1
}
if (-not $storageReady) { throw 'MinIO не запустился.' }

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python-окружение не найдено. Выполните команды установки из README.md.'
}
$vite = Join-Path $root 'apps\web\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $vite)) {
    throw 'Веб-зависимости не установлены. Выполните npm ci в apps/web.'
}
$nodeCommand = Get-Command node.exe -ErrorAction Stop

Write-Host 'Применяю миграции и загружаю начальную конфигурацию…'
& $python -m alembic -c backend/migrations/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Миграция БД завершилась с ошибкой.' }
& $python -m backend.infrastructure.postgres.seed
if ($LASTEXITCODE -ne 0) { throw 'Загрузка начальной конфигурации завершилась с ошибкой.' }

$runDir = Join-Path $root '.local\run'
$logDir = Join-Path $root '.local\logs'
New-Item -ItemType Directory -Force -Path $runDir, $logDir | Out-Null
$statePath = Join-Path $runDir 'processes.json'
$state = if (Test-Path -LiteralPath $statePath) {
    Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
} else { [pscustomobject]@{} }

function Test-Http($url) {
    try { return (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2).StatusCode -eq 200 }
    catch { return $false }
}

function Wait-Http($url) {
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (Test-Http $url) { return }
        Start-Sleep -Seconds 1
    }
    throw "Сервис не ответил: $url. Проверьте .local/logs/."
}

function Get-Listener($port) {
    return Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Assert-OwnedListener($name, $listener) {
    $entry = $state.$name
    if (-not $entry) {
        throw "Порт $($listener.LocalPort) занят процессом вне этого запуска. Остановите его вручную."
    }
    $process = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    $samePath = $process -and [string]::Equals($process.Path, $entry.path, [StringComparison]::OrdinalIgnoreCase)
    $sameStart = $process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $entry.started
    if (-not ($samePath -and $sameStart)) { throw "Порт $($listener.LocalPort) принадлежит другому процессу." }
    if ($listener.OwningProcess -eq $entry.pid) { return }
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    $isPythonChild = $name -eq 'api' -and $owner -and
        $owner.ParentProcessId -eq $entry.pid -and $owner.Name -eq 'python.exe'
    if (-not $isPythonChild) {
        throw "Порт $($listener.LocalPort) занят процессом вне этого запуска. Остановите его вручную."
    }
}

$apiListener = Get-Listener 8000
if ($apiListener) {
    Assert-OwnedListener 'api' $apiListener
    if (-not (Test-Http 'http://127.0.0.1:8000/health')) { throw 'Порт 8000 занят другим процессом.' }
    Write-Host 'API уже запущен.'
} else {
    $api = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'backend.apps.api.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'api.out.log') -RedirectStandardError (Join-Path $logDir 'api.err.log')
    $state | Add-Member -NotePropertyName api -NotePropertyValue ([pscustomobject]@{ pid = $api.Id; path = $python; started = $api.StartTime.ToUniversalTime().ToString('o') }) -Force
    Wait-Http 'http://127.0.0.1:8000/health'
    Write-Host 'API работает.'
}

$webListener = Get-Listener 5173
if ($webListener) {
    Assert-OwnedListener 'web' $webListener
    if (-not (Test-Http 'http://127.0.0.1:5173/')) { throw 'Порт 5173 занят другим процессом.' }
    Write-Host 'Веб-кабинет уже запущен.'
} else {
    $webDir = Join-Path $root 'apps\web'
    $web = Start-Process -FilePath $nodeCommand.Source -ArgumentList @('"' + $vite + '"', '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory $webDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'web.out.log') -RedirectStandardError (Join-Path $logDir 'web.err.log')
    $state | Add-Member -NotePropertyName web -NotePropertyValue ([pscustomobject]@{ pid = $web.Id; path = $nodeCommand.Source; started = $web.StartTime.ToUniversalTime().ToString('o') }) -Force
    Wait-Http 'http://127.0.0.1:5173/'
    Write-Host 'Веб-кабинет работает.'
}

$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
Write-Host 'Готово: http://127.0.0.1:5173/'
Write-Host 'Telegram запускается отдельно после настройки токенов.'
