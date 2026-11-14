"""U6 lesson loader (``justchess/lessons.py``): BR1.1-BR1.4.

Each test writes short YAML or JSON lessons into its own ``tmp_path`` folder;
only ``test_shipped_lessons_load_and_replay`` reads the shipped ``lessons/``
folder, and no test changes it.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import chess
import pytest

from justchess import lessons
from justchess.lessons import LessonStore, load_catalog

ROOT = Path(__file__).resolve().parent.parent

GOOD_YAML = """\
name: Test Opening
side: white
moves:
  - san: e4
    note: Take the centre.
  - san: e5
    note: Black takes the centre too.
  - san: Nf3
    uci: g1f3
    note: Attack e5.
"""


def write(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def reasons(catalog: lessons.LessonCatalog) -> dict[str, str]:
    return {problem.file: problem.reason for problem in catalog.problems}


def test_shipped_lessons_load_and_replay() -> None:
    catalog = load_catalog(ROOT / "lessons")
    assert catalog.problems == ()
    expected = {
        "italian": ("Italian Game", "C53", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3"]),
        "monte-carlo": ("French Exchange: Monte Carlo Variation", "C01", ["e4", "e6", "d4", "d5", "exd5", "exd5", "c4"]),
    }
    assert set(expected) <= set(catalog.lessons), "the two U6 lessons are still shipped (P2 U5 adds more)"
    for lesson_id, (name, eco, line) in expected.items():
        assert catalog.lessons[lesson_id]["kind"] == "opening", "a file without kind stays an opening"
        lesson = catalog.lessons[lesson_id]
        assert (lesson["name"], lesson["eco"], lesson["side"]) == (name, eco, "white")
        assert [step["san"] for step in lesson["steps"]] == line
        assert 2 <= len(lesson["objectives"]) <= 3
        board = chess.Board()
        for step in lesson["steps"]:
            assert step["fenBefore"] == board.fen(), f"{lesson_id} ply {step['ply']} starts where the last one ended"
            assert step["note"].strip(), f"{lesson_id} {step['san']} has a note"
            board.push_uci(step["uci"])
            assert step["fenAfter"] == board.fen()
        assert not board.is_game_over(), f"{lesson_id} plays its full line"


NEW_LESSONS = {
    "opening": {"ruy-lopez", "sicilian", "french", "caro-kann", "queens-gambit", "london", "kings-indian", "scandinavian"},
    "trap": {"legals-mate", "fried-liver", "fishing-pole", "englund-gambit-trap"},
    "defence": {"scholars-mate-defence", "fried-liver-defence", "early-queen-raids", "wayward-queen"},
}


def test_every_shipped_p2_lesson_loads_annotated_with_its_kind_and_length() -> None:
    """P2 U5 BR1.3: the 16 new lessons load with no skip, a note on every ply, 8+ plies (traps 6+)."""
    catalog = load_catalog(ROOT / "lessons")
    assert catalog.problems == (), catalog.problems
    counts = catalog.counts_by_kind()
    assert counts["opening"] >= 8 + 2 and counts["trap"] >= 4 and counts["defence"] >= 4, counts
    for kind, ids in NEW_LESSONS.items():
        for lesson_id in ids:
            lesson = catalog.lessons.get(lesson_id)
            assert lesson is not None, f"{lesson_id} is shipped"
            assert lesson["kind"] == kind, lesson_id
            assert len(lesson["steps"]) >= (6 if kind == "trap" else 8), lesson_id
            assert all(step["note"].strip() for step in lesson["steps"]), lesson_id
            assert lesson["objectives"], f"{lesson_id} has objectives"
    assert {item["id"] for item in catalog.summaries("trap")} == NEW_LESSONS["trap"]


def test_missing_required_field_is_skipped_with_its_reason(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    write(tmp_path, "good.yaml", GOOD_YAML)
    write(tmp_path, "no-side.yaml", GOOD_YAML.replace("side: white\n", ""))
    write(tmp_path, "no-note.yaml", GOOD_YAML.replace("    note: Attack e5.\n", ""))
    with caplog.at_level(logging.WARNING, logger="justchess.lessons"):
        catalog = load_catalog(tmp_path)
    assert set(catalog.lessons) == {"good"}, "valid files still load"
    found = reasons(catalog)
    assert found["no-side.yaml"] == "missing required field 'side'"
    assert found["no-note.yaml"] == "move 3: missing required field 'note'"
    logged = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert "Skipped lesson file no-side.yaml: missing required field 'side'" in logged


def test_illegal_san_is_skipped(tmp_path: Path) -> None:
    write(tmp_path, "bad.yaml", GOOD_YAML.replace("san: e5", "san: Ke2"))
    catalog = load_catalog(tmp_path)
    assert catalog.lessons == {}
    assert reasons(catalog) == {"bad.yaml": "move 2: 'Ke2' is not legal in this position"}


def test_san_and_uci_that_disagree_are_skipped(tmp_path: Path) -> None:
    write(tmp_path, "bad.yaml", GOOD_YAML.replace("uci: g1f3", "uci: g1h3"))
    write(tmp_path, "garbled.yaml", GOOD_YAML.replace("uci: g1f3", "uci: knight"))
    catalog = load_catalog(tmp_path)
    assert catalog.lessons == {}
    assert reasons(catalog)["bad.yaml"] == "move 3: SAN 'Nf3' and UCI 'g1h3' disagree (the SAN is g1f3)"
    assert reasons(catalog)["garbled.yaml"] == "move 3: uci 'knight' is not a UCI move"


def test_duplicate_id_is_skipped(tmp_path: Path) -> None:
    write(tmp_path, "opening.json", json.dumps({"name": "From JSON", "side": "white",
                                                 "moves": [{"san": "d4", "note": "Centre."}]}))
    write(tmp_path, "opening.yaml", GOOD_YAML)
    catalog = load_catalog(tmp_path)
    assert catalog.lessons["opening"]["name"] == "From JSON", "the first file in name order wins"
    assert reasons(catalog) == {"opening.yaml": "duplicate id 'opening' (already loaded from opening.json)"}


def test_oversized_file_and_symlink_are_skipped(tmp_path: Path) -> None:
    write(tmp_path, "good.yaml", GOOD_YAML)
    write(tmp_path, "huge.yaml", GOOD_YAML + "# " + "x" * lessons.MAX_FILE_BYTES + "\n")
    outside = write(tmp_path.parent, f"{tmp_path.name}-outside.yaml", GOOD_YAML)
    (tmp_path / "linked.yaml").symlink_to(outside)
    (tmp_path / "folder.yaml").mkdir()
    catalog = load_catalog(tmp_path)
    assert set(catalog.lessons) == {"good"}
    assert reasons(catalog) == {
        "huge.yaml": "file too large",
        "linked.yaml": "symlinks are not read",
        "folder.yaml": "not a regular file",
    }


def test_json_and_yaml_are_both_accepted_and_yaml_is_read_safely(tmp_path: Path) -> None:
    write(tmp_path, "from-yaml.yml", GOOD_YAML)
    write(tmp_path, "from-json.json", json.dumps({
        "name": "JSON Opening", "side": "black", "eco": "B20", "aliases": ["Sicilian"],
        "moves": [{"san": "e4", "uci": "e2e4", "note": "White starts."},
                  {"san": "c5", "note": "The Sicilian.", "alternatives": [{"san": "e5", "note": "Classical."}]}],
        "objectives": ["Fight for d4."],
    }))
    write(tmp_path, "unsafe.yaml", "name: !!python/object/apply:os.system ['echo hacked']\nside: white\nmoves: []\n")
    write(tmp_path, "typo.yaml", GOOD_YAML + "objectifs: [one]\n")
    catalog = load_catalog(tmp_path)
    assert set(catalog.lessons) == {"from-yaml", "from-json"}
    sicilian = catalog.lessons["from-json"]
    assert (sicilian["side"], sicilian["eco"], sicilian["aliases"]) == ("black", "B20", ["Sicilian"])
    assert sicilian["steps"][1]["alternatives"] == [{"san": "e5", "note": "Classical."}]
    found = reasons(catalog)
    assert found["unsafe.yaml"].startswith("invalid YAML"), "safe_load refuses python tags"
    assert found["typo.yaml"] == "unknown field 'objectifs'"


def test_steps_carry_the_right_fens_and_legal_moves(tmp_path: Path) -> None:
    write(tmp_path, "endgame.yaml", (
        "name: Promotion\nside: black\nstart: 8/8/8/8/8/2k5/p7/2K5 b - - 0 1\n"
        "moves:\n  - san: a1=Q+\n    uci: a2a1q\n    note: Promote, and it is mate.\n"
    ))
    lesson = load_catalog(tmp_path).lessons["endgame"]
    assert lesson["start"] == "8/8/8/8/8/2k5/p7/2K5 b - - 0 1"
    (step,) = lesson["steps"]
    assert step["side"] == "black", "the first ply belongs to the side to move in the start FEN"
    assert step["fenBefore"] == "8/8/8/8/8/2k5/p7/2K5 b - - 0 1"
    assert step["fenAfter"] == "8/8/8/8/8/2k5/8/q1K5 w - - 0 2"
    board = chess.Board(step["fenBefore"])
    assert step["legalBefore"] == sorted(move.uci() for move in board.legal_moves)
    assert step["legalBefore"] == sorted(step["legalBefore"])
    assert "a2a1q" in step["legalBefore"] and "a2a1n" in step["legalBefore"]
    assert (step["uci"], step["ply"]) == ("a2a1q", 0)
    assert step["san"] == "a1=Q#", "the SAN is normalised (the file wrote a1=Q+, but it is mate)"


def test_bad_start_eco_and_id_are_reported(tmp_path: Path) -> None:
    write(tmp_path, "bad-start.yaml", GOOD_YAML + "start: not a fen\n")
    write(tmp_path, "bad-eco.yaml", GOOD_YAML + "eco: Z99\n")
    write(tmp_path, "Bad_Name.yaml", GOOD_YAML)
    write(tmp_path, "empty.yaml", "")
    found = reasons(load_catalog(tmp_path))
    assert found["bad-start.yaml"] == "start is not a valid FEN"
    assert found["bad-eco.yaml"] == "eco must look like C53 (a letter A-E and two digits)"
    assert found["Bad_Name.yaml"].startswith("the file name is not a valid lesson id")
    assert found["empty.yaml"] == "the file must hold a mapping of fields"


def test_a_new_file_is_picked_up_on_the_next_list_call(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    write(tmp_path, "first.yaml", GOOD_YAML)
    first = store.catalog()
    assert set(first.lessons) == {"first"}
    assert store.catalog() is first, "an unchanged folder is not rescanned"
    write(tmp_path, "second.yaml", GOOD_YAML.replace("Test Opening", "Another"))
    second = store.catalog()
    assert second is not first and set(second.lessons) == {"first", "second"}
    assert set(first.lessons) == {"first"}, "the old catalog is never changed in place"
    os.remove(tmp_path / "first.yaml")
    assert set(store.catalog().lessons) == {"second"}


def test_a_lesson_without_kind_is_an_opening_and_kind_is_in_its_summary(tmp_path: Path) -> None:
    """P2 U5 BR1.1: no kind means opening; the kind travels in the lesson and in the summary."""
    write(tmp_path, "plain.yaml", GOOD_YAML)
    write(tmp_path, "trap.yaml", GOOD_YAML.replace("Test Opening", "A Trap") + "kind: trap\n")
    catalog = load_catalog(tmp_path)
    assert catalog.problems == ()
    assert catalog.lessons["plain"]["kind"] == "opening"
    assert catalog.lessons["trap"]["kind"] == "trap"
    assert [(item["id"], item["kind"]) for item in catalog.summaries()] == [("trap", "trap"), ("plain", "opening")]


def test_an_unknown_kind_skips_the_file_with_its_reason(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    write(tmp_path, "good.yaml", GOOD_YAML + "kind: defence\n")
    write(tmp_path, "odd.yaml", GOOD_YAML + "kind: endgame\n")
    write(tmp_path, "number.yaml", GOOD_YAML + "kind: 3\n")
    with caplog.at_level(logging.WARNING, logger="justchess.lessons"):
        catalog = load_catalog(tmp_path)
    assert set(catalog.lessons) == {"good"}, "valid files still load"
    assert reasons(catalog) == {
        "odd.yaml": "kind must be 'opening', 'trap' or 'defence'",
        "number.yaml": "kind must be 'opening', 'trap' or 'defence'",
    }
    assert "Skipped lesson file odd.yaml: kind must be 'opening', 'trap' or 'defence'" in caplog.text


def test_summaries_filter_by_kind_and_counts_cover_every_kind(tmp_path: Path) -> None:
    write(tmp_path, "one.yaml", GOOD_YAML)
    write(tmp_path, "two.yaml", GOOD_YAML.replace("Test Opening", "Second") + "kind: opening\n")
    write(tmp_path, "snare.yaml", GOOD_YAML.replace("Test Opening", "Snare") + "kind: trap\n")
    catalog = load_catalog(tmp_path)
    assert catalog.counts_by_kind() == {"opening": 2, "trap": 1, "defence": 0}
    assert [item["id"] for item in catalog.summaries("opening")] == ["two", "one"]
    assert [item["id"] for item in catalog.summaries("trap")] == ["snare"]
    assert catalog.summaries("defence") == []
    assert lessons.is_kind("trap") and not lessons.is_kind("Trap") and not lessons.is_kind(None)


def test_a_missing_folder_gives_an_empty_catalog_and_a_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="justchess.lessons"):
        catalog = LessonStore(tmp_path / "nowhere").catalog()
    assert (catalog.lessons, catalog.problems, catalog.dir_stamp) == ({}, (), "missing")
    assert any("does not exist" in record.getMessage() for record in caplog.records)
