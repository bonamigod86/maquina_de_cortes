"""Rotas de templates de corte (CRUD, clone, preview)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.template_schemas import (
    Template,
    TemplateCreate,
    TemplatePreviewIn,
    TemplateUpdate,
)
from app.services import template_store as store
from app.services.pipeline import template_render as tpl_render

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("/", response_model=list[Template])
def list_templates(mine: bool = True, public: bool = True):
    return store.list_templates(include_mine=mine, include_public=public)


@router.post("/", response_model=Template)
def create_template(body: TemplateCreate):
    return store.create_template(body)


@router.get("/{template_id}", response_model=Template)
def get_template(template_id: str):
    t = store.get_template(template_id)
    if t is None:
        raise HTTPException(404, "Template não encontrado")
    return t


@router.put("/{template_id}", response_model=Template)
def update_template(template_id: str, body: TemplateUpdate):
    t = store.update_template(template_id, body.model_dump(exclude_none=True))
    if t is None:
        raise HTTPException(404, "Template não encontrado ou é embutido")
    return t


@router.delete("/{template_id}")
def delete_template(template_id: str):
    if not store.delete_template(template_id):
        raise HTTPException(404, "Template não encontrado ou é embutido")
    return {"ok": True}


@router.post("/{template_id}/clone", response_model=Template)
def clone_template(template_id: str):
    t = store.clone_template(template_id)
    if t is None:
        raise HTTPException(404, "Template não encontrado")
    return t


@router.post("/preview")
def preview_template(body: TemplatePreviewIn):
    """Renderiza um frame de preview (270x480) de um rascunho ou template salvo."""
    tpl = body.model_dump(exclude_none=True)
    if body.template_id:
        existing = store.get_template(body.template_id)
        if existing is not None:
            merged = existing.model_dump()
            merged.update({k: v for k, v in tpl.items() if k not in ("template_id",) and v is not None})
            tpl = merged
        else:
            tpl["id"] = body.template_id
    tpl.setdefault("id", store.new_template_id())
    if "elements" not in tpl or not tpl["elements"]:
        tpl["elements"] = []

    from app.core.config import DATA_DIR, ensure_dirs

    ensure_dirs()
    previews_dir = DATA_DIR / "templates" / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    out = previews_dir / f"{tpl['id']}.jpg"
    try:
        tpl_render.render_preview(tpl, out)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Falha ao renderizar preview: {e}") from e
    return {"thumbnail": str(out)}