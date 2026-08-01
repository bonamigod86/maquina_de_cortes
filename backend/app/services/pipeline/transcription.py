"""Etapa 2: transcrição com Faster-Whisper (timestamps de frases e palavras)."""
from __future__ import annotations

import threading
from pathlib import Path

from app.core.config import MODELS_CACHE, Settings
from app.models.schemas import Segment, Transcription, WordTS

_lock = threading.Lock()
_model_cache: dict = {}


def _model_dir(settings: Settings) -> Path:
    return MODELS_CACHE / f"models--Systran--faster-whisper-{settings.whisper_model}"


def ensure_model_downloaded(settings: Settings, on_progress=None, cancel_event=None) -> None:
    """Baixa o modelo Whisper com progresso reportado (primeira execução)."""
    from huggingface_hub import snapshot_download
    from tqdm import tqdm

    repo = f"Systran/faster-whisper-{settings.whisper_model}"
    if _model_dir(settings).exists():
        return

    class _ReportTqdm(tqdm):
        def __init__(self, *args, **kwargs):
            self._report = kwargs.pop("report", None)
            self._last = 0.0
            super().__init__(*args, **kwargs)

        def update(self, n=1):
            super().update(n)
            if self.total and self._report:
                frac = self.n / self.total
                if frac - self._last >= 0.01 or frac >= 1.0:
                    self._last = frac
                    self._report(frac)

    def _progress(frac: float) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Download cancelado")
        if on_progress:
            on_progress(frac * 0.95)

    MODELS_CACHE.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo,
        local_dir=str(MODELS_CACHE),
        tqdm_class=_ReportTqdm,
        tqdm_kwargs={"report": _progress},
    )
    if on_progress:
        on_progress(1.0)


def _get_model(settings: Settings, on_progress=None, cancel_event=None):
    global _model_cache
    key = settings.whisper_model
    with _lock:
        if key not in _model_cache:
            from faster_whisper import WhisperModel

            ensure_model_downloaded(settings, on_progress, cancel_event)
            device = "cuda" if settings.use_gpu else "cpu"
            compute = settings.whisper_compute
            if compute == "auto":
                compute = "float16" if device == "cuda" else "int8"
            try:
                _model_cache[key] = WhisperModel(
                    settings.whisper_model,
                    device=device,
                    compute_type=compute,
                    download_root=str(MODELS_CACHE),
                )
            except Exception:
                _model_cache[key] = WhisperModel(
                    settings.whisper_model, device="cpu", compute_type="int8", download_root=str(MODELS_CACHE)
                )
        return _model_cache[key]


def transcribe(audio_path: str, settings: Settings, on_progress=None, cancel_event=None) -> Transcription:
    """Transcreve o áudio gerando timestamps de segmentos e palavras."""
    model = _get_model(settings, on_progress=on_progress, cancel_event=cancel_event)
    language = None if settings.language == "auto" else settings.language
    kwargs = {
        "word_timestamps": True,
        "vad_filter": True,
        "language": language,
        "beam_size": 3,
    }

    segments_info, info = model.transcribe(audio_path, **kwargs)
    segments: list[Segment] = []
    total = float(info.duration) or 1.0
    for i, seg in enumerate(segments_info):
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Transcrição cancelada")
        if on_progress:
            on_progress(min(seg.end / total, 1.0))
        words = [
            WordTS(word=w.word, start=w.start, end=w.end, probability=float(w.probability or 1.0))
            for w in (seg.words or [])
        ]
        segments.append(
            Segment(
                id=i,
                start=float(seg.start),
                end=float(seg.end),
                text=seg.text.strip(),
                words=words,
            )
        )

    return Transcription(
        language=getattr(info, "language", "") or "",
        duration=float(info.duration),
        segments=segments,
    )


def sentences_from_segments(transcription: Transcription) -> list[dict]:
    """Divide a transcrição em frases (sentenças) com timestamps interpolados.

    Timestamps das palavras dentro do segmento são aproximados por
    posição proporcional — suficiente para cortes e legendas precisas
    ao nível de ~100ms.
    """
    sentences: list[dict] = []
    punct_chars = {".", "!", "?", "…", ":", ";"}
    for seg in transcription.segments:
        text = seg.text.strip()
        if not text:
            continue
        words = seg.words

        # índices de corte após pontuação forte
        cut_after = [i for i, c in enumerate(text) if c in punct_chars]
        starts = [0] + [i + 1 for i in cut_after if i + 1 < len(text)]
        ends = [i + 1 for i in cut_after] + [len(text)]

        n = len(words)
        for si, (s, e) in enumerate(zip(starts, ends)):
            chunk = text[s:e].strip()
            if not chunk:
                continue
            # proporção temporal do trecho dentro do segmento
            frac_start = s / max(len(text), 1)
            frac_end = e / max(len(text), 1)
            # timestamps usando palavras reais quando disponíveis
            if n and words:
                i0 = min(int(frac_start * n), n - 1)
                i1 = min(int(frac_end * n), n - 1)
                w0, w1 = words[i0], words[i1]
                # ajuste fino do início: palavra cujo início cai antes
                while i0 > 0 and words[i0].start > seg.start + frac_start * (seg.end - seg.start):
                    i0 -= 1
                    w0 = words[i0]
                t0 = w0.start
                t1 = w1.end
            else:
                t0 = seg.start + frac_start * (seg.end - seg.start)
                t1 = seg.start + frac_end * (seg.end - seg.start)
                t1 = max(t1, t0 + 0.2)
            t0 = max(t0, seg.start)
            t1 = min(t1, seg.end)
            t1 = max(t1, t0 + 0.1)
            sentences.append(
                {
                    "index": len(sentences),
                    "start": round(t0, 3),
                    "end": round(t1, 3),
                    "text": chunk,
                    "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability} for w in words],
                }
            )
    return sentences


def save_transcription(project_id: str, transcription: Transcription, sentences: list[dict]) -> None:
    from app.services.project import ProjectStore

    ProjectStore.write_json(project_id, "transcription.json", transcription.model_dump())
    ProjectStore.write_json(project_id, "sentences.json", sentences)
