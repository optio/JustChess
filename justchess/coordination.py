"""External room events and short-lived presence; listeners live only with sockets."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("justchess.coordination")


class AddressBook:
    """Shared decline cooldowns inside the room mutation's transaction."""

    def __init__(self, conn, memory):
        self.conn, self.memory = conn, memory

    def note_request(self, request_id, address):
        self.conn.execute("INSERT INTO request_addresses(request_id, address_hash) VALUES (?, ?) "
                          "ON CONFLICT(request_id) DO NOTHING", (request_id, hashlib.sha256(address.encode()).hexdigest()))

    def note_declined(self, request_id, code, now):
        row = self.conn.execute("SELECT address_hash FROM request_addresses WHERE request_id = ?", (request_id,)).fetchone()
        if row:
            self.conn.execute("INSERT INTO room_declines(room_code, address_hash, declined_at) VALUES (?, ?, ?) "
                              "ON CONFLICT(room_code, address_hash) DO UPDATE SET declined_at = excluded.declined_at",
                              (code, row[0], now))
            self.conn.execute("DELETE FROM request_addresses WHERE request_id = ?", (request_id,))

    def declined_recently(self, code, address, now):
        row = self.conn.execute("SELECT declined_at FROM room_declines WHERE room_code = ? AND address_hash = ?",
                                (code, hashlib.sha256(address.encode()).hexdigest())).fetchone()
        return row is not None and now - row[0] < self.memory


def channel(db, code):
    # A channel must be isolated per schema as well as room (including test schemas).
    # The schema is read once per Database (db.schema_name caches it).
    schema = db._schema
    if schema is None:
        with db.read() as conn:
            schema = db.schema_name(conn)
    return "jc_" + hashlib.sha256((schema + ":" + code).encode()).hexdigest()[:40]


class Coordination:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    def publish(self, code):
        if self.db.backend == "postgresql":
            name = channel(self.db, code)
            with self.db.read() as conn:
                conn.execute("SELECT pg_notify(?, ?)", (name, code))

    def presence(self, code):
        with self.db.read() as conn:
            return conn.execute("SELECT slot, visible, heard_at FROM live_presence "
                                "WHERE room_code = ? AND heard_at > ?",
                                (code, self.clock() - 10)).fetchall()

    def touch(self, code, connection_id, slot, visible, heard_at):
        if self.db.backend != "postgresql" or slot is None:
            return
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO live_presence(connection_id, room_code, slot, visible, heard_at) "
                         "VALUES (?, ?, ?, ?, ?) ON CONFLICT(connection_id) DO UPDATE "
                         "SET visible = excluded.visible, heard_at = excluded.heard_at",
                         (connection_id, code, slot, int(visible), heard_at))

    def leave(self, connection_id):
        if self.db.backend == "postgresql":
            with self.db.transaction() as conn:
                conn.execute("DELETE FROM live_presence WHERE connection_id = ?", (connection_id,))

    @asynccontextmanager
    async def listening(self, code, resync):
        if self.db.backend != "postgresql":
            yield
            return
        import psycopg
        from psycopg import sql

        ready = asyncio.Event()

        async def listen():
            delay = 0.1
            while True:
                try:
                    raw = await psycopg.AsyncConnection.connect(
                        self.db._database_url, autocommit=True, connect_timeout=5)
                    try:
                        await raw.execute(sql.SQL("LISTEN {}").format(sql.Identifier(channel(self.db, code))))
                        ready.set()
                        # LISTEN is established before resync, closing the connect/event race.
                        await resync(code)
                        delay = 0.1
                        async for event in raw.notifies():
                            if event.payload == code:
                                await resync(code)
                    finally:
                        await raw.close()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Never log raw psycopg errors/DSNs or capability values.
                    logger.warning("Room listener interrupted; reconnecting")
                    ready.set()
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 5)

        task = asyncio.create_task(listen())
        try:
            await asyncio.wait_for(ready.wait(), 6)
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
