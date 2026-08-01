"""Helpers de formatação de tempo e identificadores."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def clean_filename(name: str) -> str:
    name = re.sub(r"[^\w\-. ]+", "", name, flags=re.UNICODE)
    return name.strip()[:80] or "video"


def srt_timestamp(seconds: float) -> str:
    ms = int(round((seconds % 1) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
