"""Keep ambient production database configuration out of every test.

PostgreSQL integration cases opt in with JUSTCHESS_TEST_DATABASE_URL and an
isolated schema. Individual configuration tests set DATABASE_URL explicitly.
"""

import pytest


@pytest.fixture(autouse=True)
def isolated_database_environment(monkeypatch):
    # Empty also prevents app.py's .env loader from reintroducing a production URL.
    monkeypatch.setenv("DATABASE_URL", "")
