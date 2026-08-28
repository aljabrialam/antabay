"""Contract tests for POST /webhooks/atlas (T010-T011).

TDD gate: these tests must fail (ImportError against the not-yet-existing
router module, then NotImplementedError once the skeleton exists) before
implementation.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from starlette.requests import Request


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'webhook_contract.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


async def _fake_request(body: bytes) -> Request:
    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "POST", "headers": []}
    return Request(scope, receive)


class _StubNotification:
    def __init__(self, confirmation_triggered: bool) -> None:
        self.confirmation_triggered = confirmation_triggered


class _StubWebhookService:
    """Reports a notification requiring confirmation, whose confirm() always fails
    — proving the handler never calls it inline, only schedules it."""

    def receive(self, raw_body: bytes, received_at: datetime) -> _StubNotification:
        return _StubNotification(confirmation_triggered=True)

    def confirm(self, notification: _StubNotification) -> None:
        raise RuntimeError("confirm() must never be called before the response is returned")


class TestEndpointAcknowledgesBeforeConfirmationRuns:
    @pytest.mark.asyncio
    async def test_confirm_is_scheduled_not_awaited_inline(self) -> None:
        from journey.api.routers.webhooks import receive_atlas_webhook

        service = _StubWebhookService()
        background_tasks = BackgroundTasks()
        request = await _fake_request(
            b'{"cid": "x", "type": "order.ticketed", "status": -1, "data": {"orderNo": "X"}}'
        )

        result = await receive_atlas_webhook(request, background_tasks, service)

        assert result == {"status": "received"}
        assert len(background_tasks.tasks) == 1
        assert background_tasks.tasks[0].func == service.confirm


class TestEndpointAcknowledgesMalformedBody:
    def test_200_for_invalid_json(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        from journey.api.main import app

        client = TestClient(app)
        response = client.post("/webhooks/atlas", content=b"not valid json{{{")

        assert response.status_code == 200

    def test_200_and_persisted_for_json_missing_all_fields(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        from journey.api.main import app
        from journey.storage.repository import JourneyRepository

        client = TestClient(app)
        response = client.post("/webhooks/atlas", content=b"{}")

        assert response.status_code == 200
        repo = JourneyRepository()
        # No order_reference to query by; confirm persistence via a direct
        # table scan through the repository's underlying connection.
        from sqlalchemy import select

        from journey.storage.db import get_connection
        from journey.storage.tables import webhook_notifications

        with get_connection() as conn:
            rows = conn.execute(select(webhook_notifications)).mappings().all()
        assert len(rows) == 1
        assert rows[0]["raw_payload_json"] == "{}"
