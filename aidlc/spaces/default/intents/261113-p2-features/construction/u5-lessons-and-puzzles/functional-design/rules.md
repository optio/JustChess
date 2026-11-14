# Business Rules — u5-lessons-and-puzzles

```yaml
rules:
  - id: BR1.1
    statement: Every lesson has a kind; a lesson without one is an opening.
    category: validation
    applies_to: Lesson
    trigger: lesson load
    logic: kind must be one of opening, trap, defence; missing kind = opening; any other value skips the file with a log line (existing skip behaviour)
    violation: file skipped and logged
    source: FR7.1, FR7.2, FR8.4
  - id: BR1.2
    statement: The lesson list can be filtered by kind.
    category: policy
    applies_to: GET /api/lessons
    trigger: request
    logic: optional query ?kind=opening|trap|defence; the summary of each lesson includes kind; an unknown kind value returns 400
    violation: wrong lessons listed
    source: FR7.1, FR8.4
  - id: BR1.3
    statement: The repo ships the required new lessons, each fully annotated and replaying legally.
    category: constraint
    applies_to: lessons/
    trigger: build and test
    logic: |
      Openings: ruy-lopez, sicilian, french, caro-kann, queens-gambit, london, kings-indian, scandinavian.
      Traps: legals-mate, fried-liver, fishing-pole, englund-gambit-trap.
      Defence, at least 4: scholars-mate-defence, fried-liver-defence, early-queen-raids, wayward-queen.
      Each has a note on every move, in original wording, and at least 8 plies, except traps, which need at least 6.
      A test loads every file and fails on any skip.
    violation: test fails
    source: FR7.1, FR7.2, FR7.3, FR8.4
  - id: BR2.1
    statement: Puzzles are loaded once at start-up from puzzles/*.json and validated; invalid puzzles are skipped and logged.
    category: validation
    applies_to: Puzzles
    trigger: app start
    logic: |
      For each puzzle, all of these must hold:
        - theme matches its file;
        - fen is legal;
        - every move is legal in order;
        - mateIn1 and mateIn2 puzzles end in checkmate after the last player move;
        - player-move counts match the theme.
      A failing puzzle is skipped with one log line that names its id.
      A file that cannot be read or parsed is skipped as a whole.
      Missing puzzles/ leaves the tactics tab empty, saying "Puzzles are not installed".
    violation: bad puzzle served
    source: FR8.3, NFR4
  - id: BR2.2
    statement: The shipped set has about 300 puzzles per theme, stays within 5 MB, and is credited.
    category: constraint
    applies_to: puzzles/
    trigger: build and test
    logic: each theme file holds 250..400 puzzles after validation; total size of puzzles/ is at most 5 MB; puzzles/LICENSE.md and static/ASSETS.md credit the Lichess puzzle database (CC0); the curation script records the source URL and the filter used
    violation: test fails
    source: FR8.3, FR8.6, NFR6
  - id: BR2.3
    statement: A puzzle is presented after the opponent's set-up move; the player must find the solution moves.
    category: policy
    applies_to: puzzle play
    trigger: puzzle opened
    logic: the board shows fen, then plays moves[0] (the set-up) with the normal slide; the player is the side to move after it; the board is oriented for the player
    violation: wrong side or position
    source: FR8.3
  - id: BR2.4
    statement: Moves are checked on the server against the solution; the opponent's replies come from the puzzle.
    category: calculation
    applies_to: POST /api/puzzles/{theme}/{id}/check
    trigger: player move
    logic: |
      Body {ply, uci}, where ply is the index into moves of the expected player move: an odd number from 1 to len(moves)-1, because moves[0] is the set-up.
      IF uci equals moves[ply] THEN correct: return the reply moves[ply+1] if any; solved when no reply remains.
      ELSE IF the move gives checkmate (any legal mate counts as correct on the last player move) THEN solved.
      ELSE wrong, with no solution in the answer.
      Hints and the solution use a separate route, POST /api/puzzles/{theme}/{id}/hint with body {ply, level}:
        - level "piece" returns {from: square of moves[ply]};
        - level "move" returns {uci: moves[ply]};
        - level "solution" returns {line: moves[ply:]}, the whole remaining line.
      An unknown theme or id gives 404; an illegal move, a bad ply or a bad level gives 400.
    violation: wrong verdict
    source: FR8.3
  - id: BR2.5
    statement: A wrong move is shown, then taken back, and can be retried without limit; hints come in two steps.
    category: policy
    applies_to: puzzle screen
    trigger: wrong move; Hint; Show solution
    logic: |
      Wrong move: shown for 600 ms, then taken back, and a banner explains it ("Not this one. Try again.").
      Hint, first press: highlights the piece to move. Second press: draws the arrow.
      Show solution: plays the rest at 800 ms per move and marks the puzzle "seen" but not solved.
      Next puzzle: goes to the next unsolved one in the theme.
    violation: lost retries or no hint
    source: FR8.3
  - id: BR3.1
    statement: The trainer hub shows its groups as tabs, with progress counts.
    category: policy
    applies_to: /learn
    trigger: page load
    logic: |
      Tabs come from the registry: Openings, Traps, Tactics, Defence, and Endgames once U6 registers it.
      ARIA tablist, with Left/Right/Home/End keys.
      Each tab shows "<solved>/<total>".
      The selected tab is remembered per device.
      Each row has a title, an optional subtitle, a "Done" mark and one action (Learn or Solve).
    violation: missing tab or counts
    source: FR8.1, FR8.5
  - id: BR3.2
    statement: Progress is recorded per device when a lesson's practice is completed or a puzzle is solved.
    category: policy
    applies_to: TrainerProgress
    trigger: lesson practice reaches its complete phase (the trainer state gains an arrowShown flag and a progress effect; a run where the arrow was shown still counts as done, since the arrow only appears after 3 misses); puzzle solved without "Show solution"
    logic: |
      Write the key <group>:<id> with the time.
      The Tactics tab count = solved puzzles in that theme; the tab total = sum over themes.
      Storage errors are ignored, and progress just isn't kept.
    violation: progress lost or wrong
    source: FR8.5
  - id: BR3.3
    statement: The Tactics tab credits the Lichess puzzle database.
    category: policy
    applies_to: hub Tactics tab, puzzle screen
    trigger: render
    logic: the line "Puzzles from the Lichess puzzle database, released under CC0." is shown under the Tactics list and on the puzzle screen
    violation: missing credit
    source: FR8.6
  - id: BR3.4
    statement: The main screen's Train button opens the hub.
    category: policy
    applies_to: lobby
    trigger: Train pressed
    logic: Train opens /learn, which is now the hub, with the Openings tab first
    violation: dead button
    source: FR8.1
```

## Summary

| ID | Rule | Source |
|---|---|---|
| BR1.1 | Lesson `kind` (opening default, trap, defence) | FR7.1, FR7.2, FR8.4 |
| BR1.2 | `?kind=` filter on the lesson list | FR7.1, FR8.4 |
| BR1.3 | 8 openings, 4 traps, 4 defence lessons; annotated, legal, tested | FR7.1–FR7.3, FR8.4 |
| BR2.1 | Puzzles validated at start-up; bad ones skipped | FR8.3, NFR4 |
| BR2.2 | 250–400 per theme, at most 5 MB, CC0 credit | FR8.3, FR8.6, NFR6 |
| BR2.3 | The set-up move is played first; the player finds the solution | FR8.3 |
| BR2.4 | Moves checked against the solution on the server; any mate counts at the end | FR8.3 |
| BR2.5 | Wrong-move feedback, two-step hint, show solution, next puzzle | FR8.3 |
| BR3.1 | Hub tabs with counts, ARIA tablist | FR8.1, FR8.5 |
| BR3.2 | Per-device progress | FR8.5 |
| BR3.3 | Lichess credit shown | FR8.6 |
| BR3.4 | Train opens the hub | FR8.1 |
