"""ZIP export integration tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.export.zip_exporter import ZipExporter
from app.schemas.decision_schema import Decision, DecisionRecord, DecisionType
from app.schemas.event_schema import BrowserEvent, EventType
from app.schemas.note_schema import NoteType, ReasoningNote
from app.schemas.session_schema import SessionRecord
from app.storage.file_store import FileStore
from app.storage.session_store import SessionStore
from app.utils.time_utils import now_iso, session_timestamp


@pytest.fixture()
def session_folder(tmp_path: Path) -> Path:
    """Create a fully-populated session folder inside a temp dir."""
    ts = session_timestamp()
    session_record = SessionRecord(
        agent_name="Test Agent",
        client_reference="Test Client",
        destination="Test Destination",
        travel_dates="2026-09-01",
        travelers="2",
        budget="$1,000",
        trip_type="test",
    )
    session_record.started_at = now_iso()
    session_record.ended_at = now_iso()
    session_record.status = "finished"

    folder = tmp_path / f"session_{ts}_Test_Agent_Test_Client"
    file_store = FileStore(folder)
    file_store.initialise()

    store = SessionStore(session_record, folder)

    store.add_event(
        BrowserEvent(
            session_id=session_record.session_id,
            timestamp=now_iso(),
            event_type=EventType.page_navigated,
            url="https://example.com",
            domain="example.com",
            page_title="Example",
        )
    )
    store.add_note(
        ReasoningNote(
            session_id=session_record.session_id,
            timestamp=now_iso(),
            note_type=NoteType.site_choice_reason,
            note_text="Checking pricing on example.com",
        )
    )
    store.add_decision(
        DecisionRecord(
            session_id=session_record.session_id,
            timestamp=now_iso(),
            decision_type=DecisionType.reject_option,
            option_name="Some Hotel",
            decision=Decision.rejected,
            reason_text="Too expensive.",
        )
    )
    store.write_all()

    # Fake a screenshot file
    fake_screenshot = folder / "screenshots" / "001_navigation_example.png"
    fake_screenshot.write_bytes(b"\x89PNG\r\n")

    return folder


def test_zip_created(session_folder: Path, tmp_path: Path) -> None:
    exporter = ZipExporter()
    zip_path = exporter.export(
        session_folder=session_folder,
        agent_name="Test Agent",
        client_reference="Test Client",
        session_timestamp="20260901_120000",
    )
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"
    assert zip_path.stat().st_size > 0


def test_zip_contains_required_files(session_folder: Path) -> None:
    exporter = ZipExporter()
    zip_path = exporter.export(
        session_folder=session_folder,
        agent_name="Test Agent",
        client_reference="Test Client",
        session_timestamp="20260901_120000",
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [Path(n).name for n in zf.namelist()]

    required = {"session.json", "events.json", "notes.json", "decisions.json", "metadata.json"}
    assert required.issubset(set(names)), f"Missing files: {required - set(names)}"


def test_metadata_json_is_valid(session_folder: Path) -> None:
    exporter = ZipExporter()
    zip_path = exporter.export(
        session_folder=session_folder,
        agent_name="Test Agent",
        client_reference="Test Client",
        session_timestamp="20260901_120000",
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find metadata.json entry
        meta_entry = next(n for n in zf.namelist() if n.endswith("metadata.json"))
        raw = zf.read(meta_entry)

    metadata = json.loads(raw)
    assert metadata["app_version"]
    assert metadata["browser_engine"] == "chromium (playwright)"
    assert isinstance(metadata["total_events"], int)
    assert isinstance(metadata["total_screenshots"], int)


def test_zip_contains_screenshot(session_folder: Path) -> None:
    exporter = ZipExporter()
    zip_path = exporter.export(
        session_folder=session_folder,
        agent_name="Test Agent",
        client_reference="Test Client",
        session_timestamp="20260901_120000",
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [Path(n).name for n in zf.namelist()]

    assert "001_navigation_example.png" in names


def test_events_json_has_correct_count(session_folder: Path) -> None:
    exporter = ZipExporter()
    zip_path = exporter.export(
        session_folder=session_folder,
        agent_name="Test Agent",
        client_reference="Test Client",
        session_timestamp="20260901_120000",
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        events_entry = next(n for n in zf.namelist() if n.endswith("events.json"))
        events = json.loads(zf.read(events_entry))

    assert len(events) == 1
    assert events[0]["event_type"] == EventType.page_navigated.value
