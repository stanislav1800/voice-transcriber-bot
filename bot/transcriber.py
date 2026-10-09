"""Обёртка над faster-whisper. Работает синхронно — вызывать из отдельного потока."""

import logging
from dataclasses import dataclass

import av
from faster_whisper import WhisperModel

log = logging.getLogger(__name__)

# Пауза между фрагментами речи, после которой начинается новый абзац
PARAGRAPH_GAP_SEC = 2.0


@dataclass
class Progress:
    """Прогресс распознавания; пишется из рабочего потока, читается из asyncio."""

    done: float = 0.0
    total: float = 0.0

    @property
    def percent(self) -> int:
        if self.total <= 0:
            return 0
        return min(99, int(self.done / self.total * 100))


def probe_duration(path: str) -> float:
    """Длительность файла в секундах без декодирования всего аудио."""
    with av.open(path) as container:
        if container.duration:
            return container.duration / 1_000_000
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is not None and stream.duration and stream.time_base:
            return float(stream.duration * stream.time_base)
    return 0.0


class Transcriber:
    def __init__(
        self,
        model_size: str,
        models_dir: str,
        cpu_threads: int,
        language: str | None,
        beam_size: int,
    ) -> None:
        log.info("Загружаю модель %s (int8, %d потоков)…", model_size, cpu_threads)
        self._model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
            num_workers=1,
            download_root=models_dir,
        )
        self._language = language
        self._beam_size = beam_size
        log.info("Модель загружена")

    def transcribe(self, path: str, progress: Progress) -> str:
        segments, info = self._model.transcribe(
            path,
            language=self._language,
            beam_size=self._beam_size,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
        )
        progress.total = info.duration

        paragraphs: list[list[str]] = [[]]
        last_end = 0.0
        for seg in segments:  # генератор: распознавание идёт по мере итерации
            text = seg.text.strip()
            if text:
                if paragraphs[-1] and seg.start - last_end > PARAGRAPH_GAP_SEC:
                    paragraphs.append([])
                paragraphs[-1].append(text)
                last_end = seg.end
            progress.done = seg.end

        return "\n\n".join(" ".join(p) for p in paragraphs if p)
