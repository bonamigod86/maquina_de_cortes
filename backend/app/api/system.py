"""Rotas de configurações e sistema."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import DATA_DIR, Settings
from app.services.ai import get_provider, provider_status
from app.services.learning.store import FeedbackStore
from app.services.queue.manager import queue

router = APIRouter(prefix="/api", tags=["system"])


@router.post("/brand/logo")
def upload_logo(file: UploadFile = File(...)):
    """Salva o logo da marca e atualiza o brand_kit, retornando o caminho absoluto."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Envie uma imagem (PNG/JPEG)")
    brand_dir = DATA_DIR / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    ext = ".png"
    name = Path(file.filename or "").suffix.lower()
    if name in (".jpg", ".jpeg", ".webp", ".gif"):
        ext = name
    dest = brand_dir / f"logo{ext}"
    dest.write_bytes(file.file.read())
    s = Settings.load()
    if "brand_kit" not in s.brand_kit or not isinstance(s.brand_kit, dict):
        s.brand_kit = dict(s.brand_kit)
    s.brand_kit["logo_path"] = str(dest)
    s.brand_kit["use_logo"] = True
    s.save()
    return {"path": str(dest), "url": f"/media/brand/logo{ext}"}


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
