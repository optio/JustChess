# Code Quality Assessment: JustChess

## Summary

The redesign (units U1 to U6) replaced the earlier two-file app with a well-structured modular backend and a plain-module frontend built around pure, tested state machines. Code is readable, documented per module with the business rules it implements, defensive at every boundary (tokens hashed, origin and size limits, safe file and archive handling, fail-open or fail-closed choices stated explicitly), and broadly tested. The main limits are architectural rather than stylistic: one process only, a board that sizes by width only, two fixed seats per room, and no engine integration yet. There is still no linter configuration, coverage tool or CI. Almost all of this code is uncommitted, and parts of it changed during the scan.

## Quick Ratings

| Criterion | Backend (`justchess/`) | `stockfish_install.py` | Frontend JS | CSS |
|---|---|---|---|---|
| Naming clarity | good (domain names: `authorize_seat`, `apply_move`, `claimable_draw`) | good | good (descriptive camelCase; constants for every user-facing string) | good (token names, BEM-like classes) |
| Function size | good (most under 30 lines; `api.py` route closures are short, the file is long) | good | fair (`app.js` `startApp` is one 500-line closure of small inner functions; `board.js` `createBoard` likewise) | n/a |
| Error handling | good (`DomainError` mapping, DB errors logged by room code, background tasks never raise) | good | good (clients resolve, never reject; hooks contained; board never stays locked) | n/a |
| Test presence | good (U1 core suite, notifications, analysis, lessons, push, NFR integration, `.env`) | good | good (reducers, view model, clients, geometry, interaction, contrast, assets) | fair (contrast and assets tested; layout only through browser tests) |
| Duplication | fair (end-reason wording in four places) | good | fair (`make()` DOM helper repeated in several view modules) | good |
| Dead code | good (`python-multipart` unused) | good | good | good |

## Tests

- **Suites** (skimmed, not run): `tests/core/` (rooms, games, live, db, api), top-level Python files for the game screen in a browser, NFR integration, push end-to-end and API, analysis, check-move API, lessons and lessons API, notifications, accessibility in a browser, frontend JS runner, installer, and `.env` loading; `tests/js/` with 19 files.
- **Size**: about 153 Python test functions and about 139 JS tests by name count.
- **Browser tests** need Chromium (`JUSTCHESS_CHROMIUM`) and are skipped with the reason otherwise.
- **Coverage tool**: none, so no coverage figure exists.
- **Not run** in this scan; pass or fail state unknown.

## Linting, Formatting, Types

No formatter, linter or type checker is configured. Python is fully type-annotated in the new modules and follows PEP 8 with long lines in places (up to about 120 characters). `# noqa` codes in `app.py` (E402) and `notifications.py` (D102) suggest Ruff is used informally. JS is consistently formatted (2 spaces, double quotes, semicolons) without a config file. `tokens.css` must keep one declaration per line because `contrast.js` parses it.

## CI/CD

None: no `.github/`, no pipeline, no Dockerfile, no pre-commit configuration.

## Documentation

- `README.md`: current; configuration table (including `.env`), notifications, lessons schema, Stockfish, design system and demo page, limitations.
- Every Python module has a docstring naming its unit, rules and contracts; functions have docstrings.
- Every JS module starts with a contract comment (exports, events, effects, decisions).
- `static/ASSETS.md` pins every third-party asset with source, licence and sha256.

## Technical Debt

