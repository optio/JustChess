"""U4 route ``POST /api/rooms/{code}/check-move`` (BR2.1, BR2.2).

* The answer shape ``{warning, san, version}`` for a clean move, a mate-allowing
  move and a hanging piece.
* U1's check order and refusals: seat (403), playing (409, also while waiting),
  version (409 with the snapshot), turn (403), legality (400), plus the origin
  guard (403) and the body limit (413).
* The check writes nothing: the version is unchanged and the move still goes in.
* Timing (BR2.2, derived from NFR5): a busy middlegame and a position where
  every move allows mate (111 stored half-moves to replay) both answer in
  300 ms or less on this host, measured with ``time.perf_counter`` over 5 runs,
  asserting on the median and on the maximum.

Every game here is played through the real ``/moves`` route from the starting
position, because the server always replays the stored moves.
"""

from __future__ import annotations

import statistics
import time

import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess.api import create_app

BUDGET_SECONDS = 0.300

# 1.f3 e5: White to move, g4?? allows Qh4#.
FOOLS_MATE_SETUP = ["f2f3", "e7e5"]
# Ruy Lopez, Breyer variation after 14...g6: White to move with 37 legal moves.
BREYER = ("e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5 a4b3 d7d6 c2c3 e8g8 "
          "h2h3 c6b8 d2d4 b8d7 b1d2 c8b7 b3c2 f8e8 d2f1 e7f8 f1g3 g7g6").split()
# A long random game ending with Black in check (Qa8+) where both legal moves, Ke7 and Kd7, allow mate in one.
EVERY_MOVE_ALLOWS_MATE = (
    "e2e3 b8c6 f1e2 f7f5 c2c3 g7g5 e2f1 a7a5 f1e2 a8b8 e1f1 f5f4 g2g3 f4f3 h2h4 b8a8 d1e1 b7b5 "
    "h1h3 c8b7 a2a4 c6b8 b2b4 g5h4 g3h4 e7e6 d2d4 c7c6 b1d2 c6c5 h3g3 f8h6 g3g5 b7d5 g5g2 d8c8 "
    "e3e4 h6d2 g2g3 a8a6 e4d5 d2c3 b4a5 c3d4 h4h5 e8d8 c1d2 g8h6 a4b5 d8e7 e2d3 h6g8 d3g6 a6b6 "
    "e1c1 b6d6 a5a6 c8b7 d5e6 d7e6 f1e1 d6a6 g6b1 b8c6 e1f1 a6a4 b1g6 e6e5 g6f7 d4e3 d2e1 b7a8 "
    "a1a4 a8a5 g3g4 g8f6 c1c4 e3c1 e1a5 h7h6 a4b4 c6a7 g4g5 f6h7 f7g8 e5e4 c4d5 a7c6 a5c7 c1a3 "
    "c7h2 c6e5 d5c6 e5g6 c6b7 e7d8 h2c7 d8d7 b7a7 a3c1 g1f3 c1f4 g5g4 h8g8 c7e5 d7c8 g4f4 g6f8 "
    "f3g5 c8d8 a7a8").split()
FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A started app on a temporary database with Stockfish preparation disabled."""
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    with TestClient(create_app(db_path=tmp_path / "check.sqlite3", engine_dir=tmp_path / "engines")) as started:
        yield started


class Room:
    """A room with both seats taken; tracks the version from each move's snapshot."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        created = client.post("/api/rooms").json()
        self.code, self.white = created["code"], created["token"]
        self.black = client.post(f"/api/rooms/{self.code}/join", json={}).json()["token"]
        self.version = self.state()["version"]
        self.plies = 0

    def state(self) -> dict:
        return self.client.get(f"/api/rooms/{self.code}", headers={"X-Seat-Token": self.white}).json()

    def token_to_move(self) -> str:
        return self.white if self.plies % 2 == 0 else self.black

    def play(self, moves: list[str]) -> Room:
        for uci in moves:
            answer = self.client.post(f"/api/rooms/{self.code}/moves",
                                      json={"token": self.token_to_move(), "uci": uci, "version": self.version})
            assert answer.status_code == 200, (uci, answer.text)
            self.version = answer.json()["version"]
            self.plies += 1
        return self

    def check(self, uci: str, *, token: str | None = None, version: int | None = None, **kwargs):
        body = {"token": token or self.token_to_move(), "uci": uci,
                "version": self.version if version is None else version}
        return self.client.post(f"/api/rooms/{self.code}/check-move", json=body, **kwargs)


def ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


# --- answers ----------------------------------------------------------------

def test_a_clean_move_has_no_warning(client: TestClient) -> None:
    room = Room(client)
    assert ok(room.check("e2e4")) == {"warning": None, "san": "e4", "version": room.version}


