"""Pydantic schema round-trip validation tests."""

from __future__ import annotations

import json
import uuid

import pytest

from app.schemas.decision_schema import Decision, DecisionRecord, DecisionType, TierBucket
from app.schemas.event_schema import BrowserEvent, EventType
from app.schemas.note_schema import NoteType, ReasoningNote
from app.schemas.session_schema import SessionRecord
from app.utils.time_utils import now_iso


class TestSessionRecord:
    def test_minimal_creation(self):
        s = SessionRecord(
            agent_name="Alice",
            client_reference="Jones Family",
            destination="Costa Rica",
            travel_dates="2026-09-01 to 2026-09-10",
            travelers="2 adults",
            budget="$5,000",
            trip_type="adventure",
        )
        assert s.session_id  # UUID assigned
        assert s.app_version
        assert s.operating_system
        assert s.status == "started"

    def test_json_round_trip(self):
        s = SessionRecord(
            agent_name="Bob",
            client_reference="Smith",
            destination="Peru",
            travel_dates="2026-10-01",
            travelers="2",
            budget="$4,000",
            trip_type="cultural",
        )
        data = s.model_dump()
        restored = SessionRecord(**data)
        assert restored.session_id == s.session_id
        assert restored.agent_name == "Bob"


class TestBrowserEvent:
    def test_page_navigation_event(self):
        e = BrowserEvent(
            session_id=str(uuid.uuid4()),
            timestamp=now_iso(),
            event_type=EventType.page_navigated,
            url="https://example.com",
            domain="example.com",
            page_title="Example Domain",
        )
        assert e.event_id
        assert e.event_type == EventType.page_navigated

    def test_input_event_with_redaction_flag(self):
        e = BrowserEvent(
            session_id=str(uuid.uuid4()),
            timestamp=now_iso(),
            event_type=EventType.input,
            url="https://example.com",
            input_value="[REDACTED]",
            input_type="password",
            redacted=True,
        )
        assert e.redacted is True
        assert e.input_value == "[REDACTED]"

    def test_json_round_trip(self):
        e = BrowserEvent(
            session_id=str(uuid.uuid4()),
            timestamp=now_iso(),
            event_type=EventType.click,
            url="https://example.com",
            element_tag="button",
            element_text="Search",
        )
        raw = json.dumps(e.model_dump(), default=str)
        data = json.loads(raw)
        restored = BrowserEvent(**data)
        assert restored.event_id == e.event_id


class TestReasoningNote:
    def test_note_creation(self):
        n = ReasoningNote(
            session_id=str(uuid.uuid4()),
            timestamp=now_iso(),
            note_type=NoteType.option_rejected,
            note_text="Price was 30% above budget ceiling.",
            url="https://booking.com",
        )
        assert n.note_id
        assert n.note_type == NoteType.option_rejected

    def test_all_note_types_valid(self):
        sid = str(uuid.uuid4())
        for nt in NoteType:
            n = ReasoningNote(
                session_id=sid,
                timestamp=now_iso(),
                note_type=nt,
                note_text="test",
            )
            assert n.note_type == nt


class TestDecisionRecord:
    def test_full_decision(self):
        d = DecisionRecord(
            session_id=str(uuid.uuid4()),
            timestamp=now_iso(),
            decision_type=DecisionType.reject_option,
            option_name="Hilton Garden Inn",
            vendor_or_site="Expedia",
            price_seen="1800",
            currency="USD",
            decision=Decision.rejected,
            tier_bucket=TierBucket.premium,
            reason_text="Over budget and poor location.",
            hard_filter_failed=True,
            reusable_rule_candidate=False,
        )
        assert d.decision == Decision.rejected
        assert d.hard_filter_failed is True

    def test_json_round_trip(self):
        d = DecisionRecord(
            session_id=str(uuid.uuid4()),
            timestamp=now_iso(),
            decision_type=DecisionType.shortlist_option,
            option_name="Hotel Casona",
            decision=Decision.shortlisted,
        )
        data = d.model_dump()
        restored = DecisionRecord(**data)
        assert restored.decision_id == d.decision_id
