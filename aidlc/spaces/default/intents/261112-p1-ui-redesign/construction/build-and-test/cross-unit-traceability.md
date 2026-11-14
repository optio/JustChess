# Cross-Unit Traceability — Build and Test

Source: `aidlc engine sensor-traceability --stage build-and-test`, run on 2026-11-13.

## Verdict

- **Functional requirements: pass.** All 56 FR IDs are built, each in at least one unit file.
- **Non-functional requirements: fail at the unit level.** The sensor lists NFR1–NFR6, NFR8a and NFR9 as uncovered. None of the units' `traceability.json` files list NFR IDs, because the plan skipped NFR Requirements and NFR Design, so the units traced FRs and business rules only. This stage verified each NFR directly in the Target Verification Matrix (`build-and-test-summary.md`). The only NFR left unverified there is NFR3's live push check.

## Functional coverage, by unit

| Unit | FR IDs built (file examples) |
|---|---|
| u1-core-game | FR1.1–FR1.7 (`justchess/rooms.py`, `api.py`, `live.py`), FR3.2, FR3.4–FR3.6, FR3.10, FR4.2–FR4.5 (`justchess/games.py`, `rooms.py`), FR9.1 (`api.py`), FR11.1–FR11.2 (`db.py`, `housekeeping.py`) |
| u2-design-system-board | FR3.1, FR3.3, FR3.6, FR3.9, FR5.1–FR5.3, FR10.1–FR10.5 (`static/js/board/*`, `static/js/settings.js`, `static/css/*`, `static/pieces/cburnett/`) |
| u3-game-screen | FR1.2, FR1.3, FR1.5–FR1.7, FR2.1–FR2.2, FR3.4–FR3.5, FR4.1, FR4.3–FR4.5, FR5.4–FR5.6, FR10.1, FR10.4, FR10.6, FR11.2 (`static/js/app.js`, `screens/*`, `view-model.js`, `screen-state.js`, `share.js`, `seat-store.js`, `static/css/app.css`) |
| u4-blunder-warnings | FR3.7, FR3.8, FR3.9, FR3.11 (`justchess/analysis.py`, `static/js/blunder.js`) |
| u5-notifications | FR6.1–FR6.8 (`justchess/notifications.py`, `static/sw.js`, `static/js/notifications.js`) |
| u6-training | FR7.1–FR7.7, FR8.1 (`justchess/lessons.py`, `lessons/*.yaml`, `static/js/training/*`) |

## Non-functional coverage (verified by this stage, not traced by units)

| ID | Covered here by | Verdict |
|---|---|---|
| NFR1 | `tests/core/test_api.py` (seat token required) | Met |
| NFR2 | `tests/core/test_rooms.py`, `tests/js/api.test.mjs`, log checks | Met |
| NFR3 | README HTTPS note (Met); live push on localhost | Unverified |
| NFR3a | Key scan; `tests/test_notifications.py` | Met |
| NFR4 | `tests/test_nfr_integration.py` | Met |
| NFR5 | `tests/test_nfr_integration.py` (p95 22.7 ms on the host) | Met |
| NFR6 | `tests/js/contrast.test.mjs`, `tests/test_accessibility_browser.py` | Met |
| NFR8a | origin tests in core, push and lesson API tests | Met |
| NFR9 | whole suite | Met |

## Uncovered elements to surface at the gate

- **NFR1–NFR9 are not in any unit's traceability file.** The plan skipped the NFR stages; this stage verified them directly.
- **NFR3's live push check is Unverified.**
