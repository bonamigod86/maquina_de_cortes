"""Download de vídeos a partir de URLs (YouTube, Twitch, Kick, etc.) via yt-dlp."""
from __future__ import annotations

from pathlib import Path

from app.services.project import ProjectStore

# qualidade -> seletor de formato do yt-dlp (melhor stream até a resolução)
FORMAT_MAP = {
    "360p": "wv*[height<=360]+wa/w[height<=360]/b",
    "720p": "bv*[height<=720]+ba/b[height<=720]/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]/b",
    "source": "bv*+ba/b",
}

PLATFORM_HINTS = {
    "youtube": ["youtube.com", "youtu.be"],
    "twitch": ["twitch.tv"],
    "kick": ["kick.com"],
    "twitter": ["x.com", "twitter.com"],
    "instagram": ["instagram.com"],
    "facebook": ["facebook.com", "fb.watch"],
}


def download_url(url: str, project_id: str, quality: str = "1080p") -> tuple[str, str]:
    """Baixa o vídeo para original/original.mp4 e retorna (caminho, título)."""
    import yt_dlp

    from app.core.config import ffmpeg_bin

    dest = ProjectStore.path(project_id, "original")
    dest.mkdir(parents=True, exist_ok=True)
    fmt = FORMAT_MAP.get(quality, FORMAT_MAP["1080p"])
    opts = {
        "outtmpl": str(dest / "yt.%(ext)s"),
        "format": fmt,
        "merge_output_format": "mp4",
        "no_playlist": True,
        "quiet": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
    }
    try:
        opts["ffmpeg_location"] = str(Path(ffmpeg_bin()).parent)
    except Exception:
        pass
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"Falha ao baixar: {e}") from e

    title = ""
    if isinstance(info, dict):
        title = info.get("title") or info.get("webpage_title") or ""

    files = [p for p in dest.glob("yt.*")]
    if not files:
        raise RuntimeError("Nenhum arquivo foi baixado")
    src = max(files, key=lambda p: p.stat().st_size)
    final = dest / "original.mp4"
    if src != final:
        src.replace(final)
    return str(final), title
