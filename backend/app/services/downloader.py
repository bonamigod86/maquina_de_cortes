"""Download de vídeos a partir de URLs (YouTube e outros) via yt-dlp."""
from __future__ import annotations

from pathlib import Path

from app.services.project import ProjectStore


def download_youtube(url: str, project_id: str) -> tuple[str, str]:
    """Baixa o vídeo para original/original.mp4 e retorna (caminho, título)."""
    import yt_dlp

    from app.core.config import ffmpeg_bin

    dest = ProjectStore.path(project_id, "original")
    dest.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(dest / "yt.%(ext)s"),
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
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
