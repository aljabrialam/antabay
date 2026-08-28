"""ScoringService — deterministic, stateless flight option scorer (003-option-scoring).

Evaluation pipeline (per option, in this order):
  1. Expiry check
  2. Currency pre-check
  3. Hard constraint checks
  4. Connection evaluation + exclusion checks
  5. Preference ranking of survivors
  6. Selection / tie reporting
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from journey.models.flight import FlightOption, Leg
from journey.models.objective import ConstraintType, TravelObjective
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

_TIME_FMT = "%Y%m%d%H%M"
_DATE_FMT = "%Y%m%d"


def _parse_time(s: str) -> datetime:
    return datetime.strptime(s, _TIME_FMT)


def _total_cost(opt: FlightOption) -> Decimal:
    return opt.adult_price + opt.adult_tax


def _evaluate_connections(opt: FlightOption, objective: TravelObjective) -> ConnectionEvaluation:
    """Compute per-gap connection times and check exclusion rules."""
    legs = opt.legs
    times: list[int] = []
    impossible: list[int] = []

    for i in range(len(legs) - 1):
        arr = _parse_time(legs[i].arr_time)
        dep = _parse_time(legs[i + 1].dep_time)
        minutes = int((dep - arr).total_seconds() // 60)
        times.append(minutes)
        if minutes <= 0:
            impossible.append(i)

    prefs: list[str] = []
    if objective.preferences and objective.preferences.constraint_type == ConstraintType.SOFT:
        prefs = objective.preferences.value

    excluded = False
    exclusion_rule: str | None = None

    if "direct_only" in prefs and len(legs) > 1:
        excluded = True
        exclusion_rule = "direct_only"

    return ConnectionEvaluation(
        option_id=opt.option_id,
        connection_times=times,
        connection_excluded=excluded,
        exclusion_rule=exclusion_rule,
        impossible_connections=impossible,
    )


def _min_connection_minutes(prefs: list[str]) -> int | None:
    """Extract minimum connection time in minutes from a preference like 'min_connection_60'."""
    for p in prefs:
        if p.startswith("min_connection_"):
            try:
                return int(p[len("min_connection_"):])
            except ValueError:
                pass
    return None


def _scarcity_score(opt: FlightOption) -> tuple[int, int]:
    """Return (no_risk, seat_count) — higher is better; used for scarcity tiebreaking."""
    if not opt.legs:
        return (1, 0)
    # Use worst leg for scarcity
    worst_seat = min(leg.seat_count for leg in opt.legs)
    any_risk = any(leg.risk_sellout for leg in opt.legs)
    return (0 if any_risk else 1, worst_seat)


def _build_rationale(
    opt: FlightOption,
    objective: TravelObjective,
    objective_elements: list[str],
) -> Rationale:
    cost = _total_cost(opt)
    arrival_margin: int | None = None
    if objective.latest_arrival:
        last_arr = _parse_time(opt.legs[-1].arr_time)
        deadline = _parse_time(objective.latest_arrival.value)
        arrival_margin = int((deadline - last_arr).total_seconds() // 60)

    parts: list[str] = []
    if "budget_amount" in objective_elements:
        parts.append(f"total cost {cost} is within budget")
    if arrival_margin is not None:
        parts.append(f"arrives {arrival_margin} minutes before deadline")
    if not parts:
        parts.append("satisfies all stated constraints")

    return Rationale(
        option_id=opt.option_id,
        objective_elements=objective_elements,
        summary="; ".join(parts) + ".",
        arrival_margin_minutes=arrival_margin,
        total_cost=cost,
    )


class ScoringService:
    def score(
        self,
        objective: TravelObjective,
        options: list[FlightOption],
        now: datetime,
    ) -> ScoringRun:
        # Empty set — no scoring, no report
        if not options:
            return ScoringRun(
                run_id=str(uuid.uuid4()),
                objective=objective,
                evaluated_at=now,
                scored_options=[],
                selected_option=None,
                no_satisfying_option=None,
            )

        # NFR-001: sort by option_id for order-independence
        sorted_options = sorted(options, key=lambda o: o.option_id)

        prefs: list[str] = []
        if objective.preferences is not None:
            prefs = objective.preferences.value

        budget_currency: str | None = (
            objective.budget_currency.value if objective.budget_currency else None
        )

        scored: list[ScoredOption] = []
        survivors: list[tuple[FlightOption, ConnectionEvaluation | None]] = []
        unsatisfied_constraints: set[str] = set()

        for opt in sorted_options:
            elim: EliminationRecord | None = None
            conn_eval: ConnectionEvaluation | None = None

            # --- Step 1: Expiry check ---
            if opt.expire_at is None:
                elim = EliminationRecord(
                    option_id=opt.option_id,
                    reason_code="expiry_unknown",
                    reason_detail="Offer expiry could not be determined; treated as expired.",
                    constraint_id=None,
                )
            elif opt.expire_at <= now:
                elim = EliminationRecord(
                    option_id=opt.option_id,
                    reason_code="offer_expired",
                    reason_detail=f"Offer expired at {opt.expire_at.isoformat()}.",
                    constraint_id=None,
                )

            # --- Step 2: Currency pre-check ---
            if elim is None and budget_currency is not None:
                if opt.currency != budget_currency:
                    elim = EliminationRecord(
                        option_id=opt.option_id,
                        reason_code="currency_mismatch",
                        reason_detail=(
                            f"Option currency {opt.currency!r} differs from "
                            f"objective currency {budget_currency!r}; not comparable."
                        ),
                        constraint_id=None,
                    )

            # --- Step 3: Hard constraint checks ---
            if elim is None:
                cost = _total_cost(opt)

                if objective.budget_amount and objective.budget_amount.constraint_type == ConstraintType.HARD:
                    if cost > objective.budget_amount.value:
                        elim = EliminationRecord(
                            option_id=opt.option_id,
                            reason_code="budget_exceeded",
                            reason_detail=f"Total cost {cost} exceeds budget {objective.budget_amount.value}.",
                            constraint_id="budget_amount",
                        )
                        unsatisfied_constraints.add("budget_amount")

            if elim is None and objective.departure_date and objective.departure_date.constraint_type == ConstraintType.HARD:
                first_dep_date = opt.legs[0].dep_time[:8]
                if first_dep_date != objective.departure_date.value:
                    elim = EliminationRecord(
                        option_id=opt.option_id,
                        reason_code="wrong_departure_date",
                        reason_detail=f"Departs on {first_dep_date}, expected {objective.departure_date.value}.",
                        constraint_id="departure_date",
                    )
                    unsatisfied_constraints.add("departure_date")

            if elim is None and objective.origin and objective.origin.constraint_type == ConstraintType.HARD:
                if opt.legs[0].dep_airport != objective.origin.value:
                    elim = EliminationRecord(
                        option_id=opt.option_id,
                        reason_code="wrong_origin",
                        reason_detail=f"Departs from {opt.legs[0].dep_airport}, expected {objective.origin.value}.",
                        constraint_id="origin",
                    )
                    unsatisfied_constraints.add("origin")

            if elim is None and objective.destination and objective.destination.constraint_type == ConstraintType.HARD:
                if opt.legs[-1].arr_airport != objective.destination.value:
                    elim = EliminationRecord(
                        option_id=opt.option_id,
                        reason_code="wrong_destination",
                        reason_detail=f"Arrives at {opt.legs[-1].arr_airport}, expected {objective.destination.value}.",
                        constraint_id="destination",
                    )
                    unsatisfied_constraints.add("destination")

            if elim is None and objective.latest_arrival and objective.latest_arrival.constraint_type == ConstraintType.HARD:
                last_arr = _parse_time(opt.legs[-1].arr_time)
                deadline = _parse_time(objective.latest_arrival.value)
                if last_arr > deadline:
                    elim = EliminationRecord(
                        option_id=opt.option_id,
                        reason_code="arrival_too_late",
                        reason_detail=f"Arrives at {opt.legs[-1].arr_time}, deadline {objective.latest_arrival.value}.",
                        constraint_id="latest_arrival",
                    )
                    unsatisfied_constraints.add("latest_arrival")

            # --- Step 4: Connection evaluation + exclusion ---
            if elim is None and len(opt.legs) > 1:
                conn_eval = _evaluate_connections(opt, objective)

                # Impossible connection
                if conn_eval.impossible_connections:
                    elim = EliminationRecord(
                        option_id=opt.option_id,
                        reason_code="impossible_connection",
                        reason_detail=(
                            f"Non-positive connection time at gap(s) "
                            f"{conn_eval.impossible_connections}."
                        ),
                        constraint_id=None,
                    )

                # Exclusion rules (direct_only)
                if elim is None and conn_eval.connection_excluded:
                    elim = EliminationRecord(
                        option_id=opt.option_id,
                        reason_code="connection_excluded",
                        reason_detail=f"Excluded by rule: {conn_eval.exclusion_rule}.",
                        constraint_id=None,
                    )

                # min_connection_N
                if elim is None:
                    min_conn = _min_connection_minutes(prefs)
                    if min_conn is not None:
                        short = [t for t in conn_eval.connection_times if t < min_conn]
                        if short:
                            elim = EliminationRecord(
                                option_id=opt.option_id,
                                reason_code="min_connection_time",
                                reason_detail=(
                                    f"Connection time {short} below minimum {min_conn} min."
                                ),
                                constraint_id=None,
                            )

            if elim is not None:
                scored.append(ScoredOption(
                    option=opt,
                    outcome=ScoringOutcome.ELIMINATED,
                    rank=None,
                    rationale=None,
                    elimination=elim,
                    rejection_reason=None,
                    connection_eval=conn_eval,
                ))
            else:
                survivors.append((opt, conn_eval))

        # --- All eliminated ---
        if not survivors:
            all_elim_constraints = [
                sc.elimination.constraint_id or sc.elimination.reason_code
                for sc in scored
                if sc.elimination
            ]
            unique_constraints = sorted(set(all_elim_constraints))
            no_sat = NoSatisfyingOptionReport(
                unsatisfied_constraints=unique_constraints,
                eliminated_count=len(scored),
                summary=f"No option satisfied: {', '.join(unique_constraints)}.",
            ) if scored else None

            return ScoringRun(
                run_id=str(uuid.uuid4()),
                objective=objective,
                evaluated_at=now,
                scored_options=scored,
                selected_option=None,
                no_satisfying_option=no_sat,
            )

        # --- Step 5: Preference ranking of survivors ---
        # Build preference dimensions as sort keys (lower index = higher priority)
        # Each key function returns a value where "better" means sorting first (ascending).

        active_prefs = [p for p in prefs if not p.startswith("min_connection_") and p != "direct_only"]

        def _pref_sort_key(item: tuple[FlightOption, ConnectionEvaluation | None]) -> list[Any]:
            opt, _ = item
            keys: list[Any] = []
            for pref in active_prefs:
                if pref == "cost":
                    keys.append(_total_cost(opt))
                elif pref == "arrival_margin":
                    # Higher margin is better → negate for ascending sort
                    if objective.latest_arrival:
                        last_arr = _parse_time(opt.legs[-1].arr_time)
                        deadline = _parse_time(objective.latest_arrival.value)
                        margin = int((deadline - last_arr).total_seconds() // 60)
                        keys.append(-margin)
                    else:
                        keys.append(0)
                elif pref == "scarcity":
                    no_risk, seats = _scarcity_score(opt)
                    # Higher no_risk and more seats = better → negate both
                    keys.append((-no_risk, -seats))
            return keys

        # Implicit scarcity tiebreaker when "scarcity" not already in prefs
        use_implicit_scarcity = "scarcity" not in active_prefs

        def _full_sort_key(item: tuple[FlightOption, ConnectionEvaluation | None]) -> list[Any]:
            opt, _ = item
            base = _pref_sort_key(item)
            if use_implicit_scarcity:
                no_risk, seats = _scarcity_score(opt)
                base = base + [(-no_risk, -seats)]
            return base

        survivors_sorted = sorted(survivors, key=_full_sort_key)

        # --- Step 6: Detect ties and assign ranks ---
        # Two items tie if their full sort key is equal
        best_key = _full_sort_key(survivors_sorted[0])
        tied_at_top = [s for s in survivors_sorted if _full_sort_key(s) == best_key]
        is_full_tie = len(tied_at_top) == len(survivors_sorted) and len(tied_at_top) > 1

        # Assign ranks — options with equal key share a rank
        rank_counter = 1
        prev_key = None
        ranked_survivors: list[tuple[FlightOption, ConnectionEvaluation | None, int]] = []
        for item in survivors_sorted:
            k = _full_sort_key(item)
            if prev_key is not None and k != prev_key:
                rank_counter += 1
            ranked_survivors.append((item[0], item[1], rank_counter))
            prev_key = k

        # Determine objective elements satisfied (for rationale)
        def _objective_elements(opt: FlightOption) -> list[str]:
            elems: list[str] = []
            if objective.budget_amount:
                elems.append("budget_amount")
            if objective.origin:
                elems.append("origin")
            if objective.destination:
                elems.append("destination")
            if objective.departure_date:
                elems.append("departure_date")
            if objective.latest_arrival:
                elems.append("latest_arrival")
            return elems

        # Build ScoredOptions for survivors
        selected: ScoredOption | None = None
        survivor_scored: list[ScoredOption] = []

        for opt, conn_eval, rank in ranked_survivors:
            is_selected = (rank == 1 and not is_full_tie)
            if is_selected:
                outcome = ScoringOutcome.SELECTED
                rationale = _build_rationale(opt, objective, _objective_elements(opt))
                rejection = None
            else:
                outcome = ScoringOutcome.RANKED
                rationale = None
                if rank > 1 or is_full_tie:
                    # Determine rejection reason based on top preference dimension
                    reason_code = "outranked"
                    reason_detail = "A better option was selected."
                    if active_prefs:
                        top_pref = active_prefs[0]
                        if top_pref == "cost":
                            reason_code = "outranked_cost"
                            best_cost = _total_cost(ranked_survivors[0][0])
                            reason_detail = (
                                f"A cheaper option exists (cost {best_cost} < {_total_cost(opt)})."
                            )
                        elif top_pref == "arrival_margin":
                            reason_code = "outranked_arrival_margin"
                            reason_detail = "An option with a larger arrival margin exists."
                        elif top_pref == "scarcity":
                            reason_code = "outranked_scarcity"
                            reason_detail = "An option with better availability exists."
                    elif use_implicit_scarcity:
                        reason_code = "outranked_scarcity"
                        reason_detail = "An option with better availability exists."
                    rejection = RejectionReason(
                        option_id=opt.option_id,
                        reason_code=reason_code,
                        reason_detail=reason_detail,
                    )
                else:
                    rejection = None

            so = ScoredOption(
                option=opt,
                outcome=outcome,
                rank=rank,
                rationale=rationale,
                elimination=None,
                rejection_reason=rejection,
                connection_eval=conn_eval,
            )
            survivor_scored.append(so)
            if is_selected:
                selected = so

        all_scored = scored + survivor_scored

        # If full tie, no option is selected; no_satisfying_option is None (tie ≠ no-options)
        return ScoringRun(
            run_id=str(uuid.uuid4()),
            objective=objective,
            evaluated_at=now,
            scored_options=all_scored,
            selected_option=selected,
            no_satisfying_option=None,
        )
