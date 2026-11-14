## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-13T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261113-p2-features/construction/u1-game-screen-polish/functional-design/rules.md > BR1.2 and BR1.6; frontend-components.md > Board "onCaptureShown" and CapturedRow | The captured row is derived from the server move list (BR1.6), but an optimistic capture is shown before the server confirms it, so the move list does not yet hold that move. The ghost animation ends and calls onCaptureShown, yet the row cannot list the piece until confirmation, so the 200 ms settle after the shrink (BR1.3) is not consistently achievable for the player's own captures. The specs do not say which wins. | State explicitly whether the row is updated optimistically (and reconciled on confirm or reject) or only after confirmation. Then align the BR1.3 timing and the onCaptureShown contract with that choice. | New |
| R-02 | Major | aidlc/spaces/default/intents/261113-p2-features/construction/u1-game-screen-polish/functional-design/functional-spec.md > W2 mode table; rules.md > BR2.1, BR2.2 | The modes overlap. A viewport with width at least 1024 and height at most 500 matches both desktop and landscape-phone, with no precedence stated. BR2.1's 640 px desktop cap is missing from the CSS formula in frontend-components.md (BoardFit). The 7 FR4.1 sizes are never listed, so the mode chooser tests cannot be written from this design. | Define mode precedence (landscape-phone first, for example). Add the 640 px cap to the BoardFit CSS. List the 7 test sizes with their expected mode and side. | New |
| R-03 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u1-game-screen-polish/functional-design/frontend-components.md > CapturedRow | The `is-new` fade is undefined on first render, on reload and on replay, where every captured piece would look new. | Add a rule that the initial render and a full-list replace do not animate. Only a one-piece append does. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u1-game-screen-polish/functional-design/rules.md > BR1.1 logic | "A square other than the mover's origin" is confusing. The existing diffMove already returns the victim square, so the rule can simply defer to it. | Reword BR1.1 to use diffMove's captured list as the source of truth. | New |
| R-05 | Minor | aidlc/spaces/default/intents/261113-p2-features/construction/u1-game-screen-polish/functional-design/functional-spec.md > Tests | No test is named for the 1.6 s "Copied" label reset, the refused-clipboard path, QR encoder load failure, or the BR1.2 no-double-animation case. | Add these cases to the unit and browser test lists. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| traceability.json read | All 11 FRs (FR2.1-2.3, FR4.1-4.3, FR5.1-5.5) are OK and each target names BR IDs that exist in rules.md | Traceability is complete. NFR2-NFR5 are cited in rule sources but not listed as upstream IDs; this is acceptable. |
| code spot-check (geometry.js, board.js, interaction.js, share.js) | diffMove returns captured with en passant, finishAnimations and slideBack exist, and share.js already has chooseShareMethod and copyText | The design extends the existing code feasibly. |

### Summary

The design covers all of U1's FRs, traces cleanly to BR IDs, and extends existing code (diffMove, finishAnimations, share helpers) feasibly. Two Major gaps (the captured-row timing for optimistic captures, and the layout-mode overlap and test sizes) should be settled at the gate. Neither blocks implementation.
