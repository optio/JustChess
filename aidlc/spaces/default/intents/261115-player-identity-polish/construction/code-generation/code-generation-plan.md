## Summary

- Builds: account-free cross-device identity, moderated nicknames and selection/outcome polish.
- Touches: backend schema/profile/API, browser identity/footer/board/results, gameplay configuration and tests.
- Tests: requirement-driven Python/Node checks, real PostgreSQL parity and representative real-browser scenarios.

## Implementation Steps

- [x] Step 1: Establish baseline with uv run --frozen pytest -q and node --test tests/js/. Inspect application seams and existing browser test tooling before edits. FR1-FR7/NFR2.
- [x] Step 2: Add player/session/recovery/seat associations and schema version bump in db.py plus small players.py module. Keep SQLite/PostgreSQL support; owner allows recreation, no backwards compatibility. Prefer explicit startup refusal/instructions for incompatible external PG data over wiping an arbitrary populated external schema automatically. Implement profile/recovery credential hashing, distinct session and recovery authority, regenerated recovery invalidation while existing sessions remain valid. Write/run isolated model/SQL tests after implementation. FR2-FR4/NFR1-NFR2.
- [x] Step 3: Add bounded, origin-protected, rate-limited identity/profile/recovery APIs and attach authenticated players to newly acquired seats. Restore authorized existing room seats without rotating away other devices; retain turn/version locks and existing anonymous room flows. Include nicknames in appropriate viewer snapshots. Add and run API tests for two-device use, impersonation, replacement, invalid/revoked recovery and safe errors. FR2-FR6/NFR1.
- [x] Step 4: Add English-only server-side nickname validation/filtering using a local bounded vocabulary; Unicode/case/common obfuscation normalization and token-aware matching avoiding innocent substring false positives. Optional cleared name and bounded length; text-only presentation. Add/run validation/API tests. FR5/NFR1.
- [x] Step 5: Add browser identity store/client and footer save/copy/regenerate/nickname controls. Fragment-only private recovery link; redeem via body then clear fragment, preserve explicit copy/bookmark URL. Handle invalid links/storage failures clearly. Restore game list/seat credentials from identity. Add/run Node tests after implementation. FR2-FR5/NFR1.
- [x] Step 6: Enlarge selected piece without geometry/hit-target changes, reusing board state. Add viewer-relative win/loss text and finite winner-only confetti via existing result lifecycle, reduced motion and cancellation/reopen guards. Keep draw/watch/pass-along neutral and computer labels explicit. Put configurable scales/timings in gameplay.yaml and update validation/defaults as needed. Add/run view-model/motion/selection tests. FR1/FR6-FR7/NFR2.
- [x] Step 7: Verify real PostgreSQL identity/domain parity with dedicated disposable service, existing suites and real-browser workflows (existing tooling, no production data). Add tests/test_players.py, tests/test_player_api.py, tests/js/player-identity.test.mjs and extend relevant result/board tests; exact final file names may follow existing repository conventions. Browser checks must cover visible selection growth, cross-device recovery/nickname, personalized result and confetti/reduced-motion. Record limits honestly. FR1-FR7/NFR1-NFR2.
- [x] Step 8: Update README, gameplay docs and HANDOVER with current behavior/private link warning/recreation policy; remove completed handover items. Write code-summary.md and traceability.json, tick completed steps. No commits/push/deployment without request for this intent. FR1-FR7/NFR1-NFR2.

## Boundaries and Decisions

No accounts/email, identity merging, nickname uniqueness, training-progress synchronization, external account service or multi-worker support. Keep changes within existing architecture. Recovery secrets are high entropy, stored hashed; no plaintext recovery verifier in DB. Existing signed-in sessions are separate credentials. Only authorized identity association may release room seat credentials. Device restoration cannot steal arbitrary room seats; pass-along semantics remain explicit. A clear recovery link security warning belongs in the save UI. New schema may reset app-owned data only under documented owner-authorized recreation policy; never wipe unrelated external tables. Tests always isolated, never read .env or real databases.

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

