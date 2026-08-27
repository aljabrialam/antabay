from __future__ import annotations

import json
import unicodedata
from decimal import Decimal
from typing import Any, cast

from dashscope import Generation

from journey.models.objective import (
    ConstrainedField,
    ConstraintType,
    ParseResult,
    TravelObjective,
)

_MODEL = "qwen-plus-2025-04-28"
_OBJECTIVE_FIELDS = [
    "origin",
    "destination",
    "latest_arrival",
    "departure_date",
    "budget_amount",
    "budget_currency",
    "pax_count",
    "preferences",
]


def _normalise(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _build_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "submit_objective",
            "description": (
                "Extract the travel objective from the user's stated goal. "
                "Only populate fields explicitly present in the goal. "
                "Leave absent fields out entirely. "
                "Mark fields whose constraint type is unclear in _ambiguous_fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "destination": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "latest_arrival": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "departure_date": {
                        "type": "object",
                        "description": "Departure date in YYYYMMDD format (e.g. 20260905).",
                        "properties": {
                            "value": {"type": "string"},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "budget_amount": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "budget_currency": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "pax_count": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "integer"},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "preferences": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "array", "items": {"type": "string"}},
                            "constraint_type": {"type": "string", "enum": ["HARD", "SOFT"]},
                        },
                        "required": ["value", "constraint_type"],
                    },
                    "_ambiguous_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Field names whose constraint type is genuinely unclear.",
                    },
                },
                "required": [],
            },
        },
    }


class ObjectiveParser:
    def parse(self, raw_goal: str) -> ParseResult:
        normalised = _normalise(raw_goal)
        messages: Any = [{"role": "user", "content": normalised}]
        response: Any = Generation.call(
            model=_MODEL,
            messages=messages,
            tools=[_build_tool_schema()],
            tool_choice={"type": "function", "function": {"name": "submit_objective"}},
            temperature=0,
        )
        raw: dict[str, Any] = {}
        if response.output.choices:
            tool_calls = response.output.choices[0].message.tool_calls
            if tool_calls:
                raw = json.loads(tool_calls[0].function.arguments)

        field_data: dict[str, Any] = {k: v for k, v in raw.items() if k != "_ambiguous_fields"}
        ambiguous: list[str] = raw.get("_ambiguous_fields", [])

        kwargs: dict[str, Any] = {}
        for fname in _OBJECTIVE_FIELDS:
            if fname in field_data:
                fval = field_data[fname]
                val = fval["value"]
                ct = ConstraintType(fval["constraint_type"])
                if fname == "budget_amount":
                    val = Decimal(str(val))
                kwargs[fname] = ConstrainedField(value=val, constraint_type=ct)

        objective = TravelObjective(**kwargs)
        absent = [f for f in _OBJECTIVE_FIELDS if f not in field_data]
        return ParseResult(objective=objective, absent_fields=absent, ambiguous_fields=ambiguous)
