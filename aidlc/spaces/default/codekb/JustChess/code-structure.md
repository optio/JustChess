# Code Structure

> Focused merge, 2026-11-15: current findings cover player identity/presentation and persistence seams. Outside-focus descriptions are retained prior-store context and are not newly verified; see the timestamp for exact coverage.

| Location | Responsibility |
|---|---|
| app.py | Environment load and ASGI entry point |
| justchess/api.py | App factory, lifecycle, route handlers and services |
| justchess/db.py, postgres.py, rooms.py, games.py, summaries.py | Schema, persistence and room/game domain |
| justchess/live.py, security.py, ratelimit.py, housekeeping.py | Live sessions, request controls and cleanup |
| justchess/engine.py, computer.py, analysis.py | UCI queue, computer orchestration and move warnings |
| justchess/lessons.py, puzzles.py, endgames.py | Validated training catalogs and move adjudication |
| justchess/notifications.py, vapid.py | Subscription validation, event claims and key management |
| justchess/envfile.py, gameplay.py; gameplay.yaml | Startup configuration |
| static/js/ | Plain ES-module shell, functional state/view models, board, game and training UI |
| static/css/; templates/index.html; static/sw.js | Styles, shared HTML shell and notification worker |
| lessons/; endgames/; puzzles/ | Authored walkthroughs/positions and generated puzzle catalogs |
| stockfish_install.py; scripts/curate_puzzles.py | Verified engine provisioning and offline puzzle curation |
| tests/core/, tests/, tests/js/ | Python, browser/integration and Node regression checks |
| pyproject.toml; uv.lock; .env.example; README.md | Dependencies, lock, configuration example and operation guide |

Generated puzzle rows, demo files, binary fonts/pieces and the broad test suite were inventoried rather than individually deeply read. AI-DLC installation/workspace files, secrets, database files, dependencies and caches are excluded from application analysis.


## Focused additions and classification

- Repository/adapter: justchess/db.py and postgres.py select storage and translate the narrow SQL/row/error contract.
- Model/service: rooms.py defines room-scoped Seat and Room, token transfer and slot-based scores; games.py snapshot sections expose no nickname/player identifier.
- Frontend model/utility: seat-store.js, settings.js, view-model.js and board/interaction.js.
- Frontend presentation: settings-panel.js, board/board.js, screens/overlay.js, screens/win-sequence.js; tokens.css/board.css; templates/index.html.
- Controller/orchestration excerpts: api.py continue routes and app.js end lifecycle/fragment handling; screens/game.js private-link row. These larger files were only skimmed in this run.
- Tests deeply inspected: tests/js/seat-store.test.mjs and settings.test.mjs. Broader route/room/result/browser/PostgreSQL tests were located, not deeply reverified.

