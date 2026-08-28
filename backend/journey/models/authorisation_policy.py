from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Literal


class Rule(str, Enum):
    AUTH_MONEY = "AUTH-MONEY"
    AUTH_CANCEL = "AUTH-CANCEL"
    AUTH_IRREVERSIBLE = "AUTH-IRREVERSIBLE"
    AUTH_CONSTRAINT = "AUTH-CONSTRAINT"


RULE_DESCRIPTIONS: dict[Rule, str] = {
    Rule.AUTH_MONEY: "The action spends the traveller's money.",
    Rule.AUTH_CANCEL: "The action cancels or voids a booking.",
    Rule.AUTH_IRREVERSIBLE: "The action cannot be reversed.",
    Rule.AUTH_CONSTRAINT: "The action would breach a hard constraint the traveller has stated.",
}


@dataclass
class ProposedAction:
    action_id: str
    description: str
    cost_amount: Decimal
    cost_description: str
    objective_effect: str
    cancels_or_voids_booking: bool
    is_reversible: bool
    breaches_hard_constraint: bool


@dataclass
class AuthorisationDecision:
    action_id: str
    classification: Literal["permitted_autonomously", "requires_authorisation"]
    matched_rules: list[str]
