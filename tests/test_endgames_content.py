"""P2 U6 shipped endgame content (BR1.2): the endgames/ folder loads cleanly and covers every category."""

from __future__ import annotations

import logging
from pathlib import Path

import chess
import pytest

from justchess import endgames

ROOT = Path(__file__).resolve().parent.parent
SHIPPED = endgames.default_endgames_dir(ROOT)


@pytest.fixture(scope="module")
def catalog() -> endgames.EndgameCatalog:
    return endgames.load_catalog(SHIPPED)


def test_every_shipped_position_loads_and_none_is_skipped(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="justchess.endgames"):
        loaded = endgames.load_catalog(SHIPPED)
    assert loaded.installed and loaded.skipped == 0
    assert "Skipped" not in caplog.text and "Only" not in caplog.text, caplog.text
    for position in loaded.positions:
        board = chess.Board(position.fen)
        assert board.is_valid() and not board.is_game_over(claim_draw=True), position.id


def test_there_are_at_least_three_positions_per_category(catalog) -> None:
    counts = endgames.summarise(catalog.positions)
    assert set(counts) == set(endgames.CATEGORIES)
    assert all(count >= endgames.MIN_PER_CATEGORY for count in counts.values()), counts
    assert [p.order for p in catalog.in_category("queen-mate")] == [1, 2, 3]


def test_every_goal_fits_its_category_and_the_material(catalog) -> None:
    for position in catalog.positions:
        assert position.goal in endgames.CATEGORY_GOALS[position.category], position.id
        board = chess.Board(position.fen)
        player = board.turn
        if position.goal == "mate":
            assert board.pieces(chess.QUEEN, player) or board.pieces(chess.ROOK, player), position.id
        if position.goal == "promote":
            assert board.pieces(chess.PAWN, player), position.id
    goals = {position.goal for position in catalog.positions if position.category in ("king-pawn", "opposition")}
    assert goals == {"promote", "draw"}, "both pawn goals are taught"


def test_every_position_has_a_hint_and_a_title_in_plain_text(catalog) -> None:
    for position in catalog.positions:
        assert 1 <= len(position.hint) <= endgames.HINT_MAX, position.id
        assert 1 <= len(position.title) <= endgames.TITLE_MAX, position.id
        assert "<" not in position.hint and "\n" not in position.hint, position.id
    assert len({position.hint for position in catalog.positions}) == len(catalog.positions), "no hint is copied"
