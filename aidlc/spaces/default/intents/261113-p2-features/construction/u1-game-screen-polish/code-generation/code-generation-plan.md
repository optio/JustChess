# Code Generation Plan — u1-game-screen-polish

U1 is a front-end-only unit: capture animation, board fit and the share dialog. It follows `construction/u1-game-screen-polish/functional-design/` (`functional-spec.md`, `rules.md` BR1.1–BR3.6, `frontend-components.md`), `inception/units-generation/unit-of-work.md` (U1) and requirements FR2.1–FR2.3, FR4.1–FR4.3 and FR5.1–FR5.5. No server, API or database code changes.

Brownfield: these extend the existing ES modules in `static/js/` and the CSS in `static/css/`. The test runner already exists: `node --test` through `tests/js/index.js`, plus the headless Chromium tests in `tests/`.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "org",
  "ordering": "implement each applicable testable layer, then write and run that layer's tests.",
  "scope": "refactor",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:322f3cce51ad835b556974215be0ae0a5aba55c673c92ff6b1b327e7eb2426e8",
  "contract_sha256": "sha256:84a32ec0d9dd634774d2a290b523e6e0d5e6f77259469f3112500519cb132392"
}
```

These layers don't apply to U1, because it changes no server code: data model/database, repository/data access, and API/endpoint. The "business logic" layer here means the pure front-end helpers (capture detection, layout maths, share links, QR encoding). They are tested with `node --test`. The frontend-behaviour layer is tested in headless Chromium.

## Steps

- [x] **Step 1 — Structure.** Create the new modules as empty, documented skeletons:
  - `static/js/captures.js`, `static/js/layout.js`, `static/js/share-dialog.js`, `static/js/qr-canvas.js`;
  - the vendored `static/js/vendor/qrcode.js` (MIT, licence header kept), credited in `static/ASSETS.md` (ADR-008).
- [x] **Step 2 — Runner check.** Confirm `node --test tests/js/` and `uv run --frozen pytest -q tests/test_u1_polish_browser.py` run, and record them in `unit-test-instructions.md`.
- [x] **Step 3 — Helpers: implement** (BR1.6, BR2.1–BR2.4, BR3.3, BR3.4, BR3.6):
  - `captures.js`: `capturedPieces(moves, pending)` replays from the start position with the existing chess helpers and returns pieces by side, ordered Q R B N P; `captureLabel(...)`.
  - `layout.js`: `boardMode(w, h)` (landscape-phone first, then desktop, then portrait) and `boardSide(w, h)`, mirroring the CSS, with the table of 7 sizes in `functional-spec.md` W2.
  - `share.js`: `appLinks(url, text)` (email, whatsapp, telegram, sms, all URL-encoded) and `dialogText({ waiting, colour })`.
  - `qr-canvas.js`: `qrMatrix(text)` (level M) and `drawQr(canvas, text)` (black on white, 4-module quiet zone, device-pixel-ratio scaling).
- [x] **Step 4 — Helpers: tests** (`node --test`):
  - `tests/js/captures.test.mjs`: normal capture, en passant, promotion with capture, no captures, a pending own move, label text. 6 tests.
  - `tests/js/layout.test.mjs`: the 7 FR4.1 sizes (mode and side), 1024 × 500 precedence, the 320 px floor. 6 tests.
  - `tests/js/share.test.mjs` (extended): app link shapes, encoding of `&` `#` and spaces, dialog text when waiting and when joined. 5 new tests.
  - `tests/js/qr.test.mjs`: the matrix size for a known URL, finder patterns, the same output for the same input, a too-long input rejected with an error. 4 tests.
- [x] **Step 5 — Front end: implement**:
  - **Board (BR1.1–BR1.5):**
    - `fadeCaptured` becomes a scale-and-fade, 1 → 0.35 with opacity 1 → 0.
    - `--t-capture` changes from 150 ms to 260 ms in `tokens.css`, using `--ease-out`.
    - Optimistic captures animate once, and `onCaptureShown` is added.
  - **Game screen (BR1.6):** a CapturedRow under the status line, using `capturedPieces` with the pending move, `aria-label`, and an `is-new` 200 ms settle only for newly added pieces. CSS goes in `app.css`.
  - **Board fit (BR2.1–BR2.5):** CSS in `app.css` and `board.css`: `min(100%, calc(100svh - var(--reserve)), var(--cap))`, the 352 px and 288 px floors, a landscape-phone media query after desktop, edge to edge under 400 px in portrait.
  - **Share dialog (BR3.1–BR3.6):**
    - A native `<dialog>` in `templates/index.html`.
    - `share-dialog.js` handles open, focus, Copy and "Copied", app links, "More…" only with a share sheet, a backdrop click, Escape, and returning focus.
    - The QR code is drawn on first open through a dynamic import, and shows "QR code unavailable" if that fails.
    - `app.js` wires Share to the dialog and drops the old `#share-fallback` and `#share-field` path. The `continue on another device` copy path keeps using `copyText`, now through the dialog field.
- [x] **Step 6 — Front end: tests** (headless Chromium, `tests/test_u1_polish_browser.py`, reusing the `live_server`/`browser`/`Page` helpers from `tests/test_game_screen.py`):
  - At the 7 FR4.1 sizes, the board's bottom edge is inside the viewport at scroll 0 and squares meet the floor (FR4.1, FR4.2).
  - A capture makes a ghost on the right square, including en passant; none appears under emulated reduced motion (FR2.1, FR2.2).
  - A tap during the animation still selects a square (FR2.3).
  - The share dialog: focus starts on Copy link, Tab stays inside, Escape closes it, focus returns to Share, the game screen is unchanged, and the QR canvas is drawn (FR5.1–FR5.5).
  - "Copied" appears and resets.

  That is 7 browser tests. Run the existing suite, keeping P1's 44 px accessibility test green.
- [x] **Step 7 — Config.** No new runtime configuration. `static/sw.js` keeps caching the new modules if the asset list needs them.
- [x] **Step 8 — Docs and traceability.** README: a short note on the share dialog and the board fit. `code-summary.md` and `traceability.json` map FR and BR to files.

## Requirement-to-step map

| ID | Steps |
|---|---|
| FR2.1 | 3, 4, 5, 6 |
| FR2.2 | 5, 6 |
| FR2.3 | 5, 6 |
| FR4.1 | 3, 4, 5, 6 |
| FR4.2 | 3, 4, 5, 6 |
| FR4.3 | 5, 6 |
| FR5.1 | 5, 6 |
| FR5.2 | 5, 6 |
| FR5.3 | 3, 4, 5 |
| FR5.4 | 1, 3, 4, 5, 6 |
| FR5.5 | 5, 6 |

## Constraints
- Never open or migrate the real `justchess.sqlite3`. The browser tests use `tmp_path` databases through the existing fixtures.
- No secrets or tokens in URLs or logs. The invite link carries only the room code.
- Files are written with file tools only.
