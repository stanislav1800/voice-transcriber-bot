"""Настройки бота из переменных окружения (.env)."""

import os
from dataclasses import dataclass


def _parse_ids(raw: str) -> frozenset[int]:
    ids = set()
    for part in raw.replace(" ", "").split(","):
        if part:
            ids.add(int(part))
    return frozenset(ids)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    allowed_users: frozenset[int]
    model_size: str
    language: str | None
    beam_size: int
    cpu_threads: int
    max_duration_sec: int
    max_queue: int
    models_dir: str
    tmp_dir: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан")

    # Пустой список допустим: бот будет только сообщать ID в ответ на /start
    allowed = _parse_ids(os.getenv("ALLOWED_USERS", ""))

    # WHISPER_LANGUAGE: "ru", "en", ... или "auto" для автоопределения
    lang = os.getenv("WHISPER_LANGUAGE", "ru").strip().lower()

    return Settings(
        bot_token=token,
        allowed_users=allowed,
        model_size=os.getenv("WHISPER_MODEL", "base").strip(),
        language=None if lang in ("", "auto") else lang,
        beam_size=int(os.getenv("WHISPER_BEAM_SIZE", "1")),
        cpu_threads=int(os.getenv("WHISPER_CPU_THREADS", "1")),
        max_duration_sec=int(os.getenv("MAX_DURATION_MIN", "10")) * 60,
        max_queue=int(os.getenv("MAX_QUEUE", "10")),
        models_dir=os.getenv("MODELS_DIR", "/models"),
        tmp_dir=os.getenv("TMP_DIR", "/tmp/stt"),
    )
