"""Tests for POST /api/rooms/summaries (P2 U2, BR2.1-BR2.3, W4).

Rooms are made through the API on a temporary database (``make_client``);
states the API cannot reach yet (a draw, a pending join request from U3) are
written straight into that temporary file.
"""

from __future__ import annotations

import json
import logging

import pytest

from justchess import rooms
from justchess.db import Database
from justchess.summaries import INVALID_REQUEST, MAX_BODY_BYTES
from tests.core.conftest import create_room, join_room, move

FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]  # black (seat B) mates white (seat A)
SUMMARIES = "/api/rooms/summaries"


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def raw_db(tmp_path):
    """The client's own temporary database file (see conftest.make_client)."""
    return Database(tmp_path / "api.sqlite3")


def ask(client, *seats, **kwargs):
    return client.post(SUMMARIES, json={"seats": [{"code": code, "token": token} for code, token in seats]}, **kwargs)


def summaries_for(client, *seats):
    response = ask(client, *seats)
    assert response.status_code == 200, response.text
    return response.json()["rooms"]


def two_player_room(client):
    a = create_room(client)
    b = join_room(client, a["code"])
    return a, b


def test_a_found_summary_has_every_field(client, clock):
    a, _b = two_player_room(client)

    [summary] = summaries_for(client, (a["code"], a["token"]))

    assert summary == {
        "code": a["code"], "found": True, "kind": "friend", "computerLevel": None, "opponent": "joined",
        "colour": "white", "status": "playing", "yourTurn": True, "result": None, "endReason": None,
        "lastActivityAt": clock(), "endedAt": None,
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "pendingJoinRequest": False,
    }


def test_unknown_room_and_wrong_token_answer_the_same_not_found_shape(client):
    a, _b = two_player_room(client)

    unknown, wrong, right = summaries_for(client, ("ZZZZZ9", a["token"]), (a["code"], "not-this-seat"),
                                          (a["code"], a["token"]))

    assert unknown == {"code": "ZZZZZ9", "found": False}
    assert wrong == {"code": a["code"], "found": False}, "a wrong token does not reveal that the room exists"
    assert right["found"] is True


def test_your_turn_and_their_turn_follow_the_side_to_move(client):
    a, b = two_player_room(client)
    assert move(client, a["code"], a["token"], "e2e4", 1).status_code == 200

    mine, theirs = summaries_for(client, (a["code"], b["token"]), (a["code"], a["token"]))

    assert (mine["colour"], mine["yourTurn"]) == ("black", True)
    assert (theirs["colour"], theirs["yourTurn"]) == ("white", False)
    assert "4P3" in mine["fen"], "the current position is sent for the thumbnail"


def test_won_lost_and_drawn_from_each_seats_view(client, clock, raw_db):
    a, b = two_player_room(client)
    for version, uci in enumerate(FOOLS_MATE, start=1):
        token = a["token"] if version % 2 == 1 else b["token"]
        assert move(client, a["code"], token, uci, version).status_code == 200

    loser, winner = summaries_for(client, (a["code"], a["token"]), (a["code"], b["token"]))
    assert (loser["status"], loser["result"], loser["yourTurn"]) == ("finished", "lost", False)
    assert (winner["result"], winner["endReason"], winner["endedAt"]) == ("won", "checkmate", clock())

    c, d = two_player_room(client)
    with raw_db.transaction() as conn:
        conn.execute("UPDATE games SET status = 'finished', result = '1/2-1/2', end_reason = 'stalemate', ended_at = ? "
                     "WHERE room_code = ?", (clock(), c["code"]))
    drawn = summaries_for(client, (c["code"], c["token"]), (c["code"], d["token"]))
    assert [s["result"] for s in drawn] == ["drawn", "drawn"]


def test_a_room_waiting_for_its_friend(client):
    a = create_room(client)

    [summary] = summaries_for(client, (a["code"], a["token"]))

    assert (summary["status"], summary["opponent"], summary["yourTurn"], summary["kind"]) == \
        ("waiting", "waiting", False, "friend")


