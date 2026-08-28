from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from journey.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_webhook_service() -> WebhookService:
    return WebhookService()


@router.post("/atlas")
async def receive_atlas_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    service: WebhookService = Depends(get_webhook_service),
) -> dict[str, str]:
    """Accept an Atlas notification (FR-001). Acknowledgement never waits
    on confirmation — confirm() is scheduled to run after this response
    is sent (NFR-001)."""
    raw_body = await request.body()
    notification = service.receive(raw_body, datetime.now(tz=timezone.utc))
    if notification.confirmation_triggered:
        background_tasks.add_task(service.confirm, notification)
    return {"status": "received"}
