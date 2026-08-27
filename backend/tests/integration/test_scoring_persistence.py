"""Integration tests for ScoringRun persistence (003-option-scoring, Phase 6).

TDD gate (T054–T055): written BEFORE tables.py and repository additions.
These tests MUST fail until T056–T059 are implemented.

Tests use an in-memory SQLite DB and two separate sessions to verify round-trip.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event

from journey.models.flight import FlightOption, Leg
from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
from journey.models.scoring import (
    EliminationRecord,
    NoSatisfyingOptionReport,
    Rationale,
    ScoredOption,
    ScoringOutcome,
    ScoringRun,
)
from journey.storage.tables import metadata

# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------

NOW = datetime(2026, 9, 5, 2, 31, tzinfo=timezone.utc)


def _make_leg(option_id: str = "OPT1") -> Leg:
    return Leg(
        leg_id=f"LEG_{option_id}",
        option_id=option_id,
        segment_index=1,
        carrier="ZE",
        flight_number="ZE609",
        dep_airport="ICN",
        arr_airport="NRT",
        dep_time="202609051030",
        arr_time="202609051300",
        duration_minutes=150,
        stop_cities="",
        cabin_class="S",
        seat_count=9,
        risk_sellout=False,
        code_share=False,
        aircraft_code="738",
        fare_family="Discount",
    )


def _make_option(option_id: str = "OPT1") -> FlightOption:
    return FlightOption(
        option_id=option_id,
        journey_id="J1",
        search_record_id="SR1",
        fid=f"FID_{option_id}",
        routing_identifier=f"RI::{option_id}",
        currency="USD",
        adult_price=Decimal("100"),
        adult_tax=Decimal("20"),
        transaction_fee=Decimal("0"),
        refreshed_at=None,
        expire_at=datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc),
        is_multi_leg=False,
        separate_bookings=False,
        legs=[_make_leg(option_id)],
        recorded_at=datetime(2026, 9, 5, 2, 30, tzinfo=timezone.utc),
    )


def _hard(value):
    return ConstrainedField(value=value, constraint_type=ConstraintType.HARD)


def _make_run_with_selected() -> tuple[ScoringRun, str]:
    """Return (ScoringRun with a selected option, journey_id)."""
    opt = _make_option("SELECTED_OPT")
    rationale = Rationale(
        option_id="SELECTED_OPT",
        objective_elements=["budget_amount", "origin"],
        summary="Within budget; departs from correct origin.",
        arrival_margin_minutes=120,
        total_cost=Decimal("120"),
    )
    scored = ScoredOption(
        option=opt,
        outcome=ScoringOutcome.SELECTED,
        rank=1,
        rationale=rationale,
        elimination=None,
        rejection_reason=None,
        connection_eval=None,
    )
    objective = TravelObjective(
        origin=_hard("ICN"),
        destination=_hard("NRT"),
        pax_count=_hard(1),
        budget_amount=_hard(Decimal("300")),
        budget_currency=_hard("USD"),
    )
    run = ScoringRun(
        run_id="RUN_SELECTED_001",
        objective=objective,
        evaluated_at=NOW,
        scored_options=[scored],
        selected_option=scored,
        no_satisfying_option=None,
    )
    return run, "J1"


def _make_run_with_no_satisfying() -> tuple[ScoringRun, str]:
    """Return (ScoringRun with no_satisfying_option set, journey_id)."""
    opt = _make_option("ELIM_OPT")
    elim = EliminationRecord(
        option_id="ELIM_OPT",
        reason_code="budget_exceeded",
        reason_detail="Cost exceeds budget.",
        constraint_id="budget_amount",
    )
    scored = ScoredOption(
        option=opt,
        outcome=ScoringOutcome.ELIMINATED,
        rank=None,
        rationale=None,
        elimination=elim,
        rejection_reason=None,
        connection_eval=None,
    )
    no_sat = NoSatisfyingOptionReport(
        unsatisfied_constraints=["budget_amount"],
        eliminated_count=1,
        summary="No option satisfied budget_amount.",
    )
    objective = TravelObjective(
        origin=_hard("ICN"),
        destination=_hard("NRT"),
        pax_count=_hard(1),
        budget_amount=_hard(Decimal("50")),
        budget_currency=_hard("USD"),
    )
    run = ScoringRun(
        run_id="RUN_NO_SAT_001",
        objective=objective,
        evaluated_at=NOW,
        scored_options=[scored],
        selected_option=None,
        no_satisfying_option=no_sat,
    )
    return run, "J1"


@pytest.fixture
def repo(tmp_path):
    """JourneyRepository bound to an isolated in-memory SQLite DB."""
    db_path = f"sqlite:///{tmp_path}/test_scoring.db"
    engine = create_engine(db_path)
    metadata.create_all(engine)

    import journey.storage.repository as repo_module
    original = repo_module.get_connection

    from contextlib import contextmanager
    @contextmanager
    def patched():
        with engine.connect() as conn:
            yield conn

    repo_module.get_connection = patched

    from journey.storage.repository import JourneyRepository
    yield JourneyRepository()

    repo_module.get_connection = original


# ---------------------------------------------------------------------------
# T054: ScoringRun round-trip — selected option
# ---------------------------------------------------------------------------

class TestScoringRunRoundTrip:
    def test_save_and_reload_selected_run(self, repo):
        run, journey_id = _make_run_with_selected()
        repo.save_scoring_run(run, journey_id)

        reloaded = repo.get_scoring_run(run.run_id)

        assert reloaded.run_id == run.run_id
        assert reloaded.evaluated_at == run.evaluated_at
        assert reloaded.selected_option is not None
        assert reloaded.selected_option.option.option_id == "SELECTED_OPT"
        assert reloaded.selected_option.rationale.total_cost == Decimal("120")
        assert reloaded.selected_option.rationale.arrival_margin_minutes == 120
        assert "budget_amount" in reloaded.selected_option.rationale.objective_elements
        assert reloaded.no_satisfying_option is None
        assert len(reloaded.scored_options) == 1

    def test_option_count_and_eliminated_count_stored(self, repo):
        run, journey_id = _make_run_with_selected()
        repo.save_scoring_run(run, journey_id)

        # Verify via direct DB query that the summary columns are set
        from sqlalchemy import text
        import journey.storage.repository as repo_module
        with repo_module.get_connection() as conn:
            row = conn.execute(
                text("SELECT option_count, eliminated_count, selected_option_id FROM scoring_runs WHERE run_id = :rid"),
                {"rid": run.run_id}
            ).mappings().one()
        assert row["option_count"] == 1
        assert row["eliminated_count"] == 0
        assert row["selected_option_id"] == "SELECTED_OPT"


# ---------------------------------------------------------------------------
# T054: ScoringRun round-trip — no_satisfying_option
# ---------------------------------------------------------------------------

class TestScoringRunWithNoSatisfying:
    def test_save_and_reload_no_satisfying_run(self, repo):
        run, journey_id = _make_run_with_no_satisfying()
        repo.save_scoring_run(run, journey_id)

        reloaded = repo.get_scoring_run(run.run_id)

        assert reloaded.run_id == run.run_id
        assert reloaded.selected_option is None
        assert reloaded.no_satisfying_option is not None
        assert "budget_amount" in reloaded.no_satisfying_option.unsatisfied_constraints
        assert reloaded.no_satisfying_option.eliminated_count == 1
        assert len(reloaded.scored_options) == 1
        elim = reloaded.scored_options[0].elimination
        assert elim is not None
        assert elim.reason_code == "budget_exceeded"


# ---------------------------------------------------------------------------
# T055: ScoringRunNotFoundError
# ---------------------------------------------------------------------------

class TestGetScoringRunNotFound:
    def test_raises_scoring_run_not_found_error(self, repo):
        from journey.errors import ScoringRunNotFoundError
        with pytest.raises(ScoringRunNotFoundError):
            repo.get_scoring_run("nonexistent-run-id")
