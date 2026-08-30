"""Export, promote, and load demonstration captures
(014-demonstration-capture, FR-010, FR-011, FR-013, research.md R4).

A Captured Event Stream is a JSON array of {event_type, payload,
simulated, recorded_at} rows, in the same shape
`tests/fixtures/journey_events_001.json` already uses. `load()` reuses
`seed_console_fixture.py`'s generalised `seed_replay()` (research.md R7)
so a capture can be reproduced into a fresh journey and driven through
the existing /replay endpoint with zero network calls (FR-011).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

_DEFAULT_MANIFEST_PATH = (
    Path(__file__).parent.parent / "tests" / "fixtures" / "demo_captures" / "canonical.json"
)


def export(journey_id: str, out_path: Path) -> None:
    """Write journey_id's full event stream to out_path (FR-010)."""
    from journey.storage.repository import JourneyRepository

    repo = JourneyRepository()
    events = repo.get_events_from_sequence(journey_id, from_sequence=0)
    rows = [
        {
            "sequence": event.sequence,
            "event_type": event.event_type.value,
            "payload": event.payload,
            "simulated": event.simulated,
            "recorded_at": event.recorded_at.isoformat(),
        }
        for event in events
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=2))


def promote(file_path: Path, manifest_path: Path | None = None) -> None:
    """Designate file_path as the canonical capture (FR-013).

    A deliberate, separate step from export() — never called
    automatically just because a run passed (Clarifications session)."""
    target = manifest_path if manifest_path is not None else _DEFAULT_MANIFEST_PATH
    manifest: dict[str, Any] = {
        "canonical_file": file_path.name,
        "promoted_at": datetime.now().astimezone().isoformat(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2))


def load(file_path: Path) -> str:
    """Reproduce file_path's captured events into a fresh journey,
    returning the new journey_id. Touches only the local database — no
    network call is made anywhere in this path (FR-011)."""
    from scripts.seed_console_fixture import seed_replay

    return seed_replay(fixture_path=file_path)
