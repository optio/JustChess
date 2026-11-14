"""P2 U6 endgame HTTP routes with the fake UCI engine (BR2.5, BR3.1-BR3.3, W1, W2).

The engine is the U4 fake (``tests/fakes``): it answers with the first legal
move in UCI order, so the defender's reply is predictable. Each test passes its
own small endgame folder to ``create_app``; nothing touches justchess.sqlite3.
"""

from __future__ import annotations

import time
from pathlib import Path

import chess
import pytest

from justchess import engine as engine_module
from justchess import gameplay as gameplay_module
from tests.fakes.computer_api import computer_client, computer_clock, services_of  # noqa: F401

MATE_IN_ONE = "4k3/8/4K3/8/8/8/8/7R w - - 0 1"  # Rh8#
QUEEN_BOX = "8/8/8/4k3/8/8/8/3QK3 w - - 0 1"
HOLD = "8/8/3k4/8/4K3/4P3/8/8 b - - 0 1"
POSITIONS = {
    "queen-mate": [("queen-box", "Queen box", QUEEN_BOX, "mate")],
    "rook-mate": [("rook-one", "Rook in one", MATE_IN_ONE, "mate")],
    "king-pawn": [("kp-lead", "King leads", "8/8/4k3/8/4K3/8/4P3/8 w - - 0 1", "promote")],
    "opposition": [("opp-hold", "Hold it", HOLD, "draw")],
}


@pytest.fixture
def endgames_dir(tmp_path) -> Path:
    folder = tmp_path / "endgames"
    folder.mkdir()
    for category, rows in POSITIONS.items():
        text = "positions:\n" + "".join(
            f"  - id: {pid}\n    title: {title}\n    fen: {fen}\n    goal: {goal}\n    hint: Hint for {pid}.\n"
            for pid, title, fen, goal in rows)
        (folder / f"{category}.yaml").write_text(text, encoding="utf-8")
    return folder


def settings(**endgames) -> gameplay_module.Gameplay:
    return gameplay_module.from_mapping({"endgames": endgames}, "test settings")


def play(client, position_id: str, moves):
    return client.post(f"/api/endgames/{position_id}/play", json={"moves": moves})


def first_legal_reply(fen: str, moves: list[str]) -> str:
    """What the fake engine plays: the first legal move in UCI order."""
    board = chess.Board(fen)
    for uci in moves:
        board.push_uci(uci)
    return sorted(move.uci() for move in board.legal_moves)[0]


def test_list_and_get_work_and_an_unknown_id_is_404(computer_client, endgames_dir) -> None:
    client = computer_client([], endgames_dir=endgames_dir)
    listed = client.get("/api/endgames").json()
    assert (listed["installed"], listed["available"], listed["reason"]) == (True, True, None)
    assert [c["id"] for c in listed["categories"]] == ["queen-mate", "rook-mate", "king-pawn", "opposition"]
    assert listed["categories"][1]["positions"] == [{"id": "rook-one", "title": "Rook in one", "goal": "mate", "order": 1}]
    detail = client.get("/api/endgames/opp-hold").json()
    assert {k: detail[k] for k in ("id", "category", "goal", "hint", "index", "count", "holdMoves", "side")} == {
        "id": "opp-hold", "category": "opposition", "goal": "draw", "hint": "Hint for opp-hold.", "index": 1,
        "count": 1, "holdMoves": 30, "side": "black"}
    assert detail["fen"] == HOLD and "d6e6" in detail["legalMoves"] and detail["next"] == "queen-box"
    assert "holdMoves" not in client.get("/api/endgames/rook-one").json(), "holdMoves is for draw goals only"
    for missing in ("no-such-position", "ROOK-ONE", "a" * 41):
        answer = client.get(f"/api/endgames/{missing}")
        assert (answer.status_code, answer.json()["detail"]) == (404, "No such position"), missing
    assert client.get("/api/endgames/..%2Frook-one").status_code == 404, "never a path"
    assert play(client, "no-such-position", ["e1e2"]).status_code == 404
    assert client.get("/learn/endgames/rook-one").status_code == 200, "the page route serves the app shell"


def test_a_play_round_trip_returns_the_defender_reply_and_the_verdict(computer_client, endgames_dir) -> None:
    client = computer_client([], endgames_dir=endgames_dir)
    answer = play(client, "queen-box", ["e1e2"])
    assert answer.status_code == 200, answer.text
    body = answer.json()
    expected = first_legal_reply(QUEEN_BOX, ["e1e2"])
    board = chess.Board(QUEEN_BOX)
    board.push_uci("e1e2")
    assert body["playerFen"] == board.fen()
    san = board.san(chess.Move.from_uci(expected))
    board.push_uci(expected)
    assert body["reply"] == {"uci": expected, "san": san}
    assert (body["status"], body["reason"], body["playerMoves"], body["movesLeft"]) == ("playing", None, 1, None)
    assert body["fen"] == board.fen() and body["legalMoves"] == sorted(m.uci() for m in board.legal_moves)
    held = play(client, "opp-hold", ["d6e6"]).json()
    assert (held["status"], held["movesLeft"]) == ("playing", 29), "a draw goal counts down"


