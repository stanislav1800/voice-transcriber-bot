"""Распознавание речи через GigaAM-v3 (onnx-asr). Работает синхронно — вызывать из отдельного потока."""

import logging
from dataclasses import dataclass

import av
import numpy as np
import onnx_asr
import onnxruntime as rt

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
# Пауза между фрагментами речи, после которой начинается новый абзац
PARAGRAPH_GAP_SEC = 2.0
# GigaAM понимает куски до ~25 с, длинную речь режем по паузам через VAD
MAX_SEGMENT_SEC = 20


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


def decode_audio(path: str) -> np.ndarray:
    """Любой аудио/видео-файл → моно float32, 16 кГц."""
    chunks: list[np.ndarray] = []
    resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
    with av.open(path) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("В файле нет аудиодорожки")
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32, copy=False)


class Transcriber:
    def __init__(self, model_name: str, quantization: str | None, cpu_threads: int) -> None:
        opts = rt.SessionOptions()
        opts.intra_op_num_threads = cpu_threads
        opts.inter_op_num_threads = 1
        # Не держать арену памяти между запросами — важно при 1 ГБ RAM
        opts.enable_cpu_mem_arena = False

        log.info("Загружаю модель %s (%s)…", model_name, quantization or "fp32")
        vad = onnx_asr.load_vad("silero", sess_options=opts)
        model = onnx_asr.load_model(
            model_name,
            quantization=quantization,
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self._model = model.with_vad(
            vad,
            batch_size=1,
            max_speech_duration_s=MAX_SEGMENT_SEC,
            min_silence_duration_ms=300,
            speech_pad_ms=200,
        )
        log.info("Модель загружена")

    def transcribe(self, path: str, progress: Progress) -> str:
        audio = decode_audio(path)
        progress.total = len(audio) / SAMPLE_RATE
        if not len(audio):
            return ""

        paragraphs: list[list[str]] = [[]]
        last_end = 0.0
        for seg in self._model.recognize(audio, sample_rate=SAMPLE_RATE):
            text = seg.text.strip()
            if text:
                if paragraphs[-1] and seg.start - last_end > PARAGRAPH_GAP_SEC:
                    paragraphs.append([])
                paragraphs[-1].append(text)
                last_end = seg.end
            progress.done = seg.end

        return "\n\n".join(" ".join(p) for p in paragraphs if p)
