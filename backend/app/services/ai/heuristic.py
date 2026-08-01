"""Análise heurística de conteúdo — fallback quando não há LLM disponível.

Identifica ganchos, momentos de energia, pausas dramáticas e pontuação
forte usando apenas regras de prosódia e texto.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.schemas import ContentAnalysis, Highlight

HOOK_MARKERS = re.compile(
    r"\b(você|vocês|sabe|olha|escuta|presta atenção|peraí|espera|incrível|segredo|importante|"
    r"vou te|quer saber|a verdade é|ninguém te conta|o problema|a chave|imagina|cuidado|"
    r"atenção|alerta|dica|truque|erro|nunca|sempre|100|10 vezes|mudou|explodiu|porque)\b",
    re.IGNORECASE,
)
CTA_MARKERS = re.compile(
    r"\b(segue|inscreve|comenta|curte|salva|compartilha|me segue|siga|link|comenta aqui|"
    r"deixa o like|curtir|compartilhar|ativar as notificações)\b",
    re.IGNORECASE,
)
STORY_MARKERS = re.compile(
    r"\b(eu estava|eu fui|quando eu|um dia|comecei|aconteceu|lembro|aí ele|então ela|"
    r"me contou|acontece que|era uma vez)\b",
    re.IGNORECASE,
)
EMOTION_MARKERS = re.compile(
    r"\b(amei|odeio|incrível|terrível|chorei|ri|medo|feliz|triste|raiva|orgulho|"
    r"frustrante|surpreendente|emocionante|fascinante)\b",
    re.IGNORECASE,
)


def heuristic_content_analysis(sentences: list[dict], signals: list[dict]) -> ContentAnalysis:
    """Gera destaques com base em regras de texto e prosódia."""
    highlights: list[Highlight] = []
    n = len(sentences)
    for i, s in enumerate(sentences):
        text = s["text"]
        low = text.lower()
        h = Highlight(sentence_start=i, sentence_end=i, types=[], score=0.0)
        score = 0.3
        reasons = []
        types: list[str] = []

        if HOOK_MARKERS.search(low):
            score += 0.15
            types.append("gancho")
            reasons.append("frase de engajamento direto")
        if "?" in text:
            score += 0.1
            types.append("gancho")
            reasons.append("pergunta que desperta curiosidade")
        if "!" in text:
            score += 0.1
            reasons.append("ênfase forte")
        if CTA_MARKERS.search(low):
            score += 0.1
            types.append("cta")
            reasons.append("chamada para ação natural")
        if STORY_MARKERS.search(low):
            score += 0.1
            types.append("historia")
            reasons.append("início de história")
        if EMOTION_MARKERS.search(low):
            score += 0.1
            types.append("emocionante")
            reasons.append("carga emocional no texto")

        sig = signals[i] if i < len(signals) else None
        if sig:
            if sig.get("intensity", 0) > 0.75:
                score += 0.15
                types.append("energia")
                reasons.append("pico de intensidade de voz")
            if sig.get("pace", 0) > 5.0:
                score += 0.08
                reasons.append("ritmo acelerado")
            if sig.get("emotion_score", 0) > 0.6:
                score += 0.1
                types.append("emocionante")
                reasons.append("variação prosódica alta")

        if len(text.split()) >= 8:
            score += 0.08
            types.append("explicacao")
            reasons.append("frase com conteúdo substancial")

        h.score = round(min(score, 0.98), 3)
        h.reason = "; ".join(reasons[:2])
        h.types = list(dict.fromkeys(types))
        h.retention = round(min(score + 0.1, 1), 2)
        h.virality = round(min(score * 1.1, 1), 2)
        h.educational = 0.55 if "explicacao" in h.types else 0.3
        h.sharing = round(min(score * 1.05, 1), 2)
        h.emotion = round(min(score + 0.15 if "emocionante" in h.types else score, 1), 2)
        h.clarity = 0.7
        h.duration_pref = 30.0
        if h.score >= 0.55:
            highlights.append(h)

    highlights.sort(key=lambda x: x.score, reverse=True)
    # evita sobreposição: mantém apenas destaques que não se sobrepõem demais
    merged: list[Highlight] = []
    for h in highlights:
        ok = True
        for m in merged:
            if abs(h.sentence_start - m.sentence_end) < 3 or abs(h.sentence_start - m.sentence_start) < 2:
                ok = False
                break
        if ok:
            merged.append(h)
        if len(merged) >= 12:
            break

    return ContentAnalysis(
        summary="Análise heurística local (sem LLM). Instale o Ollama para análise semântica completa.",
        themes=[],
        highlights=merged,
        hook_lines=[],
        cta_lines=[],
    )
