"""Unit tests for AuthorisationPolicyEngine.evaluate() (T005-T009, T012-T016).

TDD gate (T009, T016): these tests must fail with NotImplementedError
against the Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from typing import Any


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


def _engine() -> Any:
    from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine

    return AuthorisationPolicyEngine()


class TestEvaluateClassifiesBeforeAnyExecutionSignal:
    def test_no_rule_triggered_is_permitted_autonomously(self) -> None:
        action = _permitted_action()
        decision = _engine().evaluate(action)

        assert decision.classification == "permitted_autonomously"
        assert decision.matched_rules == []


class TestEvaluateIsDeterministic:
    def test_same_action_evaluated_repeatedly_is_identical(self) -> None:
        from journey.models.authorisation_policy import ProposedAction

        action = ProposedAction(
            action_id="a1",
            description="Book SIN-LHR flight",
            cost_amount=Decimal("1200"),
            cost_description="+GBP 1200.00",
            objective_effect="Fulfils itinerary",
            cancels_or_voids_booking=False,
            is_reversible=False,
            breaches_hard_constraint=False,
        )
        engine = _engine()

        results = [engine.evaluate(action) for _ in range(100)]

        assert all(r.classification == results[0].classification for r in results)
        assert all(r.matched_rules == results[0].matched_rules for r in results)


class TestNoLanguageModelConsulted:
    def test_engine_module_imports_no_llm_client(self) -> None:
        import journey.services.authorisation_policy_engine as module

        source = inspect.getsource(module)
        tree = ast.parse(source)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module)

        forbidden_substrings = ("dashscope", "openai", "anthropic", "llm")
        for name in imported_names:
            lowered = name.lower()
            assert not any(
                forbidden in lowered for forbidden in forbidden_substrings
            ), f"unexpected LLM-related import: {name}"


class TestMultipleRulesAllNamedNotJustFirst:
    def test_two_triggered_rules_are_both_reported(self) -> None:
        from journey.models.authorisation_policy import ProposedAction

        action = ProposedAction(
            action_id="a1",
            description="Book over-budget option",
            cost_amount=Decimal("500"),
            cost_description="+USD 500.00",
            objective_effect="Exceeds stated budget",
            cancels_or_voids_booking=False,
            is_reversible=True,
            breaches_hard_constraint=True,
        )
        decision = _engine().evaluate(action)

        assert decision.classification == "requires_authorisation"
        assert set(decision.matched_rules) == {"AUTH-MONEY", "AUTH-CONSTRAINT"}


class TestAuthMoneyRuleBothDirections:
    def test_positive_cost_triggers(self) -> None:
        from journey.models.authorisation_policy import ProposedAction

        action = ProposedAction(
            action_id="a1",
            description="Pay for seat",
            cost_amount=Decimal("50"),
            cost_description="+USD 50.00",
            objective_effect="None",
            cancels_or_voids_booking=False,
            is_reversible=True,
            breaches_hard_constraint=False,
        )
        decision = _engine().evaluate(action)

        assert decision.classification == "requires_authorisation"
        assert decision.matched_rules == ["AUTH-MONEY"]

    def test_zero_cost_does_not_trigger(self) -> None:
        decision = _engine().evaluate(_permitted_action())

        assert "AUTH-MONEY" not in decision.matched_rules


class TestAuthCancelRuleBothDirections:
    def test_cancellation_triggers(self) -> None:
        from journey.models.authorisation_policy import ProposedAction

        action = ProposedAction(
            action_id="a1",
            description="Cancel hotel booking",
            cost_amount=Decimal("0"),
            cost_description="+USD 0.00",
            objective_effect="Removes accommodation",
            cancels_or_voids_booking=True,
            is_reversible=True,
            breaches_hard_constraint=False,
        )
        decision = _engine().evaluate(action)

        assert decision.classification == "requires_authorisation"
        assert decision.matched_rules == ["AUTH-CANCEL"]

    def test_non_cancellation_does_not_trigger(self) -> None:
        decision = _engine().evaluate(_permitted_action())

        assert "AUTH-CANCEL" not in decision.matched_rules


class TestAuthIrreversibleRuleBothDirections:
    def test_irreversible_triggers(self) -> None:
        from journey.models.authorisation_policy import ProposedAction

        action = ProposedAction(
            action_id="a1",
            description="Issue non-refundable ticket",
            cost_amount=Decimal("0"),
            cost_description="+USD 0.00",
            objective_effect="Commits itinerary",
            cancels_or_voids_booking=False,
            is_reversible=False,
            breaches_hard_constraint=False,
        )
        decision = _engine().evaluate(action)

        assert decision.classification == "requires_authorisation"
        assert decision.matched_rules == ["AUTH-IRREVERSIBLE"]

    def test_reversible_does_not_trigger(self) -> None:
        decision = _engine().evaluate(_permitted_action())

        assert "AUTH-IRREVERSIBLE" not in decision.matched_rules


class TestRuleDescriptionsAreReadable:
    def test_every_rule_has_a_non_empty_description(self) -> None:
        from journey.models.authorisation_policy import RULE_DESCRIPTIONS, Rule

        for rule in Rule:
            assert rule in RULE_DESCRIPTIONS
            description = RULE_DESCRIPTIONS[rule]
            assert isinstance(description, str)
            assert len(description) > 10
            assert description[0].isupper()


class TestNoPublicMethodAcceptsAnOutcomeAssertion:
    def test_evaluate_and_request_if_required_take_no_trust_me_parameter(self) -> None:
        from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine

        evaluate_params = set(
            inspect.signature(AuthorisationPolicyEngine.evaluate).parameters
        ) - {"self"}
        request_params = set(
            inspect.signature(AuthorisationPolicyEngine.request_if_required).parameters
        ) - {"self"}

        assert evaluate_params == {"action"}
        assert request_params == {"journey_id", "action"}


class TestAuthConstraintRuleBothDirections:
    def test_constraint_breach_triggers(self) -> None:
        from journey.models.authorisation_policy import ProposedAction

        action = ProposedAction(
            action_id="a1",
            description="Book flight outside stated origin",
            cost_amount=Decimal("0"),
            cost_description="+USD 0.00",
            objective_effect="Breaches origin constraint",
            cancels_or_voids_booking=False,
            is_reversible=True,
            breaches_hard_constraint=True,
        )
        decision = _engine().evaluate(action)

        assert decision.classification == "requires_authorisation"
        assert decision.matched_rules == ["AUTH-CONSTRAINT"]

    def test_no_breach_does_not_trigger(self) -> None:
        decision = _engine().evaluate(_permitted_action())

        assert "AUTH-CONSTRAINT" not in decision.matched_rules