| # | Item | Location | Impact | Relevance to intent 261113-p2-features |
|---|---|---|---|---|
| 1 | Board size follows width only; no viewport-height cap | `static/css/app.css`, `static/css/board.css` | Board and, on phones, the status line can fall below the fold | "Board fits above the fold" |
| 2 | Mover's own captures not animated (optimistic apply removes the piece, the confirm has no diff) | `static/js/board/board.js` `runEffect("applyOptimistic")`, `interaction.js` `onPosition` | Inconsistent feedback between taking and losing a piece | "Small animation when taking or losing a piece" |
| 3 | Two fixed seats bound to tokens; tokenless join always takes seat B; no seat release | `justchess/rooms.py`, `justchess/games.py` | A local two-player mode needs a new concept; a remote join must still be possible | "Pass-along game, back to online on join" |
| 4 | Seats known only per room in `localStorage`; no index and no multi-room read | `static/js/seat-store.js`, `justchess/api.py` | An ongoing-games list needs N requests or a new route; stale seats only discovered on 404 | "Ongoing sessions on the main screen" |
| 5 | Sharing is share sheet, else clipboard, else an inline field under the top bar | `static/js/share.js`, `static/js/app.js`, `templates/index.html` | Changes the main layout on fallback; no email or messenger links | "Share modal" |
| 6 | Stockfish installed but no UCI integration; engine path only on `app.state` | `stockfish_install.py`, `justchess/api.py` | Single player needs an engine service, a game mode and a UI | "Single player with Stockfish" |
| 7 | Trainer accepts only the taught move; alternatives are display text; scripted replies only | `static/js/training/trainer-state.js`, `justchess/lessons.py` | Situation trainers with several good answers or engine replies need schema and reducer changes | "More openings", "Situation trainers" |
| 8 | `api.py` holds 714 lines of factory, services and all route groups | `justchess/api.py` | Growing hot spot as routes are added | All server-side items |
| 9 | End-reason wording in four copies | `notifications.py`, `view-model.js`, `notify-core.js`, `sw.js` | Drift risk | Low |
| 10 | In-memory locks and socket hub | `justchess/api.py`, `justchess/live.py` | One worker only | Engine work must stay off the event loop |
| 11 | Alert claims left `claimed` by a crash are never resent (by design) | `justchess/notifications.py` | A rare lost alert | Low |
| 12 | Free-play route is stateless (no repetition detection) | `justchess/lessons.py` `position_move` | Not suitable as-is for full games against an engine | Single player design choice |
| 13 | Redundant or unused dependencies; undeclared direct imports | `pyproject.toml` | Noise; fragile if pywebpush changes its dependencies | Low |
| 14 | No linter, coverage or CI | repo | No automated gate | Org floor asks for 80% coverage and CI for `feature`-type scopes |
| 15 | Large closures `startApp` and `createBoard` | `static/js/app.js`, `static/js/board/board.js` | Harder to extend (share modal, lobby list and local mode all touch `app.js`) | Medium |

Resolved since the prior store: inverted board colours, fixed orientation, missing coordinates, one-line JS and CSS, `prompt()` promotion and `alert()` errors, unused HTMX, hardcoded lessons, plaintext tokens, one game per room, automatic threefold and 50-move draws, missing migrations, unclosed connections, unbounded room locks, silent broadcast failures, uncancelled Stockfish task.

TODO, FIXME and HACK markers: none in the analyzed source.

## Security Notes

- **Strengths**: 256-bit seat tokens stored as SHA-256 hashes and compared with `hmac.compare_digest`; tokens never in URLs or logs; origin check on state changes and sockets; 4 KB body and 1 KB socket message limits; parameterised SQL; per-viewer snapshots (no legal moves for watchers); lesson files read without following symlinks, size-capped, `yaml.safe_load`, ids never joined into paths; push endpoints restricted to allow-listed HTTPS hosts with strict host parsing and no redirects; VAPID key kept outside the project and never logged; checksum-verified, link-refusing Stockfish extraction; service worker only opens same-origin room pages; `.env` loader never logs values.
- **Gaps**: no rate limiting or abuse controls; no HTTPS enforcement in the app; anyone with a room code can watch; continue links are bearer secrets (one use, 10 minutes); `.env` must stay git-ignored (it is) and should not hold the VAPID key itself (the loader's docstring says so).
- **For the upcoming work**: a share modal with `mailto:` and messenger links only navigates (no third-party fetch); a Stockfish service must cap think time and concurrent engine processes to avoid a CPU denial of service on this single process; a pass-and-play mode must not weaken seat authority for remote players.
