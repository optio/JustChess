"""U6 lesson routes in ``justchess/api.py``: BR2.1-BR2.3 and the design review decisions.

* ``GET /api/lessons``: list shape, sorted by name, no problems or paths.
* ``GET /api/lessons/{id}``: the step shape (``fenBefore``/``fenAfter``...),
  the old ``before``/``final`` keys and the inline ``LESSONS`` dict gone, 404
  for a malformed or unknown id.
* ``POST /api/position/move``: legal, illegal, invalid FEN, bad UCI pattern,
  promotion, outcomes, and the U1 origin guard.

The lessons folder is a ``tmp_path`` passed through ``JUSTCHESS_LESSONS_DIR``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess import api
from justchess.api import create_app

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
LIST_KEYS = {"id", "name", "kind", "aliases", "eco", "side", "moves"}  # P2 U5 added "kind"
STEP_KEYS = {"ply", "side", "san", "uci", "note", "fenBefore", "fenAfter", "legalBefore", "alternatives"}
MOVE_KEYS = {"fen", "san", "legalMoves", "check", "outcome"}

ZEBRA = """\
name: zebra Gambit
side: black
eco: A00
aliases: [Z]
moves:
  - san: e4
    note: White opens.
  - san: d5
    note: Black strikes back.
    alternatives:
      - san: e5
        note: Classical.
