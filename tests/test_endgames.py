"""P2 U6 endgame catalog loader (BR1.1): bad positions are skipped with a warning, a missing folder is not installed."""

from __future__ import annotations

import logging
from pathlib import Path

from justchess import endgames

GOOD = {
    "queen-mate": ("8/8/8/4k3/8/8/8/3QK3 w - - 0 1", "mate"),
    "rook-mate": ("8/8/8/4k3/8/8/8/R3K3 w - - 0 1", "mate"),
    "king-pawn": ("8/8/4k3/8/4K3/8/4P3/8 w - - 0 1", "promote"),
    "opposition": ("8/8/3k4/8/4K3/4P3/8/8 b - - 0 1", "draw"),
}


def entry(position_id: str, fen: str, goal: str, title: str = "A title", hint: str = "A hint.") -> str:
    return f"  - id: {position_id}\n    title: {title}\n    fen: {fen}\n    goal: {goal}\n    hint: {hint}\n"


def write_folder(folder: Path, extra: dict[str, list[str]] | None = None) -> Path:
    """A valid folder with three positions per category, plus ``extra`` entries appended per category."""
    folder.mkdir(parents=True, exist_ok=True)
    for category, (fen, goal) in GOOD.items():
        rows = [entry(f"{category}-{n}", fen, goal) for n in (1, 2, 3)] + (extra or {}).get(category, [])
        (folder / f"{category}.yaml").write_text("positions:\n" + "".join(rows), encoding="utf-8")
    return folder


def test_a_valid_folder_loads_in_category_order(tmp_path) -> None:
    catalog = endgames.load_catalog(write_folder(tmp_path / "endgames"))
    assert catalog.installed and catalog.skipped == 0 and len(catalog.positions) == 12
    assert [c["id"] for c in catalog.categories()] == list(endgames.CATEGORIES)
    assert catalog.place_of(catalog.get("rook-mate-2")) == (2, 3)
    assert catalog.next_of(catalog.get("opposition-3")) == "queen-mate-1", "next wraps round"


def test_bad_fen_finished_position_wrong_side_and_duplicate_id_are_each_skipped_with_a_warning(tmp_path, caplog) -> None:
    extra = {
        "queen-mate": [entry("bad-fen", "not/a/fen w - - 0 1", "mate"),
                       entry("finished", "k7/1Q6/1K6/8/8/8/8/8 b - - 0 1", "mate"),  # Black is checkmated already
                       entry("wrong-side", "8/8/8/4k3/8/8/8/3QK3 b - - 0 1", "mate")],  # Black to move has no queen
        "rook-mate": [entry("queen-mate-1", "8/8/8/4k3/8/8/8/R3K3 w - - 0 1", "mate")],  # duplicate across files
    }
    with caplog.at_level(logging.WARNING, logger="justchess.endgames"):
        catalog = endgames.load_catalog(write_folder(tmp_path / "endgames", extra))
    assert catalog.skipped == 4 and len(catalog.positions) == 12
    for name, why in (("bad-fen", "not a valid FEN"), ("finished", "already over"),
                      ("wrong-side", "needs a queen or a rook"), ("queen-mate-1", "duplicate id")):
        assert f"Skipped endgame position {name}" in caplog.text and why in caplog.text, name
        assert catalog.get(name) is None or name == "queen-mate-1"
    assert catalog.get("queen-mate-1").category == "queen-mate", "the first one stays"


def test_goal_category_mismatch_unknown_fields_and_long_text_are_skipped(tmp_path, caplog) -> None:
    extra = {
        "king-pawn": [entry("kp-mate", "8/8/4k3/8/4K3/8/4P3/8 w - - 0 1", "mate"),
                      entry("kp-long", "8/8/4k3/8/4K3/8/4P3/8 w - - 0 1", "promote", hint="x" * 201),
                      "  - id: kp-extra\n    title: T\n    fen: 8/8/4k3/8/4K3/8/4P3/8 w - - 0 1\n"
                      "    goal: promote\n    hint: H\n    solution: e4\n"],
    }
    with caplog.at_level(logging.WARNING, logger="justchess.endgames"):
        catalog = endgames.load_catalog(write_folder(tmp_path / "endgames", extra))
    assert catalog.skipped == 3
    assert "does not suit the king-pawn category" in caplog.text
    assert "at most 200 characters" in caplog.text and "unknown field 'solution'" in caplog.text


def test_a_missing_folder_means_not_installed(tmp_path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="justchess.endgames"):
        catalog = endgames.load_catalog(tmp_path / "nowhere")
    assert not catalog.installed and catalog.positions == () and catalog.categories() == []
    assert "does not exist" in caplog.text
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not endgames.load_catalog(empty).installed, "a folder with no valid position is not installed either"


def test_an_unknown_file_is_ignored_and_an_unreadable_file_is_skipped_whole(tmp_path, caplog) -> None:
    folder = write_folder(tmp_path / "endgames")
    (folder / "bishop-mate.yaml").write_text("positions:\n" + entry("bishop-1", GOOD["queen-mate"][0], "mate"),
                                             encoding="utf-8")
    (folder / "opposition.yaml").write_text("positions: [unclosed\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="justchess.endgames"):
        catalog = endgames.load_catalog(folder)
    assert catalog.get("bishop-1") is None, "only the four category files are read"
    assert catalog.in_category("opposition") == [] and len(catalog.positions) == 9
    assert "Skipped endgame file opposition.yaml" in caplog.text
    assert "Only 0 valid endgame position(s) for opposition" in caplog.text


def test_ids_are_only_compared_and_the_store_loads_once(tmp_path) -> None:
    store = endgames.EndgameStore(write_folder(tmp_path / "endgames"))
    first = store.catalog()
    assert store.catalog() is first
    for probe in ("../queen-mate", "QUEEN-MATE-1", "", None, 42, "a" * 41):
        assert first.get(probe) is None, probe
