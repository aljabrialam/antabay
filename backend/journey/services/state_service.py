from __future__ import annotations

from datetime import datetime, timezone

from journey.models.journey import (
    IdentifierFreshness,
    InvalidTransitionError,
    JourneyState,
    JourneyStateMachine,
)
from journey.storage.repository import JourneyRepository

_machine = JourneyStateMachine()


class IdentifierNotFoundError(Exception):
    pass


class JourneyStateService:
    def __init__(self, repository: JourneyRepository | None = None) -> None:
        self._repo = repository if repository is not None else JourneyRepository()

    def transition(
        self,
        journey_id: str,
        to_state: JourneyState,
        reason: str,
        now: datetime | None = None,
    ) -> None:
        ts = now if now is not None else datetime.now(tz=timezone.utc)
        record = self._repo.get_journey(journey_id)
        _machine.transition(record.state, to_state)
        self._repo.update_journey_state(journey_id, to_state, updated_at=ts)
        self._repo.append_audit_entry(
            journey_id,
            "STATE_TRANSITION",
            f"Transition to {to_state.value}: {reason}",
            recorded_at=ts,
        )

    def append_audit_entry(
        self,
        journey_id: str,
        entry_type: str,
        content: str,
        now: datetime | None = None,
    ) -> None:
        ts = now if now is not None else datetime.now(tz=timezone.utc)
        self._repo.append_audit_entry(journey_id, entry_type, content, recorded_at=ts)

    def record_authorisation_outcome(
        self,
        journey_id: str,
        request_desc: str,
        outcome: str,
        recorded_by: str,
        now: datetime | None = None,
    ) -> None:
        ts = now if now is not None else datetime.now(tz=timezone.utc)
        content = f"outcome={outcome} recorded_by={recorded_by} request={request_desc}"
        self._repo.append_audit_entry(
            journey_id, "AUTHORISATION", content, recorded_at=ts
        )

    def add_held_identifier(
        self,
        journey_id: str,
        value: str,
        issued_at: datetime,
        stale_after_seconds: int,
    ) -> None:
        self._repo.add_held_identifier(
            journey_id=journey_id,
            value=value,
            issued_at=issued_at,
            stale_after_seconds=stale_after_seconds,
        )

    def check_identifier_freshness(
        self,
        journey_id: str,
        identifier_id: str,
        now: datetime,
    ) -> IdentifierFreshness:
        record = self._repo.get_journey(journey_id)
        for ident in record.held_identifiers:
            if ident.identifier_id == identifier_id:
                return (
                    IdentifierFreshness.STALE
                    if ident.is_stale(now)
                    else IdentifierFreshness.FRESH
                )
        raise IdentifierNotFoundError(
            f"Identifier {identifier_id!r} not found on journey {journey_id!r}"
        )
