"""Fábrica de provedores de IA — troca de modelos sem alterar o pipeline."""
from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.services.ai.base import LLMProvider, strip_json
from app.services.ai.heuristic import heuristic_content_analysis
from app.services.ai.ollama import OllamaProvider, OpenAICompatProvider


def get_provider(settings: Settings) -> LLMProvider | None:
    """Retorna o provedor configurado, ou None se indisponível."""
    provider = settings.ai_provider
    if provider == "ollama":
        return OllamaProvider(settings.ai_base_url, settings.ai_model)
    if provider == "openai_compat":
        return OpenAICompatProvider(settings.ai_base_url, settings.ai_model)
    return None


def provider_status(settings: Settings) -> dict[str, Any]:
    p = get_provider(settings)
    if p is None:
        return {"ok": False, "message": "Nenhum provedor configurado", "name": settings.ai_provider}
    ok, msg = p.available()
    return {"ok": ok, "message": msg, "name": p.name}


def robust_chat_json(
    provider: LLMProvider,
    system: str,
    user: str,
    temperature: float = 0.3,
    fallback: Any = None,
) -> dict[str, Any]:
    """Chama o LLM com fallback para JSON inválido."""
    try:
        return provider.chat_json(system, user, temperature)
    except Exception:
        try:
            content = provider.chat_text(system, user, temperature)
            return json.loads(strip_json(content))
        except Exception:
            if fallback is not None:
                return fallback
            return {}


__all__ = ["get_provider", "provider_status", "robust_chat_json", "heuristic_content_analysis"]
