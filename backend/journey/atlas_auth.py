"""Shared construction of an authenticated Atlas httpx.Client.

`.antabay/atlas-capability-map.md` documents the real auth mechanism as
the `x-atlas-client-id`/`x-atlas-client-secret` request headers (§ Auth) —
distinct from the `cid` field already present in request bodies
throughout this codebase, which the map separately notes is "an extra
field observed in working request body," not the authentication itself.
No caller ever set these headers before now; every existing test mocks
the HTTP layer directly, so the gap was invisible until a real sandbox
call was made.
"""
from __future__ import annotations

import os

import httpx

_CLIENT_ID_ENV_VAR = "ATLAS_CLIENT_ID"
_CLIENT_SECRET_ENV_VAR = "ATLAS_CLIENT_SECRET"


def atlas_http_client() -> httpx.Client:
    """An httpx.Client carrying the real Atlas auth headers, read from the
    environment. Missing credentials produce an empty header value rather
    than raising — the sandbox itself rejects the request in that case,
    the same fail-visible (not fail-silent) behaviour every other Atlas
    call in this codebase already relies on for a rejected/errored call."""
    return httpx.Client(
        headers={
            "x-atlas-client-id": os.environ.get(_CLIENT_ID_ENV_VAR, ""),
            "x-atlas-client-secret": os.environ.get(_CLIENT_SECRET_ENV_VAR, ""),
        }
    )