def test_a_mate_allowing_move_gives_mate_in_one(client: TestClient) -> None:
    room = Room(client).play(FOOLS_MATE_SETUP)
    assert ok(room.check("g2g4")) == {"warning": {"kind": "mate_in_one", "move": "g4", "mate": "Qh4#"},
                                      "san": "g4", "version": room.version}


def test_a_hanging_piece_gives_hanging_piece(client: TestClient) -> None:
    room = Room(client).play(BREYER)
    answer = ok(room.check("g3h5"))
    assert answer["san"] == "Nh5"
    assert answer["warning"]["kind"] == "hanging_piece"
    assert (answer["warning"]["piece"], answer["warning"]["square"]) == ("knight", "h5")
    assert set(answer["warning"]) == {"kind", "move", "piece", "square", "capturer", "defended"}


# --- refusals, in U1's order ------------------------------------------------

def test_a_wrong_token_is_refused_with_403(client: TestClient) -> None:
    room = Room(client)
    refused = room.check("e2e4", token="not-a-seat-token")
    assert (refused.status_code, refused.json()["detail"]) == (403, "This isn't your seat")


def test_not_your_turn_is_refused_with_403(client: TestClient) -> None:
    room = Room(client)
    refused = room.check("e7e5", token=room.black)
    assert (refused.status_code, refused.json()["detail"]) == (403, "Not your turn")


def test_a_stale_version_gives_409_with_the_snapshot(client: TestClient) -> None:
    room = Room(client).play(["e2e4"])
    stale = room.check("e7e5", version=room.version - 1)
    assert stale.status_code == 409
    body = stale.json()
    assert body["detail"] == "The board changed, here is the latest position"
    assert body["snapshot"]["version"] == room.version and body["snapshot"]["slot"] == "B"


def test_an_illegal_or_malformed_move_gives_400(client: TestClient) -> None:
    room = Room(client)
    for uci in ("e2e5", "zz99"):
        refused = room.check(uci)
        assert (refused.status_code, refused.json()["detail"]) == (400, "Illegal move"), uci


def test_a_finished_or_waiting_game_gives_409(client: TestClient) -> None:
    room = Room(client).play(FOOLS_MATE)
    over = room.check("e2e4", token=room.white)
    assert (over.status_code, over.json()["detail"]) == (409, "Game is over")
    assert over.json()["snapshot"]["status"] == "finished"
    created = client.post("/api/rooms").json()
    waiting = client.post(f"/api/rooms/{created['code']}/check-move",
                          json={"token": created["token"], "uci": "e2e4", "version": 0})
    assert (waiting.status_code, waiting.json()["detail"]) == (409, "Waiting for an opponent")


def test_a_foreign_origin_and_an_oversized_body_are_refused(client: TestClient) -> None:
    room = Room(client)
    foreign = room.check("e2e4", headers={"Origin": "https://evil.example"})
    assert foreign.status_code == 403
    huge = client.post(f"/api/rooms/{room.code}/check-move",
                       json={"token": "x" * 5000, "uci": "e2e4", "version": room.version})
    assert huge.status_code == 413


def test_the_check_changes_nothing(client: TestClient) -> None:
    room = Room(client).play(FOOLS_MATE_SETUP)
    before = room.state()
    ok(room.check("g2g4"))
    ok(room.check("b1c3"))
    after = room.state()
    assert (after["version"], after["fen"], after["moveList"]) == (before["version"], before["fen"], before["moveList"])
    room.play(["g2g4"])  # the move goes in with the version the check used
    assert room.state()["lastMove"] == "g2g4"


# --- BR2.2 timing -----------------------------------------------------------

def timed_checks(room: Room, uci: str, runs: int = 5) -> list[float]:
    samples = []
    for _ in range(runs):
        started = time.perf_counter()
        ok(room.check(uci))
        samples.append(time.perf_counter() - started)
    return samples


@pytest.mark.parametrize("moves, uci, expected_kind", [
    (BREYER, "g3h5", "hanging_piece"),          # busy middlegame: the warning runs the sweep
    (EVERY_MOVE_ALLOWS_MATE, "d8e7", None),     # the mate warning is swept and dropped
], ids=["busy-middlegame", "every-move-allows-mate"])
def test_the_check_answers_within_300_ms(client: TestClient, moves: list[str], uci: str, expected_kind) -> None:
    room = Room(client).play(moves)
    answer = ok(room.check(uci))
    assert (answer["warning"] or {}).get("kind") == expected_kind
    samples = timed_checks(room, uci)
    median, worst = statistics.median(samples), max(samples)
    print(f"check-move timing {uci}: median {median * 1000:.1f} ms, max {worst * 1000:.1f} ms")
    assert median <= BUDGET_SECONDS, samples
    assert worst <= BUDGET_SECONDS, samples
