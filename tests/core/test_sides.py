"""Random creator colour, switching sides and the app version (2026-11-15 follow-ups)."""

from __future__ import annotations

from pathlib import Path

import pytest

from justchess import gameplay, version
from tests.core.conftest import create_room, join_room, move
from tests.fakes.computer_api import computer_client, computer_clock, state, wait_idle, wait_plies  # noqa: F401


def side(client, code, token, colour):
    return client.post(f"/api/rooms/{code}/side", json={"token": token, "colour": colour})


def snapshot(client, code, token):
    answer = client.get(f"/api/rooms/{code}", headers={"X-Seat-Token": token})
    assert answer.status_code == 200, answer.text
    return answer.json()


# --- the creator's colour -------------------------------------------------------

def test_random_creator_colour_uses_the_chooser(make_client, monkeypatch) -> None:
    monkeypatch.delenv("JUSTCHESS_CREATOR_COLOUR")
    client = make_client(colour_chooser=lambda colours: "black")
    room = create_room(client)
    assert room["colour"] == "black"
    mine = snapshot(client, room["code"], room["token"])
    assert (mine["colour"], mine["seats"]["B"]["colour"]) == ("black", "white")
    friend = join_room(client, room["code"])
    assert friend["colour"] == "white"
    assert snapshot(client, room["code"], friend["token"])["legalMoves"], "White (the friend) moves first"


def test_pinned_creator_colour_and_bad_values(make_client, monkeypatch) -> None:
    monkeypatch.setenv("JUSTCHESS_CREATOR_COLOUR", "black")
    assert create_room(make_client(colour_chooser=lambda colours: "white"))["colour"] == "black"
    with pytest.raises(gameplay.GameplayError):
        gameplay.with_env_overrides(gameplay.DEFAULT_GAMEPLAY, {"JUSTCHESS_CREATOR_COLOUR": "purple"})
    with pytest.raises(gameplay.GameplayError):
        gameplay.from_mapping({"rooms": {"creator_colour": "green"}})
    assert gameplay.from_mapping({"rooms": {"creator_colour": "white"}}).creator_colour == "white"
    assert gameplay.DEFAULT_GAMEPLAY.creator_colour == "random"


# --- switching sides before a friend joins ----------------------------------------

def test_switch_sides_while_waiting_until_the_first_move_or_a_friend(make_client) -> None:
    client = make_client()
    room = create_room(client)
    code, token = room["code"], room["token"]
    assert snapshot(client, code, token)["canSwitchSides"] is True
    answer = side(client, code, token, "black")
    assert answer.status_code == 200, answer.text
    assert (answer.json()["colour"], answer.json()["version"]) == ("black", 1)
    assert side(client, code, token, "black").json()["version"] == 1, "the same colour changes nothing"
    assert side(client, code, token, "purple").status_code == 400
    friend = join_room(client, code)
    assert friend["colour"] == "white"
    assert snapshot(client, code, token)["canSwitchSides"] is False
    refused = side(client, code, token, "white")
    assert (refused.status_code, refused.json()["detail"]) == (409, "You can't switch sides now")
    assert snapshot(client, code, friend["token"])["canSwitchSides"] is False, "only seat A is offered it"
    assert side(client, code, friend["token"], "black").status_code == 403


def test_switch_sides_in_pass_along_only_before_the_first_move(make_client) -> None:
    client = make_client()
    room = create_room(client)
    code, token = room["code"], room["token"]
    mode = client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": "pass_along"}).json()
    assert side(client, code, token, "black").status_code == 200
    current = snapshot(client, code, token)
    assert move(client, code, token, "e2e4", current["version"]).status_code == 200
    assert snapshot(client, code, token)["canSwitchSides"] is False
    assert side(client, code, token, "white").status_code == 409
    assert mode["mode"] == "pass_along"


# --- switching sides against the computer -----------------------------------------

def test_switch_sides_with_the_stand_in_any_time_and_the_computer_answers(computer_client) -> None:
    client = computer_client(["--delay", "0.05"])
    room = client.post("/api/rooms").json()
    code, token = room["code"], room["token"]
    snap = client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": "computer", "level": "beginner"}).json()
    assert move(client, code, token, "e2e4", snap["version"]).status_code == 200
    after = wait_plies(client, code, token, 2)
    assert after["canSwitchSides"] is True and after["colour"] == "white"
    switched = side(client, code, token, "black")
    assert switched.status_code == 200, switched.text
    assert switched.json()["colour"] == "black" and switched.json()["counted"] is False
    # Now White (the computer) is to move: it answers by itself.
    later = wait_plies(client, code, token, 3)
    assert later["turn"] == "black" and later["legalMoves"]


