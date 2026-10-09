import asyncio
import logging
import os
import shutil

from aiogram import Bot, Dispatcher

from .config import load_settings
from .handlers import router
from .transcriber import Transcriber
from .worker import Worker

log = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()

    # Чистим временные файлы, оставшиеся от прошлого запуска
    shutil.rmtree(settings.tmp_dir, ignore_errors=True)
    os.makedirs(settings.tmp_dir, exist_ok=True)
    os.makedirs(settings.models_dir, exist_ok=True)

    # Модель грузим один раз при старте (при первом запуске она скачается)
    transcriber = await asyncio.to_thread(
        Transcriber,
        settings.model_size,
        settings.models_dir,
        settings.cpu_threads,
        settings.language,
        settings.beam_size,
    )

    # Без parse_mode по умолчанию: распознанный текст отправляется как есть
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    worker = Worker(bot, transcriber, settings.max_queue)
    worker_task = asyncio.create_task(worker.run())

    try:
        log.info("Бот запущен")
        await dp.start_polling(bot, settings=settings, worker=worker)
    finally:
        worker_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
