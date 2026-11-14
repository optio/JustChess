"""Data-layer helpers for the U4 computer-room tests: create a room, play moves as a seat, read the game."""

from __future__ import annotations

from justchess import games, rooms
from justchess.db import Database


def new_computer_room(db: Database, now: float, level: str = "casual", white_slot: str = "A") -> tuple[str, str]:
    """Create a computer room with game 1 playing; return (code, seat A's token)."""
    with db.transaction() as conn:
        room, _seat, token = rooms.create_computer_room(conn, now, level, white_slot)
        games.create_computer_game(conn, room.code, white_slot, now)
    return room.code, token


def current(db: Database, code: str) -> games.Game:
    with db.read() as conn:
        return games.current_game(conn, code)


def moves_of(db: Database, code: str) -> list[str]:
    game = current(db, code)
    with db.read() as conn:
        return [move.uci for move in games.load_moves(conn, game.game_id)]


def play(db: Database, code: str, now: float, ucis: list[str], computer: bool = True) -> games.Game:
    """Play each move as the seat to move, one transaction per move, recording the score at an end."""
    game = current(db, code)
    for uci in ucis:
        with db.read() as conn:
            board = games.replay_board(games.load_moves(conn, game.game_id))
        slot = game.slot_of(board.turn)
        with db.transaction() as conn:
            game = games.apply_move(conn, game, slot, uci, game.version, now, computer=computer)
            if game.status == games.FINISHED and game.result:
                rooms.record_result(conn, code, game.result, game.white_slot, counted=game.counted)
    return game


def room_of(db: Database, code: str) -> rooms.Room:
    with db.read() as conn:
        return rooms.get_room(conn, code)
