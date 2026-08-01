"""Configurações globais da aplicação, persistidas localmente."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
SETTINGS_FILE = DATA_DIR / "settings.json"
FEEDBACK_DB = DATA_DIR / "feedback.db"
MODELS_CACHE = DATA_DIR / "models"

DEFAULT_SUBTITLE_STYLE = {
    "style": "tiktok",
    "font": "Arial Black",
    "font_size": 72,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width": 4,
    "shadow": True,
    "shadow_color": "#000000",
    "position": "bottom",
    "animation": "pop",
    "words_per_line": 6,
}


class Settings(BaseModel):
    whisper_model: str = "medium"
    whisper_device: str = "auto"
    whisper_compute: str = "auto"
    language: str = "auto"
    ai_provider: str = "ollama"
    ai_model: str = "qwen2.5:7b"
    ai_base_url: str = "http://localhost:11434"
    ai_temperature: float = 0.3
    min_clip_duration: float = 15.0
    max_clip_duration: float = 60.0
    clip_durations: list[float] = Field(default_factory=lambda: [15.0, 30.0, 45.0, 60.0])
    subtitle_style: dict[str, Any] = Field(default_factory=lambda: dict(DEFAULT_SUBTITLE_STYLE))
    export_quality: str = "high"
    use_gpu: bool = True
    max_clips: int = 8
    download_subtitles: bool = True
    face_detection: bool = True

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        if SETTINGS_FILE.exists():
            try:
                return cls.model_validate_json(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        s = cls()
        s.save()
        return s


def ensure_dirs() -> None:
    for d in (DATA_DIR, PROJECTS_DIR, MODELS_CACHE):
        d.mkdir(parents=True, exist_ok=True)


def detect_cuda() -> bool:
    from app.core.cuda import register_cuda_paths

    register_cuda_paths()
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def ffmpeg_bin() -> str:
    """Localiza o ffmpeg instalado (PATH, winget ou fallback comum)."""
    import shutil

    candidates = [os.environ.get("FFMPEG", ""), "ffmpeg", "ffmpeg.exe"]
    for c in candidates:
        if c:
            p = shutil.which(c)
            if p:
                return p
    # caminhos comuns do winget
    try:
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        for d in base.glob("Gyan.FFmpeg*"):
            for f in d.rglob("ffmpeg.exe"):
                return str(f)
    except Exception:
        pass
    alt = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    try:
        for f in alt.glob("ffmpeg*"):
            return str(f)
    except Exception:
        pass
    raise RuntimeError(
        "FFmpeg não encontrado. Instale com: winget install Gyan.FFmpeg"
    )
