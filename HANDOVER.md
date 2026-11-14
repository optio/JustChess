# JustChess — Handover and Remaining Work

Last updated: 2026-11-14. This file lets a new, empty session pick up where the last one stopped.

## Where things stand

- **P2 features are built.** The AI-DLC intent is `261113-p2-features`, and its record lives in `aidlc/spaces/default/intents/261113-p2-features/`. All six units are done, reviewed and checkpoint-approved:
  - U1 game screen polish: capture animation, the board fits above the fold, the share dialog;
  - U2 data and the "Your games" list;
  - U3 pass-along play and join requests;
  - U4 play the computer (Stockfish), with easier levels and `gameplay.yaml`;
  - U5 opening, trap and defence lessons, and tactics puzzles;
  - U6 endgame trainer.
- **Tests:** `uv run --frozen pytest -q` gives 386 passed and 1 skipped (push end-to-end, which needs a real push service). `node --test tests/js/` gives 221 passed.
- **The P2 workflow is complete.** Build and Test (stage 8 of 8) was approved on 2026-11-14, with every target Met. Its results are in `aidlc/spaces/default/intents/261113-p2-features/construction/build-and-test/`.
- **Everything is committed and pushed to `origin/main`**, including U6, the Build and Test record and this file.

## How to resume in a new session

1. Open Claude Code in this folder.
2. Start the next piece of work, task 3 below, with `/aidlc` and a description. The P2 workflow has no open gates.
3. Tasks 4 to 6 are small and can be done at any time.

## Remaining tasks

Tasks 1 and 2 (approve Build and Test; commit and push P2) were finished on 2026-11-14.

### 3. New piece of work: PostgreSQL through `DATABASE_URL`
The owner asked for this on 2026-11-14:

> If in .env a DATABASE_URL is configured, then use that. If not, the buildin sqlite

When asked which database, they chose **PostgreSQL**.
- **Start it as its own AI-DLC intent after P2 is closed**, for example `/aidlc Support PostgreSQL via DATABASE_URL in .env, falling back to the built-in SQLite`.
- **Why it's big:** the app is SQLite-only today.
  - `justchess/db.py` and about 120 `sqlite3` calls in `justchess/` use SQLite-specific SQL, such as partial unique indexes and `INSERT … ON CONFLICT`.
  - The per-room locks assume a single process.
  - The schema version check uses `PRAGMA user_version`.
- **What it needs:**
  - a database layer that works with both SQLite and Postgres;
  - SQL that runs on both;
  - a `psycopg` dependency;
  - Postgres-backed tests, for example against a test database given by an environment variable and skipped when it's absent;
  - `DATABASE_URL` added to `.env.example`, the env-file test's allowed list and the README.
- With no `DATABASE_URL`, `JUSTCHESS_DB` and the built-in `justchess.sqlite3` stay the default.

### 4. Check push notifications by hand
The push end-to-end test can't run on the Pi's headless Chromium. Check on a real phone that turn alerts arrive.
- Web Push needs the VAPID settings in `.env`. **Never put VAPID keys inside the project folder.** Keep the key file outside it and point to it from `.env`.
- The start-up line "Web Push is disabled: …" means those settings are missing.

### 5. Decide which credit to show for the chess pieces
The cburnett pieces in `pieces/cburnett/` come from the Lichess repo, which carries two licence statements: CC BY-SA 3.0 and GPLv2+. Both are recorded in `pieces/cburnett/LICENSE.md` and `static/ASSETS.md`. Which credit the site shows is the owner's decision. It currently shows "Pieces: cburnett, CC BY-SA 3.0".

### 6. Optional follow-ups from the code reviews (all minor)
- **U3 pass-along:**
  - The hourly clean-up lapses expired join requests without telling open pages. The page's own countdown hides the banner anyway.
  - The 10-minute block after a decline is kept in memory, so it resets on restart.
  - A malformed `X-Forwarded-For` behind a trusted proxy falls back to the proxy's address, so everyone behind that proxy shares one rate window.
  - The join-request status poll has no rate limit.
- **U6 endgames:**
  - No test covers a client disconnecting during an endgame move (the 409 "The move was cancelled"). The shared helper is covered through the hint tests.
  - The rate limit is applied before the 404 and body checks, so bad requests use up the allowance.
- **Deprecation warnings in the test run:**
  - python-chess uses `asyncio.DefaultEventLoopPolicy`, which is removed in Python 3.16. Upgrade python-chess when a fixed version exists.
  - `tests/test_nfr_integration.py` uses the old `websockets` `connect()` style.

## Standing rules for this project
- Run Python through `uv run --frozen`.
- Tests never open or migrate the real `justchess.sqlite3`. They use temporary databases.
- Seat and request tokens never go in URLs, logs or error bodies.
- Never write VAPID keys inside the project.
- Commit or push only when the owner asks.
- Gameplay numbers (computer levels, limits, timings) live in `gameplay.yaml`, so tune them there rather than in code.

## Useful pointers
- **AI-DLC state:** `aidlc/spaces/default/intents/261113-p2-features/aidlc-state.md`.
- **Unit designs and code summaries:** `aidlc/spaces/default/intents/261113-p2-features/construction/<unit>/`.
- **Requirements:** `aidlc/spaces/default/intents/261113-p2-features/inception/requirements-analysis/requirements.md`.
- **Decisions (ADRs):** `aidlc/spaces/default/intents/261113-p2-features/inception/domain-design/decisions.md`.
- **Running and configuring the app:** `README.md`, including the "Play the computer", "Endgame trainer" and "Tuning gameplay" sections.
- **Asset credits:** `static/ASSETS.md`.
