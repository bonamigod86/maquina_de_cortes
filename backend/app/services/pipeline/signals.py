"""Etapa 3: detecção de cenas, silêncios, energia, ritmo e intensidade de voz."""
from __future__ import annotations

import numpy as np

from app.models.schemas import Analysis, Scene, SentenceSignal, Silence

HOP = 0.1  # janela de análise em segundos


def detect_silences(samples: np.ndarray, sr: int, threshold_db: float = -35.0, min_silence: float = 0.4) -> list[Silence]:
    """Detecta períodos de silêncio baseados em RMS."""
    hop = int(HOP * sr)
    rms = _rms_curve(samples, sr)
    thr = 10 ** (threshold_db / 20)
    silent = rms < thr
    silences: list[Silence] = []
    start = None
    for i, is_sil in enumerate(silent):
        t = i * HOP
        if is_sil and start is None:
            start = t
        elif not is_sil and start is not None:
            d = t - start
            if d >= min_silence:
                silences.append(Silence(start=round(start, 2), end=round(t, 2), duration=round(d, 2)))
            start = None
    if start is not None:
        d = len(samples) / sr - start
        if d >= min_silence:
            silences.append(Silence(start=round(start, 2), end=round(len(samples) / sr, 2), duration=round(d, 2)))
    return silences


def _rms_curve(samples: np.ndarray, sr: int) -> np.ndarray:
    hop = int(HOP * sr)
    n = max(1, len(samples) // hop)
    rms = np.sqrt(np.mean(np.power(samples[: n * hop].reshape(n, hop), 2), axis=1))
    return rms


def _envelope(samples: np.ndarray, sr: int, window: float = 0.05) -> np.ndarray:
    hop = int(window * sr)
    n = max(1, len(samples) // hop)
    return np.sqrt(np.mean(np.power(samples[: n * hop].reshape(n, hop), 2), axis=1))


def energy_profile(samples: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Curva de energia (RMS) em janelas de HOP segundos."""
    rms = _rms_curve(samples, sr)
    times = np.arange(len(rms)) * HOP
    return times, rms


def detect_scenes(video_path: str, on_progress=None, cancel_event=None, fps_target: float = 2.0) -> list[float]:
    """Detecta cortes de cena/câmera com PySceneDetect (amostra frames)."""
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(video_path)
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=27.0, min_scene_len=0.8))
    cuts: list[float] = []
    try:
        for cuts_iter, _ in sm.detect_scenes(video, show_progress=False, frame_skip=int(video.frame_rate // fps_target)):
            cuts.extend(float(c.get_seconds()) for c in cuts_iter)
    except Exception:
        pass
    return sorted(set(round(c, 2) for c in cuts))


def analyze_sentences(
    sentences: list[dict],
    samples: np.ndarray,
    sr: int,
    silences: list[Silence],
    scenes: list[float],
) -> list[SentenceSignal]:
    """Computa sinais por frase: energia, ritmo, intensidade e emoção prosódica."""
    times, rms = energy_profile(samples, sr)
    if len(times) == 0:
        return []
    rms_max = max(float(np.percentile(rms, 99)), 1e-6)
    silence_mask = np.zeros(len(times), dtype=bool)
    for s in silences:
        silence_mask[(times >= s.start) & (times <= s.end)] = True

    def _rms_in(t0: float, t1: float) -> float:
        m = (times >= t0) & (times <= t1) & (~silence_mask)
        if not m.any():
            return 0.0
        return float(np.mean(rms[m]) / rms_max)

    out: list[SentenceSignal] = []
    for i, s in enumerate(sentences):
        energy = _rms_in(s["start"], s["end"])
        n_words = len([w for w in s["words"] if s["start"] <= w["start"] <= s["end"]])
        pace = n_words / max(s["end"] - s["start"], 0.3)
        # intensidade = energia + variação local de energia
        m = (times >= max(s["start"] - 0.5, 0)) & (times <= min(s["end"] + 0.5, times[-1]))
        local = rms[m] / rms_max
        intensity = float(np.clip(energy * 0.7 + (np.std(local) * 1.5 if len(local) > 1 else 0.0), 0, 1.2))
        # emoção prosódica: picos de energia rápidos + pausa antes (suspense)
        pause_before = 0.0
        for sil in silences:
            if sil.end <= s["start"] + 0.1 and sil.start >= s["start"] - 3.0:
                pause_before = max(pause_before, sil.duration)
        emotion = float(np.clip(intensity * 0.6 + min(pause_before, 1.5) / 1.5 * 0.4, 0, 1))
        out.append(
            SentenceSignal(
                sentence_index=i,
                start=s["start"],
                end=s["end"],
                energy=round(energy, 3),
                pace=round(pace, 2),
                intensity=round(min(intensity, 1.0), 3),
                emotion_score=round(emotion, 3),
                text=s["text"],
            )
        )
    return out


def run_signals(
    project_id: str,
    video_path: str,
    wav_path: str,
    sentences: list[dict],
    on_progress=None,
    cancel_event=None,
) -> Analysis:
    """Executa toda a análise de sinais e persiste o resultado."""
    from app.services.pipeline.audio import load_audio_samples

    samples, sr = load_audio_samples(wav_path)
    if on_progress:
        on_progress(0.15)
    silences = detect_silences(samples, sr)
    if cancel_event and cancel_event.is_set():
        raise RuntimeError("Análise cancelada")
    if on_progress:
        on_progress(0.35)
    scenes = detect_scenes(video_path, on_progress=lambda p: on_progress(0.35 + p * 0.45), cancel_event=cancel_event)
    if on_progress:
        on_progress(0.85)
    sigs = analyze_sentences(sentences, samples, sr, silences, scenes)
    if on_progress:
        on_progress(1.0)
    scenes_out: list[Scene] = []
    prev = 0.0
    for c in scenes:
        if c - prev >= 0.5:
            scenes_out.append(Scene(start=round(prev, 2), end=round(c, 2)))
        prev = c
    scenes_out.append(Scene(start=round(prev, 2), end=round(len(samples) / sr, 2)))
    return Analysis(
        scenes=scenes_out,
        silences=silences,
        sentence_signals=sigs,
    )
