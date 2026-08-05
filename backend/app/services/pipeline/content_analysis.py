"""Etapa 4: IA compreende o contexto completo do vídeo e sugere destaques."""
from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.models.schemas import ContentAnalysis, Highlight
from app.services.ai import get_provider, heuristic_content_analysis

SYSTEM_PROMPT = (
    "Você é um editor de vídeos verticais extremamente experiente (TikTok, Reels, Shorts). "
    "Recebe a transcrição COMPLETA de um vídeo long form (podcast, entrevista, curso, live). "
    "Sua tarefa: encontrar os MELHORES momentos para virar clipes de 15 a 60 segundos. "
    "Pense como um editor humano: o corte precisa ter início e fim claros, fazer sentido sozinho, "
    "enganchar nos primeiros 2 segundos e entregar valor até o final. "
    "PRIORIZE QUALIDADE sobre quantidade: poucos cortes excelentes valem mais que muitos medianos.\n\n"
    "Categorias que você deve reconhecer: gancho, educativo, engraçado, historia, impactante, "
    "curiosidade, explicacao, cta, emocionante, energia.\n\n"
    "Avalie CADA destaque em 6 métricas independentes, de 0.0 a 1.0 (1 casa decimal), "
    "usando ESTAS réguas explícitas — não chute números:\n"
    "- retention: probabilidade de o espectador assistir até o fim. Alta (>=0.85) exige gancho nos 2s "
    "iniciais E tensão/valor crescente até o fim; média (0.6-0.8) quando o início é razoável mas há "
    "trecho arrastado; baixa (<0.5) quando o começo é fraco ou o trecho é longo demais sem payoff.\n"
    "- virality: potencial de alcance amplo/espontâneo. Alto quando há frase marcante e quotável, "
    "surpresa, opinião forte, dado chocante ou polêmica; baixo para conteúdo puramente expositivo "
    "sem nada memorável.\n"
    "- educational: quanto ensina algo concreto e verificável (técnica, passo, dado, definição, "
    "exemplo prático). Opinião/motivação genérica => baixo (<0.4).\n"
    "- sharing: probabilidade de alguém ENVIAR o trecho a outra pessoa de propósito (utilidade "
    "prática, identificação, \"preciso mostrar isso\"). DIFERENTE de virality: sharing é envio "
    "direcionado, virality é exposição ampla.\n"
    "- emotion: intensidade da carga emocional transmitida (surpresa, humor, raiva, emoção pessoal, "
    "tensão). Trecho neutro/informativo => baixo.\n"
    "- clarity: o trecho faz sentido SOZINHO, sem o contexto do vídeo? Tem início e fim claros e uma "
    "única ideia central? Se começa ou termina no meio de uma ideia, deixando gancho não resolvido, "
    "clarity <= 0.4 OBRIGATORIAMENTE.\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Nenhuma nota sem evidência no texto ou nos sinais prosódicos recebidos.\n"
    "2. Explique em 'reason' (1-2 frases) o principal motivo de o trecho funcionar.\n"
    "3. Trecho não autocontido (ideia cortada no início ou no fim) => clarity <= 0.4.\n"
    "4. Se o trecho inteiro é apenas contexto/transição, sem valor standalone, score <= 0.4.\n"
    "5. A soma retention+virality+educational+sharing+emotion+clarity pode variar livremente; "
    "cada uma é independente.\n\n"
    "Responda APENAS com JSON válido no formato: "
    '{"summary": "resumo do vídeo em 2 frases", "themes": ["tema1"], "hook_lines": ["frases de abertura fortes"], '
    '"cta_lines": ["frases de chamada para ação"], "highlights": [{"sentence_start": 5, "sentence_end": 9, '
    '"types": ["gancho", "impactante"], "score": 0.95, "reason": "por que funciona", '
    '"retention": 0.9, "virality": 0.85, "educational": 0.7, "sharing": 0.8, "emotion": 0.75, "clarity": 0.9, '
    '"duration_pref": 30}]}. '
    "sentence_start/end são índices das frases numeradas que você recebeu. "
    "O trecho deve ser contíguo e com coerência narrativa completa (sem ideias cortadas). "
    "score de 0 a 1. Inclua entre 3 e 10 highlights. "
    "NUNCA inclua frases que comecem ou terminem no meio de uma ideia."
)


