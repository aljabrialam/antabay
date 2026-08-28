from __future__ import annotations

import json
import os
from datetime import datetime

from sqlalchemy.exc import NoResultFound

from journey.errors import InjectorDisabledError, JourneyHasNoOrderError, JourneyNotFoundError
from journey.models.webhook import InboundNotification
from journey.services.webhook_service import WebhookService
from journey.storage.repository import JourneyRepository

_SCHEDULE_CHANGED_TYPE = "schedule.changed"

_ENABLED_ENV_VAR = "DISRUPTION_INJECTOR_ENABLED"


class DisruptionInjectorService:
    def __init__(
        self,
        repository: JourneyRepository | None = None,
        webhook_service: WebhookService | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._repo = repository if repository is not None else JourneyRepository()
        self._webhook_service = (
            webhook_service if webhook_service is not None else WebhookService(repository=self._repo)
        )
        self._enabled = (
            enabled
            if enabled is not None
            else os.environ.get(_ENABLED_ENV_VAR, "").lower() == "true"
        )

    def inject(
        self, journey_id: str, revised_arrival_time: datetime, now: datetime
    ) -> InboundNotification:
        if not self._enabled:
            raise InjectorDisabledError()

        try:
            self._repo.get_journey(journey_id)
        except NoResultFound as exc:
            raise JourneyNotFoundError(journey_id) from exc

        order_no = self._repo.get_order_no_for_journey(journey_id)
        if order_no is None:
            raise JourneyHasNoOrderError(journey_id)

        envelope = {
            "cid": "<client id>",
            "type": _SCHEDULE_CHANGED_TYPE,
            "status": 0,
            "data": {
                "orderNo": order_no,
                "revisedArrivalTime": revised_arrival_time.isoformat(),
            },
        }
        raw_body = json.dumps(envelope).encode("utf-8")

        notification = self._webhook_service.receive(raw_body, now, simulated=True)
        if notification.confirmation_triggered:
            self._webhook_service.confirm(notification)
        return notification