def test_pending_join_request_shows_for_seat_a_only_and_not_once_expired(client, clock, raw_db):
    a, b = two_player_room(client)
    with raw_db.transaction() as conn:
        conn.execute("INSERT INTO join_requests (room_code, requester_token_hash, created_at, expires_at) "
                     "VALUES (?, 'requester-hash', ?, ?)", (a["code"], clock(), clock() + 600))

    seat_a, seat_b = summaries_for(client, (a["code"], a["token"]), (a["code"], b["token"]))
    assert (seat_a["pendingJoinRequest"], seat_b["pendingJoinRequest"]) == (True, False)

    clock.advance(601)
    [expired] = summaries_for(client, (a["code"], a["token"]))
    assert expired["pendingJoinRequest"] is False


def test_one_browser_holding_both_seats_gets_both_views_and_duplicates_collapse(client):
    a, b = two_player_room(client)

    answers = summaries_for(client, (a["code"], a["token"]), (a["code"], b["token"]), (a["code"], a["token"]))

    assert [(s["code"], s["colour"]) for s in answers] == [(a["code"], "white"), (a["code"], "black")]


def test_malformed_bodies_get_the_fixed_400_without_the_token(client, caplog):
    secret = "a-secret-seat-token-that-must-not-leak"
    bad_bodies = [
        {"seats": []},
        {"seats": [{"code": "abc123", "token": secret}]},  # lower case code
        {"seats": [{"code": "ABC123", "token": secret + "x" * 128}]},  # token too long
        {"seats": [{"code": "ABC123", "token": ""}]},
        {"seats": [{"code": "ABC123", "token": secret}] * 51},
        {"seats": [["ABC123", secret]]},
        {"rooms": [{"code": "ABC123", "token": secret}]},
        [secret],
    ]
    with caplog.at_level(logging.DEBUG):
        for body in bad_bodies:
            response = client.post(SUMMARIES, json=body)
            assert response.status_code == 400, body
            assert response.json() == {"detail": INVALID_REQUEST, "error": "bad_request"}
            assert secret not in response.text
        broken = client.post(SUMMARIES, content=b'{"seats": [{"code": "ABC123", "token": "' + secret.encode() + b'"',
                             headers={"Content-Type": "application/json"})
        assert broken.status_code == 400 and secret not in broken.text
        a = create_room(client)
        assert ask(client, (a["code"], a["token"])).status_code == 200
    assert secret not in caplog.text and a["token"] not in caplog.text, "tokens never reach the logs"


def test_body_limit_is_8_kb_for_this_route_only_and_the_origin_is_checked(client):
    seats = [{"code": f"A{i:05d}", "token": "t" * 128} for i in range(50)]
    body = json.dumps({"seats": seats})
    assert 4096 < len(body) <= MAX_BODY_BYTES, "a full 50-seat request fits only under the 8 KB override"
    accepted = client.post(SUMMARIES, content=body, headers={"Content-Type": "application/json"})
    assert accepted.status_code == 200 and all(not s["found"] for s in accepted.json()["rooms"])

    too_big = client.post(SUMMARIES, content=b"{" + b" " * MAX_BODY_BYTES + b"}",
                          headers={"Content-Type": "application/json"})
    assert too_big.status_code == 413
    other_route = client.post("/api/rooms/ABC123/join", content=b"{" + b" " * 5000 + b"}",
                              headers={"Content-Type": "application/json"})
    assert other_route.status_code == 413, "every other route keeps the 4 KB limit"

    a = create_room(client)
    foreign = ask(client, (a["code"], a["token"]), headers={"Origin": "https://evil.example"})
    assert foreign.status_code == 403


def test_summaries_are_read_only_and_keep_no_room_alive(client, clock, raw_db):
    a, b = two_player_room(client)
    with raw_db.read() as conn:
        before = (rooms.get_room(conn, a["code"]), rooms.get_seats(conn, a["code"]))

    clock.advance(3600)
    summaries_for(client, (a["code"], a["token"]), (a["code"], b["token"]))

    with raw_db.read() as conn:
        after = (rooms.get_room(conn, a["code"]), rooms.get_seats(conn, a["code"]))
    assert after[0].last_activity_at == before[0].last_activity_at
    assert {s: seat.last_seen_at for s, seat in after[1].items()} == {s: seat.last_seen_at for s, seat in before[1].items()}
    assert after == before