def build_user_prompt(sentences: list[dict], signals: list[dict], user_prefs: dict | None = None) -> str:
    """Monta o prompt com a transcrição completa numerada + sinais prosódicos."""
    lines: list[str] = []
    pref_note = ""
    if user_prefs and (user_prefs.get("tag_weights") or user_prefs.get("preferred_duration")):
        weights = user_prefs.get("tag_weights") or {}
        top_tags = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:4]
        if top_tags:
            pref_note = (
                "\nO usuário aprendeu que gosta especialmente de: "
                + ", ".join(f"{t} (peso {w:.2f})" for t, w in top_tags if w > 1.0)
                + ". Valorize mais esses tipos de conteúdo.\n"
            )
        if user_prefs.get("preferred_duration"):
            pref_note += f"\nO usuário prefere cortes em torno de {user_prefs['preferred_duration']:.0f} segundos.\n"
    lines.append(
        "Abaixo está a transcrição completa dividida em frases numeradas. Cada frase tem: índice, "
        "tempo, texto e sinais de fala (energia 0-1, ritmo em palavras/s, intensidade 0-1, emoção prosódica 0-1)."
        + pref_note
        + "\n\n"
    )
    sig_map = {s["sentence_index"]: s for s in signals}
    for i, s in enumerate(sentences):
        sig = sig_map.get(i)
        sig_txt = ""
        if sig:
            sig_txt = f" [energia={sig['energy']:.2f} ritmo={sig['pace']:.1f} intensidade={sig['intensity']:.2f} emoção={sig['emotion_score']:.2f}]"
        lines.append(f"[{i}] ({s['start']:.1f}s-{s['end']:.1f}s){sig_txt} {s['text']}")
    return "\n".join(lines)


def analyze_content(
    project_id: str,
    sentences: list[dict],
    signals: list[dict],
    settings: Settings,
    user_prefs: dict | None = None,
    on_progress=None,
    cancel_event=None,
) -> ContentAnalysis:
    """Executa a análise de conteúdo usando o provedor configurado (ou heurística)."""
    if on_progress:
        on_progress(0.1)
    provider = get_provider(settings)
    if provider is None:
        if on_progress:
            on_progress(1.0)
        return heuristic_content_analysis(sentences, signals)
    ok, msg = provider.available()
    if not ok:
        if on_progress:
            on_progress(1.0)
        return heuristic_content_analysis(sentences, signals)

    prompt = build_user_prompt(sentences, signals, user_prefs)
    if cancel_event and cancel_event.is_set():
        raise RuntimeError("Análise cancelada")
    if on_progress:
        on_progress(0.35)
    try:
        raw = provider.chat_json(SYSTEM_PROMPT, prompt, temperature=settings.ai_temperature)
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    if on_progress:
        on_progress(0.9)

    highlights = []
    for h in raw.get("highlights", []):
        try:
            item = Highlight.model_validate(h)
            item.score = round(min(max(item.score, 0.0), 1.0), 3)
            item.retention = round(min(max(item.retention, 0.0), 1.0), 2)
            item.virality = round(min(max(item.virality, 0.0), 1.0), 2)
            item.educational = round(min(max(item.educational, 0.0), 1.0), 2)
            item.sharing = round(min(max(item.sharing, 0.0), 1.0), 2)
            item.emotion = round(min(max(item.emotion, 0.0), 1.0), 2)
            item.clarity = round(min(max(item.clarity, 0.0), 1.0), 2)
            highlights.append(item)
        except Exception:
            continue
    # valida índices
    n = len(sentences)
    valid = []
    for h in highlights:
        if h.sentence_start < 0 or h.sentence_end >= n or h.sentence_end < h.sentence_start:
            continue
        if (h.sentence_end - h.sentence_start) * 5 > settings.max_clip_duration + 15:
            continue
        valid.append(h)
    valid.sort(key=lambda h: h.score, reverse=True)

    if not valid:
        valid = heuristic_content_analysis(sentences, signals).highlights

    analysis = ContentAnalysis(
        summary=raw.get("summary", "")[:1000] if isinstance(raw.get("summary"), str) else "",
        themes=raw.get("themes", [])[:10] if isinstance(raw.get("themes"), list) else [],
        highlights=valid,
        hook_lines=raw.get("hook_lines", [])[:5] if isinstance(raw.get("hook_lines"), list) else [],
        cta_lines=raw.get("cta_lines", [])[:5] if isinstance(raw.get("cta_lines"), list) else [],
    )
    if on_progress:
        on_progress(1.0)
    return analysis
