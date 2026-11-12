"""Local evaluation evidence, ordinary editable SQLite; no signed audit claims."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from .model import ROOT, SOURCE_FINGERPRINT
from . import __version__


class RunStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else ROOT.parents[1] / "work/gridshield-runtime/runs.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, outcome TEXT NOT NULL, report TEXT NOT NULL)")

    def save(self, kind, report):
        if kind not in {"assessment", "replay", "benchmark"}:
            raise ValueError("Unsupported report kind.")
        saved = dict(report)
        saved.setdefault("id", str(uuid4()))
        saved.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        saved.setdefault("app_version", __version__)
        saved.setdefault("source_hash", SOURCE_FINGERPRINT)
        saved["record_kind"] = kind
        if kind == "benchmark":
            title = "Declared development comparison"
            summary = saved["summary"]
            outcome = f"{summary['gridshield']['matches']}/{summary['total']} expected labels"
        else:
            title, outcome = saved["title"], saved["status"]
        encoded = json.dumps(saved, allow_nan=False)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                       (saved["id"], saved["created_at"], kind, title, outcome, encoded))
        return saved

    def recent(self):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT id, created_at, kind, title, outcome FROM runs ORDER BY created_at DESC, rowid DESC LIMIT 20").fetchall()
        return [dict(zip(("id", "created_at", "kind", "title", "outcome"), row)) for row in rows]

    def get(self, identifier):
        try:
            if str(UUID(identifier)) != identifier:
                return None
        except (ValueError, TypeError, AttributeError):
            return None
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT report FROM runs WHERE id = ?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None
