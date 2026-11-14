## Summary

- Builds: optional PostgreSQL persistence via DATABASE_URL with SQLite defaults.
- Touches: database/app/domain modules, dependencies, tests, .env.example, README.md and HANDOVER.md.
- Tests: requirement-driven configuration, schema, isolation, failures and backend parity tests plus existing regressions.

## Implementation Steps

- [x] Step 1: Run existing Python and JavaScript suites before application edits; verify pytest runner and record baseline. Inspect all persistence SQL/connection usage. FR2, NFR2.
- [x] Step 2: Add psycopg dependency and update uv.lock using uv lock; implement backend-aware connection/schema/transaction support in justchess/db.py (and a small adapter module if clearer). Preserve existing SQLite version-4 behavior, including archive/recreate for older files; do not invent SQLite legacy migrations. PostgreSQL creates empty schema transactionally, retains current schema, rejects unknown/older unsupported/newer schemas without destructive resets. Add and run schema/adapter tests after implementation. FR2, FR3, NFR1.
- [x] Step 3: Make domain SQL, IDs, row access and errors portable in rooms.py, games.py, summaries.py, notifications.py and other persistence consumers as needed; maintain transactions and current domain behavior. Write/run parity tests after changes, including rollback, constraints, joins, moves, summaries, cleanup and push state. FR2.
- [x] Step 4: Wire DATABASE_URL selection at application startup, preserving explicit create_app(db_path=...) isolation over ambient config. Preserve environment/.env precedence; absent or empty URL selects SQLite; invalid nonempty URL fails safely without fallback. Write/run configuration, failure/redaction and app tests after implementation. FR1, FR4, NFR1.
- [x] Step 5: Add tests/test_postgres.py (or similarly scoped files) with disposable PostgreSQL integration setup selected only through JUSTCHESS_TEST_DATABASE_URL; use an isolated schema and never normal DATABASE_URL for integration tests. Add local unit tests runnable without PostgreSQL and protect ambient-config test isolation. FR1-FR5, NFR1-NFR2.
- [x] Step 6: Update .env.example, tests/test_envfile.py allowlist, README and HANDOVER with precedence, schema policy, one-worker operation and isolated verification. Remove done handover tasks and retain active checkpoint. FR5, NFR2.
- [x] Step 7: Run targeted tests, then existing regressions; run real PostgreSQL tests if a dedicated service can be supplied with existing tooling. Record skips/limits honestly. Write code-summary.md and traceability.json mapping every FR/NFR to implementation/tests; tick completed plan steps. FR1-FR5, NFR1-NFR2.

## Scope and Risks

No UI or gameplay redesign, data transfer, distributed coordination, commit, push or deployment. Synchronous DB access remains consistent with the current app. PostgreSQL schemas use portable constraints and double-precision timestamps. SQL translation, if used, must be narrow and tested; database exceptions must retain correct transaction semantics and never expose connection credentials. Keep all existing user changes.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "org",
  "ordering": "implement each applicable testable layer, then write and run that layer's tests.",
  "scope": "express",
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
  "input_sha256": "sha256:c8f84e35190e007d9863fad236154d0269ab9bf633fc2a3ff106ed965ba4a9b9",
  "contract_sha256": "sha256:bb76c1b22f8307be6e5780d50cabab891684449d5b164bd0e825e9e4e5c61e5b"
}
```

