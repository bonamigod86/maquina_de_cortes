"""Wrapper para invocação de FFmpeg/FFprobe."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from app.core.config import ffmpeg_bin

_FFMPEG = None
_FFPROBE = None


def _paths() -> tuple[str, str]:
    global _FFMPEG, _FFPROBE
    if _FFMPEG and _FFPROBE:
        return _FFMPEG, _FFPROBE
    ffmpeg = ffmpeg_bin()
    base = Path(ffmpeg).parent
    ffprobe = str(base / "ffprobe.exe") if os.name == "nt" else str(base / "ffprobe")
    if not Path(ffprobe).exists():
        found = shutil.which("ffprobe")
        if found:
            ffprobe = found
    _FFMPEG, _FFPROBE = ffmpeg, ffprobe
    return ffmpeg, ffprobe


def run(cmd: list[str], capture: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)


def ffprobe(path: str) -> dict:
    """Retorna metadados do vídeo via ffprobe."""
    _, ffprobe = _paths()
    p = run([ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path])
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {p.stderr}")
    return json.loads(p.stdout)


def media_info(path: str) -> dict:
    """Extrai duração, resolução e fps do vídeo."""
    data = ffprobe(path)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    fps = 0.0
    if v and v.get("avg_frame_rate", "0/0") != "0/0":
        num, den = v["avg_frame_rate"].split("/")
        try:
            fps = float(num) / float(den)
        except ZeroDivisionError:
            fps = 0.0
    return {
        "duration": duration,
        "width": int(v.get("width", 0)) if v else 0,
        "height": int(v.get("height", 0)) if v else 0,
        "fps": fps,
        "has_audio": a is not None,
        "format": data.get("format", {}).get("format_name", ""),
    }


def run_ffmpeg(
    args: list[str],
    on_progress: callable | None = None,
    duration: float | None = None,
    cancel_event=None,
) -> None:
    """Executa ffmpeg com progresso por tempo processado."""
    ffmpeg, _ = _paths()
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y"]
    if duration and on_progress:
        cmd += ["-progress", "pipe:1", "-nostats"]
    cmd += args
    env = dict(os.environ)
    env.setdefault("FFMPEG_LOGLEVEL", "error")
    # fontconfig (Windows): sem config, libass não encontra fontes
    fonts_conf = Path(__file__).resolve().parents[2] / "data" / "fonts" / "fonts.conf"
    if fonts_conf.exists():
        env.setdefault("FONTCONFIG_FILE", str(fonts_conf))
    env.setdefault("FONTCONFIG_PATH", str(fonts_conf.parent))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE if duration and on_progress else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    err_lines: list[str] = []
    if proc.stderr:
        def _drain_stderr() -> None:
            for ln in proc.stderr:
                err_lines.append(ln)

        threading.Thread(target=_drain_stderr, daemon=True).start()
    if duration and on_progress and proc.stdout:
        for line in proc.stdout:
            if cancel_event is not None and cancel_event.is_set():
                proc.terminate()
                raise RuntimeError("Processamento cancelado")
            if line.startswith("out_time_ms="):
                try:
                    t = int(line.split("=", 1)[1].strip()) / 1_000_000
                    on_progress(min(t / duration, 1.0))
                except (ValueError, ZeroDivisionError):
                    pass
    proc.wait()
    if proc.returncode != 0:
        err = "".join(err_lines)[-4000:]
        raise RuntimeError(f"ffmpeg retornou {proc.returncode}: {err}")
