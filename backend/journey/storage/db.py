import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.environ.get("JOURNEY_DB_URL", "sqlite:///journey.db")
        _engine = create_engine(url, future=True)
    return _engine


def reset_engine(url: str | None = None) -> None:
    """Replace the module-level engine. Used in tests to point at an in-memory DB."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    resolved = url if url is not None else os.environ.get("JOURNEY_DB_URL", "sqlite:///journey.db")
    _engine = create_engine(resolved, future=True)


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    with get_engine().connect() as conn:
        yield conn