objectives: [Strike the centre.]
"""


@pytest.fixture
def lessons_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "lessons"
    folder.mkdir()
    (folder / "zebra.yaml").write_text(ZEBRA, encoding="utf-8")
    (folder / "alpha.json").write_text(json.dumps({
        "name": "Alpha Opening", "side": "white",
        "moves": [{"san": "d4", "note": "Centre."}]}), encoding="utf-8")
    (folder / "broken.yaml").write_text("name: Broken\nside: white\nmoves:\n  - san: Qxf7\n    note: no\n", encoding="utf-8")
    return folder


@pytest.fixture
def client(tmp_path: Path, lessons_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JUSTCHESS_LESSONS_DIR", str(lessons_dir))
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    with TestClient(create_app(db_path=tmp_path / "lessons.sqlite3", engine_dir=tmp_path / "engines")) as started:
        yield started


def move(client: TestClient, fen: str, uci: str, **headers: str):
    return client.post("/api/position/move", json={"fen": fen, "uci": uci}, headers=headers)


def test_list_shape_and_sort_order(client: TestClient, lessons_dir: Path) -> None:
    response = client.get("/api/lessons")
    assert response.status_code == 200
    listed = response.json()
    assert [lesson["id"] for lesson in listed] == ["alpha", "zebra"], "sorted by name, ignoring case"
    assert all(set(lesson) == LIST_KEYS for lesson in listed)
    assert listed[1] == {"id": "zebra", "name": "zebra Gambit", "kind": "opening", "aliases": ["Z"], "eco": "A00",
                         "side": "black", "moves": 2}
    assert listed[0]["eco"] is None and listed[0]["aliases"] == []
    text = response.text
    assert "broken" not in text and str(lessons_dir) not in text, "no problems and no file paths are sent"


def test_detail_shape_and_the_old_keys_are_gone(client: TestClient) -> None:
    response = client.get("/api/lessons/zebra")
    assert response.status_code == 200
    lesson = response.json()
    assert set(lesson) == {"id", "name", "kind", "aliases", "eco", "side", "start", "objectives", "steps"}
    assert (lesson["start"], lesson["objectives"]) == ("startpos", ["Strike the centre."])
    first, second = lesson["steps"]
    assert all(set(step) == STEP_KEYS for step in lesson["steps"])
    assert "before" not in first and "final" not in lesson
    assert (first["fenBefore"], first["uci"], first["side"]) == (START_FEN, "e2e4", "white")
    assert second["fenBefore"] == first["fenAfter"] and second["side"] == "black"
    assert len(first["legalBefore"]) == 20
    assert second["alternatives"] == [{"san": "e5", "note": "Classical."}]
    assert not hasattr(api, "LESSONS"), "the inline lesson dict is removed"


@pytest.mark.parametrize("lesson_id", ["broken", "missing", "Zebra", "zebra.yaml", "-zebra", "z" * 49, "zebra%20", "..zebra"])
def test_malformed_and_unknown_ids_are_404(client: TestClient, lesson_id: str) -> None:
    response = client.get(f"/api/lessons/{lesson_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Lesson not found"}


def test_a_new_lesson_file_appears_on_the_next_list_call(client: TestClient, lessons_dir: Path) -> None:
    assert len(client.get("/api/lessons").json()) == 2
    (lessons_dir / "middle.yml").write_text(ZEBRA.replace("zebra Gambit", "Middle Game"), encoding="utf-8")
    assert [lesson["id"] for lesson in client.get("/api/lessons").json()] == ["alpha", "middle", "zebra"]
    assert client.get("/api/lessons/middle").status_code == 200


def test_position_move_plays_a_legal_move(client: TestClient) -> None:
    response = move(client, START_FEN, "g1f3")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == MOVE_KEYS
    assert data["fen"] == "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1"
    assert (data["san"], data["check"], data["outcome"]) == ("Nf3", False, None)
    assert len(data["legalMoves"]) == 20 and data["legalMoves"] == sorted(data["legalMoves"])


@pytest.mark.parametrize(("fen", "uci", "detail"), [
    (START_FEN, "e2e5", "Illegal move"),
    (START_FEN, "e2-e4", "Illegal move"),
    (START_FEN, "E2E4", "Illegal move"),
    ("not a fen", "e2e4", "Invalid position"),
    ("8/8/8/8/8/8/8/8 w - - 0 1", "e2e4", "Invalid position"),
    ("4k3/8/8/8/8/8/8/4K2K w - - 0 1", "e1e2", "Invalid position"),
])
def test_position_move_refuses_bad_input(client: TestClient, fen: str, uci: str, detail: str) -> None:
    response = move(client, fen, uci)
    assert response.status_code == 400
    assert response.json() == {"detail": detail}


def test_position_move_promotion_needs_its_letter(client: TestClient) -> None:
    fen = "8/P7/8/8/8/8/8/k6K w - - 0 1"
    assert move(client, fen, "a7a8").json() == {"detail": "Illegal move"}
    data = move(client, fen, "a7a8n").json()
    assert (data["san"], data["fen"]) == ("a8=N", "N7/8/8/8/8/8/8/k6K b - - 0 1")
    queen = move(client, fen, "a7a8q").json()
    assert (queen["san"], queen["check"]) == ("a8=Q+", True)


def test_position_move_reports_checkmate_and_stalemate(client: TestClient) -> None:
    fools = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
    mate = move(client, fools, "d8h4").json()
    assert (mate["san"], mate["check"], mate["outcome"], mate["legalMoves"]) == ("Qh4#", True, "checkmate", [])
    stale = move(client, "k7/8/1Q6/8/8/8/8/7K w - - 0 1", "b6c7").json()
    assert (stale["outcome"], stale["check"]) == ("stalemate", False)
    bare = move(client, "k7/8/8/8/8/8/1r6/K7 w - - 0 1", "a1b2").json()
    assert bare["outcome"] == "insufficient_material"


def test_position_move_refuses_a_foreign_origin(client: TestClient) -> None:
    refused = move(client, START_FEN, "e2e4", origin="https://evil.example")
    assert refused.status_code == 403
    allowed = move(client, START_FEN, "e2e4", origin="http://testserver")
    assert allowed.status_code == 200


def test_the_kind_filter_lists_one_kind(client: TestClient, lessons_dir: Path) -> None:
    """P2 U5 BR1.2."""
    (lessons_dir / "snare.yaml").write_text(ZEBRA.replace("zebra Gambit", "Snare") + "kind: trap\n", encoding="utf-8")
    assert [item["id"] for item in client.get("/api/lessons?kind=trap").json()] == ["snare"]
    assert [item["id"] for item in client.get("/api/lessons?kind=opening").json()] == ["alpha", "zebra"]
    assert client.get("/api/lessons?kind=defence").json() == []
    assert [item["id"] for item in client.get("/api/lessons").json()] == ["alpha", "snare", "zebra"], "no kind: all"


@pytest.mark.parametrize("kind", ["endgame", "Trap", "", "opening,trap"])
def test_an_unknown_kind_is_400(client: TestClient, kind: str) -> None:
    response = client.get("/api/lessons", params={"kind": kind})
    assert response.status_code == 400
    assert response.json() == {"detail": "Unknown lesson kind"}


def test_the_learn_paths_serve_the_page_shell(client: TestClient) -> None:
    for path in ("/learn", "/learn/italian", "/learn/not-a-lesson", "/learn/tactics/fork"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert '<main id="app"' in response.text and "/static/js/app.js" in response.text
