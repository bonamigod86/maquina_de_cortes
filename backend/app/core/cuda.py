"""Detecção e carregamento de runtime CUDA (cuBLAS/cuDNN via pip, Windows)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _site_packages() -> Path:
    return Path(sys.prefix) / "Lib" / "site-packages"


def register_cuda_paths() -> None:
    """Adiciona diretórios das DLLs CUDA (nvidia-*-cu12) ao PATH antes do ctranslate2.

    No Windows, o ctranslate2 carrega as DLLs via PATH do processo.
    Idempotente: não duplica entradas já presentes (evita estourar o limite
    de ~32767 caracteres do PATH no Windows).
    """
    if os.name != "nt":
        return
    nvidia = _site_packages() / "nvidia"
    if not nvidia.exists():
        return
    current = os.environ.get("PATH", "") or ""
    parts = current.split(";") if current else []
    added: list[str] = []
    for pkg in ("cublas", "cudnn", "cuda_nvrtc", "cufft", "curand"):
        bin_dir = nvidia / pkg / "bin"
        if bin_dir.exists():
            p = str(bin_dir)
            if p not in parts:
                parts.insert(0, p)
                added.append(p)
    if added:
        os.environ["PATH"] = ";".join(parts)


def cuda_available() -> bool:
    """Verifica se GPU CUDA funciona de fato com o ctranslate2."""
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False
