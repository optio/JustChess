# Code Generation Plan — docs retirement and Stockfish auto-install

## Summary

- Builds: retires REQUIREMENTS.md in favour of the AI-DLC requirements, and makes the app fetch and verify a pinned Stockfish binary at boot
- Touches: REQUIREMENTS.md (deleted), README.md, app.py, new stockfish_install.py, new tests/test_stockfish_install.py, pyproject.toml, .gitignore, the requirements record (FR9, constraint update)
- Tests: 7 unit tests for the Stockfish installer (pytest, no network)

## Scope

This build step covers the docs change plus a Stockfish install when the app boots, as you asked when choosing the build scope ("1, but also include the stockfish install upon boot"). The P1 product features in `requirements.md` (FR1–FR8, NFR1–NFR10) are not built here. They are left for a separate piece of work with its own design and plan, and are listed as `Deferred` in this step's traceability.

Using Stockfish for blunder warnings or practice judgement is also not built here: this step only makes the engine available. The current code (`app.py`, the code knowledge base in `aidlc/spaces/default/codekb/JustChess/`) is changed only where the steps below say.

## Design notes (Stockfish auto-install)

- Pinned release: official Stockfish `sf_19` from `https://github.com/official-stockfish/Stockfish/releases/download/sf_19/`. Assets and SHA-256 checksums are taken from the GitHub release:
  - Linux aarch64: `stockfish-linux-arm64-universal.tar.gz`, sha256 `fe26cfd1d9db4c8af3d21e24d9ff34cacb31c1f940085a7583da11796f2bac01`
  - Linux x86_64: `stockfish-linux-x86-64-universal.tar.gz`, sha256 `9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f`
  - macOS: `stockfish-macos-universal.tar.gz`, sha256 `a1f0e3bcc5a6927a11fe6fc8e54a779754645f3c2bae2cf13420fd1957adaa77`
- Resolution order at boot:
  1. `STOCKFISH_PATH` environment variable, when it points to an executable file;
  2. `stockfish` on the system PATH;
  3. a binary already installed by this app under `.engines/stockfish-sf_19/`;
  4. otherwise download, verify and install the pinned build — unless `STOCKFISH_AUTO_INSTALL=0`.
- Safety:
  - The checksum must match before anything is extracted.
  - Only the one regular-file member whose name starts with `stockfish` is extracted, by name, into the install folder. Absolute paths, `..` and links are refused.
  - The binary is made executable.
  - Downloads time out after 60 s.
  - Any failure is logged and the app starts without an engine; boot never fails because of Stockfish.
- Startup: the install runs in a background thread started from the FastAPI lifespan, so the app serves requests immediately. The result is kept on `app.state.stockfish` and shown by a new read-only `GET /api/engine` (`{"available": bool, "path_source": "env"|"path"|"cached"|"downloaded"|null, "version": "sf_19"|null}`). The binary's file path is not exposed.
- Licence: Stockfish is GPLv3. Downloading it on the server at runtime does not redistribute it. The README notes that a published image which includes the binary takes on GPL obligations.

## Steps

- [x] Step 1: Verify the existing test runner and record the exact command. `uv run --frozen pytest --version` reports pytest 9.2.0 (dev group). No tests exist yet. Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` to `pyproject.toml`. The command for this step's tests is in `unit-test-instructions.md`.
- [x] Step 2: Business logic — create `stockfish_install.py` with:
  - `PINNED_VERSION`;
  - a `RELEASES` table (platform key → asset name and sha256);
  - `platform_key()`;
  - `resolve_existing(env, which, install_dir)`;
  - `verify_sha256(path, expected)`;
  - `safe_extract(archive, member_prefix, dest)`;
  - `download(url, dest, timeout)`;
  - `ensure_stockfish(install_dir, env, auto_install)`, which returns a small result object (`path`, `source`, `version`, `error`).

  Network and filesystem access go through parameters so tests can replace them. Errors at each integration boundary (download, checksum, extraction, chmod) are caught, logged with `logging`, and returned in `error`. None are silent.
- [x] Step 3: Business logic tests — write and run `tests/test_stockfish_install.py` (7 tests, no network; downloads are faked with a locally built tar.gz):
  - (a) `STOCKFISH_PATH` wins when executable;
  - (b) a PATH binary is used when there is no env path;
  - (c) an already installed cached binary is reused without downloading;
  - (d) download plus correct checksum installs an executable binary;
  - (e) a checksum mismatch installs nothing and reports an error;
  - (f) an archive member with `..` or an absolute path is refused;
  - (g) `STOCKFISH_AUTO_INSTALL=0` or an unsupported platform returns "not available" without downloading.
- [x] Step 4: API / endpoint — in `app.py`:
  - extend `lifespan` to start `ensure_stockfish` in a background thread (`asyncio.to_thread`, not awaited before `yield`);
  - store the result on `app.state.stockfish`;
  - add `GET /api/engine` returning availability, source and version.

  Existing routes are unchanged.
- [x] Step 5: API / endpoint tests — add to `tests/test_stockfish_install.py` one test that patches `ensure_stockfish` to a fake result. It checks that `GET /api/engine` reports it, using FastAPI's `TestClient` (httpx is already in the dev group). The file then holds 8 tests in total.
- [x] Step 6: Environment configuration — add `.engines/` to `.gitignore` (outside the AI-DLC block).
- [x] Step 7: Documentation:
  - delete `REQUIREMENTS.md`;
  - in `README.md`, replace the line that links to it with a link to `aidlc/spaces/default/intents/261111-requirements-review/inception/requirements-analysis/requirements.md`, plus a note that requirements live in the AI-DLC records;
  - add a short "Stockfish" section: auto-install at boot, `STOCKFISH_PATH`, `STOCKFISH_AUTO_INSTALL=0`, the `.engines/` folder, and the GPLv3 note.
- [x] Step 8: Requirements record update. Add to `aidlc/spaces/default/intents/261111-requirements-review/inception/requirements-analysis/requirements.md`:
  - FR9 "Chess engine availability" with FR9.1, "The app installs a pinned, checksum-verified Stockfish at boot when none is present, and starts normally when it cannot" (Built, Must, P1, origin: your build-scope answer);
  - a matching constraint wording: an engine may be installed, and using it for analysis is a later decision.

  Add FR9 and FR9.1 to its `traceability.json`.
- [x] Step 9: Traceability — write this step's `traceability.json`. FR9.1 is `OK` and targets `stockfish_install.py`; every other FR/NFR ID is `Deferred`, with your build-scope answer as the reason.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "org",
  "ordering": "implement each applicable testable layer, then write and run that layer's tests.",
  "scope": "poc",
  "test_strategy": "minimal",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    }
  ],
  "obligations": {
    "strategy": "minimal",
    "strategy_volume": [
      "One verifiable test per requirement at the narrowest effective level.",
      "At least one happy-path unit test per component.",
      "Unit tests are the default; a bugfix/security scope floor may require an integration or E2E regression when that is the narrowest level that reproduces the defect."
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
  "input_sha256": "sha256:ddd208517f68585f816e80821872bd21e26dc15e7bf545c6a78ec96b6afc20da",
  "contract_sha256": "sha256:8780c9b6738d34215859c7d0d02b149a16944cf2942a43d2c2dee67268c80df0"
}
```

Inapplicable layers: there is no data-model, repository or frontend change in this step, so those layers have no steps.
