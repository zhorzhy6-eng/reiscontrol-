param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not (Test-Path -LiteralPath $desktop)) { throw 'Рабочий стол не найден.' }
$powerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shell = New-Object -ComObject WScript.Shell

foreach ($item in @(
    @{ name = 'Рейс-Контроль — запуск'; script = 'Start-Local.ps1'; icon = 44 },
    @{ name = 'Рейс-Контроль — остановка'; script = 'Stop-Local.ps1'; icon = 28 }
)) {
    $shortcut = $shell.CreateShortcut((Join-Path $desktop ($item.name + '.lnk')))
    $shortcut.TargetPath = $powerShell
    $shortcut.Arguments = '-NoProfile -NoExit -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot $item.script) + '"'
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = $item.name
    $shortcut.IconLocation = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',' + $item.icon
    $shortcut.Save()
}

$webShortcut = Join-Path $desktop 'Рейс-Контроль — кабинет логиста.url'
@('[InternetShortcut]', 'URL=http://127.0.0.1:5173/') | Set-Content -LiteralPath $webShortcut -Encoding ASCII
Write-Host "Ярлыки созданы на рабочем столе: $desktop"
