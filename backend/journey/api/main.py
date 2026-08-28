from fastapi import FastAPI

from journey.api.routers.events import router as events_router

app = FastAPI(title="Antabay Journey API", version="0.1.0")

app.include_router(events_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
