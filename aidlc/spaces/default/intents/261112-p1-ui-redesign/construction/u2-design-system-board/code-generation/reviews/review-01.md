## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-12
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | static/css/board.css:96-101 (.sq.is-last::before) with static/css/tokens.css:62 (--hl-last) and tests/js/contrast.test.mjs:55-57 | Coordinate labels are only contrast-tested on bare squares. The last-move overlay (brass at 38%) lightens the dark squares under the white label. Computed from the real tokens, the label falls to 4.14:1 on Walnut and maple and 4.22:1 on Tournament dark squares, below the 4.5:1 the plan commits to for labels. The check overlay and the target-dot shade also change the light-square label ratio, but those stay above 4.5:1 at the label corners. Last move is shown on almost every position, so this is the normal state. | Add contrast pairs for label on dark and light square under the last-move overlay, for all three boards. Then lighten the label colour, weaken --hl-last, or move the overlay under a darker label scheme until every pair is 4.5:1 or more. | New |
| R-02 | Minor | tests/js/contrast.test.mjs:36-39 with static/js/contrast.js pieceChecks | The piece test takes the better of fill and edge, so a black piece passes through the edge token alone (black fill is about 2.4:1 on Rosewood dark). The edge is a 0.6px double drop-shadow (tokens.css:73), and the test cannot show it is visible at piece size. The test confirms a token value, not what renders. | Add a check that `.piece.is-black` and the promotion `img.is-black` use `--piece-edge` (a CSS text assertion), and look at the edge on Rosewood in the demo page. Consider a 1px edge if it is faint. | New |
| R-03 | Minor | static/js/settings-panel.js:34, static/ASSETS.md "Licence note", static/pieces/cburnett/LICENSE.md | The licence question stays open. The UI credit says "Pieces: cburnett, CC BY-SA 3.0", yet ASSETS.md says the copy served comes from Lichess's GPLv2+ listing and "which credit to show is the project owner's call". CC BY-SA also asks for the author's name and a licence link, and the panel shows neither (the README does name the author). The files are unmodified, so there is no share-alike trigger yet. | Get the owner's decision before U3 ships the panel. Then show "Pieces: cburnett (Colin M.L. Burnett), CC BY-SA 3.0" with a link to the licence, or record GPLv2+ as the chosen licence. | New |
| R-04 | Minor | static/js/board/promotion.js:79-80 and static/js/board/board.js:346-351 | When the board locks, or a new position closes the picker, `cancel()` runs `finish`, which focuses the anchor square. That can pull focus off whatever the user is doing (for example the settings panel) when a remote position arrives. | Only restore focus on user-driven close (Escape, outside click, choice). Pass a flag from `cancel()` to skip it. | New |
| R-05 | Minor | static/ASSETS.md fonts table (version 5.3.0) | I could not verify the pinned `@fontsource` version or the sha256 values against the registry, because no network fetch was done. The tests check each file against its recorded hash only. This confirms the files did not change, not that they match the claimed source. | Re-download one file from the pinned URL during the next build review and compare hashes. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| node --test tests/js/ | PASS: 33 tests, 0 fail, 0 skipped | The reducer, geometry, settings, notification-hook, boot allow-list and asset tests pass. The contrast tests read the real tokens.css through contrast.js and assert non-empty result sets, so they are not always-pass. The gap is the highlight states (see Major). |
| uv run --frozen pytest -q | PASS: 48 passed | The Node suite runs inside pytest, and the TestClient follows every demo-page reference with no 404. |

**Checked and sound:** the reducer is pure, and locking from any state clears the selection and closes the picker (interaction.js:94-99). It keeps `pending` until a position or reject arrives, and squares keep `aria-disabled` while staying focusable (board.js:218-233). The 64 squares are built once and reused (board.js:121-122). The first render does not pulse (board.js:164, 475). A position equal to the optimistic one gives no animation (interaction.js:107). Castling is chosen by the king's two-square move. The notifications hook returns a Promise<boolean> and the switch is disabled while it is pending (settings-panel.js:134-146). boot.js uses the same key and allow-lists as the store. The old files static/app.js and static/style.css are unchanged in git. The `templates/index.html` change was already in the working tree before this unit and is not in the unit manifest.

### Summary

The unit is implementable and all the plan's findings are resolved in code, with 33 Node tests and 48 pytest tests passing. The one Major finding is that label contrast is untested, and measurably under 4.5:1, on last-move highlighted dark squares. Fix it before U3 builds on the tokens. The cburnett licence choice is still open and belongs to the owner.
