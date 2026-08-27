"""Failing unit tests for JourneyStateMachine (T031)."""
from __future__ import annotations

import pytest

from journey.models.journey import JourneyState, JourneyStateMachine, InvalidTransitionError


class TestJourneyStateMachinePermittedTransitions:
    def test_objective_confirmed_to_searching_permitted(self) -> None:
        sm = JourneyStateMachine()
        sm.transition(JourneyState.OBJECTIVE_CONFIRMED, JourneyState.SEARCHING)

    def test_objective_confirmed_to_cancelled_permitted(self) -> None:
        sm = JourneyStateMachine()
        sm.transition(JourneyState.OBJECTIVE_CONFIRMED, JourneyState.CANCELLED)

    def test_objective_confirmed_to_abandoned_permitted(self) -> None:
        sm = JourneyStateMachine()
        sm.transition(JourneyState.OBJECTIVE_CONFIRMED, JourneyState.ABANDONED)


class TestJourneyStateMachineForbiddenTransitions:
    def test_objective_confirmed_to_objective_confirmed_raises(self) -> None:
        sm = JourneyStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(JourneyState.OBJECTIVE_CONFIRMED, JourneyState.OBJECTIVE_CONFIRMED)

    def test_cancelled_to_searching_raises(self) -> None:
        sm = JourneyStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(JourneyState.CANCELLED, JourneyState.SEARCHING)

    def test_abandoned_to_objective_confirmed_raises(self) -> None:
        sm = JourneyStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(JourneyState.ABANDONED, JourneyState.OBJECTIVE_CONFIRMED)

    def test_searching_to_objective_confirmed_raises(self) -> None:
        sm = JourneyStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(JourneyState.SEARCHING, JourneyState.OBJECTIVE_CONFIRMED)


class TestJourneyStateMachineErrorDetails:
    def test_invalid_transition_error_contains_states(self) -> None:
        sm = JourneyStateMachine()
        with pytest.raises(InvalidTransitionError) as exc_info:
            sm.transition(JourneyState.CANCELLED, JourneyState.SEARCHING)
        msg = str(exc_info.value)
        assert "CANCELLED" in msg
        assert "SEARCHING" in msg

    def test_invalid_transition_leaves_no_side_effects(self) -> None:
        sm = JourneyStateMachine()
        with pytest.raises(InvalidTransitionError):
            sm.transition(JourneyState.CANCELLED, JourneyState.SEARCHING)
        # After a failed transition the machine remains usable
        sm.transition(JourneyState.OBJECTIVE_CONFIRMED, JourneyState.CANCELLED)
