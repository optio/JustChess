"""Anonymous identity model; isolated databases only."""
import pytest

from justchess import DomainError, games, players, rooms
from justchess.db import prepare_database


@pytest.fixture
def db(tmp_path):
    return prepare_database(tmp_path / "players.sqlite3")


def test_recovery_preserves_both_devices_and_revokes_only_old_bookmark(db):
    with db.transaction() as conn:
        first = players.create(conn, 1)
        other = players.create(conn, 1)
        assert first["playerId"] != other["playerId"]
        room, seat, original = rooms.create_room(conn, 1, lambda: "PLY001")
        games.create_first_game(conn, room.code, 1)
        players.attach(conn, first["token"], room.code, original)
        second = players.restore(conn, first["recovery"], 2)
        assert second["seats"][0]["code"] == room.code
        for token in (first["token"], second["token"], original):
            assert rooms.authorize_seat(conn, room.code, token).seat_id == seat.seat_id
        with pytest.raises(DomainError):
            players.attach(conn, other["token"], room.code, original)
        fresh = players.regenerate(conn, first["token"])
        with pytest.raises(DomainError):
            players.restore(conn, first["recovery"], 3)
        assert players.restore(conn, fresh, 3)["playerId"] == first["playerId"]
        assert players.profile(conn, second["token"])["playerId"] == first["playerId"]
        assert conn.execute("SELECT token_hash FROM player_sessions LIMIT 1").fetchone()[0] != first["token"]
        assert conn.execute("SELECT recovery_hash FROM players WHERE player_id = ?", (first["playerId"],)).fetchone()[0] != fresh


@pytest.mark.parametrize("name", ["Fuck", "f.u.c.k", "F U C K", "sh1t", "b!tch", "ＦＵＣＫ", "a" * 25, "<script>", 123])
def test_invalid_nicknames_are_rejected(name):
    with pytest.raises(DomainError):
        players.nickname(name)


@pytest.mark.parametrize("name", ["Scunthorpe", "Dickinson", "Cassidy", " Alice   Smith ", "", "José"])
def test_ordinary_nicknames_are_not_blanket_substring_blocked(name):
    assert isinstance(players.nickname(name), str)


def test_unknown_session_cannot_access_seat_or_profile(db):
    with db.transaction() as conn:
        with pytest.raises(DomainError):
            players.authenticate(conn, "bad")
        assert players.seat_id(conn, "ABC123", players.secret()) is None
