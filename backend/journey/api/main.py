from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from journey.api.routers.events import router as events_router
from journey.storage.db import get_engine
from journey.storage.tables import metadata


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    metadata.create_all(get_engine())
    yield


app = FastAPI(title="Antabay Journey API", version="0.1.0", lifespan=lifespan)

app.include_router(events_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
