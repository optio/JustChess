# JustChess — Handover and Remaining Work

Last updated: 2026-11-15. This file lets a new, empty session pick up where the last one stopped.

## How to resume in a new session

1. Open your coding assistant in this folder and read this file.
2. Player identity/game polish (`261115-player-identity-polish`) and PostgreSQL support are complete; do not repeat either. Build and Test is approved. No deployment target was selected, so deployment and monitoring stages did not apply. Start new work only when requested.
3. Keep this file limited to outstanding work: remove completed items as they finish and update the active checkpoint.

## Remaining tasks

### 1. Check push notifications by hand
The push end-to-end test can't run on the Pi's headless Chromium. Check on a real phone that turn alerts arrive.
- Web Push needs the VAPID settings in `.env`. **Never put VAPID keys inside the project folder.** Keep the key file outside it and point to it from `.env`.
- The start-up line "Web Push is disabled: …" means those settings are missing.

### 2. Decide which credit to show for the chess pieces
The cburnett pieces in `pieces/cburnett/` come from the Lichess repo, which carries two licence statements: CC BY-SA 3.0 and GPLv2+. Both are recorded in `pieces/cburnett/LICENSE.md` and `static/ASSETS.md`. Which credit the site shows is the owner's decision. It currently shows "Pieces: cburnett, CC BY-SA 3.0".

### 3. Optional follow-ups from the code reviews (all minor)
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
- Do not restore database files merely because of a workflow file-change warning. The owner explicitly permits database recreation for the player-identity change (2026-11-15); tests still use isolated databases.

## Useful pointers
- **Completed player identity/polish record:** `aidlc/spaces/default/intents/261115-player-identity-polish/`; final tests: 429 Python passed, 1 existing push E2E skip; 224 JavaScript passed; real PostgreSQL/Chromium checks passed. Owner requested commit and push on 2026-11-15; no deployment was requested. Schema 5: SQLite archives older files; PostgreSQL needs an empty/recreated application schema. Owner permits recreation because the app is not live; no backward compatibility is required.
- **Completed PostgreSQL record:** `aidlc/spaces/default/intents/261114-postgresql-support/`; final tests: 405 Python passed, 1 existing push E2E skip; 221 JavaScript passed; real PostgreSQL checks passed. The owner requested commit and push on 2026-11-15. No deployment was requested.
- **Current code knowledge:** `aidlc/spaces/default/codekb/JustChess/`.
- **Unit designs and code summaries:** `aidlc/spaces/default/intents/261113-p2-features/construction/<unit>/`.
- **PostgreSQL requirements:** `aidlc/spaces/default/intents/261114-postgresql-support/inception/requirements-analysis/requirements.md`.
- **Decisions (ADRs):** `aidlc/spaces/default/intents/261113-p2-features/inception/domain-design/decisions.md`.
- **Running and configuring the app:** `README.md`, including the "Play the computer", "Endgame trainer" and "Tuning gameplay" sections.
- **Asset credits:** `static/ASSETS.md`.
