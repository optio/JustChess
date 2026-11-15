"""Anonymous profiles: session and replaceable recovery capabilities are separate.

Only hashes are stored. A player session also authorizes seats explicitly linked
to that player, so recovery never needs plaintext room credentials in storage.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata

from justchess import DomainError

TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
MAX_NICKNAME = 24
# Deliberately bounded English vocabulary. Token matching avoids the Scunthorpe
# problem; this is a local safety net, not a promise of perfect moderation.
BLOCKED = frozenset("fuck fucking fucker motherfucker shit bullshit bitch bastard asshole arsehole cunt dick cock pussy nigger nigga faggot fag whore slut wanker twat piss porn rape rapist".split())
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest() if isinstance(token, str) and TOKEN.fullmatch(token) else None


def secret():
    return secrets.token_urlsafe(32)


def nickname(value):
    if not isinstance(value, str):
        raise DomainError(400, "Nickname must be text")
    clean = " ".join(unicodedata.normalize("NFKC", value).split())
    if len(clean) > MAX_NICKNAME or any(unicodedata.category(c).startswith("C") for c in clean):
        raise DomainError(400, "Choose a nickname of at most 24 characters")
    if any(not (c.isalnum() or c in " '-_.$@!") for c in clean):
        raise DomainError(400, "Use letters, numbers, spaces, apostrophes, dots, dashes or underscores")
    folded = "".join(c for c in unicodedata.normalize("NFKD", clean.casefold()) if not unicodedata.combining(c)).translate(LEET)
    words = re.findall(r"[a-z]+", folded)
    compact = "".join(words)
    if any(word in BLOCKED for word in words) or compact in BLOCKED:
        raise DomainError(400, "Please choose a different nickname: English profanity is not allowed")
    return clean


def authenticate(conn, token):
    row = conn.execute("SELECT p.* FROM players p JOIN player_sessions s ON s.player_id = p.player_id WHERE s.token_hash = ?", (digest(token),)).fetchone()
    if row is None:
        raise DomainError(403, "Your player session is invalid. Restore your private player link.")
    return row


def new_session(conn, player_id, now):
    token = secret()
    # Bound forgotten sessions per player without invalidating currently active
    # devices during ordinary recovery. Refuse excessive recovery instead.
    if conn.execute("SELECT count(*) FROM player_sessions WHERE player_id = ?", (player_id,)).fetchone()[0] >= 100:
        raise DomainError(429, "Too many saved devices for this player")
    conn.execute("INSERT INTO player_sessions (token_hash, player_id, created_at) VALUES (?, ?, ?)", (digest(token), player_id, now))
    return token


def create(conn, now):
    player_id, recovery = secrets.token_hex(16), secret()
    conn.execute("INSERT INTO players (player_id, recovery_hash, created_at) VALUES (?, ?, ?)", (player_id, digest(recovery), now))
    token = new_session(conn, player_id, now)
    return {**profile(conn, token), "token": token, "recovery": recovery}


def profile(conn, token):
    player = authenticate(conn, token)
    rows = conn.execute("SELECT s.room_code, s.slot, r.mode, r.computer_level FROM seats s JOIN rooms r ON r.code = s.room_code WHERE s.player_id = ? ORDER BY r.last_activity_at DESC LIMIT 50", (player["player_id"],)).fetchall()
    return {"playerId": player["player_id"], "nickname": player["nickname"], "seats": [
        {"code": row["room_code"], "slot": row["slot"], "token": token, "kind": "computer" if row["mode"] == "computer" else "friend", "computerLevel": row["computer_level"]} for row in rows]}


def restore(conn, recovery, now):
    row = conn.execute("SELECT player_id FROM players WHERE recovery_hash = ?", (digest(recovery),)).fetchone()
    if row is None:
        raise DomainError(403, "This private player link is invalid or has been replaced")
    token = new_session(conn, row[0], now)
    return {**profile(conn, token), "token": token}


def regenerate(conn, token):
    player = authenticate(conn, token)
    recovery = secret()
    conn.execute("UPDATE players SET recovery_hash = ? WHERE player_id = ?", (digest(recovery), player["player_id"]))
    return recovery


def attach(conn, token, code, seat_token):
    from justchess import rooms
    player = authenticate(conn, token)
    seat = rooms.authorize_seat(conn, code, seat_token)
    owner = conn.execute("SELECT player_id FROM seats WHERE seat_id = ?", (seat.seat_id,)).fetchone()[0]
    if owner is not None and owner != player["player_id"]:
        raise DomainError(403, "This seat belongs to another player")
    other = conn.execute("SELECT seat_id FROM seats WHERE room_code = ? AND player_id = ? AND seat_id <> ?", (code, player["player_id"], seat.seat_id)).fetchone()
    if other:
        raise DomainError(409, "This player already has a seat in this room")
    conn.execute("UPDATE seats SET player_id = ? WHERE seat_id = ?", (player["player_id"], seat.seat_id))


def seat_id(conn, code, token):
    row = conn.execute("SELECT s.seat_id FROM seats s JOIN player_sessions p ON p.player_id = s.player_id WHERE s.room_code = ? AND p.token_hash = ?", (code, digest(token))).fetchone()
    return row[0] if row else None


def names(conn, code):
    return {row["slot"]: row["nickname"] for row in conn.execute("SELECT s.slot, p.nickname FROM seats s JOIN players p ON p.player_id = s.player_id WHERE s.room_code = ?", (code,)).fetchall()}