def test_the_players_finishing_move_does_not_ask_the_engine(computer_client, endgames_dir, monkeypatch) -> None:
    client = computer_client([], endgames_dir=endgames_dir)
    engine = services_of(client).engine
    calls = []
    original = engine.submit
    monkeypatch.setattr(engine, "submit", lambda *args, **kwargs: calls.append(args) or original(*args, **kwargs))
    body = play(client, "rook-one", ["h1h8"]).json()
    assert (body["status"], body["reason"], body["reply"], body["legalMoves"]) == ("passed", "checkmate", None, [])
    assert calls == [], "a finished board is never sent to the engine"


def test_illegal_move_even_length_too_long_and_malformed_bodies_are_400(computer_client, endgames_dir) -> None:
    client = computer_client([], endgames_dir=endgames_dir)
    for moves, detail in ((["e1e3"], "Illegal move (move 1)"),
                          (["e1e2", "e5e4", "zzzz"], "Illegal move (move 3)"),
                          (["e1e2", "e5e4"], "The moves must end with your move"),
                          (["e1e2"] * 301, "This attempt is too long; start again"),
                          ([], "Invalid moves"), ("e1e2", "Invalid moves"), (None, "Invalid moves")):
        answer = play(client, "queen-box", moves)
        assert (answer.status_code, answer.json()["detail"]) == (400, detail), moves
    foreign = client.post("/api/endgames/queen-box/play", json={"moves": ["e1e2"]},
                          headers={"Origin": "https://elsewhere.example"})
    assert foreign.status_code == 403, "the play route is origin-checked"


def test_an_oversized_body_is_413(computer_client, endgames_dir) -> None:
    client = computer_client([], endgames_dir=endgames_dir)
    answer = play(client, "queen-box", ["e1e2"] * 700)  # about 5.6 KB, over the default 4 KB limit
    assert answer.status_code == 413


def test_503_when_the_engine_is_unavailable(computer_client, endgames_dir) -> None:
    client = computer_client(installed=False, endgames_dir=endgames_dir)
    listed = client.get("/api/endgames").json()
    assert (listed["installed"], listed["available"], listed["reason"]) == (True, False, "No chess engine is installed")
    refused = play(client, "queen-box", ["e1e2"])
    assert (refused.status_code, refused.json()["detail"]) == (503, "No chess engine is installed")
    finished = play(client, "rook-one", ["h1h8"])
    assert finished.status_code == 200 and finished.json()["status"] == "passed", \
        "an attempt the player's move ends is answered without the engine"


def test_503_busy_when_the_queue_is_at_the_refusal_threshold(computer_client, endgames_dir, monkeypatch) -> None:
    client = computer_client([], endgames_dir=endgames_dir)
    engine = services_of(client).engine
    monkeypatch.setattr(engine, "queued_count", lambda: 16)
    busy = play(client, "queen-box", ["e1e2"])
    assert (busy.status_code, busy.json()["detail"]) == (503, engine_module.BUSY)
    monkeypatch.setattr(engine, "queued_count", lambda: 15)
    assert play(client, "queen-box", ["e1e2"]).status_code == 200, "below the threshold the defender answers"


def test_the_wait_limit_cancels_the_engine_request_and_answers_busy(computer_client, endgames_dir, monkeypatch) -> None:
    client = computer_client(["--delay", "4"], grace=10.0, endgames_dir=endgames_dir,
                             gameplay=settings(wait_limit_seconds=1))
    engine = services_of(client).engine
    cancelled = []
    original = engine.cancel
    monkeypatch.setattr(engine, "cancel", lambda ticket: cancelled.append(ticket.request_id) or original(ticket))
    started = time.monotonic()
    answer = play(client, "queen-box", ["e1e2"])
    elapsed = time.monotonic() - started
    assert (answer.status_code, answer.json()["detail"]) == (503, engine_module.BUSY)
    assert 0.9 <= elapsed < 3.5, elapsed
    assert len(cancelled) == 1, "the waiting engine request was cancelled"
    assert engine.queued_count() == 0


def test_more_than_the_per_minute_limit_is_429(computer_client, computer_clock, endgames_dir) -> None:
    client = computer_client([], endgames_dir=endgames_dir, gameplay=settings(play_per_minute=2))
    assert [play(client, "rook-one", ["h1h8"]).status_code for _ in range(2)] == [200, 200]
    refused = play(client, "rook-one", ["h1h8"])
    assert refused.status_code == 429 and refused.headers["Retry-After"] == "60"
    computer_clock.advance(61)
    assert play(client, "rook-one", ["h1h8"]).status_code == 200, "the window slides"
