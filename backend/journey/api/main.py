import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from journey.api.routers.disruption_injector import router as disruption_injector_router
from journey.api.routers.events import router as events_router
from journey.api.routers.webhooks import router as webhooks_router
from journey.services.webhook_service import WebhookService
from journey.storage.db import get_engine
from journey.storage.tables import metadata

# FR-010: independent of the confirmation budget window in webhook_service.py
# (data-model.md's Confirmation Budget Window entity — the two are distinct,
# separately tunable parameters).
_RECONCILIATION_INTERVAL_SECONDS = 300


async def _reconciliation_loop() -> None:
    service = WebhookService()
    while True:
        await asyncio.sleep(_RECONCILIATION_INTERVAL_SECONDS)
        await asyncio.to_thread(service.reconcile_active_journeys, datetime.now(tz=timezone.utc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    metadata.create_all(get_engine())
    task = asyncio.create_task(_reconciliation_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Antabay Journey API", version="0.1.0", lifespan=lifespan)

app.include_router(events_router)
app.include_router(webhooks_router)
app.include_router(disruption_injector_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
