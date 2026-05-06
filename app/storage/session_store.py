"""In-memory session store that flushes to JSON on demand."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.schemas.decision_schema import DecisionRecord
from app.schemas.event_schema import BrowserEvent
from app.schemas.note_schema import ReasoningNote
from app.schemas.session_schema import SessionRecord

logger = logging.getLogger(__name__)


class SessionStore:
    """Holds all session data in memory and writes it to disk when requested.

    Call :meth:`write_all` after every meaningful action and on shutdown to
    ensure partial data is always recoverable.
    """

    def __init__(self, session: SessionRecord, session_folder: Path) -> None:
        self.session: SessionRecord = session
        self.session_folder: Path = session_folder
        self.events: list[BrowserEvent] = []
        self.notes: list[ReasoningNote] = []
        self.decisions: list[DecisionRecord] = []

    # ------------------------------------------------------------------
    # Append helpers
    # ------------------------------------------------------------------

    def add_event(self, event: BrowserEvent) -> None:
        self.events.append(event)

    def add_note(self, note: ReasoningNote) -> None:
        self.notes.append(note)

    def add_decision(self, decision: DecisionRecord) -> None:
        self.decisions.append(decision)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def write_all(self) -> None:
        """Serialise all in-memory data to JSON files in the session folder."""
        try:
            self._write_json("session.json", self.session.model_dump())
            self._write_json(
                "events.json",
                [e.model_dump() for e in self.events],
            )
            self._write_json(
                "notes.json",
                [n.model_dump() for n in self.notes],
            )
            self._write_json(
                "decisions.json",
                [d.model_dump() for d in self.decisions],
            )
            logger.debug("Session data written to %s", self.session_folder)
        except Exception:
            logger.exception("Failed to write session data")

    def _write_json(self, filename: str, data: object) -> None:
        path: Path = self.session_folder / filename
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Convenience counters
    # ------------------------------------------------------------------

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def note_count(self) -> int:
        return len(self.notes)

    @property
    def decision_count(self) -> int:
        return len(self.decisions)
