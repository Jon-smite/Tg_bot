# Скрипт для запуска бота с переменной окружения

# Загружаем токен из .env файла
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    $content = Get-Content $envFile
    foreach ($line in $content) {
        if ($line -match "^\s*#" -or $line -eq "") {
            continue
        }
        $parts = $line -split "=", 2
        if ($parts.Count -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            Set-Item "env:$key" $value
        }
    }
    Write-Host "✓ Загружены переменные из .env" -ForegroundColor Green
}

# Запускаем бот
Write-Host "🤖 Запускаю TelePsycho бота..." -ForegroundColor Cyan
python main.py
