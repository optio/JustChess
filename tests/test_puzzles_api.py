"""P2 U5 puzzle routes in ``justchess/api.py``: W3, BR2.4.

The puzzle folder is the fixture set from ``tests/fixtures/puzzle_set.py``
written to ``tmp_path`` and passed through ``JUSTCHESS_PUZZLES_DIR``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess.api import create_app
from tests.fixtures.puzzle_set import write_puzzle_dir

DETAIL_KEYS = {"id", "theme", "label", "fen", "setup", "playerMoves", "rating", "side", "afterSetup", "legalMoves", "check"}


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, puzzles_dir: Path):
    monkeypatch.setenv("JUSTCHESS_PUZZLES_DIR", str(puzzles_dir))
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    return TestClient(create_app(db_path=tmp_path / "puzzles.sqlite3", engine_dir=tmp_path / "engines"))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with _start(tmp_path, monkeypatch, write_puzzle_dir(tmp_path / "puzzles")) as started:
        yield started


def check(client: TestClient, theme: str, puzzle_id: str, ply, uci, **headers: str):
    return client.post(f"/api/puzzles/{theme}/{puzzle_id}/check", json={"ply": ply, "uci": uci}, headers=headers)


def hint(client: TestClient, theme: str, puzzle_id: str, ply, level):
    return client.post(f"/api/puzzles/{theme}/{puzzle_id}/hint", json={"ply": ply, "level": level})


def test_the_theme_list_has_labels_and_counts(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    response = client.get("/api/puzzles")
    assert response.status_code == 200
    assert response.json() == [
        {"theme": "fork", "label": "Forks", "count": 2}, {"theme": "pin", "label": "Pins", "count": 2},
        {"theme": "skewer", "label": "Skewers", "count": 2},
        {"theme": "discoveredAttack", "label": "Discovered attacks", "count": 2},
        {"theme": "mateIn1", "label": "Mate in 1", "count": 2}, {"theme": "mateIn2", "label": "Mate in 2", "count": 2},
    ]
    with _start(tmp_path, monkeypatch, tmp_path / "missing") as empty:
        assert empty.get("/api/puzzles").json() == [], "not installed: no themes, and no crash"


def test_a_theme_lists_its_puzzles_in_rating_order(client: TestClient) -> None:
    assert client.get("/api/puzzles/mateIn1").json() == [{"id": "Rk001", "rating": 600}, {"id": "Fo001", "rating": 900}]
    for path in ("/api/puzzles/nope", "/api/puzzles/Fork", "/api/puzzles/..%2Fetc"):
        response = client.get(path)
        assert response.status_code == 404, path


def test_the_detail_never_carries_the_solution(client: TestClient) -> None:
    response = client.get("/api/puzzles/mateIn2/Bk001")
    assert response.status_code == 200
    detail = response.json()
    assert set(detail) == DETAIL_KEYS
    assert (detail["setup"], detail["playerMoves"], detail["side"], detail["label"]) == ("a7a6", 2, "white", "Mate in 2")
    assert detail["afterSetup"] == "2r3k1/5ppp/p7/8/8/8/P2Q1PPP/3R2K1 w - - 0 2"
    assert "d2d8" in detail["legalMoves"] and detail["check"] is False
    assert "moves" not in detail and "d1d8" not in response.text, "the final solution move is nowhere in the answer"
    assert client.get("/api/puzzles/mateIn1/Fo001").json()["side"] == "black", "the side to move after the set-up"
    assert client.get("/api/puzzles/mateIn2/Zz999").status_code == 404
    assert client.get("/api/puzzles/mateIn2/bad-id").status_code == 404


def test_a_correct_move_returns_the_reply_and_the_last_one_solves(client: TestClient) -> None:
    first = check(client, "mateIn2", "Bk001", 1, "d2d8")
    assert first.status_code == 200
    data = first.json()
    assert (data["result"], data["reply"], data["check"]) == ("correct", "c8d8", True)
    assert data["replyFen"] == "3r2k1/5ppp/p7/8/8/8/P4PPP/3R2K1 w - - 0 3"
    assert "d1d8" in data["legalMoves"]
    last = check(client, "mateIn2", "Bk001", 3, "d1d8").json()
    assert last["result"] == "solved" and last["check"] is True and "reply" not in last


def test_a_wrong_move_leaks_no_solution(client: TestClient) -> None:
    response = check(client, "mateIn2", "Bk001", 1, "d2d7")
    assert response.status_code == 200
    assert response.json() == {"result": "wrong"}
    assert check(client, "fork", "Fk002", 1, "d5b6").json() == {"result": "wrong"}, "a legal non-solution move"


def test_an_alternative_mate_counts_as_solved(client: TestClient) -> None:
    assert check(client, "mateIn1", "Rk001", 1, "e1e8").json()["result"] == "solved"
    assert check(client, "mateIn1", "Rk001", 1, "d1d8").json()["result"] == "solved"


def test_hints_at_each_level_and_the_400_and_404_cases(client: TestClient) -> None:
    assert hint(client, "mateIn2", "Bk001", 1, "piece").json() == {"from": "d2"}
    assert hint(client, "mateIn2", "Bk001", 1, "move").json() == {"uci": "d2d8"}
    solution = hint(client, "mateIn2", "Bk001", 3, "solution").json()
    assert solution["line"] == ["d1d8"] and len(solution["fens"]) == 1
    full = hint(client, "mateIn2", "Bk001", 1, "solution").json()
    assert full["line"] == ["d2d8", "c8d8", "d1d8"] and len(full["fens"]) == 3
    for ply in (0, 2, 5, -1, "1", True, None):
        response = check(client, "mateIn2", "Bk001", ply, "d2d8")
        assert (response.status_code, response.json()) == (400, {"detail": "Invalid ply"}), ply
    for uci in ("d2d9", "e2e4", "D2D8", 42):
        assert check(client, "mateIn2", "Bk001", 1, uci).json() == {"detail": "Illegal move"}, uci
    assert hint(client, "mateIn2", "Bk001", 1, "everything").status_code == 400
    assert check(client, "mateIn2", "Zz999", 1, "d2d8").status_code == 404
    assert hint(client, "nope", "Bk001", 1, "piece").status_code == 404
    refused = check(client, "mateIn2", "Bk001", 1, "d2d8", origin="https://evil.example")
    assert refused.status_code == 403, "the POSTs are origin-checked"
    too_big = client.post("/api/puzzles/mateIn2/Bk001/check", content=b"{" + b" " * 5000 + b"}",
                          headers={"content-type": "application/json"})
    assert too_big.status_code == 413, "the POSTs are size-limited"


def test_the_puzzle_page_route_serves_the_shell(client: TestClient) -> None:
    for path in ("/learn/tactics/fork", "/learn/tactics/unknown"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert '<main id="app"' in response.text and "/static/js/app.js" in response.text
