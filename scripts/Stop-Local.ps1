param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $root
$statePath = Join-Path $root '.local\run\processes.json'

if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($name in @('web', 'api')) {
        $entry = $state.$name
        if (-not $entry) { continue }
        $process = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        $samePath = [string]::Equals($process.Path, $entry.path, [StringComparison]::OrdinalIgnoreCase)
        $sameStart = $process.StartTime.ToUniversalTime().ToString('o') -eq $entry.started
        if ($samePath -and $sameStart) {
            Stop-Process -Id $process.Id -Force
            Write-Host "Остановлен $name."
        } else {
            Write-Warning "PID $($entry.pid) теперь принадлежит другому процессу; он не остановлен."
        }
    }
    Remove-Item -LiteralPath $statePath
}

$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$docker = if ($dockerCommand) { $dockerCommand.Source } else {
    Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
}
if (Test-Path -LiteralPath $docker) {
    & $docker compose down
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось остановить контейнеры.' }
}
Write-Host 'Локальная среда остановлена. Данные PostgreSQL и MinIO сохранены.'
