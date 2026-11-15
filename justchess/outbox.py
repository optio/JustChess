"""Bounded durable Web Push delivery, relevance checks and lease-based retries.

Delivery is at-least-once across an interruption during a remote send. The stable
notification tag coalesces that unavoidable ambiguous acceptance case on devices.
Per-subscription acknowledgements avoid replaying known successful endpoints.
"""

from __future__ import annotations

import time
import uuid
import logging

import chess

from justchess import DomainError, games, notifications as push, rooms, work

MAX_AGE = 300
LEASE = 180
MAX_ATTEMPTS = 5
logger = logging.getLogger("justchess.notifications")


def enqueue(conn, event, now):
    if event is None:
        return
    conn.execute(
        "INSERT INTO notification_outbox(room_code, slot, event_key, kind, title, body, created_at, available_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(room_code, slot, event_key) DO NOTHING",
        (event.room_code, event.target_slot, event.event_key, event.kind, event.title, event.body, now, now))
    if event.kind in ("move", "ended", "joined"):
        conn.execute("UPDATE notification_outbox SET status = 'skipped' WHERE room_code = ? AND slot = ? "
                     "AND event_key <> ? AND kind IN ('move', 'ended', 'joined') AND status = 'pending' "
                     "AND lease_until <= ?", (event.room_code, event.target_slot, event.event_key, now))


def relevant(conn, event, created_at, now):
    if now - created_at > (3600 if event.kind == "ended" else MAX_AGE):
        return False
    try:
        game = games.current_game(conn, event.room_code)
        if event.kind == "ended":
            return game.status == games.FINISHED and event.event_key == f"ended:{game.number}"
        if event.kind == "join_request":
            request = rooms.visible_request(conn, event.room_code, now)
            return request is not None and event.event_key == f"join-request:{request.request_id}"
        if game.status != games.PLAYING:
            return False
        if game.slot_of(chess.Board(game.fen).turn) != event.target_slot:
            return False
        if event.kind == "joined":
            return game.number == 1 and not games.load_moves(conn, game.game_id)
        moves = games.load_moves(conn, game.game_id)
        return bool(moves) and event.event_key == f"move:{game.number}:{moves[-1].ply}"
    except DomainError:
        return False


class Outbox:
    def __init__(self, db, vapid, sender, clock, presence):
        self.db, self.vapid, self.sender = db, vapid, sender
        self.clock, self.presence = clock, presence

    def drain(self, limit=2, budget=25):
        """At most two jobs/25s, global ownership, no independent retry process."""
        now, started = self.clock(), time.monotonic()
        with self.db.transaction() as conn:
            owner = work.claim(conn, "notification-drain", now, LEASE)
        if not owner:
            return 0
        count = 0
        try:
            for _ in range(limit):
                if time.monotonic() - started >= budget:
                    break
                job = self._claim()
                if job is None:
                    break
                self._deliver(job, started + budget)
                count += 1
            return count
        finally:
            with self.db.transaction() as conn:
                work.release(conn, "notification-drain", owner)

    def dispatch(self, event):
        """The triggering request attempts its own recipient even during a global drain."""
        job = self._claim(event)
        if job:
            self._deliver(job, time.monotonic() + 25)

    def _claim(self, event=None):
        now, owner = self.clock(), uuid.uuid4().hex
        with self.db.transaction() as conn:
            extra = " AND room_code = ? AND slot = ? AND event_key = ?" if event else ""
            values = (now, now, event.room_code, event.target_slot, event.event_key) if event else (now, now)
            row = conn.execute("SELECT * FROM notification_outbox WHERE status = 'pending' AND available_at <= ? "
                               "AND lease_until <= ?" + extra + " ORDER BY created_at DESC LIMIT 1", values).fetchone()
            if row is None:
                return None
            changed = conn.execute("UPDATE notification_outbox SET lease_owner = ?, lease_until = ?, "
                                   "attempts = attempts + 1 WHERE room_code = ? AND slot = ? AND event_key = ? "
                                   "AND status = 'pending' AND lease_until <= ?",
                                   (owner, now + LEASE, row["room_code"], row["slot"], row["event_key"], now)).rowcount
            return (dict(row), owner) if changed else None

    def _deliver(self, job, deadline):
        row, owner = job
        event = push.AlertEvent(row["kind"], row["room_code"], row["slot"], row["event_key"], row["title"], row["body"])
        status = "pending"
        with self.db.read() as conn:
            useful = relevant(conn, event, row["created_at"], self.clock())
            subscriptions = push.list_subscriptions(conn, event.room_code, event.target_slot)
        if not useful or self.presence(event.room_code, event.target_slot).page_covers_it:
            status = "skipped"
        elif not self.vapid.enabled or not subscriptions:
            status = "skipped"
        else:
            failed = False
            for subscription in subscriptions:
                with self.db.read() as conn:
                    owns = conn.execute("SELECT 1 FROM notification_outbox WHERE room_code = ? AND slot = ? "
                                        "AND event_key = ? AND lease_owner = ? AND lease_until > ?",
                                        (event.room_code, event.target_slot, event.event_key, owner, self.clock())).fetchone()
                    if not owns:
                        return
                    done = conn.execute("SELECT 1 FROM notification_deliveries WHERE room_code = ? AND slot = ? "
                                        "AND event_key = ? AND subscription_id = ?",
                                        (event.room_code, event.target_slot, event.event_key, subscription.id)).fetchone()
                    useful = relevant(conn, event, row["created_at"], self.clock())
                if done:
                    continue
                if not useful:
                    status = "skipped"
                    break
                if time.monotonic() >= deadline:
                    failed = True
                    break
                try:
                    result = self.sender(subscription.info(), event.payload(), self.vapid)
                except Exception:
                    logger.warning("Alert %s for room %s could not be dispatched; retry retained",
                                   event.event_key, event.room_code)
                    result = push.PushResult(0)
                if 200 <= result.status < 300 or push.is_gone(result):
                    with self.db.transaction() as conn:
                        if push.is_gone(result):
                            conn.execute("DELETE FROM push_subscriptions WHERE id = ?", (subscription.id,))
                        conn.execute("INSERT INTO notification_deliveries(room_code, slot, event_key, subscription_id) "
                                     "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                                     (event.room_code, event.target_slot, event.event_key, subscription.id))
                else:
                    failed = True
            if status != "skipped":
                status = "pending" if failed else "sent"
        attempts = row["attempts"] + 1
        if status == "pending" and attempts >= MAX_ATTEMPTS:
            status = "failed"
        with self.db.transaction() as conn:
            conn.execute("UPDATE notification_outbox SET status = ?, available_at = ?, lease_until = 0, lease_owner = NULL "
                         "WHERE room_code = ? AND slot = ? AND event_key = ? AND lease_owner = ?",
                         (status, self.clock() + min(30 * 2 ** attempts, 900), event.room_code,
                          event.target_slot, event.event_key, owner))
            # Keep the existing diagnostics/API record useful with the new durable queue.
            push.claim(conn, event, self.clock())
            push.mark(conn, event, push.FAILED if status == "pending" else status, self.clock())
