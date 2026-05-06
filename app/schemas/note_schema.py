"""Pydantic schema for human reasoning notes (notes.json)."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NoteType(str, Enum):
    session_criteria = "Session Criteria"
    site_choice_reason = "Site Choice Reason"
    option_rejected = "Option Rejected"
    option_shortlisted = "Option Shortlisted"
    final_selection_reason = "Final Selection Reason"
    reusable_protocol_rule = "Reusable Protocol Rule"
    escalation_uncertainty = "Escalation/Uncertainty Note"
    other = "Other"


class ReasoningNote(BaseModel):
    note_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    timestamp: str
    note_type: NoteType
    note_text: str
    url: Optional[str] = None
    page_title: Optional[str] = None
    screenshot_path: Optional[str] = None

    model_config = {"extra": "ignore"}
