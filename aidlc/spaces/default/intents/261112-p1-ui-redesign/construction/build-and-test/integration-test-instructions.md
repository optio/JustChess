# Integration Test Instructions — JustChess P1

## Framework

These tests use pytest. Each one starts its own uvicorn server on a free port, with a temporary database. Browser tests drive headless Chromium through the DevTools Protocol, using the `websockets` package that uvicorn already installs. Nothing extra is installed.

## How to run

```bash
uv run --frozen pytest tests/test_nfr_integration.py tests/test_game_screen.py tests/test_accessibility_browser.py tests/test_push_e2e.py -q -rs
```

All of these also run inside the whole-suite command, `uv run --frozen pytest -q`.

## Cross-unit boundaries covered

| Boundary | Test | Engine |
|---|---|---|
| Core game (U1) and game screen (U3) and board (U2): a full two-player game, overlay and rematch | `test_game_screen.py::test_two_player_browser_game` | Chromium |
| Blunder check (U4) inside the game screen move hook (U3) | `test_game_screen.py::test_blunder_dialog_browser_run` | Chromium |
| Trainer (U6) with the board (U2), at `/learn` | `test_game_screen.py::test_lesson_trainer_browser_run` | Chromium |
| Notifications (U5), service worker, game screen (U3): background-tab notification | `test_game_screen.py::test_background_tab_gets_a_local_notification` | Chromium |
| Real Web Push (U5) through a vendor push service | `test_push_e2e.py` | Chromium; skipped when the build has no push service |
| Concurrency (U1): joins and moves against a real server | `test_nfr_integration.py` | uvicorn with threads |
| Move delivery time (U1 live updates) | `test_nfr_integration.py` | uvicorn with sockets |
| Accessibility at phone width (U2 and U3) | `test_accessibility_browser.py` | Chromium at 390 × 844 |

## Coverage expectations

No coverage floor applies (refactor scope). Every key boundary above has at least one test.

## Test data

Every test makes its own rooms in a temporary database. The real `justchess.sqlite3` is never opened. VAPID keys for the push test are generated in pytest's `tmp_path`.
