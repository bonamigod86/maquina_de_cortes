"""Análise heurística de conteúdo — fallback quando não há LLM disponível.

Cada métrica (retenção, viralidade, educacional, compartilhamento, emoção,
clareza) é computada de forma INDEPENDENTE, a partir de sinais observáveis
(prosódia + texto), em vez de ser derivada de um único score de base.
"""
from __future__ import annotations

import re

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
EDU_MARKERS = re.compile(
    r"(\d+\s?%|\bporque\b|\bpor que\b|\bcomo\b|\bdica\b|\btruque\b|\bpasso\b|\bpassos\b|"
    r"\bmétodo\b|\btécnica\b|\bexemplo\b|\bdiferença\b|\bresultado\b|\bestudo\b|\bpesquisa\b|"
    r"\bregra\b|\bevite\b|\berro\b|\bprimeiro\b|\bsegundo\b|\bterceiro\b|\bporcentagem\b)",
    re.IGNORECASE,
)
# Inícios que indicam continuação de um pensamento anterior (não autocontido)
MID_THOUGHT_START = re.compile(
    r"^(mas|então|e aí|e daí|e depois|aí (ele|ela|eu)|porque|por que|ou seja|enfim|e também|"
    r"além disso|dessa forma|então você)\b",
    re.IGNORECASE,
)


def _clamp(x: float) -> float:
    return round(min(max(x, 0.0), 1.0), 2)


def _length_ok(words: int) -> float:
    """Faixa ideal para um clipe standalone: nem truncado, nem longo demais."""
    if 8 <= words <= 30:
        return 1.0
    if 4 <= words <= 45:
        return 0.6
    return 0.3


def heuristic_content_analysis(sentences: list[dict], signals: list[dict]) -> ContentAnalysis:
    """Gera destaques com métricas independentes baseadas em texto e prosódia."""
    highlights: list[Highlight] = []
    n = len(sentences)
    for i, s in enumerate(sentences):
        text = s["text"]
        low = text.lower()
        words = len(text.split())

        # Sinais binários de texto
        hook = 1.0 if HOOK_MARKERS.search(low) else 0.0
        question = 1.0 if "?" in text else 0.0
        exclaim = 1.0 if "!" in text else 0.0
        cta = 1.0 if CTA_MARKERS.search(low) else 0.0
        story = 1.0 if STORY_MARKERS.search(low) else 0.0
        emotion_word = 1.0 if EMOTION_MARKERS.search(low) else 0.0
        edu = 1.0 if EDU_MARKERS.search(low) else 0.0

        # Sinais prosódicos (energia, intensidade, emoção da voz)
        sig = signals[i] if i < len(signals) else {}
        energy = float(sig.get("energy", 0.0) or 0.0)
        intensity = float(sig.get("intensity", 0.0) or 0.0)
        emotion_prosody = float(sig.get("emotion_score", 0.0) or 0.0)

        # Autocontinuidade do trecho
        starts_clean = 0.0 if MID_THOUGHT_START.search(low) else 1.0
        ends_clean = 1.0 if text.rstrip().endswith((".", "!", "?", "…", '"', "»")) else 0.4

        hook_strength = min(1.0, 0.6 * hook + 0.25 * question + 0.15 * exclaim)

        # ----- Métricas independentes -----
        retention = _clamp(0.40 * hook_strength + 0.25 * _length_ok(words) + 0.20 * intensity + 0.15 * energy)
        virality = _clamp(0.35 * hook_strength + 0.25 * exclaim + 0.25 * max(emotion_word, emotion_prosody) + 0.15 * energy)
        emotion = _clamp(0.45 * emotion_prosody + 0.25 * emotion_word + 0.20 * exclaim + 0.10 * story)
        neutrality = 1.0 - max(hook, emotion_word, exclaim)  # trecho expositivo, sem apelo forte
        substance = min(words / 25.0, 1.0)
        educational = _clamp(0.45 * edu + 0.35 * substance + 0.20 * neutrality)
        sharing = _clamp(0.35 * cta + 0.30 * max(edu, hook) + 0.20 * emotion_word + 0.15 * story)
        clarity = _clamp(0.40 * starts_clean + 0.40 * ends_clean + 0.20 * _length_ok(words))

        # Score global com os mesmos pesos do ranking final (clips.py)
        score = (
            retention * 0.30
            + virality * 0.25
            + educational * 0.15
            + sharing * 0.15
            + emotion * 0.10
            + clarity * 0.05
        )
        score = round(min(score, 0.98), 3)

        types: list[str] = []
        reasons: list[str] = []
        if hook_strength >= 0.5:
            types.append("gancho")
            reasons.append("frase de engajamento direto")
        if question:
            types.append("gancho")
            reasons.append("pergunta que desperta curiosidade")
        if cta:
            types.append("cta")
            reasons.append("chamada para ação natural")
        if story:
            types.append("historia")
            reasons.append("início de história")
        if emotion >= 0.55:
            types.append("emocionante")
            reasons.append("carga emocional")
        if intensity > 0.75:
            types.append("energia")
            reasons.append("pico de intensidade de voz")
        if words >= 8 or edu:
            types.append("explicacao")
            reasons.append("conteúdo com substância")
        types = list(dict.fromkeys(types))

        h = Highlight(
            sentence_start=i,
            sentence_end=i,
            types=types,
            score=score,
            reason="; ".join(reasons[:2]),
            retention=retention,
            virality=virality,
            educational=educational,
            sharing=sharing,
            emotion=emotion,
            clarity=clarity,
            duration_pref=30.0,
        )
        if h.score >= 0.5:
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
