"""GET /api/health: the monitoring signal (Observability Setup, 2026-11-15)."""

from __future__ import annotations

import sqlite3

from tests.fakes.computer_api import computer_client, computer_clock  # noqa: F401


def test_health_is_ok_with_database_and_engine(computer_client) -> None:
    client = computer_client()
    answer = client.get("/api/health")
    assert answer.status_code == 200
    assert answer.json() == {"status": "ok", "database": "ok", "engine": "available"}
    assert answer.headers["cache-control"] == "no-store"


def test_health_is_503_without_an_engine(make_client) -> None:
    client = make_client()  # the core fixture runs without any engine
    answer = client.get("/api/health")
    assert answer.status_code == 503
    assert answer.json() == {"status": "degraded", "database": "ok", "engine": "unavailable"}


def test_health_reports_a_database_failure_without_details(computer_client, monkeypatch) -> None:
    client = computer_client()
    db = client.app.state.services.db

    def broken():
        raise sqlite3.OperationalError("connection refused to secret-host:5432")

    monkeypatch.setattr(db, "_checkout", broken)
    answer = client.get("/api/health")
    assert answer.status_code == 503
    assert answer.json() == {"status": "degraded", "database": "down", "engine": "available"}
    assert "secret-host" not in answer.text
