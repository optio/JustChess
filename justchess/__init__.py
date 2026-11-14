"""JustChess backend package.

Modules, one per component (see the U1 functional design):

- ``db``: SQLite connection, schema version 4 and the startup check (P2 U2 BR1.1).
- ``summaries``: the read-only room summaries behind the "Your games" list (P2 U2).
- ``rooms``: rooms, seats, tokens, presence, score and rematch (BR1.x, BR3.x).
- ``games``: chess rules, game lifecycle and the per-viewer snapshot (BR2.x).
- ``live``: WebSocket connections, hello handshake and presence (BR4.4).
- ``housekeeping``: 30-day cleanup of idle rooms (BR4.2).
- ``security``: origin check and request body limit middleware (BR4.3).
- ``ratelimit``: the join-request rate limit and the client address behind it (P2 U3).
- ``analysis``: blunder analysis for a candidate move (U4, mate in one and hanging pieces).
- ``notifications``: alert events, push subscriptions, the one-alert claim and Web Push (U5).
- ``vapid``: Web Push (VAPID) keys from the environment, and the key generator (U5).
- ``api``: HTTP routes, orchestration and the application factory.

``DomainError`` is the shared base for refusals raised by the business modules;
the API layer turns it into an HTTP response with ``status`` and ``message``.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """A business rule refused the request.

    ``status`` is the HTTP status the API layer answers with, ``message`` the
    human-readable reason shown to the player. Never put tokens in either.
    """

    def __init__(self, status: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra
