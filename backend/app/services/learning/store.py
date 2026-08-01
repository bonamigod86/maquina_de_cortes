"""Armazenamento local de avaliações e perfil de preferências do usuário."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

from app.core.config import FEEDBACK_DB

_lock = threading.Lock()

RATINGS = {"excellent": 1.0, "good": 0.6, "bad": -0.4, "ignore": 0.0}


class FeedbackStore:
    """Persiste avaliações de cortes e deriva preferências aprendidas."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or str(FEEDBACK_DB)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute(
            """CREATE TABLE IF NOT EXISTS feedback (
                clip_id TEXT PRIMARY KEY,
                project_id TEXT,
                rating TEXT,
                tags TEXT,
                duration REAL,
                title TEXT,
                caption TEXT,
                created_at TEXT
            )"""
        )
        return con

    def record(
        self,
        clip_id: str,
        project_id: str,
        rating: str,
        tags: list[str] | None = None,
        duration: float = 0.0,
        title: str = "",
        caption: str = "",
    ) -> None:
        with _lock:
            con = self._connect()
            con.execute(
                """INSERT OR REPLACE INTO feedback
                   (clip_id, project_id, rating, tags, duration, title, caption, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    clip_id,
                    project_id,
                    rating,
                    ",".join(tags or []),
                    duration,
                    title,
                    caption,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            con.commit()
            con.close()

    def clear(self, clip_id: str) -> None:
        with _lock:
            con = self._connect()
            con.execute("DELETE FROM feedback WHERE clip_id=?", (clip_id,))
            con.commit()
            con.close()

    def all(self) -> list[dict]:
        with _lock:
            con = self._connect()
            cur = con.execute("SELECT * FROM feedback")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            con.close()
            return [dict(zip(cols, r)) for r in rows]

    def profile(self) -> dict:
        """Deriva preferências aprendidas a partir das avaliações."""
        rows = self.all()
        if not rows:
            return {"tag_weights": {}, "preferred_duration": None, "samples": 0}

        tag_weights: dict[str, float] = {}
        durations_good: list[float] = []
        n_good = 0
        for r in rows:
            w = RATINGS.get(r["rating"], 0.0)
            if w <= 0:
                continue
            n_good += 1
            if r["duration"]:
                durations_good.append(r["duration"])
            for tag in (r["tags"] or "").split(","):
                tag = tag.strip()
                if tag:
                    tag_weights[tag] = tag_weights.get(tag, 0.0) + w
        if n_good == 0:
            return {"tag_weights": {}, "preferred_duration": None, "samples": 0}

        # normaliza pesos: média por avaliação
        for k in tag_weights:
            tag_weights[k] = round(tag_weights[k] / n_good, 3)

        pref_dur = None
        if durations_good:
            pref_dur = round(sum(durations_good) / len(durations_good), 1)

        return {
            "tag_weights": tag_weights,
            "preferred_duration": pref_dur,
            "samples": n_good,
            "counts": {r: sum(1 for x in rows if x["rating"] == r) for r in RATINGS},
        }
