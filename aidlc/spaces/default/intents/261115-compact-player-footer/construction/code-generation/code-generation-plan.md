## Summary

- Builds: compact player footer, inline nickname editing, clear recovery actions and styled help/confirmation dialogs.
- Touches: templates/index.html, static/css/app.css, static/js/player-identity.js, focused tests, README and HANDOVER.
- Tests: requirement-driven browser/client checks for five footer requirements and accessibility, plus existing regressions.

## Implementation Steps

### Authorized Vercel Extension (execute after preserved completed footer steps)

- [x] Step V1: Establish current regression baseline from approved Build/Test and run targeted backend runner before edits. Inspect request/engine/live/notifier lifecycles. Update HANDOVER with current extension checkpoint. VFR1-VFR5.
- [x] Step V2: Implement PostgreSQL room transaction locks and shared event/presence coordination with direct Neon LISTEN/NOTIFY; WebSocket lifetime owns listeners, reconnect resync. Retain SQLite local path, stale-version validation and secret-safe payloads. Add/run real PG two-instance conflict/live tests. VFR2-VFR3.
- [x] Step V3: Refactor Vercel engine/background lifecycle into bounded request-safe/durable claimed operations, revalidation/retry and ephemeral verified installer. Avoid immortal background queues, preserve local behavior where appropriate. Add/run computer/trainer/race tests. VFR1/VFR4.
- [x] Step V4: Add durable notification outbox relevance/coalescing, bounded global claims/leases/send/retry and protected daily cron/housekeeping endpoint. Reuse existing push sender and VAPID secret; reject unauthorized cron, suppress stale events. Schema additions must not wipe external data. Add/run retry/push/multi-instance tests. VFR5.
- [x] Step V5: Add Vercel Python/dependency/static configuration, excludes for .env/databases/framework/runtime/tests, correct startup writable path. Update .env.example/README as needed. Root configures Production branch production and Preview via authenticated CLI in deployment stages; worker does not deploy. VFR1/VFR6.
- [x] Step V6: Run targeted real PG tests and full Python/Node/browser regressions; fix failures, record precise limits. Extend summary/traceability preserving existing footer evidence; HANDOVER after every meaningful step. VFR1-VFR6.

No Production deployment or Git production branch creation/push authorized. Owner requests actual implementation, verified Preview and release-branch settings. External project settings/Preview remain root responsibility; don't bypass stage outcomes.

- [x] Step 1: Run baseline Python/Node suites before application edits and inspect exact existing footer/dialog conventions. Record results and update HANDOVER active implementation checkpoint. FR1-FR5/NFR1-NFR2.
- [x] Step 2: Refine footer markup/CSS into compact aligned responsive groups, retaining attribution and 44px targets with smaller visual treatment. Inline SVG save/pencil/help icons reuse existing visual language; accessible names and focus states. FR1-FR2/FR5/NFR1.
- [x] Step 3: Implement explicit nickname display/edit/pending states in player-identity.js: unset editable, saved readonly pencil, inline save, Enter submit, pending protection, errors retaining draft/prior saved value and refresh not overwriting active draft. Write/run focused tests after implementation. FR2/NFR1.
- [x] Step 4: Consolidate to Copy player link, short privacy/cross-device help and New link. Retain actual bookmarkable/selectable recovery link as fallback/details rather than competing primary anchor. Implement styled modal(s) matching existing share dialog for regeneration and ? help. Explain ordinary page bookmark vs private link, revoke semantics, keep existing session. Handle cancel/Escape/backdrop/focus return, pending/error and no unintended network side effects. Write/run client and real-browser tests. FR3-FR5/NFR1.
- [x] Step 5: Update tests/test_player_identity_browser.py and tests/js/player-identity.test.mjs plus relevant accessibility checks; remove confirm stubs and validate actual dialog interaction. Real Chromium at 320/375px and desktop: layout overflow, nickname state transitions/errors, copy fallback, help semantics/focus, regeneration cancel/confirm/revocation/pending. Capture screenshots inside intent record for review if tooling permits; inspect them. Run existing Python/Node regressions after changes. Backend unchanged, no repeated PostgreSQL provisioning needed unless frontend change exposes a DB regression. FR1-FR5/NFR1.
- [x] Step 6: Update README if control wording changes, finish code-summary.md and traceability.json with all seven IDs, tick plan boxes. Keep HANDOVER updated after each milestone and test result; include exact next action/pending gate and leave only outstanding work. NFR2.

## Boundaries

Completed footer remains frontend-only. The authorized Vercel extension additionally changes backend coordination, auxiliary tables, bounded engine/push lifecycle and runtime configuration; identity/session APIs remain unchanged. Test with temporary databases, never .env or normal app data. No commits/push/deployment requested. Minimal test-after ordering applies to the single changed frontend layer, existing backend layers inapplicable. Preserve others' edits.

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

