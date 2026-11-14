"""P2 U5 puzzle loader (``justchess/puzzles.py``): BR2.1 validation and BR2.2 shipped set.

The validator tests write small theme files into ``tmp_path`` (built from
``tests/fixtures/puzzle_set.py``); the shipped-set tests read the committed
``puzzles/`` folder and never change it.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

import pytest

from justchess import puzzles
from justchess.puzzles import PuzzleStore, load_puzzles, validate_puzzle
from tests.fixtures.puzzle_set import PUZZLES, write_puzzle_dir

ROOT = Path(__file__).resolve().parent.parent
SHIPPED = ROOT / "puzzles"
MAX_TOTAL_BYTES = 5 * 1024 * 1024


def fixture(theme: str, index: int = 0) -> dict:
    return copy.deepcopy(PUZZLES[theme][index])


def with_extra(theme: str, *extra: dict) -> dict[str, list[dict]]:
    """The fixture set with ``extra`` puzzles appended to one theme."""
    data = copy.deepcopy(PUZZLES)
    data[theme] = data[theme] + list(extra)
    return data


def test_a_valid_set_loads_sorted_by_rating(tmp_path: Path) -> None:
    catalog = load_puzzles(write_puzzle_dir(tmp_path / "puzzles"))
    assert catalog.installed and catalog.skipped == 0
    assert [entry["theme"] for entry in catalog.theme_list()] == list(puzzles.THEMES)
    assert all(entry["count"] == 2 for entry in catalog.theme_list())
    assert [puzzle["id"] for puzzle in catalog.puzzles("mateIn1")] == ["Rk001", "Fo001"], "easier first"
    assert catalog.get("mateIn2", "Bk001")["moves"] == ["a7a6", "d2d8", "c8d8", "d1d8"]
    assert catalog.get("mateIn2", "../x") is None and catalog.get("nope", "Bk001") is None
    assert validate_puzzle(fixture("fork"), "fork")["id"] == "Fk001"


def test_an_illegal_move_skips_the_puzzle_and_logs_its_id(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    bad = {**fixture("fork", 1), "id": "Bad01", "moves": ["h7h6", "d5c7", "e8e1", "c7a8"]}
    with caplog.at_level(logging.WARNING, logger="justchess.puzzles"):
        catalog = load_puzzles(write_puzzle_dir(tmp_path / "puzzles", with_extra("fork", bad)))
    assert [puzzle["id"] for puzzle in catalog.puzzles("fork")] == ["Fk001", "Fk002"]
    assert catalog.skipped == 1
    assert "Skipped puzzle Bad01 in fork.json: move 3 (e8e1) is illegal" in caplog.text
    with pytest.raises(puzzles.PuzzleError, match="not a UCI move"):
        validate_puzzle({**fixture("fork"), "moves": ["g7g6", "Nc7"]}, "fork")


def test_a_mate_theme_that_does_not_end_in_mate_is_skipped(tmp_path: Path) -> None:
    no_mate = {**fixture("mateIn1", 1), "id": "NoMt1", "moves": ["a7a6", "d1d7"]}
    catalog = load_puzzles(write_puzzle_dir(tmp_path / "puzzles", with_extra("mateIn1", no_mate)))
    assert catalog.get("mateIn1", "NoMt1") is None and catalog.skipped == 1
    with pytest.raises(puzzles.PuzzleError, match="mateIn1 must end in checkmate"):
        validate_puzzle(no_mate, "mateIn1")


def test_a_wrong_player_move_count_is_skipped() -> None:
    mate_in_two_as_one = {**fixture("mateIn2"), "theme": "mateIn1"}
    with pytest.raises(puzzles.PuzzleError, match="mateIn1 needs 1 player move"):
        validate_puzzle(mate_in_two_as_one, "mateIn1")
    odd = {**fixture("fork", 1), "moves": ["h7h6", "d5c7", "e8d7"]}
    with pytest.raises(puzzles.PuzzleError, match="must end with a player move"):
        validate_puzzle(odd, "fork")
    with pytest.raises(puzzles.PuzzleError, match="at least 2"):
        validate_puzzle({**fixture("fork"), "moves": ["g7g6"]}, "fork")


def test_a_puzzle_in_the_wrong_theme_file_or_with_bad_fields_is_skipped(tmp_path: Path) -> None:
    stray = fixture("pin")  # theme "pin" inside fork.json
    catalog = load_puzzles(write_puzzle_dir(tmp_path / "puzzles", with_extra("fork", stray)))
    assert len(catalog.puzzles("fork")) == 2 and catalog.skipped == 1
    with pytest.raises(puzzles.PuzzleError, match="does not match its file"):
        validate_puzzle(stray, "fork")
    with pytest.raises(puzzles.PuzzleError, match="rating"):
        validate_puzzle({**fixture("fork"), "rating": 99}, "fork")
    with pytest.raises(puzzles.PuzzleError, match="id must be"):
        validate_puzzle({**fixture("fork"), "id": "toolong1"}, "fork")
    with pytest.raises(puzzles.PuzzleError, match="unknown field"):
        validate_puzzle({**fixture("fork"), "solution": []}, "fork")
    # a file for the wrong theme, or one that is not JSON, is skipped as a whole
    folder = tmp_path / "puzzles"
    (folder / "skewer.json").write_text(json.dumps({"theme": "pin", "puzzles": PUZZLES["pin"]}), encoding="utf-8")
    (folder / "pin.json").write_text("{not json", encoding="utf-8")
    whole = load_puzzles(folder)
    assert whole.puzzles("skewer") == () and whole.puzzles("pin") == ()
    assert len(whole.puzzles("fork")) == 2, "the other files still load"


def test_every_shipped_puzzle_loads_with_no_skips() -> None:
    catalog = load_puzzles(SHIPPED)
    assert catalog.installed and catalog.skipped == 0
    for theme in puzzles.THEMES:
        found = catalog.puzzles(theme)
        assert [p["rating"] for p in found] == sorted(p["rating"] for p in found), f"{theme} is in rating order"
        assert len({p["id"] for p in found}) == len(found), f"{theme} has no duplicate ids"
        raw = json.loads((SHIPPED / f"{theme}.json").read_text(encoding="utf-8"))
        assert raw["source"] == puzzles.SOURCE and len(raw["puzzles"]) == len(found)


def test_each_shipped_theme_has_250_to_400_puzzles() -> None:
    counts = {entry["theme"]: entry["count"] for entry in load_puzzles(SHIPPED).theme_list()}
    assert set(counts) == set(puzzles.THEMES)
    assert all(250 <= count <= 400 for count in counts.values()), counts


def test_the_shipped_set_is_at_most_5_mb_and_credits_lichess() -> None:
    total = sum(path.stat().st_size for path in SHIPPED.iterdir() if path.is_file())
    assert total <= MAX_TOTAL_BYTES, f"puzzles/ takes {total} bytes"
    licence = (SHIPPED / "LICENSE.md").read_text(encoding="utf-8")
    assert "Lichess puzzle database" in licence and "CC0" in licence
    assert "https://database.lichess.org" in licence and "Popularity >= 80" in licence
    assets = (ROOT / "static" / "ASSETS.md").read_text(encoding="utf-8")
    assert "Lichess puzzle database" in assets and "CC0" in assets


def test_a_missing_folder_means_not_installed(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="justchess.puzzles"):
        store = PuzzleStore(tmp_path / "nowhere")
        catalog = store.catalog()
    assert (catalog.installed, catalog.themes, catalog.theme_list()) == (False, {}, [])
    assert catalog.puzzles("fork") == ()
    assert store.catalog() is catalog, "the folder is read once"
    assert "does not exist" in caplog.text
