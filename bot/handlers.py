import asyncio
import contextlib
import logging
import os
import uuid

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from .config import Settings
from .transcriber import probe_duration
from .worker import Job, Worker

log = logging.getLogger(__name__)
router = Router()

# Ограничение Bot API на скачивание файлов
MAX_FILE_SIZE = 20 * 1024 * 1024


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message, settings: Settings) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in settings.allowed_users:
        await message.answer(
            f"Доступ закрыт. Твой ID: <code>{user_id}</code>", parse_mode="HTML"
        )
        return
    await message.answer(
        "Пришли или перешли голосовое, кружок или аудиофайл — верну текст.\n"
        f"Лимит длительности: {settings.max_duration_sec // 60} мин."
    )


def _extract_media(message: Message):
    """(file_id, file_size, duration) для поддерживаемых типов сообщений."""
    if message.voice:
        m = message.voice
        return m.file_id, m.file_size, m.duration
    if message.video_note:
        m = message.video_note
        return m.file_id, m.file_size, m.duration
    if message.audio:
        m = message.audio
        return m.file_id, m.file_size, m.duration
    if message.document and (message.document.mime_type or "").startswith(
        ("audio/", "video/")
    ):
        m = message.document
        return m.file_id, m.file_size, None
    return None


@router.message(F.voice | F.video_note | F.audio | F.document)
async def on_media(message: Message, bot: Bot, settings: Settings, worker: Worker) -> None:
    if not message.from_user or message.from_user.id not in settings.allowed_users:
        return  # чужим не отвечаем

    media = _extract_media(message)
    if media is None:
        await message.reply("Это не похоже на аудио.")
        return
    file_id, file_size, duration = media

    if file_size and file_size > MAX_FILE_SIZE:
        await message.reply("Файл больше 20 МБ — Telegram не даст его скачать.")
        return
    if duration and duration > settings.max_duration_sec:
        await message.reply(
            f"Слишком длинная запись: лимит {settings.max_duration_sec // 60} мин."
        )
        return
    if worker.is_full():
        await message.reply("Очередь переполнена, попробуй чуть позже.")
        return

    status = await message.reply("⬇️ Скачиваю…")
    path = os.path.join(settings.tmp_dir, f"{uuid.uuid4().hex}.bin")
    try:
        await bot.download(file_id, destination=path)
        if duration is None:  # у документов длительность заранее неизвестна
            duration = await asyncio.to_thread(probe_duration, path)
            if duration > settings.max_duration_sec:
                os.remove(path)
                await status.edit_text(
                    f"Слишком длинная запись: лимит {settings.max_duration_sec // 60} мин."
                )
                return
    except Exception:
        log.exception("Не удалось скачать или прочитать файл")
        with contextlib.suppress(OSError):
            os.remove(path)
        await status.edit_text("❌ Не удалось скачать или прочитать файл.")
        return

    ahead = worker.submit(
        Job(chat_id=message.chat.id, status_message_id=status.message_id, file_path=path)
    )
    if ahead:
        await status.edit_text(f"⏳ В очереди, впереди: {ahead}")
