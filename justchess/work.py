"""Database leases for bounded work. Expired ownership can be safely retried."""

from __future__ import annotations

import uuid


def claim(conn, key, now, ttl):
    owner = uuid.uuid4().hex
    row = conn.execute(
        "INSERT INTO work_claims(work_key, owner, expires_at) VALUES (?, ?, ?) "
        "ON CONFLICT(work_key) DO UPDATE SET owner = excluded.owner, expires_at = excluded.expires_at "
        "WHERE work_claims.expires_at <= ? RETURNING owner", (key, owner, now + ttl, now)).fetchone()
    return owner if row else None


def release(conn, key, owner):
    conn.execute("DELETE FROM work_claims WHERE work_key = ? AND owner = ?", (key, owner))
