# Запуск усього стека одним кліком.
# Викликається з Запустити.bat — сам .bat лишається ASCII, бо cmd не читає UTF-8.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ErrorActionPreference навмисно НЕ 'Stop': docker пише попередження в stderr,
# а PowerShell 5.1 загортає stderr нативного exe в ErrorRecord і вбиває скрипт.
# Успіх нативних команд перевіряємо через $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Say($text, $color = 'Gray') { Write-Host "  $text" -ForegroundColor $color }

function Fail($text) {
    Write-Host ""
    Say $text 'Red'
    Write-Host ""
    exit 1
}

function Wait-For($what, $check, $seconds = 180) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (& $check) { return $true }
        Start-Sleep -Seconds 3
        Write-Host "." -NoNewline
    }
    Write-Host ""
    return $false
}

Write-Host ""
Say "SEO Agent" 'Cyan'
Write-Host ""

# ── 1. Docker ──────────────────────────────────────────────────────────────
# Перенаправлення віддаємо cmd: у PS 5.1 `2>&1` на нативному exe породжує
# NativeCommandError навіть при коді виходу 0.
$dockerUp = { cmd /c "docker info >nul 2>&1"; $LASTEXITCODE -eq 0 }

if (& $dockerUp) {
    Say "[1/3] Docker уже працює."
} else {
    $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $exe)) { Fail "Docker Desktop не знайдено. Встановіть його або запустіть вручну." }

    Say "[1/3] Стартую Docker Desktop (зазвичай 30–60 секунд)"
    Start-Process $exe | Out-Null
    if (-not (Wait-For 'docker' $dockerUp 240)) { Fail "Docker не піднявся за 4 хвилини. Запустіть його вручну." }
    Write-Host ""
    Say "[1/3] Docker готовий." 'Green'
}

# ── 2. Контейнери ──────────────────────────────────────────────────────────
Write-Host ""
Say "[2/3] Піднімаю контейнери (перший запуск — кілька хвилин)"
docker compose up -d
if ($LASTEXITCODE -ne 0) { Fail "Не вдалося підняти стек. Подивіться повідомлення вище." }

# ── 3. Дашборд ─────────────────────────────────────────────────────────────
Write-Host ""
Say "[3/3] Чекаю, поки дашборд відповість"
$webUp = {
    try { (Invoke-WebRequest 'http://localhost:3000' -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 }
    catch { $false }
}
if (-not (Wait-For 'dashboard' $webUp 300)) {
    Fail "Дашборд не відповів за 5 хвилин. Перевірте: docker compose logs frontend"
}

Write-Host ""
Write-Host ""
Say "Готово." 'Green'
Write-Host ""
Say "Дашборд:  http://localhost:3000" 'White'
Say "API:      http://localhost:8000/docs" 'White'
Write-Host ""
Say "Зупинити — Зупинити.bat" 'DarkGray'
Write-Host ""

Start-Process 'http://localhost:3000'
Start-Sleep -Seconds 3
exit 0
