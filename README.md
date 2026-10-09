# voice-transcriber-bot

Личный Telegram-бот, который превращает голосовые в текст. Распознавание полностью локальное ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)), рассчитан на слабый сервер: 1 vCPU / 1 ГБ RAM.

- голосовые, кружки, аудиофайлы и аудио/видео-документы (до 20 МБ — ограничение Bot API);
- доступ только для ID из `ALLOWED_USERS`, остальным бот не отвечает;
- задачи выполняются по одной, статус «Распознаю… N%» обновляется в сообщении;
- длинный текст режется на несколько сообщений;
- контейнер ограничен по памяти, чтобы при нехватке не пострадали другие сервисы на хосте.

## Запуск

```bash
git clone https://github.com/stanislav1800/voice-transcriber-bot.git
cd voice-transcriber-bot
cp .env.example .env
nano .env            # BOT_TOKEN; ALLOWED_USERS можно заполнить позже
docker compose up -d --build
docker compose logs -f
```

При первом запуске скачивается модель (~150 МБ для `base`) в volume `models`, при перезапусках повторно не качается.

Свой Telegram ID: напиши боту `/start` — он ответит «Доступ закрыт. Твой ID: …». Впиши его в `ALLOWED_USERS` и перезапусти: `docker compose up -d`.

## Настройки (.env)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_TOKEN` | — | токен от @BotFather |
| `ALLOWED_USERS` | — | разрешённые Telegram ID через запятую |
| `WHISPER_MODEL` | `base` | `tiny` / `base` / `small` |
| `WHISPER_LANGUAGE` | `ru` | код языка или `auto` |
| `WHISPER_BEAM_SIZE` | `1` | 1 — быстрее, 5 — немного точнее |
| `WHISPER_CPU_THREADS` | `1` | потоки CPU |
| `MAX_DURATION_MIN` | `10` | лимит длительности записи |
| `MAX_QUEUE` | `10` | максимум задач в очереди |

## Память

| Модель | RAM (int8) | Качество на русском |
|---|---|---|
| `tiny` | ~150 МБ | слабое |
| `base` | ~250–300 МБ | среднее |
| `small` | ~550–700 МБ | хорошее |

Лимит контейнера — 450 МБ (`docker-compose.yml`). Для `small` подними `mem_limit` до ~800m, но только если на сервере реально есть свободная память, иначе модель уйдёт в swap и распознавание станет очень медленным.

На хосте желательно иметь swap как страховку:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## Если модель не скачивается

Модели берутся с huggingface.co. Если сервер не может до него достучаться, добавь в `.env` зеркало:

```
HF_ENDPOINT=https://hf-mirror.com
```

## Обновление

```bash
git pull && docker compose up -d --build
```
