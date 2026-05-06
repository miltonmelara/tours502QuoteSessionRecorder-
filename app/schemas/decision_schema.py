"""Pydantic schema for structured decision records (decisions.json)."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    reject_option = "reject_option"
    shortlist_option = "shortlist_option"
    select_budget = "select_budget"
    select_balanced = "select_balanced"
    select_premium = "select_premium"
    escalate = "escalate"


class Decision(str, Enum):
    rejected = "rejected"
    shortlisted = "shortlisted"
    selected = "selected"
    escalated = "escalated"


class TierBucket(str, Enum):
    budget = "budget"
    balanced = "balanced"
    premium = "premium"
    none = "none"


class DecisionRecord(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    timestamp: str
    decision_type: DecisionType
    option_name: str
    vendor_or_site: Optional[str] = None
    option_url: Optional[str] = None
    price_seen: Optional[str] = None
    currency: Optional[str] = None
    decision: Decision
    tier_bucket: TierBucket = TierBucket.none
    reason_text: str = ""
    hard_filter_failed: bool = False
    reusable_rule_candidate: bool = False
    screenshot_path: Optional[str] = None

    model_config = {"extra": "ignore"}
