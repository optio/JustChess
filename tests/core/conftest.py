"""Shared fixtures for the U1 core tests. Every test gets its own database in tmp_path."""

from __future__ import annotations

from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess.api import create_app
from justchess.db import Database, prepare_database

START = 1_800_000_000.0  # a fixed server time for reproducible clocks


class FakeClock:
    """An injectable ``now()`` clock that tests move forward by hand."""

    def __init__(self, start: float = START) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def db(tmp_path) -> Database:
    return prepare_database(tmp_path / "test.sqlite3")


@pytest.fixture
def make_client(tmp_path, monkeypatch, clock):
    """Return a factory for started TestClients on a temporary database.

    The database path comes from ``JUSTCHESS_DB`` (pointing into tmp_path) and
    the Stockfish preparation is patched to a no-op, so no network is used.
    """
    monkeypatch.setenv("JUSTCHESS_DB", str(tmp_path / "api.sqlite3"))
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    with ExitStack() as stack:
        def factory(**kwargs) -> TestClient:
            kwargs.setdefault("receive_timeout", 5.0)
            return stack.enter_context(TestClient(create_app(clock=clock, **kwargs)))

        yield factory


def create_room(client: TestClient) -> dict:
    response = client.post("/api/rooms")
    assert response.status_code == 201, response.text
    return response.json()


def join_room(client: TestClient, code: str, token: str | None = None) -> dict:
    response = client.post(f"/api/rooms/{code}/join", json={"token": token})
    assert response.status_code == 200, response.text
    return response.json()


def move(client: TestClient, code: str, token: str, uci: str, version: int):
    return client.post(f"/api/rooms/{code}/moves", json={"token": token, "uci": uci, "version": version})
