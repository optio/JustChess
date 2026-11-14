"""Origin check and request body limit (BR4.3), as plain ASGI middleware.

``OriginGuardMiddleware`` refuses state-changing HTTP requests (anything but
GET, HEAD and OPTIONS) and every WebSocket handshake whose ``Origin`` header is
present and differs from the app's own origin. The expected origin is
``JUSTCHESS_ORIGIN`` when set; otherwise the request's ``Host`` with the
``X-Forwarded-Proto`` scheme when present, else the request scheme. A request
without an ``Origin`` header passes (it cannot come from a cross-site page).

``BodyLimitMiddleware`` counts the streamed body bytes, chunked requests
included, and answers 413 as soon as the total passes the limit. The accepted
body (at most the limit) is replayed to the application. The limit is
``MAX_BODY_BYTES`` (4 KB) unless the request path is in the middleware's
``overrides`` table; P2 U2 gives ``POST /api/rooms/summaries`` 8 KB there
(BR2.1) and every other route keeps 4 KB.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping

from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.websockets import WebSocket

logger = logging.getLogger("justchess.security")

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
MAX_BODY_BYTES = 4096
CLOSE_POLICY = 1008


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", ()):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_json(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("ascii"))]})
    await send({"type": "http.response.body", "body": body})


def expected_origin(scope: Scope, configured: str | None) -> str | None:
    """Return the app's own origin for this request, or None when it cannot be told."""
    if configured:
        return configured.strip().rstrip("/").lower()
    host = _header(scope, b"host")
    if not host:
        return None
    forwarded = _header(scope, b"x-forwarded-proto")
    if forwarded:
        scheme = forwarded.split(",")[0].strip().lower()
    else:
        scheme = {"ws": "http", "wss": "https"}.get(scope.get("scheme", "http"), scope.get("scheme", "http"))
    return f"{scheme}://{host}".lower()


class OriginGuardMiddleware:
    """Refuse cross-origin state changes (403) and cross-origin sockets (close 1008)."""

    def __init__(self, app: ASGIApp, configured_origin: str | None = None) -> None:
        self.app = app
        self.configured_origin = configured_origin

    def _allowed(self, scope: Scope) -> bool:
        origin = _header(scope, b"origin")
        if origin is None:
            return True
        return origin.strip().rstrip("/").lower() == expected_origin(scope, self.configured_origin)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        kind = scope["type"]
        guarded = kind == "websocket" or (kind == "http" and scope.get("method") not in SAFE_METHODS)
        if not guarded or self._allowed(scope):
            await self.app(scope, receive, send)
            return
        logger.info("Refused a cross-origin %s to %s", kind, scope.get("path"))
        if kind == "websocket":
            await WebSocket(scope, receive, send).close(code=CLOSE_POLICY)
        else:
            await _send_json(send, 403, "Cross-origin requests are not allowed")


class BodyLimitMiddleware:
    """Answer 413 for request bodies over the limit, counting streamed chunks.

    ``overrides`` maps an exact request path to its own limit in bytes; any
    other path uses ``max_bytes``.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES,
                 overrides: Mapping[str, int] | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.overrides = dict(overrides or {})

    def limit_for(self, path: str) -> int:
        """Return the body limit in bytes for this request path."""
        return self.overrides.get(path, self.max_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope.get("path", ""))
        declared = _header(scope, b"content-length")
        if declared is not None:
            if not declared.strip().isdigit():
                await _send_json(send, 400, "Invalid Content-Length")
                return
            if int(declared) > limit:
                await _send_json(send, 413, "Request body too large")
                return
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return  # the client went away before sending its body
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > limit:
                await _send_json(send, 413, "Request body too large")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        await self.app(scope, _replay(b"".join(chunks), receive), send)


def _replay(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay
