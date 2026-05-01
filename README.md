# 🤖 TelePsycho Bot

Telegram бот для скачивания видео, аудио и фото с YouTube, Instagram и поиска музыки.

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка токена

Создай файл `.env` в корне проекта:
```
BOT_TOKEN=твой_токен_от_бота_здесь
```

Или используй пример:
```bash
cp .env.example .env
# Отредактируй .env и добавь свой токен
```

### 3. Запуск бота

#### PowerShell (рекомендуется)
```powershell
.\run_bot.ps1
```

#### Windows CMD
```cmd
run_bot.bat
```

#### Прямой запуск
```bash
python main.py
```

Или с переменной окружения:
```powershell
$env:BOT_TOKEN='твой_токен'; python main.py
```

## 📝 Что умеет бот

- 🎬 **YouTube** — Скачивание видео (MP4) и аудио (MP3)
- 📸 **Instagram** — Скачивание Reels и постов
- 🎵 **Музыка** — Поиск и скачивание треков по названию

## 🛠 Требования

- Python 3.8+
- FFmpeg (для преобразования в MP3)
- Интернет соединение

## 📦 Зависимости

- `aiogram` — Telegram Bot API
- `yt-dlp` — Скачивание видео/аудио
- `python-dotenv` — Загрузка переменных окружения

## ⚙️ Структура проекта

```
tg_bot/
├── main.py              # Основной код бота
├── .env                 # Переменные окружения (НЕ коммитить!)
├── .env.example         # Шаблон .env
├── .gitignore          # Git ignore правила
├── requirements.txt    # Зависимости Python
├── run_bot.ps1         # Скрипт запуска (PowerShell)
├── run_bot.bat         # Скрипт запуска (CMD)
└── downloads/          # Папка для скачанных файлов
```

## ⚠️ Важно

- **Не коммить** файл `.env` — он содержит приватный токен!
- Максимальный размер файла для Telegram: **50 МБ**
- Требуется FFmpeg для работы с MP3

## 🐛 Решение проблем


### "BOT_TOKEN не установлена"
```powershell
$env:BOT_TOKEN='твой_токен'; python main.py
```

### Зависимости не установлены
```bash
pip install -r requirements.txt --upgrade
```
