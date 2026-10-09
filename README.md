# voice-transcriber-bot

Личный Telegram-бот, который превращает голосовые в текст. Распознавание полностью локальное: модель [GigaAM-v3](https://huggingface.co/ai-sage/GigaAM-v3) от Сбера, обученная на русской речи, через [onnx-asr](https://github.com/istupakov/onnx-asr). Рассчитан на слабый сервер: 1 vCPU / 1 ГБ RAM.

- голосовые, кружки, аудиофайлы и аудио/видео-документы (до 20 МБ — ограничение Bot API);
- текст сразу с пунктуацией (e2e-модель), длинная речь режется по паузам (Silero VAD);
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

При первом запуске скачивается модель (~230 МБ в int8) в volume `models`, при перезапусках повторно не качается.

Свой Telegram ID: напиши боту `/start` — он ответит «Доступ закрыт. Твой ID: …». Впиши его в `ALLOWED_USERS` и перезапусти: `docker compose up -d`.

## Настройки (.env)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_TOKEN` | — | токен от @BotFather |
| `ALLOWED_USERS` | — | разрешённые Telegram ID через запятую |
| `ASR_MODEL` | `gigaam-v3-e2e-rnnt` | или `gigaam-v3-e2e-ctc` — чуть быстрее, чуть менее точная |
| `ASR_QUANTIZATION` | `int8` | `none` — полная точность (~900 МБ, на 1 ГБ RAM не влезет) |
| `CPU_THREADS` | `1` | потоки CPU |
| `MAX_DURATION_MIN` | `10` | лимит длительности записи |
| `MAX_QUEUE` | `10` | максимум задач в очереди |

## Память

Лимит контейнера — 550 МБ (`docker-compose.yml`), GigaAM в int8 в него укладывается. На хосте желательно иметь swap как страховку:

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
docker image prune -f && docker builder prune -f   # убрать старые образы и кэш сборки
```
