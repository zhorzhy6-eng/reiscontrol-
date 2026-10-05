param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$start = Join-Path $root 'scripts\Start-Local.ps1'
$stop = Join-Path $root 'scripts\Stop-Local.ps1'
$install = Join-Path $root 'scripts\Install-DesktopShortcuts.ps1'

& $install
$desktop = [Environment]::GetFolderPath('Desktop')
foreach ($name in @('Рейс-Контроль — запуск.lnk', 'Рейс-Контроль — остановка.lnk', 'Рейс-Контроль — кабинет логиста.url')) {
    if (-not (Test-Path -LiteralPath (Join-Path $desktop $name))) { throw "Missing shortcut: $name" }
}

& $start
& $start
foreach ($url in @('http://127.0.0.1:8000/health', 'http://127.0.0.1:5173/', 'http://127.0.0.1:9000/minio/health/live')) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
    if ($response.StatusCode -ne 200) { throw "Service failed: $url" }
}

& $stop
foreach ($port in @(8000, 5173)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port remains open after stop: $port"
    }
}

& $start
Write-Host 'Launcher smoke test passed; services are running.'
