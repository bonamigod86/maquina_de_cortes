"""Sistema de aprendizado: ajusta pontuações com base no perfil do usuário."""
from __future__ import annotations

from app.services.learning.store import FeedbackStore

_store = FeedbackStore()


def user_profile() -> dict:
    return _store.profile()


def apply_preference_weights(score: float, types: list[str], duration_pref: float, profile: dict) -> float:
    """Multiplica a pontuação bruta por afinidade aprendida (tipos + duração)."""
    adjusted = score
    weights = profile.get("tag_weights") or {}
    for t in types:
        w = weights.get(t, 0.0)
        if w:
            adjusted *= 1.0 + (w - 0.5) * 0.4
    pref_dur = profile.get("preferred_duration")
    if pref_dur and duration_pref:
        diff = abs(pref_dur - duration_pref)
        if diff <= 5:
            adjusted *= 1.1
        elif diff > 20:
            adjusted *= 0.92
    return min(adjusted, 1.0)
