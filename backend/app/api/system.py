"""Rotas de configurações e sistema."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import Settings
from app.services.ai import get_provider, provider_status
from app.services.learning.store import FeedbackStore
from app.services.queue.manager import queue

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/settings")
def get_settings():
    s = Settings.load()
    return s.model_dump()


@router.put("/settings")
def update_settings(body: dict):
    s = Settings.load()
    merged = s.model_dump()
    merged.update(body.get("settings", {}))
    try:
        new = Settings.model_validate(merged)
    except Exception as e:
        raise HTTPException(400, f"Configurações inválidas: {e}")
    new.save()
    return new.model_dump()


@router.get("/system/status")
def system_status():
    s = Settings.load()
    st = provider_status(s)
    from app.core.config import detect_cuda

    return {
        "cuda_available": detect_cuda(),
        "ai_provider": s.ai_provider,
        "ai_model": s.ai_model,
        "ai_ok": st.get("ok", False),
        "ai_message": st.get("message", ""),
        "queue": queue.snapshot(),
        "learning": FeedbackStore().profile(),
    }


@router.get("/system/models")
def available_models():
    """Lista modelos disponíveis no provedor configurado."""
    s = Settings.load()
    provider = get_provider(s)
    if not provider:
        return {"models": []}
    try:
        import httpx

        if s.ai_provider == "ollama":
            r = httpx.get(f"{s.ai_base_url}/api/tags", timeout=3)
            return {"models": [m.get("name", "") for m in r.json().get("models", [])]}
        r = httpx.get(f"{s.ai_base_url}/models", timeout=3)
        return {"models": [m.get("id", "") for m in r.json().get("data", [])]}
    except Exception:
        return {"models": []}
