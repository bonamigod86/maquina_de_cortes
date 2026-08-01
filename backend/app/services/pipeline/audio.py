"""Etapa 1: extração de áudio do vídeo."""
from __future__ import annotations

import soundfile as sf

from app.utils import ffmpeg as ff


def extract_audio(video_path: str, out_wav: str, on_progress=None, duration: float | None = None, cancel_event=None) -> str:
    ff.run_ffmpeg(
        [
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            out_wav,
        ],
        on_progress=on_progress,
        duration=duration,
        cancel_event=cancel_event,
    )
    return out_wav


def load_audio_samples(wav_path: str) -> tuple[any, int]:
    """Carrega amostras de áudio (16kHz mono) para análise de sinais."""
    data, sr = sf.read(wav_path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, sr
