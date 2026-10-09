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
    asr_model: str
    asr_quantization: str | None
    cpu_threads: int
    max_duration_sec: int
    max_queue: int
    tmp_dir: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан")

    # Пустой список допустим: бот будет только сообщать ID в ответ на /start
    allowed = _parse_ids(os.getenv("ALLOWED_USERS", ""))

    # ASR_QUANTIZATION: int8 (меньше памяти) или пусто/none для полной точности
    quant = os.getenv("ASR_QUANTIZATION", "int8").strip().lower()

    return Settings(
        bot_token=token,
        allowed_users=allowed,
        asr_model=os.getenv("ASR_MODEL", "gigaam-v3-e2e-rnnt").strip(),
        asr_quantization=None if quant in ("", "none") else quant,
        cpu_threads=int(os.getenv("CPU_THREADS", "1")),
        max_duration_sec=int(os.getenv("MAX_DURATION_MIN", "10")) * 60,
        max_queue=int(os.getenv("MAX_QUEUE", "10")),
        tmp_dir=os.getenv("TMP_DIR", "/tmp/stt"),
    )
