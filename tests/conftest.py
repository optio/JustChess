"""Keep ambient production database configuration out of every test.

PostgreSQL integration cases opt in with JUSTCHESS_TEST_DATABASE_URL and an
isolated schema. Individual configuration tests set DATABASE_URL explicitly.
"""

import pytest


@pytest.fixture(autouse=True)
def isolated_database_environment(monkeypatch):
    # Empty also prevents app.py's .env loader from reintroducing a production URL.
    monkeypatch.setenv("DATABASE_URL", "")
    # New friend rooms pick the creator's colour at random in production; the
    # suite pins White so its scripted games stay deterministic. Tests of the
    # random choice clear this variable.
    monkeypatch.setenv("JUSTCHESS_CREATOR_COLOUR", "white")
