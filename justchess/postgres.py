"""Small psycopg adapter for the application's qmark SQL and SQLite-style rows.

Driver errors deliberately cross this boundary as sanitized sqlite3 errors:
the existing service handlers already catch that hierarchy, and raw PostgreSQL
diagnostics may include submitted capability hashes or connection credentials.
No statement-level recovery is attempted: a failed transaction must roll back.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from typing import Any


class Row:
    """Support the named and positional reads used by domain modules."""

    def __init__(self, names: list[str], values: Sequence[Any]):
        self._names = names
        self._values = tuple(values)

    def __getitem__(self, key):
        return self._values[self._names.index(key)] if isinstance(key, str) else self._values[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def keys(self) -> list[str]:
        return self._names


def row_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(names, values)


def parameters(sql: str) -> str:
    """Translate qmarks outside SQL literals; leave quoted question marks intact.

    Application SQL uses single-quoted literals and standard identifiers, no
    comments/dollar-quoted strings. Escape percent signs for psycopg binding.
    """
    result = []
    quoted = False
    for character in sql:
        if character == "'":
            quoted = not quoted
        result.append("%s" if character == "?" and not quoted else "%%" if character == "%" else character)
    return "".join(result)


class Connection:
    """Expose only the connection operations used by JustChess."""

    def __init__(self, raw, driver):
        self.raw = raw
        self.driver = driver

    def execute(self, sql: str, values=()):
        # Summaries require a stable multi-query snapshot, not READ COMMITTED.
        if sql.strip().upper() == "BEGIN":
            sql = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY"
        elif sql.strip().upper() == "BEGIN IMMEDIATE":
            sql = "BEGIN"
        try:
            return self.raw.execute(parameters(sql), values)
        except self.driver.IntegrityError:
            raise sqlite3.IntegrityError("PostgreSQL constraint violation") from None
        except self.driver.Error:
            raise sqlite3.DatabaseError("PostgreSQL operation failed") from None

    def close(self) -> None:
        self.raw.close()


def connect(url: str) -> Connection:
    try:
        import psycopg
    except ImportError:
        raise sqlite3.OperationalError("PostgreSQL driver unavailable; install the locked dependencies") from None
    try:
        raw = psycopg.connect(url, autocommit=True, connect_timeout=5, row_factory=row_factory)
    except (psycopg.Error, ValueError):
        raise sqlite3.OperationalError("PostgreSQL connection failed; check DATABASE_URL and server access") from None
    return Connection(raw, psycopg)
