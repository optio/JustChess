# Code Generation Plan — u2-design-system-board

## Summary

- Builds: the new "Club Set" look. That covers the colour tokens with light and dark themes and three board colours, self-hosted fonts and cburnett pieces, and a board module. The board has correct colours, flips to your side, shows coordinates, highlights, keyboard play, slide, capture and check animations, and a promotion picker. A settings module and a standalone demo page are included.
- Touches: new files under `static/` (`css/`, `js/`, `fonts/`, `pieces/cburnett/`, `logo.svg`, `demo/board.html`); new `tests/js/` (Node tests) and `tests/test_frontend_js.py`, which runs them inside the approved pytest command. The old `static/app.js`, `static/style.css` and `templates/index.html` are left alone; U3 replaces them.
- Tests: about 40 Node tests on pure modules (geometry, move diff, interaction reducer, focus, labels, settings, contrast), plus one pytest wrapper and a static check that the assets exist.

## Inputs

- `construction/u2-design-system-board/functional-design/` (`functional-spec.md`, `frontend-components.md`, `rules.md`).
- `inception/refined-mockups/design-system-mapping.md`, `interaction-spec.md`, `accessibility-checklist.md` and the published mockup.
- `inception/units-generation/unit-of-work.md` (U2) and `inception/requirements-analysis/requirements.md`.

## Design review findings resolved in this build

The functional design review (advisory, NOT-READY) raised the points below. The build settles each one as follows.

