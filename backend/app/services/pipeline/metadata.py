"""Etapa 6: geração de títulos, legendas, hashtags e descrições por corte."""
from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings
from app.models.schemas import Clip
from app.services.ai import get_provider

SYSTEM_PROMPT = (
    "Você é um especialista em marketing de conteúdo para TikTok, Instagram Reels e YouTube Shorts. "
    "Recebe o trecho exato de um vídeo e deve criar textos prontos para postagem. "
    "Responda APENAS com JSON: "
    '{"title": "título chamativo máx 60 caracteres", "caption": "legenda 1-3 frases com gancho", '
    '"description": "descrição 2-4 frases", "hashtags": ["#tag1"], "hook": "primeira frase do vídeo", '
    '"cta": "frase de chamada para ação natural", "keywords": ["palavra-chave"]}. '
    "Tudo no idioma do trecho do vídeo."
)

TEMPLATE_TITLES = [
    "{hook} 🤯",
    "Isso muda tudo: {topic}",
    "O que ninguém te conta sobre {topic}",
    "{hook} | Clipe completo",
    "Você sabia? {topic}",
]


def _fallback_metadata(clip: Clip) -> dict:
    words = clip.transcript_excerpt.split()
    topic = " ".join(words[:4]).rstrip(",;") or "esse assunto"
    first = clip.transcript_excerpt[:90]
    return {
        "title": f"{first[:55]}{'…' if len(first) > 55 else ''}",
        "caption": f"{first}\n\nAssista até o final! 👀",
        "description": f"{first}\n\n🎬 Corte de {clip.project_id}",
        "hashtags": ["#shorts", "#viral", "#fy", "#viralvideo"],
        "hook": first[:40],
        "cta": "Comenta aqui o que você achou! 👇",
        "keywords": [w for w in words[:6] if len(w) > 3],
    }


def generate_clip_metadata(clip: Clip, context: dict, settings: Settings) -> dict:
    """Gera metadados via LLM (ou template como fallback)."""
    provider = get_provider(settings)
    excerpt = clip.transcript_excerpt[:2500]
    user_prompt = (
        f"Contexto do vídeo original:\n{context.get('summary', '')}\n\n"
        f"Trecho do corte:\n{excerpt}\n\n"
        f"Categorias: {', '.join(clip.tags) or 'geral'}\n"
        f"Duração: {clip.duration:.0f}s"
    )
    if provider:
        try:
            ok, _ = provider.available()
            if ok:
                raw = provider.chat_json(SYSTEM_PROMPT, user_prompt, temperature=settings.ai_temperature)
                if raw.get("title"):
                    return {
                        "title": str(raw["title"])[:120],
                        "caption": str(raw.get("caption", ""))[:2000],
                        "description": str(raw.get("description", ""))[:2000],
                        "hashtags": [str(h) for h in raw.get("hashtags", [])][:12],
                        "hook": str(raw.get("hook", ""))[:200],
                        "cta": str(raw.get("cta", ""))[:200],
                        "keywords": [str(k) for k in raw.get("keywords", [])][:12],
                    }
        except Exception:
            pass
    fb = _fallback_metadata(clip)
    fb["hashtags"] = [f"#{tag}" for tag in clip.tags[:4]] + ["#shorts", "#fyp"]
    return fb


def write_metadata_files(project_id: str, clips: list[Clip], settings: Settings, summary: str, themes: list[str]) -> None:
    from app.services.project import ProjectStore

    folder = ProjectStore.folder(project_id)
    metadata: dict = {
        "summary": summary,
        "themes": themes,
        "clips": [
            {
                "id": c.id,
                "title": c.title,
                "caption": c.caption,
                "description": c.description,
                "hashtags": c.hashtags,
                "hook": c.hook,
                "cta": c.cta,
                "keywords": c.keywords,
                "tags": c.tags,
                "score": c.total_score,
                "duration": c.duration,
                "start": c.source_start,
                "end": c.source_end,
            }
            for c in clips
        ],
    }
    ProjectStore.write_json(project_id, "metadata.json", metadata)

    titles = [f"{c.title}" for c in clips if c.title]
    captions = [f"--- {c.title} ---\n{c.caption}\n{c.description}\n\n{' '.join(c.hashtags)}" for c in clips]
    (folder / "Títulos.txt").write_text("\n".join(titles), encoding="utf-8")
    (folder / "Legendas_Postagem.txt").write_text("\n\n".join(captions), encoding="utf-8")


def regenerate_field(clip: Clip, field: str, settings: Settings, hint: str = "") -> str:
    """Regenera título ou legenda via IA."""
    provider = get_provider(settings)
    if not provider:
        return ""
    field_names = {"title": "title", "caption": "caption"}
    kind = field_names.get(field, "title")
    system = (
        f"Você gera {field_names.get(field)} para posts de redes sociais. "
        "Responda APENAS com JSON {\"text\": \"...\"}. "
        f"Idioma: português brasileiro, a menos que o trecho esteja em outro idioma."
    )
    user = f"Trecho:\n{clip.transcript_excerpt[:1500]}\nCategorias: {', '.join(clip.tags)}\n"
    if hint:
        user += f"Instrução extra: {hint}\n"
    if kind == "title":
        user += "Gere um título chamativo, curto (máx 60 caracteres) e com gancho."
    else:
        user += "Gere uma legenda pronta para postar: gancho, corpo e chamada para ação, com quebras de linha."
    try:
        ok, _ = provider.available()
        if not ok:
            return ""
        raw = provider.chat_json(system, user, temperature=0.6)
        return str(raw.get("text", "")).strip()
    except Exception:
        return ""
