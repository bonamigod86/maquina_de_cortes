"""Persistência de templates de corte (JSON em data/templates/)."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.config import DATA_DIR
from app.models.template_schemas import Template, TemplateCreate
from app.utils.helpers import new_id, now_iso

TEMPLATES_DIR = DATA_DIR / "templates"
DEFAULTS_DIR = TEMPLATES_DIR / "defaults"


def _ensure() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULTS_DIR.mkdir(parents=True, exist_ok=True)


def _write(t: Template, root: Path = TEMPLATES_DIR) -> None:
    p = root / f"{t.id}.json"
    p.write_text(t.model_dump_json(indent=2), encoding="utf-8")


def _read(p: Path) -> Template | None:
    try:
        t = Template.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if t.thumbnail and not Path(t.thumbnail).exists():
        t.thumbnail = None
    if not t.thumbnail:
        for ext in ("jpg", "png"):
            cand = TEMPLATES_DIR / f"{t.id}.{ext}"
            if cand.exists():
                t.thumbnail = str(cand)
                break
    return t


def _load_defaults() -> dict[str, Template]:
    out: dict[str, Template] = {}
    if DEFAULTS_DIR.exists():
        for p in sorted(DEFAULTS_DIR.glob("*.json")):
            t = _read(p)
            if t is not None:
                out[t.id] = t
    return out


def list_templates(include_mine: bool = True, include_public: bool = True) -> list[Template]:
    _ensure()
    seen: dict[str, Template] = _load_defaults()
    for p in TEMPLATES_DIR.glob("*.json"):
        t = _read(p)
        if t is not None:
            seen[t.id] = t
    res = []
    for t in seen.values():
        if t.is_builtin and not include_public:
            continue
        if not t.is_builtin and not include_mine:
            continue
        res.append(t)
    res.sort(key=lambda t: (t.is_builtin, t.name))
    return res


def get_template(template_id: str) -> Template | None:
    _ensure()
    if (DEFAULTS_DIR / f"{template_id}.json").exists():
        return _read(DEFAULTS_DIR / f"{template_id}.json")
    p = TEMPLATES_DIR / f"{template_id}.json"
    return _read(p) if p.exists() else None


def create_template(data: TemplateCreate, is_builtin: bool = False) -> Template:
    _ensure()
    t = Template(
        id=new_template_id(),
        name=data.name,
        category=data.category,
        description=data.description,
        background=data.background,
        elements=data.elements,
        is_public=data.is_public,
        is_builtin=is_builtin,
        subtitle_style_override=data.subtitle_style_override,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    _write(t)
    return t


def update_template(template_id: str, patch: dict) -> Template | None:
    t = get_template(template_id)
    if t is None or t.is_builtin:
        return None
    for k, v in patch.items():
        if v is not None and hasattr(t, k):
            setattr(t, k, v)
    t.updated_at = now_iso()
    _write(t)
    return t


def delete_template(template_id: str) -> bool:
    t = get_template(template_id)
    if t is None or t.is_builtin:
        return False
    p = TEMPLATES_DIR / f"{template_id}.json"
    if p.exists():
        p.unlink()
    thumb = TEMPLATES_DIR / f"{template_id}.png"
    if thumb.exists():
        thumb.unlink()
    return True


def clone_template(template_id: str) -> Template | None:
    t = get_template(template_id)
    if t is None:
        return None
    clone = Template(
        id=f"tpl_{new_id('')}",
        name=f"{t.name} (cópia)",
        category=t.category,
        description=t.description,
        background=dict(t.background),
        elements=[el.model_copy(deep=False) for el in t.elements],
        is_public=False,
        is_builtin=False,
        subtitle_style_override=t.subtitle_style_override,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    _write(clone)
    return clone


def new_template_id() -> str:
    return f"tpl_{new_id('')}"