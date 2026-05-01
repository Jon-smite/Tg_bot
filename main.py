import sys
import os
import asyncio
import re
import logging
import atexit
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import yt_dlp

# Пытаемся загрузить переменные из .env файла
try:
    from dotenv import load_dotenv
    # Загружаем .env из директории скрипта
    env_path = Path(__file__).parent / ".env"
    load_dotenv(str(env_path))
except Exception as e:
    print(f"⚠️ Предупреждение при загрузке .env: {e}")
    # Загружаем токен из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: переменная окружения BOT_TOKEN не установлена!")
    print("   Создай файл .env с содержимым: BOT_TOKEN=твой_токен")
    print("   Или установи переменную: $env:BOT_TOKEN='ваш_токен'")
    sys.exit(1)

# Папка, куда бот будет скачивать файлы
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Настройка логов — чтобы видеть, что происходит в консоли
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# FSM состояния для выбора музыки
class MusicStates(StatesGroup):
    waiting_for_music_search = State()
    waiting_for_music_choice = State()

# Создаём объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def is_youtube_url(url: str) -> bool:
    """Проверяет, является ли ссылка YouTube-ссылкой."""
    return bool(re.search(
        r'(youtube\.com/watch|youtu\.be/|youtube\.com/shorts)', url
    ))

def is_instagram_url(url: str) -> bool:
    """Проверяет, является ли ссылка Instagram-ссылкой."""
    return bool(re.search(
        r'instagram\.com/(p|reel|reels)/', url
    ))

def get_ydl_opts_video(output_path: str) -> dict:
    """Настройки yt-dlp для скачивания ВИДЕО с YouTube."""
    return {
        "format": "best[ext=mp4]/best[ext=webm]/best",
        "outtmpl": f"{output_path}.%(ext)s",
        "quiet": False,
        "no_warnings": False,
        # Ограничение размера: 50 МБ (лимит Telegram для ботов)
        "max_filesize": 50 * 1024 * 1024,
        "postprocessors": [{
            "key": "FFmpegVideoRemuxer",
            "preferedformat": "mp4",
        }],
    }

def get_ydl_opts_audio(output_path: str) -> dict:
    """Настройки yt-dlp для скачивания АУДИО (MP3)."""
    return {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": False,
        "no_warnings": False,
        "progress_hooks": [],
        "postprocessors": [{
            "key": "FFmpegExtractAudio",   # конвертация в MP3
            "preferredcodec": "mp3",
            "preferredquality": "192",     # качество 192 kbps
        }],
    }

def get_ydl_opts_instagram(output_path: str) -> dict:
    """Настройки yt-dlp для скачивания Instagram Reels/постов."""
    return {
        "format": "best",
        "outtmpl": f"{output_path}.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "max_filesize": 50 * 1024 * 1024,
    }