| Finding | Build decision |
|---|---|
| Black piece contrast on Rosewood (Major) | Black pieces get a 1 px light edge in CSS (`filter: drop-shadow` in `--piece-edge`, light cream at 70%), which interaction-spec.md already promised. A contrast test computes the ratio of the piece fill or edge against all six square colours and requires at least 3:1 for each. If Rosewood's dark square still fails, it is lightened just enough to pass, and the code summary records the new value. |
| Notifications hook (Major) | `hooks.onNotificationsToggle(value) → Promise<boolean>`. The switch is disabled while the promise is pending. The stored value is the resolved boolean. A rejection or `false` when turning on reverts the switch, stores `false`, and shows "Notifications are blocked in this browser" (or the error's message). With no hook, the value is stored directly. Tests cover granted, denied and throw. |
| Locking mid-interaction and animation completion (Major) | `interactive=false` from any state goes to `locked`: the selection clears, an open picker resolves `null` and closes, and a pending move stays pending until `set()` or `reject()`. Locked squares stay focusable, with `aria-disabled="true"` rather than `disabled`. Animations use the Web Animations API (`element.animate`). Completion is the animation's `finished` promise, and "finish at once" calls `finish()`. Under reduced motion no animation is created and the final state is applied synchronously, so nothing waits for `transitionend`. |
| Pure interaction logic | The interaction state machine is a pure reducer, `reduce(state, event, ctx) → {state, effects}`, in `static/js/board/interaction.js`. Board.js only runs its effects. Transition tests cover tap, retap, promotion, pending, reject and the flip of interactive. |
| Square elements and roles | The 64 square elements are created once and updated in place, so focus survives `set()`. Each square is a `button` with `role="gridcell"`, and its `aria-label` carries "selected" and "legal move". This deliberately differs from interaction-spec's plain "button", because grid navigation needs gridcells. |
| Optimistic placement, first render, castling | A position equal to the optimistic one is accepted with no animation. The first render never pulses (`inCheckBefore` starts as the initial check value). Castling is chosen by the king's two-square target (UCI `e1g1`). Tapping the rook does not castle. The caller must call `reject()` on any failure; this is documented in the module header. |
| Boot script and storage | The boot script uses the same allow-lists as the store and falls back to the defaults. It is an external file, `static/js/boot.js`, loaded synchronously in `<head>` and not inline, so a later Content-Security-Policy needs no hash. The store listens to `storage` events, so other tabs stay in sync. |
| Label colours and frame sizing | Label tokens are set per board theme: dark squares get a light label and light squares a dark one. They are chosen and tested at 4.5:1 or more. In frame mode the frame is inside the measured board width, so the squares shrink to fit, and the 374 px minimum applies to the whole frame. |

## Asset sources (pinned, licence-checked)

- **Fonts:** the woff2 files come from the `@fontsource` npm packages for Libre Caslon Display, Libre Caslon Text and Atkinson Hyperlegible, fetched from `cdn.jsdelivr.net/npm/@fontsource/<family>@<exact version>/files/…` (latin subset). Weights: Caslon Display 400; Caslon Text 400, 400 italic and 700; Atkinson 400 and 700. The OFL licence text is fetched from the same package.
- **Pieces:** the 12 cburnett SVGs come from `raw.githubusercontent.com/lichess-org/lila/<pinned commit>/public/piece/cburnett/{w,b}{K,Q,R,B,N,P}.svg`, with the CC BY-SA 3.0 credit.
- **Manifest:** `static/ASSETS.md` records each file's source URL, version or commit, licence and sha256. Downloads use `curl -fsSL` into the project, and nothing is fetched at runtime.

## Steps

- [x] Step 1: Project structure. Create `static/css/`, `static/js/board/`, `static/fonts/`, `static/pieces/cburnett/`, `static/demo/` and `tests/js/`. Add the asset manifest skeleton `static/ASSETS.md`. No change to the old client files.
- [x] Step 2: Verify the test runner. `node --version` reports 24.x, so `node --test` is built in with no npm install. Record the unit command `node --test tests/js/` in `unit-test-instructions.md`. Add `tests/test_frontend_js.py`, which runs that command through `subprocess` and fails on a non-zero exit (or skips with a clear reason when `node` is missing). This puts the JavaScript tests inside the approved check `uv run --frozen pytest -q`.
- [x] Step 3: Assets. Download the fonts and pieces as listed above, pinning the exact versions and commit, and fill `static/ASSETS.md` with the URLs, licences and sha256 values. Draw `static/logo.svg` (a 2×2 checker in a walnut tile with a brass inlay).
- [x] Step 4: Design system CSS.
  - `static/css/tokens.css`: every colour token, light and dark, with `prefers-color-scheme`, plus the `[data-theme]` overrides.
  - Brass accent with `--accent-fill` #8A6A22 in light mode.
  - Board theme tokens under `[data-board]`, with label tokens per theme.
  - Type scale, radius and motion tokens. Reduced motion sets the durations to 0.
  - `static/css/base.css`: `@font-face` rules with `font-display: swap`, the page ground, the type roles, the four button roles, the 3 px focus ring and the logo mark.
  - `static/css/board.css`: frame, inlay, grid, squares, labels inside or in the frame, the four highlights, piece sizing and the black-piece edge.
- [x] Step 5: Pure modules.
  - `static/js/board/geometry.js`:
    - square list per orientation (BR1.2);
    - square colour (BR1.1);
    - label placement (BR1.3);
    - FEN to piece map, with validation;
    - targets for a square, and whether a target is a promotion (BR2.1, BR2.2);
    - `diffMove(prevPieces, nextPieces, lastMove)` for animation, including castling, en passant and promotion, returning null when it cannot match (BR4.1);
    - focus moves with arrow keys at the edges (BR2.4);
    - the accessible name (BR3.2);
    - the king square in check.
  - `static/js/board/interaction.js`: the pure reducer described above.
  - `static/js/settings.js`:
    - `createSettings(storage)` with the allow-lists, defaults, corrupt-value fallback per key, `persistent`, `subscribe` and storage-event sync (BR6.1, BR6.2);
    - `applyToDocument`;
    - `safeLocalStorage()`.
  - `static/js/contrast.js`: a WCAG relative-luminance helper, used by the tests and the demo's self-check.
- [x] Step 6: Tests for the pure modules (`tests/js/geometry.test.mjs`, `interaction.test.mjs`, `settings.test.mjs` and `contrast.test.mjs`), run with `node --test tests/js/`:
  - a1 is dark and h1 is light;
  - black orientation puts h1 at the top left;
  - labels follow the orientation in both modes;
  - FEN parsing, including a bad FEN;
  - targets match the legal moves exactly, and promotion is detected;
  - diffMove handles a normal move, a capture, castling on both sides, en passant and promotion, and returns null for unrelated positions;
  - focus moves stop at the edges and are mirrored for black;
  - names: "e4, white pawn", "e4, empty", plus the suffixes.
  - Reducer:
    - selecting a piece that cannot move does nothing;
    - retapping clears the selection;
    - a target emits a move and enters pending;
    - a promotion target opens the picker, where cancel and pick both work;
    - interactive false from selected, promoting or pending gives locked with the right effects;
    - reject clears pending;
    - a position equal to the optimistic one gives no animation.
  - Settings:
    - the defaults;
    - a corrupt value for one key keeps the others;
    - storage that throws gives persistent false while values still work;
    - subscribers are called;
    - an unknown value is refused;
    - a storage event updates the values.
  - Contrast:
    - pieces against all six squares, 3:1 or more;
    - labels, 4.5:1 or more;
    - the primary button pairs in both themes, 4.5:1 or more;
    - body and muted text in both themes, 4.5:1 or more.
- [x] Step 7: DOM components.
  - `static/js/board/board.js`: `createBoard`, `set`, `reject`, `focus` and `destroy`, as in frontend-components.md. It builds the 64 squares once and updates them in place, uses a roving tabindex, slides with Web Animations, does the capture fade and the check pulse, honours reduced motion, and keeps pending squares `aria-disabled`.
  - `static/js/board/promotion.js`: the dialog, the focus trap, arrows, Enter and Escape, closing on an outside click, and resolving null.
  - `static/js/settings-panel.js`: radio groups and switches, the notifications hook contract above, the `extraRows` slot, the credit line and the not-persistent notice.
  - `static/js/boot.js`: sets the theme and board attributes before first paint.
- [x] Step 8: Frontend behaviour checks.
  - `static/demo/board.html`:
    - every board theme and both page themes;
    - both orientations and label modes;
    - "play a scripted game", with a capture, castling, check and a promotion;
    - the settings panel;
    - a reduced-motion toggle note;
    - a contrast self-check that lists any pair below its threshold.
  - Add `tests/js/assets.test.mjs`, which checks that every font and piece file in `ASSETS.md` exists and matches its sha256, and that `board.css` and `base.css` only reference files that exist.
  - Run `node --test tests/js/` and then `uv run --frozen pytest -q`.
- [x] Step 9: Environment and serving. The existing `/static` mount already serves everything, so no backend change is needed. Confirm that `/static/demo/board.html` loads every module and asset with no 404, using the FastAPI TestClient in `tests/test_frontend_js.py`.
- [x] Step 10: Documentation and traceability.
  - Add module header comments, including the caller's duty to call `reject()`.
  - Add a README section, "Design system and demo page", that names the credit for the pieces and fonts.
  - Fill `code-summary.md`, `traceability.json` and `source-manifest.json`.

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

Inapplicable layers:
- Data model / database and repository: U2 has no stored data on the server. Settings live in the browser and are tested as business logic in Step 6.
- API / endpoint: U2 adds no routes. Step 9 only confirms static serving.
