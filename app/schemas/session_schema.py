"""Pydantic schema for the top-level session record (session.json)."""

from __future__ import annotations

import platform
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.config import APP_VERSION


class SessionRecord(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str
    client_reference: str
    destination: str
    travel_dates: str
    travelers: str
    budget: str
    trip_type: str
    special_requirements: str = ""
    client_request_notes: str = ""
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    app_version: str = APP_VERSION
    operating_system: str = Field(
        default_factory=lambda: f"{platform.system()} {platform.release()}"
    )
    status: str = "started"  # started | paused | finished | interrupted

    model_config = {"extra": "ignore"}