def test_switching_a_lobby_computer_game_after_moves_stops_it_counting(computer_client) -> None:
    client = computer_client(["--delay", "0.05"])
    room = client.post("/api/rooms", json={"kind": "computer", "level": "beginner", "colour": "white"}).json()
    code, token = room["code"], room["token"]
    early = side(client, code, token, "black")
    assert early.status_code == 200 and early.json()["counted"] is True, "before any move the game still counts"
    wait_plies(client, code, token, 1)
    back = side(client, code, token, "white")
    assert back.status_code == 200 and back.json()["counted"] is False
    wait_idle(client)
    resign = client.post(f"/api/rooms/{code}/resign", json={"token": token, "version": state(client, code, token)["version"]})
    assert resign.status_code == 200
    assert resign.json()["score"] == {"A": 0, "B": 0, "draws": 0}, "an uncounted game leaves the score alone"
    assert resign.json()["canSwitchSides"] is False, "a finished game has no sides to switch"


# --- the app version ---------------------------------------------------------------

def test_version_resolution_order(tmp_path, monkeypatch) -> None:
    build = tmp_path / "build-version.txt"
    monkeypatch.setattr(version, "_from_git", lambda root: "abc1234")
    assert version.resolve_version({"JUSTCHESS_VERSION": "v1.2"}, build_file=build) == "v1.2"
    full = "0123456789abcdef0123456789abcdef01234567"
    assert version.resolve_version({"VERCEL_GIT_COMMIT_SHA": full}, build_file=build) == "0123456"
    build.write_text("feed123\n")
    assert version.resolve_version({}, build_file=build) == "feed123"
    build.write_text("<script>\n")
    assert version.resolve_version({}, build_file=build) == "abc1234", "unsafe text is ignored"
    monkeypatch.setattr(version, "_from_git", lambda root: None)
    assert version.resolve_version({}, build_file=tmp_path / "missing.txt") == "unknown"
    target = tmp_path / "out.txt"
    assert version.write_build_file(target, {"VERCEL_GIT_COMMIT_SHA": full}) == "0123456"
    assert target.read_text() == "0123456\n"


def test_version_from_git_in_this_checkout() -> None:
    found = version._from_git(Path(version.ROOT))
    assert found is None or (4 <= len(found) <= 40)


def test_version_is_in_the_page_and_health(make_client, monkeypatch) -> None:
    monkeypatch.setenv("JUSTCHESS_VERSION", "testver1")
    client = make_client()
    assert "Version <span class=\"t-code\">testver1</span>" in client.get("/").text
    assert client.get("/api/health").json()["version"] == "testver1"


# --- back to waiting (bug: the game acted as if a friend had joined) -------------

def test_back_to_waiting_without_moves_waits_again(make_client) -> None:
    client = make_client()
    room = create_room(client)
    code, token = room["code"], room["token"]
    for mode in ("pass_along", "waiting"):
        assert client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": mode}).status_code == 200
    mine = snapshot(client, code, token)
    assert (mine["mode"], mine["status"], mine["counted"], mine["legalMoves"]) == ("waiting", "waiting", True, [])
    assert mine["seats"]["B"]["presence"] == "empty"
    friend = join_room(client, code)
    joined = snapshot(client, code, token)
    assert joined["status"] == "playing" and joined["legalMoves"], "the friend's arrival starts the game as usual"
    assert friend["colour"] == "black"


def test_back_to_waiting_after_moves_keeps_position_but_nobody_moves(make_client) -> None:
    client = make_client()
    room = create_room(client)
    code, token = room["code"], room["token"]
    entered = client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": "pass_along"}).json()
    assert move(client, code, token, "e2e4", entered["version"]).status_code == 200
    back = client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": "waiting"}).json()
    assert (back["status"], back["legalMoves"], len(back["moveList"])) == ("playing", [], 1)
    refused = move(client, code, token, "d2d4", back["version"])
    assert (refused.status_code, refused.json()["detail"]) == (409, "Waiting for an opponent")
    friend = join_room(client, code)
    theirs = snapshot(client, code, friend["token"])
    assert theirs["turn"] == "black" and theirs["legalMoves"], "the friend continues from the position"


def test_back_to_waiting_from_the_computer_without_moves(computer_client) -> None:
    client = computer_client()
    room = client.post("/api/rooms").json()
    code, token = room["code"], room["token"]
    assert client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": "computer"}).status_code == 200
    back = client.post(f"/api/rooms/{code}/mode", json={"token": token, "mode": "waiting"}).json()
    assert (back["mode"], back["status"], back["seats"]["B"]["presence"], back["counted"]) == ("waiting", "waiting", "empty", True)


def test_snapshot_carries_each_seats_last_seen_age(make_client, clock) -> None:
    client = make_client()
    room = create_room(client)
    friend = join_room(client, room["code"])
    clock.advance(2 * 3600 + 59)
    seen = snapshot(client, room["code"], room["token"])["seats"]
    assert seen["B"]["lastSeenSeconds"] == 2 * 3600, "rounded down to whole minutes"
    assert friend["slot"] == "B"
