@echo off
REM Скрипт для запуска бота на Windows CMD

REM Загружаем токен из .env
for /f "usebackq delims==" %%A in (".env") do (
    set %%A
)

REM Активируем venv
call .venv\Scripts\activate.bat

REM Запускаем бот
echo 🤖 Запускаю TelePsycho бота...
python main.py

pause
