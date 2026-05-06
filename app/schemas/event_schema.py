"""Pydantic schema for browser events (events.json)."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    page_navigated = "page_navigated"
    click = "click"
    input = "input"
    search_submitted = "search_submitted"
    screenshot_manual = "screenshot_manual"
    screenshot_auto = "screenshot_auto"
    session_started = "session_started"
    session_finished = "session_finished"
    recording_paused = "recording_paused"
    recording_resumed = "recording_resumed"


class BrowserEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    timestamp: str
    event_type: EventType
    url: Optional[str] = None
    domain: Optional[str] = None
    page_title: Optional[str] = None
    # click-specific
    selector: Optional[str] = None
    element_text: Optional[str] = None
    element_tag: Optional[str] = None
    coordinates: Optional[dict] = None
    # input-specific
    input_value: Optional[str] = None
    input_type: Optional[str] = None
    input_name: Optional[str] = None
    redacted: bool = False
    # asset reference
    screenshot_path: Optional[str] = None
    # any extra structured metadata
    metadata: Optional[dict] = None

    model_config = {"extra": "ignore"}
