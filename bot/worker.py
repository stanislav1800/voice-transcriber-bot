"""Очередь задач: распознаём строго по одной, чтобы не перегружать 1 vCPU."""

import asyncio
import contextlib
import logging
import os
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from .transcriber import Progress, Transcriber

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096
PROGRESS_INTERVAL_SEC = 5


@dataclass
class Job:
    chat_id: int
    status_message_id: int
    file_path: str


class Worker:
    def __init__(self, bot: Bot, transcriber: Transcriber, max_queue: int) -> None:
        self._bot = bot
        self._transcriber = transcriber
        self._queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=max_queue)
        self._busy = False

    def is_full(self) -> bool:
        return self._queue.full()

    def submit(self, job: Job) -> int:
        """Ставит задачу в очередь, возвращает сколько задач перед ней."""
        ahead = self._queue.qsize() + (1 if self._busy else 0)
        self._queue.put_nowait(job)
        return ahead

    async def run(self) -> None:
        while True:
            job = await self._queue.get()
            self._busy = True
            try:
                await self._process(job)
            except Exception:
                log.exception("Ошибка при распознавании %s", job.file_path)
                await self._edit(job, "❌ Не получилось распознать файл.")
            finally:
                self._busy = False
                self._queue.task_done()
                with contextlib.suppress(OSError):
                    os.remove(job.file_path)

    async def _process(self, job: Job) -> None:
        await self._edit(job, "🎧 Распознаю…")
        progress = Progress()
        task = asyncio.create_task(
            asyncio.to_thread(self._transcriber.transcribe, job.file_path, progress)
        )

        last_percent = -1
        while True:
            done, _ = await asyncio.wait({task}, timeout=PROGRESS_INTERVAL_SEC)
            if done:
                break
            if progress.percent != last_percent:
                last_percent = progress.percent
                await self._edit(job, f"🎧 Распознаю… {last_percent}%")

        text = task.result()
        if not text:
            await self._edit(job, "🤷 Речь не распознана.")
            return

        chunks = split_text(text, TELEGRAM_LIMIT)
        await self._edit(job, chunks[0])
        for chunk in chunks[1:]:
            await self._bot.send_message(job.chat_id, chunk)

    async def _edit(self, job: Job, text: str) -> None:
        try:
            await self._bot.edit_message_text(
                text=text, chat_id=job.chat_id, message_id=job.status_message_id
            )
        except TelegramBadRequest as e:
            # «message is not modified» и подобное — не страшно
            log.debug("edit_message_text: %s", e)


def split_text(text: str, limit: int) -> list[str]:
    """Режет длинный текст на части по границам абзацев/слов."""
    chunks: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks
