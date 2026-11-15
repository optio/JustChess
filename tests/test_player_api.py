"""Player API authorization and portable seat access on isolated databases."""
import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(stockfish_install, "ensure_stockfish", lambda *_: stockfish_install.EngineResult(error="disabled"))
    with TestClient(create_app(db_path=tmp_path / "api.sqlite3", engine_dir=tmp_path / "engine")) as client:
        yield client


def call(client, action, body=None, token=None):
    return client.post("/api/player/" + action, json=body or {}, headers={"X-Player-Token": token} if token else {})


def test_nickname_recovery_two_device_seat_access_and_regeneration(client):
    a = call(client, "create").json()
    h = {"X-Player-Token": a["token"]}
    assert call(client, "nickname", {"nickname": "Alice"}, a["token"]).json()["nickname"] == "Alice"
    room = client.post("/api/rooms").json()
    assert call(client, "seats", {"code": room["code"], "token": room["token"]}, a["token"]).status_code == 200
    b = call(client, "restore", {"recovery": a["recovery"]}).json()
    assert b["nickname"] == "Alice" and b["seats"][0]["code"] == room["code"]
    client.post(f"/api/rooms/{room['code']}/join", json={})
    for token in (a["token"], b["token"], room["token"]):
        snap = client.get(f"/api/rooms/{room['code']}", headers={"X-Seat-Token": token}).json()
        assert snap["slot"] == "A" and snap["seats"]["A"]["nickname"] == "Alice"
    moved = client.post(f"/api/rooms/{room['code']}/moves", json={"token": b["token"], "uci": "e2e4", "version": snap["version"]})
    assert moved.status_code == 200
    stale = client.post(f"/api/rooms/{room['code']}/moves", json={"token": a["token"], "uci": "d2d4", "version": snap["version"]})
    assert stale.status_code == 409
    new = call(client, "regenerate", token=a["token"]).json()["recovery"]
    assert call(client, "restore", {"recovery": a["recovery"]}).status_code == 403
    assert call(client, "restore", {"recovery": new}).status_code == 200
    assert call(client, "profile", token=b["token"]).status_code == 200
    assert call(client, "profile", token=a["token"]).headers["cache-control"] == "no-store"


def test_api_rejects_impersonation_and_profanity_without_echoing_secrets(client):
    a = call(client, "create").json()
    other = call(client, "create").json()
    room = client.post("/api/rooms").json()
    assert call(client, "seats", {"code": room["code"], "token": "sentinel"}, a["token"]).status_code == 403
    assert call(client, "seats", {"code": room["code"], "token": room["token"]}, a["token"]).status_code == 200
    assert call(client, "seats", {"code": room["code"], "token": room["token"]}, other["token"]).status_code == 403
    assert call(client, "nickname", {"nickname": "f.u.c.k"}, a["token"]).status_code == 400
    assert call(client, "profile", token=a["token"]).json()["nickname"] == ""
    assert call(client, "nickname", {"nickname": "Cassidy"}, a["token"]).status_code == 200
    response = call(client, "restore", {"recovery": "sentinel"})
    assert response.status_code == 403 and "sentinel" not in response.text
    assert call(client, "regenerate").status_code == 403
    assert client.post("/api/player/create", json={}, headers={"Origin": "https://evil.invalid"}).status_code == 403


def test_profile_actions_are_bounded_and_rate_limited(client):
    assert client.post("/api/player/create", content="[1]", headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/api/player/create", content="x" * 20000).status_code == 413
    responses = [call(client, "create").status_code for _ in range(65)]
    assert 429 in responses
