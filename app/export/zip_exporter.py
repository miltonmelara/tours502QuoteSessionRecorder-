"""ZIP export service.

Assembles all session artefacts into a single ZIP file and writes
metadata.json immediately before zipping.
"""

from __future__ import annotations

import json
import logging
import platform
import zipfile
from pathlib import Path

from app.config import APP_VERSION
from app.utils.paths import safe_filename
from app.utils.time_utils import now_iso

logger = logging.getLogger(__name__)


class ZipExporter:
    """Creates a structured ZIP archive from a completed session folder."""

    def export(
        self,
        session_folder: Path,
        agent_name: str,
        client_reference: str,
        session_timestamp: str,
    ) -> Path:
        """Build the ZIP and return its path.

        The ZIP is placed next to the session folder (inside ``exports/``).

        Args:
            session_folder: Path to the session directory.
            agent_name: Human-readable agent name (used in ZIP filename).
            client_reference: Client/reference name (used in ZIP filename).
            session_timestamp: Compact timestamp string (YYYYMMDD_HHMMSS).

        Returns:
            Path to the created ZIP file.

        Raises:
            RuntimeError: If ZIP creation fails.
        """
        # Write metadata.json before zipping
        self._write_metadata(session_folder)

        # Build ZIP filename
        agent_safe = safe_filename(agent_name, 20)
        client_safe = safe_filename(client_reference, 20)
        zip_name = f"quote-session_{agent_safe}_{client_safe}_{session_timestamp}.zip"
        zip_path = session_folder.parent / zip_name

        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(session_folder.rglob("*")):
                    if file_path.is_file():
                        arcname = file_path.relative_to(session_folder.parent)
                        zf.write(file_path, arcname)

            logger.info("ZIP exported: %s  (%s bytes)", zip_path.name, zip_path.stat().st_size)
            return zip_path

        except Exception as exc:
            logger.exception("ZIP export failed")
            raise RuntimeError(f"ZIP export failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _write_metadata(self, session_folder: Path) -> None:
        """Compute and write metadata.json into the session folder."""
        screenshots_dir = session_folder / "screenshots"
        snapshots_dir = session_folder / "snapshots"

        screenshot_count = len(list(screenshots_dir.glob("*.png"))) if screenshots_dir.exists() else 0
        snapshot_count = len(list(snapshots_dir.glob("*.txt"))) if snapshots_dir.exists() else 0

        events_path = session_folder / "events.json"
        notes_path = session_folder / "notes.json"

        event_count = self._count_json_array(events_path)
        note_count = self._count_json_array(notes_path)

        # Derive ZIP filename to record in metadata
        zip_name = session_folder.name.replace("session_", "quote-session_") + ".zip"

        metadata = {
            "app_version": APP_VERSION,
            "export_created_at": now_iso(),
            "machine_os": f"{platform.system()} {platform.release()}",
            "browser_engine": "chromium (playwright)",
            "total_events": event_count,
            "total_notes": note_count,
            "total_screenshots": screenshot_count,
            "total_snapshots": snapshot_count,
            "zip_filename": zip_name,
        }

        metadata_path = session_folder / "metadata.json"
        with metadata_path.open("w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=False)
        logger.debug("metadata.json written")

    @staticmethod
    def _count_json_array(path: Path) -> int:
        """Return the number of items in a JSON array file, or 0 on failure."""
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0
