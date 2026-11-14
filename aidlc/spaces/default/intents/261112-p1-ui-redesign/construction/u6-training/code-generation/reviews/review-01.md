## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-12T00:00:00Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | static/js/training/trainer.js:440-446 (side switch keydown), :91 (radio buttons) | The "Practise as" group is marked as a radiogroup, but every radio stays in the tab order and any arrow key at once restarts practice on the other side. A keyboard user who only meant to move focus loses their progress on the line. | Use one tab stop (roving tabindex) and move focus on arrow keys. Restart practice only on Space or Enter, or on click. | New |
| R-02 | Minor | static/js/training/trainer.js:382, :409 and the other `hidden` toggles in renderControls | Controls are hidden while they have focus (Practise, Keep playing freely, Practise again). Focus then falls to the page body, so a keyboard or screen-reader user has to find their place again. | After a phase change, move focus to the new primary control or to the status message. | New |
| R-03 | Minor | static/js/training/trainer.js:409 (mockups.md Training, FR7.3) | The mockup puts the "Practise as White / Black" switch above the board. It is hidden during the walkthrough, so the side can only be chosen after Practise has started on the lesson's own side. | Show the switch during the walkthrough too (Practise then uses it), or record the deviation in the code summary. | New |
| R-04 | Minor | static/css/board.css:123 (`.sq.is-hint`), tests/js/contrast.test.mjs | The new hint ring (dashed `--accent` outline) is the only cue for the piece to move, apart from the words in the status line. No contrast test covers it against the six squares, while the arrow is covered. | Add the ring colour to the contrast report at 3:1 on all six squares, in both themes. | New |
| R-05 | Minor | tests/js (no test mounts trainer.js), tests/test_game_screen.py:446-540 | The DOM view has no unit test. Timer cancellation in `destroy()`, free play, the side switch, the outcome lock and "Other lessons" are checked in the reducer only. The Chromium run covers the walkthrough, the off-line move, Back to the line, the arrow, the replies and drawer removal, but it is skipped when Chromium is missing. `lessons-api.js` has no direct test either. | Add a jsdom-free test with a fake `win` and `api` for `destroy()` (timer and request), or extend the browser run to free play and the side switch. Add a small test for `lessons-api.js` shape checks and abort handling. | New |
| R-06 | Minor | justchess/lessons.py:172 (`yaml.safe_load`) | `safe_load` blocks object construction, but YAML aliases can still expand a 64 KB file into a very large structure. The 64 KB cap bounds the file, not the expanded size. The folder is operator-controlled, so the risk is small. Not tested. | Reject files that contain anchors or aliases, or note in the README that lesson files are trusted. | New |
| R-07 | Minor | pyproject.toml:8 and the new `[tool.pytest.ini_options]` | The plan and code summary name only `pyyaml`. The diff against HEAD also changes `fastapi` to `fastapi[standard]` and adds pytest settings. This may come from an earlier unit; the summary does not say. | State in the code summary which unit made each pyproject change, or revert any that is not part of U6. | New |
| R-08 | Minor | code-generation/unit-test-instructions.md (tests table) | The table gives 8 and 8 tests for `test_lessons.py` and `test_lessons_api.py`; code-summary.md gives 11 and 22. The two documents disagree. | Make the counts match. | New |
| R-09 | Minor | static/js/training/lessons-api.js:45-52 (`readJson`) | An abort during `response.json()` is caught as a bad body, so the call logs "unexpected body" and returns a non-aborted failure. The trainer ignores it only because it drops stale controllers, so the console shows a false error. | Return `aborted: true` when the signal is aborted before reporting a bad body. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `node --test tests/js/` | PASS: 100 tests, 0 fail | Includes trainer-state (12), arrow (3), board-rejected-tap (6), room-flow (7) and the arrow contrast test. |
| `uv run --frozen pytest -q` | PASS: 90 passed | Includes the loader and route tests and the headless Chromium trainer run, which ran and was not skipped. |

### Plan findings table: verification

- **Safe file handling:** `safe_load` and `json.loads` only. Files over 64 KB, symlinks and non-regular files are skipped, and files open with `O_NOFOLLOW`. The id is regex-checked in the route and in `get`, and is never joined into a path. A missing folder gives an empty catalog and a warning. Reload goes through a stamp and a lock.
- **`onRejectedTap`:** `interaction.js:93` fires only with a selection and a non-target tap on an empty square or an opponent piece. Deselect, Escape, reselect, locked, pending and promoting taps do not fire it. The board tests pin each case.
- **Mounting contract:** `game.js:240-262` mounts on the first open and `destroy()` calls `stopLessons`. `trainer.destroy()` clears the timer and aborts the requests. The reducer cancels the reply timer whenever the state leaves practice or restarts it, and late timers are ignored by `seq`.
- **Off-line move:** it is shown, the board is locked, and Back to the line restores the step and keeps the misses. A pending request is aborted on any exit. A failed request slides back to practice.
- **Hint:** it sets `hintSquare` and says the square in words.
- **Free play:** the route checks the uci pattern and the FEN validity. The outcome lock and the unreported repetition are documented.
- **Alternatives:** shown under each note. **Route shape:** pinned by pytest, including the 404.
- **Lesson content:** both files load and replay with legal alternatives. The notes are chess-correct as far as I can check: the Italian Game C53 line and the Monte Carlo line 1.e4 e6 2.d4 d5 3.exd5 exd5 4.c4, whose "Monte Carlo" and C01 labels I take from the requirements and did not verify against an opening reference.
- **Carried U3 failure paths:** `app.js` uses `enterRoom`, `actionAnswer` and `submitMove`, so the room-flow tests exercise live code. They cover the stale seat, 409 full, continue redeem and its 403, a 403 seat refusal, 400 and 409 moves, and a throwing hook. The existing U2 and U3 callers are unchanged: the new options are optional and all earlier tests stay green.

### Summary

No Critical or Major issues. The design decisions in the plan's findings table are implemented and covered by passing tests, including a real browser run. The remaining points are accessibility, test depth and documentation drift.
