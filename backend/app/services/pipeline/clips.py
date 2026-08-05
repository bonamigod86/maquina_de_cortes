"""Etapa 5: geração de cortes inteligentes com pontuação e ajuste de fronteiras."""
from __future__ import annotations

from app.core.config import Settings
from app.models.schemas import Clip, ClipScores, ContentAnalysis
from app.services.learning.profiler import apply_preference_weights


def _silences_between(silences: list[dict], t0: float, t1: float) -> list[dict]:
    return [s for s in silences if s["end"] > t0 and s["start"] < t1]


def _trim_silence_edges(t0: float, t1: float, silences: list[dict]) -> tuple[float, float]:
    """Remove silêncios longos (>0.55s) das bordas do trecho."""
    for s in sorted(silences, key=lambda x: x["start"]):
        if s["start"] <= t0 <= s["end"] and s["duration"] >= 0.55:
            t0 = s["end"]
        if s["start"] <= t1 <= s["end"] and s["duration"] >= 0.55 and t1 - t0 > 2.0:
            t1 = s["start"]
    return max(t0, 0.0), t1


def _expand_window(
    si: int,
    ei: int,
    target: float,
    sentences: list[dict],
    video_end: float,
    min_dur: float,
    max_dur: float,
) -> tuple[int, int]:
    """Ajusta o intervalo de frases para chegar perto da duração alvo,
    sempre alinhado a fronteiras de frases (nunca corta ideias no meio)."""
    dur = sentences[ei]["end"] - sentences[si]["start"]
    target = max(min_dur, min(target, max_dur))
    guard = 0
    while dur < target and guard < 60:
        guard += 1
        # tenta estender para frente
        if ei + 1 < len(sentences):
            nxt_end = sentences[ei + 1]["end"]
            if nxt_end - sentences[si]["start"] <= max_dur:
                ei += 1
                dur = sentences[ei]["end"] - sentences[si]["start"]
                continue
        # tenta estender para trás
        if si - 1 >= 0:
            prev_start = sentences[si - 1]["start"]
            if sentences[ei]["end"] - prev_start <= max_dur:
                si -= 1
                dur = sentences[ei]["end"] - sentences[si]["start"]
                continue
        break
    while dur > target + 0.5 and ei > si:
        # encolhe pelo fim (mantém o início do destaque)
        new_ei = ei - 1
        new_dur = sentences[new_ei]["end"] - sentences[si]["start"]
        if new_dur < min_dur:
            break
        ei = new_ei
        dur = new_dur
    return si, ei


def _nearest_duration(pref: float, settings: Settings) -> float:
    """Escolhe a duração padrão mais próxima das durações configuradas."""
    if not settings.clip_durations:
        return max(settings.min_clip_duration, min(pref, settings.max_clip_duration))
    best = min(settings.clip_durations, key=lambda d: abs(d - pref))
    return max(settings.min_clip_duration, min(best, settings.max_clip_duration))


def _score_total(scores: ClipScores) -> float:
    return (
        scores.retention * 0.30
        + scores.virality * 0.25
        + scores.educational * 0.15
        + scores.sharing * 0.15
        + scores.emotion * 0.10
        + scores.clarity * 0.05
    )


def build_clips(
    project_id: str,
    sentences: list[dict],
    content: ContentAnalysis,
    silences: list[dict],
    settings: Settings,
    profile: dict,
    video_end: float,
) -> list[Clip]:
    """Gera os cortes finais: pontuados, sem sobreposição, com fronteiras limpas."""
    drafts: list[Clip] = []
    for h in content.highlights:
        si, ei = h.sentence_start, h.sentence_end
        if si < 0 or ei >= len(sentences) or ei < si:
            continue
        target = _nearest_duration(h.duration_pref, settings)
        si, ei = _expand_window(si, ei, target, sentences, video_end, settings.min_clip_duration, settings.max_clip_duration)
        t0 = sentences[si]["start"]
        t1 = sentences[ei]["end"]
        t0, t1 = _trim_silence_edges(t0, t1, silences)
        if t1 - t0 < settings.min_clip_duration - 2:
            continue
        t1 = min(t1, video_end)

        excerpt = " ".join(s["text"] for s in sentences[si : ei + 1])
        scores = ClipScores(
            retention=round(h.retention, 2),
            virality=round(h.virality, 2),
            educational=round(h.educational, 2),
            sharing=round(h.sharing, 2),
            emotion=round(h.emotion, 2),
            clarity=round(h.clarity, 2),
        )
        total = apply_preference_weights(_score_total(scores), h.types, h.duration_pref, profile)
        drafts.append(
            Clip(
                id="",
                project_id=project_id,
                source_start=round(t0, 2),
                source_end=round(t1, 2),
                duration=round(t1 - t0, 2),
                tags=h.types,
                scores=scores,
                total_score=round(total, 3),
                transcript_excerpt=excerpt,
            )
        )

    # dedupe: escolhe os melhores sem sobreposição significativa
    drafted: list[Clip] = []
    for c in sorted(drafts, key=lambda c: c.total_score, reverse=True):
        overlaps = any(
            c.source_start < p.source_end - 1.5 and c.source_end > p.source_start + 1.5 for p in drafted
        )
        if not overlaps:
            drafted.append(c)
    return drafted
