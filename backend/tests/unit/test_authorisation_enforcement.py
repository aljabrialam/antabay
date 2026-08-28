"""Unit tests for AuthorisationPolicyEngine request/enforce lifecycle
(T019-T026, T030-T034).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import inspect
import os
from decimal import Decimal
from typing import Any


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'authorisation_enforcement.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _seed_journey(repo: Any) -> str:
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    return JourneyService(repository=repo).create_journey(objective).journey_id


def _engine(repo: Any) -> Any:
    from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine

    return AuthorisationPolicyEngine(repository=repo)


def _money_action(action_id: str = "a1", cost: str = "50") -> Any:
    from journey.models.authorisation_policy import ProposedAction

    return ProposedAction(
        action_id=action_id,
        description="Rebook LJ201",
        cost_amount=Decimal(cost),
        cost_description=f"+USD {cost}.00",
        objective_effect="Preserved",
        cancels_or_voids_booking=False,
        is_reversible=True,
        breaches_hard_constraint=False,
    )


def _permitted_action(action_id: str = "a1") -> Any:
    from journey.models.authorisation_policy import ProposedAction

    return ProposedAction(
        action_id=action_id,
        description="Refresh fare quote",
        cost_amount=Decimal("0"),
        cost_description="+USD 0.00",
        objective_effect="None",
        cancels_or_voids_booking=False,
        is_reversible=True,
        breaches_hard_constraint=False,
    )


def _authorisation_requested_events(repo: Any, journey_id: str) -> list[Any]:
    from journey.models.events import EventType

    events = repo.get_events_from_sequence(journey_id, 0)
    return [e for e in events if e.event_type is EventType.AUTHORISATION_REQUESTED]


class TestRequestIfRequiredAppendsAuthorisationRequestedEvent:
    def test_payload_states_action_cost_objective_and_rule(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        engine.request_if_required(journey_id, _money_action())

        requested = _authorisation_requested_events(repo, journey_id)
        assert len(requested) == 1
        payload = requested[0].payload
        assert payload["action"] == "Rebook LJ201"
        assert payload["cost"] == "+USD 50.00"
        assert payload["objective_effect"] == "Preserved"
        assert payload["rule_id"] == "AUTH-MONEY"


class TestRequestIfRequiredSkipsEventWhenPermitted:
    def test_no_event_appended_for_autonomous_action(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        engine.request_if_required(journey_id, _permitted_action())

        assert _authorisation_requested_events(repo, journey_id) == []


class TestEnforceAuthorisedFalseWhenNoRequestExists:
    def test_unknown_action_id_is_not_authorised(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        assert engine.enforce_authorised(journey_id, "never-proposed", Decimal("0")) is False


class TestEnforceAuthorisedFalseWhenUnanswered:
    def test_unanswered_request_blocks_execution(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        engine.request_if_required(journey_id, _money_action(action_id="a1", cost="50"))

        assert engine.enforce_authorised(journey_id, "a1", Decimal("50")) is False


class TestEnforceAuthorisedFalseWhenRefused:
    def test_refused_request_blocks_execution(self, tmp_path: Any) -> None:
        from journey.services.event_service import EventService

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        engine.request_if_required(journey_id, _money_action(action_id="a1", cost="50"))
        requested = _authorisation_requested_events(repo, journey_id)[0]
        EventService(repo).record_auth_outcome(
            journey_id, requested.payload["request_id"], "refused"
        )

        assert engine.enforce_authorised(journey_id, "a1", Decimal("50")) is False


class TestEnforceAuthorisedTrueWhenApproved:
    def test_approved_request_permits_execution(self, tmp_path: Any) -> None:
        from journey.services.event_service import EventService

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        engine.request_if_required(journey_id, _money_action(action_id="a1", cost="50"))
        requested = _authorisation_requested_events(repo, journey_id)[0]
        EventService(repo).record_auth_outcome(
            journey_id, requested.payload["request_id"], "approved"
        )

        assert engine.enforce_authorised(journey_id, "a1", Decimal("50")) is True


class TestEnforceAuthorisedHasNoTrustMeParameter:
    def test_signature_carries_no_outcome_assertion_parameter(self) -> None:
        from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine

        params = inspect.signature(AuthorisationPolicyEngine.enforce_authorised).parameters
        assert set(params) - {"self"} == {
            "journey_id",
            "action_id",
            "current_cost_amount",
        }


def _authorisation_voided_events(repo: Any, journey_id: str) -> list[Any]:
    from journey.models.events import EventType

    events = repo.get_events_from_sequence(journey_id, 0)
    return [e for e in events if e.event_type is EventType.AUTHORISATION_VOIDED]


def _grant(engine: Any, repo: Any, journey_id: str, action_id: str, cost: str) -> str:
    """Request and approve an action, returning its request_id."""
    from journey.services.event_service import EventService

    engine.request_if_required(journey_id, _money_action(action_id=action_id, cost=cost))
    requested = _authorisation_requested_events(repo, journey_id)[-1]
    EventService(repo).record_auth_outcome(
        journey_id, requested.payload["request_id"], "approved"
    )
    return requested.payload["request_id"]


class TestGrantDoesNotCarryToSubsequentAction:
    def test_different_action_id_same_cost_is_not_authorised(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        _grant(engine, repo, journey_id, action_id="a1", cost="50")

        assert engine.enforce_authorised(journey_id, "a2", Decimal("50")) is False


class TestCostChangeVoidsGrant:
    def test_changed_cost_is_not_authorised_and_records_void(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        _grant(engine, repo, journey_id, action_id="a1", cost="50")

        assert engine.enforce_authorised(journey_id, "a1", Decimal("75")) is False

        voided = _authorisation_voided_events(repo, journey_id)
        assert len(voided) == 1
        assert voided[0].payload["granted_cost"] == "50"
        assert voided[0].payload["current_cost"] == "75"

        # Re-checking the same still-mismatched cost must not double-void.
        assert engine.enforce_authorised(journey_id, "a1", Decimal("75")) is False
        assert len(_authorisation_voided_events(repo, journey_id)) == 1


class TestIdenticalResubmissionReusesExistingGrant:
    def test_resubmitting_unchanged_action_issues_no_second_request(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        _grant(engine, repo, journey_id, action_id="a1", cost="50")
        engine.request_if_required(journey_id, _money_action(action_id="a1", cost="50"))

        assert len(_authorisation_requested_events(repo, journey_id)) == 1


class TestFreshRequestIssuedAfterVoid:
    def test_new_request_id_issued_after_cost_changes(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        engine = _engine(repo)

        original_request_id = _grant(engine, repo, journey_id, action_id="a1", cost="50")
        engine.enforce_authorised(journey_id, "a1", Decimal("75"))  # triggers the void

        engine.request_if_required(journey_id, _money_action(action_id="a1", cost="75"))

        requested = _authorisation_requested_events(repo, journey_id)
        assert len(requested) == 2
        assert requested[-1].payload["request_id"] != original_request_id
        assert requested[-1].payload["cost"] == "+USD 75.00"
