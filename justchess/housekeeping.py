"""Housekeeping: delete rooms idle for 30 days, at startup and then hourly (BR4.2).

Each room is deleted in its own transaction: optional per-room cleanup hooks
first (the app always registers ``notifications.delete_room_data``, U5's
push-subscription and alert-record delete), then the room's games and moves
through Games, then its seats and the room through Rooms.
A failure is logged with the room code and the room is retried on the next run.

P2 U3 (BR2.4): every run also marks pending join requests past their expiry
``lapsed`` (``run_lapse``). It does not broadcast, because housekeeping has no
access to the live hub; the lapse on read in the request handlers is the
source of truth and this run only tidies leftovers.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Callable, Sequence

from justchess import games, rooms
from justchess.db import Database

logger = logging.getLogger("justchess.housekeeping")

RETENTION = 30 * 24 * 3600.0  # fallback; the app passes gameplay.yaml's rooms.idle_room_delete_days
INTERVAL = 3600.0

CleanupHook = Callable[[sqlite3.Connection, str], None]


def _delete_if_still_idle(db: Database, code: str, cutoff: float,
                          hooks: Sequence[CleanupHook]) -> bool:
    with db.transaction() as conn:
        row = conn.execute("SELECT last_activity_at FROM rooms WHERE code = ?", (code,)).fetchone()
        if row is None or row["last_activity_at"] >= cutoff:
            return False  # deleted meanwhile, or touched since it was listed
        for hook in hooks:
            hook(conn, code)
        games.delete_games_for_room(conn, code)
        rooms.delete_room(conn, code)
    return True


def run_cleanup(db: Database, now: float, hooks: Sequence[CleanupHook] = (), retention: float = RETENTION) -> int:
    """Delete every room idle for longer than the retention period; return how many."""
    cutoff = now - retention
    try:
        with db.read() as conn:
            idle = rooms.list_idle_rooms(conn, cutoff)
    except sqlite3.Error:
        logger.exception("Housekeeping could not list idle rooms; retrying next run")
        return 0
    deleted = 0
    for code in idle:
        try:
            if _delete_if_still_idle(db, code, cutoff, hooks):
                deleted += 1
        except Exception:  # one bad room must not stop the others; retried next run
            logger.exception("Housekeeping could not delete room %s; retrying next run", code)
    if deleted:
        logger.info("Housekeeping deleted %d idle room(s)", deleted)
    return deleted


def run_lapse(db: Database, now: float) -> int:
    """Mark leftover expired join requests lapsed, without broadcasting (BR2.4); return how many."""
    try:
        with db.transaction() as conn:
            lapsed = rooms.lapse_expired(conn, now)
    except sqlite3.Error:
        logger.exception("Housekeeping could not lapse expired join requests; retrying next run")
        return 0
    if lapsed:
        logger.info("Housekeeping marked %d expired join request(s) lapsed", lapsed)
    return lapsed


async def run_forever(db: Database, clock: Callable[[], float], hooks: Sequence[CleanupHook] = (),
                      interval: float = INTERVAL, retention: float = RETENTION) -> None:
    """Run the request lapse and the cleanup now and then every ``interval`` seconds until cancelled."""
    while True:
        try:
            await asyncio.to_thread(run_lapse, db, clock())
            await asyncio.to_thread(run_cleanup, db, clock(), hooks, retention)
        except Exception:
            logger.exception("Housekeeping run failed; retrying next run")
        await asyncio.sleep(interval)
