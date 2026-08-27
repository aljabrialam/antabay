"""Unit tests for ScoringService and scoring models (003-option-scoring).

TDD gate (T004): This file is written BEFORE implementation. The import block
below MUST fail with ImportError until T005–T012 are complete.

Quickstart scenario mapping:
  Scenario 1  → TestHardConstraintElimination
  Scenario 2  → TestNoSatisfyingOption
  Scenario 3  → TestPreferenceRanking, TestRejectionReason
  Scenario 4  → TestArrivalMargin
  Scenario 5  → TestConnectionExclusion
  Scenario 6  → TestConnectionTimeCalculation
  Scenario 7  → TestImpossibleConnection
  Scenario 8  → TestExpiryElimination
  Scenario 9  → TestCurrencyMismatch
  Scenario 10 → TestScarcitySignal
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# T004: TDD gate — these imports MUST fail before T005–T012 are implemented.
# ---------------------------------------------------------------------------
from journey.models.scoring import (
    ConnectionEvaluation,
    EliminationRecord,
    NoSatisfyingOptionReport,
    Rationale,
    RejectionReason,
    ScoredOption,
    ScoringOutcome,
    ScoringRun,
)
from journey.services.scoring_service import ScoringService

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

from journey.models.flight import FlightOption, Leg
from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective


def _make_leg(
    *,
    leg_id: str = "L1",
    option_id: str = "OPT",
    dep_airport: str = "ICN",
    arr_airport: str = "NRT",
    dep_time: str = "202609051030",
    arr_time: str = "202609051300",
    seat_count: int = 9,
    risk_sellout: bool = False,
) -> Leg:
    return Leg(
        leg_id=leg_id,
        option_id=option_id,
        segment_index=1,
        carrier="ZE",
        flight_number="ZE609",
        dep_airport=dep_airport,
        arr_airport=arr_airport,
        dep_time=dep_time,
        arr_time=arr_time,
        duration_minutes=150,
        stop_cities="",
        cabin_class="S",
        seat_count=seat_count,
        risk_sellout=risk_sellout,
        code_share=False,
        aircraft_code="738",
        fare_family="Discount",
    )


def _make_option(
    *,
    option_id: str = "OPT1",
    currency: str = "USD",
    adult_price: Decimal = Decimal("100"),
    adult_tax: Decimal = Decimal("20"),
    expire_at: datetime | None = datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc),
    legs: list[Leg] | None = None,
    is_multi_leg: bool = False,
) -> FlightOption:
    if legs is None:
        legs = [_make_leg(option_id=option_id)]
    return FlightOption(
        option_id=option_id,
        journey_id="J1",
        search_record_id="SR1",
        fid=f"FID_{option_id}",
        routing_identifier=f"RI::{option_id}",
        currency=currency,
        adult_price=adult_price,
        adult_tax=adult_tax,
        transaction_fee=Decimal("0"),
        refreshed_at=None,
        expire_at=expire_at,
        is_multi_leg=is_multi_leg,
        separate_bookings=False,
        legs=legs,
        recorded_at=datetime(2026, 9, 5, 2, 30, tzinfo=timezone.utc),
    )


def _hard(value):
    return ConstrainedField(value=value, constraint_type=ConstraintType.HARD)


def _soft(value):
    return ConstrainedField(value=value, constraint_type=ConstraintType.SOFT)


NOW = datetime(2026, 9, 5, 2, 31, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# T004: Type existence checks (fail before T005–T012)
# ---------------------------------------------------------------------------

class TestModelTypeExistence:
    def test_scoring_outcome_values(self):
        assert ScoringOutcome.SELECTED == "SELECTED"
        assert ScoringOutcome.ELIMINATED == "ELIMINATED"
        assert ScoringOutcome.RANKED == "RANKED"

    def test_elimination_record_fields(self):
        rec = EliminationRecord(
            option_id="OPT1",
            reason_code="budget_exceeded",
            reason_detail="Cost exceeds budget",
            constraint_id="budget_amount",
        )
        assert rec.option_id == "OPT1"
        assert rec.reason_code == "budget_exceeded"
        assert rec.constraint_id == "budget_amount"

    def test_rationale_fields(self):
        r = Rationale(
            option_id="OPT1",
            objective_elements=["budget_amount"],
            summary="Within budget.",
            arrival_margin_minutes=None,
            total_cost=Decimal("120"),
        )
        assert r.total_cost == Decimal("120")

    def test_rejection_reason_fields(self):
        rr = RejectionReason(
            option_id="OPT2",
            reason_code="outranked_cost",
            reason_detail="A cheaper option exists.",
        )
        assert rr.reason_code == "outranked_cost"

    def test_connection_evaluation_fields(self):
        ce = ConnectionEvaluation(
            option_id="OPT1",
            connection_times=[90],
            connection_excluded=False,
            exclusion_rule=None,
            impossible_connections=[],
        )
        assert ce.connection_times == [90]

    def test_no_satisfying_option_report_fields(self):
        r = NoSatisfyingOptionReport(
            unsatisfied_constraints=["budget_amount"],
            eliminated_count=3,
            summary="No option satisfied budget_amount.",
        )
        assert r.eliminated_count == 3

    def test_scored_option_fields(self):
        opt = _make_option()
        elim = EliminationRecord(
            option_id="OPT1",
            reason_code="budget_exceeded",
            reason_detail="Over budget",
            constraint_id="budget_amount",
        )
        so = ScoredOption(
            option=opt,
            outcome=ScoringOutcome.ELIMINATED,
            rank=None,
            rationale=None,
            elimination=elim,
            rejection_reason=None,
            connection_eval=None,
        )
        assert so.outcome == ScoringOutcome.ELIMINATED
        assert so.rank is None

    def test_scoring_run_fields(self):
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
        )
        run = ScoringRun(
            run_id="RUN1",
            objective=obj,
            evaluated_at=NOW,
            scored_options=[],
            selected_option=None,
            no_satisfying_option=None,
        )
        assert run.run_id == "RUN1"
        assert run.selected_option is None


# ---------------------------------------------------------------------------
# US1 — Hard Constraint Elimination (T014–T020)
# ---------------------------------------------------------------------------

class TestHardConstraintElimination:
    def _objective(self, **kwargs):
        base = dict(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            departure_date=_hard("20260905"),
            budget_amount=_hard(Decimal("300")),
            budget_currency=_hard("USD"),
            pax_count=_hard(1),
        )
        base.update(kwargs)
        return TravelObjective(**base)

    def test_budget_exceeded_eliminated(self):
        opt = _make_option(option_id="PRICEY", adult_price=Decimal("290"), adult_tax=Decimal("50"))
        obj = self._objective()
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert run.scored_options[0].outcome == ScoringOutcome.ELIMINATED
        assert elim.reason_code == "budget_exceeded"
        assert elim.constraint_id == "budget_amount"

    def test_arrival_too_late_eliminated(self):
        late_leg = _make_leg(arr_time="202609051600")
        opt = _make_option(option_id="LATE", legs=[late_leg])
        obj = self._objective(latest_arrival=_hard("202609051400"))
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert elim.reason_code == "arrival_too_late"
        assert elim.constraint_id == "latest_arrival"

    def test_wrong_departure_date_eliminated(self):
        wrong_leg = _make_leg(dep_time="202609061030")
        opt = _make_option(option_id="WRONGDATE", legs=[wrong_leg])
        obj = self._objective()
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert elim.reason_code == "wrong_departure_date"
        assert elim.constraint_id == "departure_date"

    def test_wrong_origin_eliminated(self):
        wrong_leg = _make_leg(dep_airport="PUS")
        opt = _make_option(option_id="WRONGORIG", legs=[wrong_leg])
        obj = self._objective()
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert elim.reason_code == "wrong_origin"
        assert elim.constraint_id == "origin"

    def test_wrong_destination_eliminated(self):
        wrong_leg = _make_leg(arr_airport="KIX")
        opt = _make_option(option_id="WRONGDEST", legs=[wrong_leg])
        obj = self._objective()
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert elim.reason_code == "wrong_destination"
        assert elim.constraint_id == "destination"

    def test_surviving_option_has_no_elimination(self):
        opt = _make_option(option_id="GOOD", adult_price=Decimal("200"), adult_tax=Decimal("30"))
        obj = self._objective()
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        assert run.scored_options[0].outcome == ScoringOutcome.SELECTED
        assert run.scored_options[0].elimination is None

    def test_total_coverage_no_silent_skip(self):
        opts = [
            _make_option(option_id="A", adult_price=Decimal("200"), adult_tax=Decimal("20")),
            _make_option(option_id="B", adult_price=Decimal("400"), adult_tax=Decimal("20")),
        ]
        obj = self._objective()
        svc = ScoringService()
        run = svc.score(obj, opts, NOW)
        assert len(run.scored_options) == 2


class TestNoSatisfyingOption:
    def test_all_eliminated_reports_unsatisfied_constraints(self):
        leg = _make_leg()
        opt_a = _make_option(option_id="A", adult_price=Decimal("400"), adult_tax=Decimal("0"))
        opt_b = _make_option(option_id="B", adult_price=Decimal("500"), adult_tax=Decimal("0"))
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            departure_date=_hard("20260905"),
            budget_amount=_hard(Decimal("300")),
            budget_currency=_hard("USD"),
            pax_count=_hard(1),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_a, opt_b], NOW)
        assert run.selected_option is None
        assert run.no_satisfying_option is not None
        assert "budget_amount" in run.no_satisfying_option.unsatisfied_constraints
        assert run.no_satisfying_option.eliminated_count == 2

    def test_empty_option_set_returns_no_selection(self):
        obj = TravelObjective(origin=_hard("ICN"), destination=_hard("NRT"), pax_count=_hard(1))
        svc = ScoringService()
        run = svc.score(obj, [], NOW)
        assert run.selected_option is None
        assert run.no_satisfying_option is None
        assert run.scored_options == []


class TestExpiryElimination:
    def test_expired_option_eliminated(self):
        past = datetime(2026, 9, 5, 2, 0, tzinfo=timezone.utc)
        opt = _make_option(option_id="EXPIRED", expire_at=past)
        obj = TravelObjective(origin=_hard("ICN"), destination=_hard("NRT"), pax_count=_hard(1))
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert elim.reason_code == "offer_expired"

    def test_no_expiry_eliminated_as_unknown(self):
        opt = _make_option(option_id="NOEXP", expire_at=None)
        obj = TravelObjective(origin=_hard("ICN"), destination=_hard("NRT"), pax_count=_hard(1))
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert elim.reason_code == "expiry_unknown"


class TestCurrencyMismatch:
    def test_foreign_currency_option_eliminated(self):
        opt = _make_option(option_id="EUR_OPT", currency="EUR")
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            budget_amount=_hard(Decimal("500")),
            budget_currency=_hard("USD"),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        elim = run.scored_options[0].elimination
        assert elim.reason_code == "currency_mismatch"

    def test_matching_currency_passes(self):
        opt = _make_option(option_id="USD_OPT", currency="USD", adult_price=Decimal("100"), adult_tax=Decimal("10"))
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            budget_amount=_hard(Decimal("500")),
            budget_currency=_hard("USD"),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        assert run.scored_options[0].outcome != ScoringOutcome.ELIMINATED or \
               run.scored_options[0].elimination.reason_code != "currency_mismatch"


class TestDeterminism:
    def _make_two_options(self):
        return [
            _make_option(option_id="AAA", adult_price=Decimal("100"), adult_tax=Decimal("10")),
            _make_option(option_id="BBB", adult_price=Decimal("200"), adult_tax=Decimal("10")),
        ]

    def test_same_selection_regardless_of_input_order(self):
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            budget_amount=_hard(Decimal("500")),
            budget_currency=_hard("USD"),
            preferences=_soft(["cost"]),
        )
        svc = ScoringService()
        opts = self._make_two_options()
        run_a = svc.score(obj, opts, NOW)
        run_b = svc.score(obj, list(reversed(opts)), NOW)
        assert run_a.selected_option.option.option_id == run_b.selected_option.option.option_id

    def test_same_rationale_regardless_of_input_order(self):
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            budget_amount=_hard(Decimal("500")),
            budget_currency=_hard("USD"),
            preferences=_soft(["cost"]),
        )
        svc = ScoringService()
        opts = self._make_two_options()
        run_a = svc.score(obj, opts, NOW)
        run_b = svc.score(obj, list(reversed(opts)), NOW)
        assert run_a.selected_option.rationale.summary == run_b.selected_option.rationale.summary


class TestRationaleConstruction:
    def test_rationale_names_satisfied_objective_elements(self):
        opt = _make_option(option_id="GOOD", adult_price=Decimal("100"), adult_tax=Decimal("20"))
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            budget_amount=_hard(Decimal("500")),
            budget_currency=_hard("USD"),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        assert run.selected_option is not None
        rationale = run.selected_option.rationale
        assert rationale is not None
        assert "budget_amount" in rationale.objective_elements
        assert rationale.total_cost == Decimal("120")

    def test_rationale_summary_is_non_empty_string(self):
        opt = _make_option(option_id="GOOD", adult_price=Decimal("100"), adult_tax=Decimal("20"))
        obj = TravelObjective(origin=_hard("ICN"), destination=_hard("NRT"), pax_count=_hard(1))
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        assert isinstance(run.selected_option.rationale.summary, str)
        assert len(run.selected_option.rationale.summary) > 0


# ---------------------------------------------------------------------------
# US2 — Preference Ranking and Rejection Explanation (T029–T035)
# ---------------------------------------------------------------------------

class TestPreferenceRanking:
    def test_cheapest_selected_with_cost_preference(self):
        opts = [
            _make_option(option_id="CHEAP", adult_price=Decimal("80"), adult_tax=Decimal("10")),
            _make_option(option_id="MID", adult_price=Decimal("150"), adult_tax=Decimal("10")),
            _make_option(option_id="PRICEY", adult_price=Decimal("200"), adult_tax=Decimal("10")),
        ]
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            preferences=_soft(["cost"]),
        )
        svc = ScoringService()
        run = svc.score(obj, opts, NOW)
        assert run.selected_option.option.option_id == "CHEAP"

    def test_ranked_options_have_ascending_rank(self):
        opts = [
            _make_option(option_id="CHEAP", adult_price=Decimal("80"), adult_tax=Decimal("10")),
            _make_option(option_id="MID", adult_price=Decimal("150"), adult_tax=Decimal("10")),
        ]
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            preferences=_soft(["cost"]),
        )
        svc = ScoringService()
        run = svc.score(obj, opts, NOW)
        by_id = {so.option.option_id: so for so in run.scored_options}
        assert by_id["CHEAP"].rank == 1
        assert by_id["MID"].rank == 2


class TestRejectionReason:
    def test_second_ranked_option_has_rejection_reason(self):
        opts = [
            _make_option(option_id="CHEAP", adult_price=Decimal("80"), adult_tax=Decimal("10")),
            _make_option(option_id="MID", adult_price=Decimal("150"), adult_tax=Decimal("10")),
        ]
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            preferences=_soft(["cost"]),
        )
        svc = ScoringService()
        run = svc.score(obj, opts, NOW)
        by_id = {so.option.option_id: so for so in run.scored_options}
        mid = by_id["MID"]
        assert mid.rejection_reason is not None
        assert mid.rejection_reason.reason_code == "outranked_cost"
        assert len(mid.rejection_reason.reason_detail) > 0


class TestArrivalMargin:
    def test_larger_arrival_margin_selected(self):
        leg_early = _make_leg(option_id="EARLY", arr_time="202609051200")
        leg_late = _make_leg(option_id="LATE_ARR", arr_time="202609051330")
        opt_early = _make_option(option_id="EARLY", legs=[leg_early])
        opt_late_arr = _make_option(option_id="LATE_ARR", legs=[leg_late])
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            latest_arrival=_hard("202609051400"),
            preferences=_soft(["arrival_margin"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_early, opt_late_arr], NOW)
        assert run.selected_option.option.option_id == "EARLY"

    def test_rationale_includes_arrival_margin_minutes(self):
        leg = _make_leg(option_id="OPT", arr_time="202609051200")
        opt = _make_option(option_id="OPT", legs=[leg])
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            latest_arrival=_hard("202609051400"),
            preferences=_soft(["arrival_margin"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        assert run.selected_option.rationale.arrival_margin_minutes == 120


class TestScarcitySignal:
    def test_low_scarcity_risk_selected_when_cost_tied(self):
        leg_a = _make_leg(option_id="A", seat_count=9, risk_sellout=False)
        leg_b = _make_leg(option_id="B", seat_count=2, risk_sellout=True)
        opt_a = _make_option(option_id="A", adult_price=Decimal("100"), adult_tax=Decimal("20"), legs=[leg_a])
        opt_b = _make_option(option_id="B", adult_price=Decimal("100"), adult_tax=Decimal("20"), legs=[leg_b])
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            preferences=_soft(["cost", "scarcity"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_a, opt_b], NOW)
        assert run.selected_option.option.option_id == "A"


class TestTieBreaking:
    def test_full_tie_reported_neither_selected(self):
        leg_a = _make_leg(option_id="A", seat_count=5, risk_sellout=False)
        leg_b = _make_leg(option_id="B", seat_count=5, risk_sellout=False)
        opt_a = _make_option(option_id="A", adult_price=Decimal("100"), adult_tax=Decimal("20"), legs=[leg_a])
        opt_b = _make_option(option_id="B", adult_price=Decimal("100"), adult_tax=Decimal("20"), legs=[leg_b])
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            preferences=_soft(["cost", "scarcity"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_a, opt_b], NOW)
        assert run.selected_option is None
        assert run.no_satisfying_option is None
        for so in run.scored_options:
            assert so.outcome == ScoringOutcome.RANKED


class TestNoPreferencesObjective:
    def test_scarcity_implicit_tiebreaker_when_no_preferences(self):
        leg_a = _make_leg(option_id="A", seat_count=9, risk_sellout=False)
        leg_b = _make_leg(option_id="B", seat_count=2, risk_sellout=True)
        opt_a = _make_option(option_id="A", adult_price=Decimal("100"), adult_tax=Decimal("20"), legs=[leg_a])
        opt_b = _make_option(option_id="B", adult_price=Decimal("100"), adult_tax=Decimal("20"), legs=[leg_b])
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_a, opt_b], NOW)
        assert run.selected_option.option.option_id == "A"


# ---------------------------------------------------------------------------
# US3 — Connection and Multi-Leg Evaluation (T043–T048)
# ---------------------------------------------------------------------------

class TestConnectionTimeCalculation:
    def test_connection_time_computed_correctly(self):
        leg0 = _make_leg(leg_id="L0", option_id="MULTI", dep_airport="ICN", arr_airport="NRT",
                         dep_time="202609051030", arr_time="202609051200")
        leg1 = _make_leg(leg_id="L1", option_id="MULTI", dep_airport="NRT", arr_airport="HND",
                         dep_time="202609051330", arr_time="202609051430")
        opt = _make_option(option_id="MULTI", legs=[leg0, leg1], is_multi_leg=True)
        obj = TravelObjective(origin=_hard("ICN"), destination=_hard("HND"), pax_count=_hard(1))
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        so = run.scored_options[0]
        assert so.connection_eval is not None
        assert so.connection_eval.connection_times == [90]
        assert so.connection_eval.connection_excluded is False


class TestConnectionExclusion:
    def test_direct_only_eliminates_multi_leg(self):
        # MULTI connects ICN→KIX→NRT (ends at NRT = destination); direct_only rule should fire
        leg0 = _make_leg(leg_id="L0", option_id="MULTI", dep_airport="ICN", arr_airport="KIX",
                         dep_time="202609051030", arr_time="202609051200")
        leg1 = _make_leg(leg_id="L1", option_id="MULTI", dep_airport="KIX", arr_airport="NRT",
                         dep_time="202609051330", arr_time="202609051430")
        opt_multi = _make_option(option_id="MULTI", legs=[leg0, leg1], is_multi_leg=True)
        opt_direct = _make_option(option_id="DIRECT", adult_price=Decimal("150"), adult_tax=Decimal("20"))
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            preferences=_soft(["direct_only"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_multi, opt_direct], NOW)
        by_id = {so.option.option_id: so for so in run.scored_options}
        assert by_id["MULTI"].elimination.reason_code == "connection_excluded"
        assert by_id["MULTI"].elimination.constraint_id is None
        assert by_id["DIRECT"].outcome == ScoringOutcome.SELECTED

    def test_exclusion_rule_recorded(self):
        leg0 = _make_leg(leg_id="L0", option_id="MULTI", dep_airport="ICN", arr_airport="NRT",
                         dep_time="202609051030", arr_time="202609051200")
        leg1 = _make_leg(leg_id="L1", option_id="MULTI", dep_airport="NRT", arr_airport="HND",
                         dep_time="202609051330", arr_time="202609051430")
        opt = _make_option(option_id="MULTI", legs=[leg0, leg1], is_multi_leg=True)
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("HND"),
            pax_count=_hard(1),
            preferences=_soft(["direct_only"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        so = run.scored_options[0]
        assert so.connection_eval.exclusion_rule == "direct_only"


class TestMinConnectionTime:
    def test_short_connection_eliminated(self):
        leg0 = _make_leg(leg_id="L0", option_id="SHORT", dep_airport="ICN", arr_airport="NRT",
                         dep_time="202609051030", arr_time="202609051200")
        leg1 = _make_leg(leg_id="L1", option_id="SHORT", dep_airport="NRT", arr_airport="HND",
                         dep_time="202609051245", arr_time="202609051345")
        opt_short = _make_option(option_id="SHORT", legs=[leg0, leg1], is_multi_leg=True)
        leg2 = _make_leg(leg_id="L0b", option_id="LONG", dep_airport="ICN", arr_airport="NRT",
                         dep_time="202609051030", arr_time="202609051200")
        leg3 = _make_leg(leg_id="L1b", option_id="LONG", dep_airport="NRT", arr_airport="HND",
                         dep_time="202609051400", arr_time="202609051500")
        opt_long = _make_option(option_id="LONG", legs=[leg2, leg3], is_multi_leg=True)
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("HND"),
            pax_count=_hard(1),
            preferences=_soft(["min_connection_60"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_short, opt_long], NOW)
        by_id = {so.option.option_id: so for so in run.scored_options}
        assert by_id["SHORT"].elimination.reason_code == "min_connection_time"
        assert by_id["LONG"].outcome == ScoringOutcome.SELECTED


class TestImpossibleConnection:
    def test_negative_connection_time_eliminated(self):
        leg0 = _make_leg(leg_id="L0", option_id="IMPOS", dep_airport="ICN", arr_airport="NRT",
                         dep_time="202609051030", arr_time="202609051400")
        leg1 = _make_leg(leg_id="L1", option_id="IMPOS", dep_airport="NRT", arr_airport="HND",
                         dep_time="202609051330", arr_time="202609051500")
        opt = _make_option(option_id="IMPOS", legs=[leg0, leg1], is_multi_leg=True)
        obj = TravelObjective(origin=_hard("ICN"), destination=_hard("HND"), pax_count=_hard(1))
        svc = ScoringService()
        run = svc.score(obj, [opt], NOW)
        so = run.scored_options[0]
        assert so.elimination.reason_code == "impossible_connection"
        assert so.connection_eval.impossible_connections == [0]


class TestDirectVsConnectionRanking:
    def test_direct_ranks_above_multi_leg_without_exclusion(self):
        # MULTI connects ICN→KIX→NRT (cheaper); no direct_only rule; MULTI should win on cost
        leg0 = _make_leg(leg_id="L0", option_id="MULTI", dep_airport="ICN", arr_airport="KIX",
                         dep_time="202609051030", arr_time="202609051200")
        leg1 = _make_leg(leg_id="L1", option_id="MULTI", dep_airport="KIX", arr_airport="NRT",
                         dep_time="202609051330", arr_time="202609051430")
        opt_multi = _make_option(option_id="MULTI", adult_price=Decimal("80"), adult_tax=Decimal("10"),
                                 legs=[leg0, leg1], is_multi_leg=True)
        opt_direct = _make_option(option_id="DIRECT", adult_price=Decimal("100"), adult_tax=Decimal("10"))
        obj = TravelObjective(
            origin=_hard("ICN"),
            destination=_hard("NRT"),
            pax_count=_hard(1),
            preferences=_soft(["cost"]),
        )
        svc = ScoringService()
        run = svc.score(obj, [opt_multi, opt_direct], NOW)
        assert run.selected_option.option.option_id == "MULTI"
