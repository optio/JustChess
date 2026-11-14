# Requirements Analysis Questions

Known request: use PostgreSQL when DATABASE_URL is configured, otherwise preserve JUSTCHESS_DB and built-in SQLite behavior. Existing process environment takes precedence over .env through the current loader. Single-worker operation remains necessary.

## Q1 — Existing SQLite data

Should this work transfer existing SQLite games into PostgreSQL?

A. No automatic transfer; switching selects a separate database (recommended for this change).
B. Include an explicit one-time SQLite-to-PostgreSQL migration tool.
X. Other (please specify)

[Answer]: A. No automatic transfer; switching selects a separate database. User selected the first option.

## Q2 — PostgreSQL schema setup

How should the selected PostgreSQL database be initialized?

A. Create and upgrade the application's tables at startup, like SQLite; the owner creates the database and supplies a role with schema permissions (recommended).
B. Provide an explicit setup/upgrade command; startup only validates the schema.
X. Other (please specify)

[Answer]: A. Create and upgrade the application's tables at startup; the owner supplies the database and schema permissions.

## Q3 — Invalid or unavailable configured database

What happens when a nonempty DATABASE_URL is invalid, unsupported or cannot connect?

A. Stop startup with a credential-safe error; do not silently use SQLite (recommended to avoid writing to an unintended database).
B. Fall back to SQLite and emit a credential-safe warning.
X. Other (please specify)

[Answer]: A. Stop startup with a credential-safe error; do not silently use SQLite.
