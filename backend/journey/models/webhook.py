from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class InboundNotification:
    notification_id: str
    received_at: datetime
    declared_event_type: str
    order_reference: str | None
    raw_payload_json: str
    journey_id: str | None
    associated: bool
    confirmation_triggered: bool
    simulated: bool = False
