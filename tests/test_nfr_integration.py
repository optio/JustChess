"""Build and Test integration checks for the non-functional targets that need a real server.

These tests start their own uvicorn process (temporary database, push off) so
requests really run concurrently, which TestClient cannot show:

- NFR4: concurrent joins seat exactly one Black; concurrent moves on the same
  version apply exactly one, and the loser gets 409 with a snapshot (never 500).
- NFR5: an opponent's socket receives the new position well within 1 second of
  the move request (measured on the host over 40 moves; 95th percentile).
"""

from __future__ import annotations

import json
import os
import socket
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    port = _free_port()
    env = {**os.environ, "STOCKFISH_AUTO_INSTALL": "0"}
    for name in ("JUSTCHESS_ORIGIN", "JUSTCHESS_VAPID_PRIVATE_KEY", "JUSTCHESS_VAPID_KEY_FILE"):
        env.pop(name, None)
    script = (
        "import sys, uvicorn; from justchess.api import create_app; "
        "uvicorn.run(create_app(db_path=sys.argv[1], engine_dir=sys.argv[2]), host='127.0.0.1', "
        "port=int(sys.argv[3]), log_level='warning')"
    )
    proc = subprocess.Popen([sys.executable, "-c", script, str(tmp_path / "nfr.sqlite3"), str(tmp_path / "engines"), str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    while True:
        try:
            if httpx.get(base + "/", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline or proc.poll() is not None:
            proc.kill()
            raise RuntimeError("test server did not start: " + (proc.stderr.read() or b"").decode()[-2000:])
        time.sleep(0.1)
    try:
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _create(base: str) -> dict:
    r = httpx.post(base + "/api/rooms", json={}, timeout=5)
    assert r.status_code == 201, r.text
    return r.json()


def _join(base: str, code: str, token: str | None = None) -> httpx.Response:
    return httpx.post(f"{base}/api/rooms/{code}/join", json={"token": token} if token else {}, timeout=5)


def _version(base: str, code: str, token: str) -> int:
    """The game's current version (joining also bumps it, so never assume 0)."""
    r = httpx.get(f"{base}/api/rooms/{code}", headers={"X-Seat-Token": token}, timeout=5)
    assert r.status_code == 200, r.text
    return r.json()["version"]


def _parallel(n: int, fn):
    """Run fn(i) in n threads released together; return the results in order."""
    barrier = threading.Barrier(n)
    results: list = [None] * n

    def run(i: int) -> None:
        barrier.wait()
        results[i] = fn(i)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results


def test_concurrent_joins_seat_exactly_one_black(server):
    for _ in range(5):  # repeat to give a race a real chance to show
        room = _create(server)
        responses = _parallel(8, lambda i: _join(server, room["code"]))
        statuses = sorted(r.status_code for r in responses)
        assert 500 not in statuses
        assert statuses.count(200) == 1, statuses
        assert statuses.count(409) == 7, statuses
        winner = next(r for r in responses if r.status_code == 200).json()
        assert winner["slot"] == "B" and winner["colour"] == "black"


def test_concurrent_moves_on_one_version_apply_exactly_one(server):
    for _ in range(5):
        room = _create(server)
        black = _join(server, room["code"]).json()
        assert black["slot"] == "B"
        # White sends four different legal first moves at once, all on the same version.
        start = _version(server, room["code"], room["token"])
        moves = ["e2e4", "d2d4", "g1f3", "c2c4"]
        responses = _parallel(4, lambda i: httpx.post(
            f"{server}/api/rooms/{room['code']}/moves",
            json={"token": room["token"], "uci": moves[i], "version": start}, timeout=5))
        statuses = sorted(r.status_code for r in responses)
        assert 500 not in statuses
        assert statuses.count(200) == 1, statuses
        assert statuses.count(409) == 3, statuses
        for r in responses:
            if r.status_code == 409:
                assert "snapshot" in r.json(), r.json()
        state = httpx.get(f"{server}/api/rooms/{room['code']}", headers={"X-Seat-Token": room["token"]}, timeout=5).json()
        assert len(state["moveList"]) == 1 and state["version"] == start + 1


def _hello(base: str, code: str, token: str):
    ws = connect(base.replace("http://", "ws://") + f"/ws/{code}", open_timeout=5)
    ws.send(json.dumps({"type": "hello", "token": token, "visible": True}))
    first = json.loads(ws.recv(timeout=5))
    assert first["type"] == "state"
    return ws


def _wait_for_version(ws, version: int, timeout: float = 5.0) -> float:
    deadline = time.monotonic() + timeout
    while True:
        message = json.loads(ws.recv(timeout=max(0.01, deadline - time.monotonic())))
        if message.get("type") == "state" and message.get("version", -1) >= version:
            return time.perf_counter()


def _forty_quiet_plies() -> list[str]:
    """A fixed, seeded sequence of 40 legal half-moves that does not end the game."""
    import random

    import chess

    rng = random.Random(7)
    while True:
        board = chess.Board()
        plies: list[str] = []
        while len(plies) < 40 and not board.is_game_over():
            move = rng.choice(sorted(board.legal_moves, key=lambda m: m.uci()))
            board.push(move)
            plies.append(move.uci())
        if len(plies) == 40 and not board.is_game_over():
            return plies


def test_opponent_receives_moves_within_one_second_p95(server):
    room = _create(server)
    black = _join(server, room["code"]).json()
    white_ws = _hello(server, room["code"], room["token"])
    black_ws = _hello(server, room["code"], black["token"])
    plies = _forty_quiet_plies()
    latencies = []
    version = _version(server, room["code"], room["token"])
    try:
        for i, uci in enumerate(plies):
            token = room["token"] if i % 2 == 0 else black["token"]
            receiver = black_ws if i % 2 == 0 else white_ws
            started = time.perf_counter()
            r = httpx.post(f"{server}/api/rooms/{room['code']}/moves",
                           json={"token": token, "uci": uci, "version": version}, timeout=5)
            if r.status_code != 200:
                pytest.fail(f"move {i} {uci} refused: {r.status_code} {r.text}")
            version += 1
            arrived = _wait_for_version(receiver, version)
            latencies.append((arrived - started) * 1000)
    finally:
        white_ws.close()
        black_ws.close()
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"\nNFR5 delivery on host: median {statistics.median(latencies):.1f} ms, p95 {p95:.1f} ms, max {latencies[-1]:.1f} ms")
    assert p95 < 1000, latencies