def get_ydl_opts_music_search(output_path: str, query: str) -> dict:
    """Настройки yt-dlp для поиска и скачивания музыки по названию."""
    return {
        # ytsearch1: — ищет первый результат на YouTube по запросу
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": False,
        "no_warnings": False,
        "default_search": "ytsearch1",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

async def search_music(query: str) -> list:
    """Ищет 10 песен по запросу на YouTube."""
    loop = asyncio.get_event_loop()
    
    def _search():
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "default_search": "ytsearch10",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            return info.get("entries", [])
    
    try:
        results = await loop.run_in_executor(None, _search)
        formatted_results = []
        for idx, item in enumerate(results[:10], 1):
            title = item.get("title", "Unknown")
            duration = item.get("duration", 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
            video_id = item.get("id", "")
            formatted_results.append({
                "num": idx,
                "title": title,
                "duration": duration_str,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id
            })
        return formatted_results
    except Exception as e:
        logger.error(f"Ошибка поиска музыки: {e}")
        return []

async def download_media(opts: dict, url: str) -> tuple[bool, str]:
    """
    Универсальная функция скачивания через yt-dlp.
    Возвращает (успех: bool, путь_к_файлу или сообщение_об_ошибке: str)
    """
    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    try:
        # Запускаем блокирующий yt-dlp в отдельном потоке,
        # чтобы не "замораживать" бота
        info = await loop.run_in_executor(None, _download)
        return True, info
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Ошибка скачивания: {e}")
        return False, str(e)
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        return False, str(e)

def find_downloaded_file(base_path: str, extensions: list) -> str | None:
    """Ищет скачанный файл по базовому пути и списку расширений."""
    # Сначала ищем файл с точно указанным расширением
    for ext in extensions:
        path = f"{base_path}.{ext}"
        if os.path.exists(path):
            return path
    
    # Если базовый путь - это сам файл (без расширения в переменной)
    if os.path.exists(base_path):
        return base_path
    
    # Иногда yt-dlp добавляет суффиксы — ищем похожие файлы
    base_dir = os.path.dirname(base_path)
    base_name = os.path.basename(base_path)
    if os.path.exists(base_dir):
        for file in os.listdir(base_dir):
            if file.startswith(base_name[:20]):  # первые 20 символов
                full_path = os.path.join(base_dir, file)
                # Проверяем расширение
                for ext in extensions:
                    if file.endswith(f".{ext}"):
                        return full_path
                # Если нет расширения в списке, но это видеофайл
                if any(file.endswith(f".{ext}") for ext in ["mp4", "mkv", "webm", "avi"]):
                    return full_path
    return None

def cleanup_file(filepath: str):
    """Удаляет файл после отправки, чтобы не засорять диск."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Удалён файл: {filepath}")
    except Exception as e:
        logger.warning(f"Не удалось удалить файл {filepath}: {e}")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start — приветствие."""
    await message.answer(
        "👋 Привет! Я — TelePsycho.\n\n"
        "Что я умею:\n"
        "🎬 <b>YouTube</b> — отправь ссылку, выбери видео или MP3\n"
        "📸 <b>Instagram</b> — отправь ссылку на Reel или пост\n"
        "🎵 <b>Музыка</b> — напиши /music и название трека\n\n"
        "Просто отправь мне ссылку или команду!",
        parse_mode="HTML"
    )

@dp.message(F.text.startswith("/music"))
async def cmd_music(message: Message, state: FSMContext):
    """Обработчик команды /music <название трека>."""
    # Убираем '/music' из текста и берём остаток как название
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "🎵 Напиши название трека после команды.\n"
            "Пример: <code>/music Linkin Park In the End</code>",
            parse_mode="HTML"
        )
        return

    query = parts[1].strip()
    status_msg = await message.answer(f"🔍 Ищу: <b>{query}</b>...", parse_mode="HTML")

    # Ищем 10 результатов
    results = await search_music(query)

    if not results:
        await status_msg.edit_text("❌ Ничего не найдено. Попробуй другой запрос.")
        return

    # Сохраняем результаты в состояние
    await state.update_data(search_results=results, user_id=message.from_user.id)
    await state.set_state(MusicStates.waiting_for_music_choice)

    # Формируем список результатов
    text = f"<b>Найдено {len(results)} результатов:</b>\n\n"
    keyboard_buttons = []
    
    for res in results:
        text += f"<b>{res['num']}.</b> {res['title'][:50]} <i>{res['duration']}</i>\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{res['num']}",
                callback_data=f"music_choice|{res['video_id']}"
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await status_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("music_choice|"))
async def cb_music_choice(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора песни из поиска."""
    video_id = callback.data.split("|", 1)[1]
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    await callback.answer()
    status_msg = await callback.message.edit_text("⏳ Скачиваю музыку...")
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = data.get("user_id", callback.from_user.id)
    search_results = data.get("search_results", [])
    
    # Находим информацию о выбранной песне
    selected = None
    for res in search_results:
        if res["video_id"] == video_id:
            selected = res
            break
    
    output_path = str(DOWNLOAD_DIR / f"music_{user_id}_{video_id}")
    opts = get_ydl_opts_music_search(output_path, url)
    success, info = await download_media(opts, url)

    if not success:
        await status_msg.edit_text("❌ Не удалось скачать трек. Попробуй позже.")
        await state.clear()
        return

    await status_msg.edit_text("📤 Трек готов, отправляю...")

    # Ищем скачанный MP3-файл
    filepath = find_downloaded_file(output_path, ["mp3", "m4a", "ogg", "wav"])

    if not filepath:
        await status_msg.edit_text("❌ Файл не найден после скачивания.")
        await state.clear()
        return

    try:
        audio_file = FSInputFile(filepath)
        title = selected["title"] if selected else "Музыка"
        
        await bot.send_audio(
            chat_id=callback.message.chat.id,
            audio=audio_file,
            title=title[:60],
            caption=f"🎵 {title[:200]}"
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Ошибка отправки аудио: {e}")
        await status_msg.edit_text(f"❌ Ошибка при отправке файла: {e}")
    finally:
        cleanup_file(filepath)
        await state.clear()


@dp.message(F.text)
async def handle_url(message: Message):
    """
    Основной обработчик текстовых сообщений.
    Определяет тип ссылки и запускает нужный загрузчик.
    """
    text = message.text.strip()

    # --- YouTube ---
    if is_youtube_url(text):
        # Создаём инлайн-кнопки для выбора формата
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Видео (MP4)",
                    callback_data=f"yt_video|{text}"
                ),
                InlineKeyboardButton(
                    text="🎵 Аудио (MP3)",
                    callback_data=f"yt_audio|{text}"
                ),
            ]
        ])
        await message.answer(
            "🎬 YouTube-ссылка обнаружена!\nЧто скачать?",
            reply_markup=keyboard
        )
        return

    # --- Instagram ---
    if is_instagram_url(text):
        await download_instagram(message, text)
        return

    # --- Ничего не подошло ---
    await message.answer(
        "🤔 Не распознал ссылку.\n\n"
        "Поддерживаются:\n"
        "• YouTube (youtube.com, youtu.be)\n"
        "• Instagram (Reels, посты)\n"
        "• Музыка: /music <название трека>"
    )


@dp.callback_query(F.data.startswith("yt_video|"))
async def cb_youtube_video(callback: CallbackQuery):
    """Скачивает YouTube-видео после нажатия кнопки 'Видео'."""
    url = callback.data.split("|", 1)[1]

    await callback.answer()  # убираем "часики" на кнопке
    status_msg = await callback.message.edit_text("⏳ Скачиваю видео... Это может занять время.")

    output_path = str(DOWNLOAD_DIR / f"video_{callback.from_user.id}")
    opts = get_ydl_opts_video(output_path)
    success, info = await download_media(opts, url)

    if not success:
        await status_msg.edit_text(
            "❌ Не удалось скачать видео.\n"
            "Возможные причины: видео недоступно, слишком большой размер (>50MB) или ограничения."
        )
        return

    await status_msg.edit_text("📤 Видео скачано, отправляю...")

    filepath = find_downloaded_file(output_path, ["mp4", "mkv", "webm", "avi"])

    if not filepath:
        await status_msg.edit_text("❌ Файл не найден после скачивания.")
        return

    try:
        video_file = FSInputFile(filepath)
        title = info.get("title", "Видео") if isinstance(info, dict) else "Видео"
        await bot.send_video(
            chat_id=callback.message.chat.id,
            video=video_file,
            caption=f"🎬 {title[:200]}",
            supports_streaming=True
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Ошибка отправки видео: {e}")
        await status_msg.edit_text(
            f"❌ Не удалось отправить видео. Скорее всего, файл слишком большой для Telegram (>50MB)."
        )
    finally:
        cleanup_file(filepath)


@dp.callback_query(F.data.startswith("yt_audio|"))
async def cb_youtube_audio(callback: CallbackQuery):
    """Скачивает аудио с YouTube после нажатия кнопки 'Аудио'."""
    url = callback.data.split("|", 1)[1]

    await callback.answer()
    status_msg = await callback.message.edit_text("⏳ Извлекаю аудио...")

    output_path = str(DOWNLOAD_DIR / f"audio_{callback.from_user.id}")
    opts = get_ydl_opts_audio(output_path)
    success, info = await download_media(opts, url)

    if not success:
        await status_msg.edit_text("❌ Не удалось скачать аудио.")
        return

    await status_msg.edit_text("📤 Аудио готово, отправляю...")

    filepath = find_downloaded_file(output_path, ["mp3", "m4a", "ogg", "wav"])

    if not filepath:
        await status_msg.edit_text("❌ Файл не найден после скачивания.")
        return

    try:
        audio_file = FSInputFile(filepath)
        title = info.get("title", "Аудио") if isinstance(info, dict) else "Аудио"
        duration = info.get("duration") if isinstance(info, dict) else None
        await bot.send_audio(
            chat_id=callback.message.chat.id,
            audio=audio_file,
            title=title[:60],
            duration=duration,
            caption=f"🎵 {title[:200]}"
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Ошибка отправки аудио: {e}")
        await status_msg.edit_text(f"❌ Ошибка при отправке: {e}")
    finally:
        cleanup_file(filepath)


async def download_instagram(message: Message, url: str):
    """Скачивает Instagram Reels или пост."""
    status_msg = await message.answer("⏳ Скачиваю с Instagram...")

    output_path = str(DOWNLOAD_DIR / f"insta_{message.from_user.id}")
    opts = get_ydl_opts_instagram(output_path)
    success, info = await download_media(opts, url)

    if not success:
        await status_msg.edit_text(
            "❌ Не удалось скачать с Instagram.\n"
            "Причины: закрытый аккаунт, ссылка устарела или Instagram заблокировал запрос."
        )
        return

    await status_msg.edit_text("📤 Готово, отправляю...")

    # Instagram может отдавать видео или фото
    filepath = find_downloaded_file(output_path, ["mp4", "jpg", "jpeg", "png", "webp"])

    if not filepath:
        await status_msg.edit_text("❌ Файл не найден после скачивания.")
        return

    try:
        ext = filepath.rsplit(".", 1)[-1].lower()
        caption = "📸 Instagram"

        if ext in ("mp4", "mkv", "webm"):
            # Это видео (Reel)
            video_file = FSInputFile(filepath)
            await bot.send_video(
                chat_id=message.chat.id,
                video=video_file,
                caption=caption,
                supports_streaming=True
            )
        else:
            # Это фото
            photo_file = FSInputFile(filepath)
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_file,
                caption=caption
            )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Ошибка отправки из Instagram: {e}")
        await status_msg.edit_text(f"❌ Ошибка при отправке: {e}")
    finally:
        cleanup_file(filepath)


async def main():
    logger.info("Бот запускается...")
    # Удаляем старые апдейты и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
