"""Schemas Pydantic compartilhados entre API e serviços."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WordTS(BaseModel):
    word: str
    start: float
    end: float
    probability: float = 1.0


class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[WordTS] = Field(default_factory=list)


class Transcription(BaseModel):
    language: str = ""
    duration: float = 0.0
    segments: list[Segment] = Field(default_factory=list)


class Scene(BaseModel):
    start: float
    end: float


class Silence(BaseModel):
    start: float
    end: float
    duration: float


class SentenceSignal(BaseModel):
    sentence_index: int
    start: float
    end: float
    energy: float = 0.0
    pace: float = 0.0
    intensity: float = 0.0
    emotion_score: float = 0.0
    text: str = ""


class Analysis(BaseModel):
    scenes: list[Scene] = Field(default_factory=list)
    silences: list[Silence] = Field(default_factory=list)
    sentence_signals: list[SentenceSignal] = Field(default_factory=list)


class Highlight(BaseModel):
    sentence_start: int
    sentence_end: int
    types: list[str] = Field(default_factory=list)
    score: float = 0.5
    reason: str = ""
    retention: float = 0.5
    virality: float = 0.5
    educational: float = 0.5
    sharing: float = 0.5
    emotion: float = 0.5
    clarity: float = 0.5
    duration_pref: float = 30.0


class ContentAnalysis(BaseModel):
    summary: str = ""
    themes: list[str] = Field(default_factory=list)
    highlights: list[Highlight] = Field(default_factory=list)
    hook_lines: list[str] = Field(default_factory=list)
    cta_lines: list[str] = Field(default_factory=list)


class ClipScores(BaseModel):
    retention: float = 0.0
    virality: float = 0.0
    educational: float = 0.0
    sharing: float = 0.0
    emotion: float = 0.0
    clarity: float = 0.0


class ClipFiles(BaseModel):
    video: str = ""
    subtitle: str = ""
    subtitle_ass: str = ""
    thumbnail: str = ""
    preview: str = ""


class Clip(BaseModel):
    id: str
    project_id: str
    source_start: float
    source_end: float
    duration: float
    title: str = ""
    caption: str = ""
    description: str = ""
    hashtags: list[str] = Field(default_factory=list)
    hook: str = ""
    cta: str = ""
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    scores: ClipScores = Field(default_factory=ClipScores)
    total_score: float = 0.0
    feedback: str | None = None
    files: ClipFiles = Field(default_factory=ClipFiles)
    transcript_excerpt: str = ""
    template_id: str | None = None
    created_at: str = ""


class PipelineStep(BaseModel):
    id: str
    label: str
    status: str = "pending"
    progress: float = 0.0
    detail: str = ""


class Project(BaseModel):
    id: str
    name: str
    source: str = ""
    source_size: int = 0
    status: str = "created"
    error: str = ""
    progress: float = 0.0
    current_step: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    steps: list[PipelineStep] = Field(default_factory=list)
    has_transcription: bool = False
    has_analysis: bool = False
    has_clips: bool = False
    clip_count: int = 0


class ProjectDetail(Project):
    transcription: Transcription | None = None
    analysis: Analysis | None = None
    content: ContentAnalysis | None = None
    clips: list[Clip] = Field(default_factory=list)
    dirs: dict[str, str] = Field(default_factory=dict)


class CreateProjectResponse(BaseModel):
    project: Project
    upload_id: str


class ExportResult(BaseModel):
    clip_id: str
    ok: bool
    path: str = ""
    error: str = ""


class FeedbackIn(BaseModel):
    rating: str  # excellent | good | bad | ignore


class RegenerateTextIn(BaseModel):
    field: str  # title | caption
    prompt_hint: str = ""


class ClipEditIn(BaseModel):
    title: str | None = None
    caption: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    hook: str | None = None
    cta: str | None = None
    keywords: list[str] | None = None
    source_start: float | None = None
    source_end: float | None = None
    duration: float | None = None
    feedback: str | None = None
    template_id: str | None = None


class ClipSplitIn(BaseModel):
    at: float


class ClipMergeIn(BaseModel):
    other_clip_id: str


class SettingsIn(BaseModel):
    settings: dict[str, Any]
