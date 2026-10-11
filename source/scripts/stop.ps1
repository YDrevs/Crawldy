# Зупинка стека. Викликається з Зупинити.bat

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "  Зупиняю контейнери..." -ForegroundColor Gray
Write-Host ""

docker compose down

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Не вдалося зупинити. Можливо, Docker уже вимкнено." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "  Зупинено. Дані аудитів збережені." -ForegroundColor Green
Write-Host "  (щоб стерти й базу: docker compose down -v)" -ForegroundColor DarkGray
Write-Host ""
Start-Sleep -Seconds 3
exit 0
