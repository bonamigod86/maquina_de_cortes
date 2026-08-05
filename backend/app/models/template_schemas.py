"""Schemas de templates de corte (layouts visuais sobre o vídeo 1080x1920)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TemplateElement(BaseModel):
    id: str
    type: Literal["text", "image", "logo", "shape", "video_slot", "cover", "subtitle_area"]
    x: float = 0.0  # 0-1 (fração do canvas 1080x1920)
    y: float = 0.0
    w: float = 1.0
    h: float = 0.2
    content: str | None = None
    style: dict[str, Any] = Field(default_factory=dict)


class Template(BaseModel):
    id: str
    name: str
    category: str = "geral"
    description: str = ""
    thumbnail: str | None = None
    is_public: bool = True
    is_builtin: bool = False
    background: dict[str, Any] = Field(default_factory=dict)  # type: none|color|gradient|image
    elements: list[TemplateElement] = Field(default_factory=list)
    subtitle_style_override: dict[str, Any] | None = None
    created_at: str = ""
    updated_at: str = ""


class TemplateCreate(BaseModel):
    name: str
    category: str = "geral"
    description: str = ""
    background: dict[str, Any] = Field(default_factory=dict)
    elements: list[TemplateElement] = Field(default_factory=list)
    is_public: bool = True
    subtitle_style_override: dict[str, Any] | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    background: dict[str, Any] | None = None
    elements: list[TemplateElement] | None = None
    is_public: bool | None = None
    subtitle_style_override: dict[str, Any] | None = None


class TemplatePreviewIn(BaseModel):
    template_id: str | None = None
    name: str = "Preview"
    category: str = "geral"
    description: str = ""
    background: dict[str, Any] = Field(default_factory=dict)
    elements: list[TemplateElement] = Field(default_factory=list)
    subtitle_style_override: dict[str, Any] | None = None
