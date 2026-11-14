"""HTTP fixtures for the U4 API tests: a started app with the fake UCI engine injected through ``create_app``.

    def test_x(computer_client):
        client = computer_client(["--delay", "0.2"])          # one flag list per engine launch
        room = create_computer(client, level="beginner", colour="white")

Stockfish discovery is patched to report a binary (the fake opener ignores the
path), the database lives in tmp_path, the clock is the shared FakeClock, and a
random colour is resolved by ``chooser`` (default: always "white"), and the
levels' random moves by ``move_chooser`` (default ``NeverRandom``, so replies are
the fake engine's deterministic move). The fixture
waits until the engine has left "starting". Import the fixture into a test
module with ``from tests.fakes.computer_api import computer_client  # noqa: F401``.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess.api import create_app
from justchess.engine import Engine
from tests.core.conftest import FakeClock
from tests.fakes.engines import NeverRandom, fake_opener

WAIT_SECONDS = 10.0


def wait_until(check, timeout: float = WAIT_SECONDS, message: str = "condition"):
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {message}")
        time.sleep(0.02)


@pytest.fixture
def computer_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def computer_client(tmp_path, monkeypatch, computer_clock):
    monkeypatch.setenv("JUSTCHESS_DB", str(tmp_path / "computer.sqlite3"))
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.delenv("JUSTCHESS_TRUSTED_PROXIES", raising=False)
    found = {"result": stockfish_install.EngineResult(path=Path("fake-stockfish"), source="env")}
    monkeypatch.setattr(stockfish_install, "ensure_stockfish", lambda _dir, _env: found["result"])
    with ExitStack() as stack:
        def factory(*launches: list[str], installed: bool = True, chooser=lambda _colours: "white",
                    grace: float = 0.5, move_chooser=None, **kwargs) -> TestClient:
            found["result"] = (stockfish_install.EngineResult(path=Path("fake-stockfish"), source="env") if installed
                               else stockfish_install.EngineResult(error="disabled in tests"))
            opener = fake_opener(*(launches or ([],)))
            kwargs.setdefault("receive_timeout", 5.0)
            app = create_app(clock=computer_clock, engine_factory=lambda: Engine(opener, grace=grace),
                             colour_chooser=chooser, move_chooser=move_chooser or NeverRandom(), **kwargs)
            client = stack.enter_context(TestClient(app))
            wait_until(lambda: client.get("/api/engine").json()["reason"] != "The computer is starting",
                       message="the engine to start")
            return client

        yield factory


def services_of(client: TestClient):
    return client.app.state.services


def create_computer(client: TestClient, level: str = "beginner", colour: str = "white") -> dict:
    response = client.post("/api/rooms", json={"kind": "computer", "level": level, "colour": colour})
    assert response.status_code == 201, response.text
    return response.json()


def state(client: TestClient, code: str, token: str | None = None) -> dict:
    headers = {"X-Seat-Token": token} if token else {}
    response = client.get(f"/api/rooms/{code}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def plies(snapshot: dict) -> int:
    return sum((1 if row["white"] else 0) + (1 if row["black"] else 0) for row in snapshot["moveList"])


def idle(client: TestClient) -> bool:
    """True once no reply task and no socket-event task is running."""
    return not services_of(client).coordinator.tasks


def wait_idle(client: TestClient, timeout: float = WAIT_SECONDS) -> None:
    wait_until(lambda: idle(client), timeout, "the computer's tasks to finish")


def wait_plies(client: TestClient, code: str, token: str, count: int, timeout: float = WAIT_SECONDS) -> dict:
    """Wait until the current game has ``count`` half-moves and no reply task runs; return the snapshot."""
    snapshot = wait_until(lambda: (lambda s: s if plies(s) == count and idle(client) else None)(state(client, code, token)),
                          timeout, f"{count} half-moves")
    return snapshot


def move(client: TestClient, code: str, token: str, uci: str, version: int):
    return client.post(f"/api/rooms/{code}/moves", json={"token": token, "uci": uci, "version": version})
