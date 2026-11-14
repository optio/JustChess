# Training Rules — u6-training

These rules apply the U6 rows of `inception/units-generation/unit-of-work-story-map.md`, taken from `inception/requirements-analysis/requirements.md`. They follow the training notes in `inception/refined-mockups/mockups.md`. The data shapes are defined in `entities.md`.

```yaml
rules:
  # BR1 — Loading lessons
  - id: BR1.1
    statement: Every .yaml, .yml or .json file in lessons/ is a lesson. Adding a file adds a lesson with no code change.
    category: policy
    applies_to: LessonCatalog
    trigger: startup; a list or detail request when the folder's file names or modification times have changed
    logic: scan the folder; parse each file; validate it (BR1.2); expand the valid ones (BR1.3); swap in the new catalog in one step
    violation: n/a
    source: FR7.6
  - id: BR1.2
    statement: A lesson file must have a valid id, a name, a side of white or black, a valid start, at least 1 and at most 60 moves each with a note, and every move must be legal in order. Files that fail are skipped, and each problem is logged at warning level with the file name and the reason.
    category: validation
    applies_to: LessonFile
    trigger: load
    logic: IF a required field is missing or of the wrong type, a SAN is illegal in its position, SAN and UCI disagree, the eco is malformed, or the id repeats THEN skip the file and record {file, reason}; valid files still load
    violation: the file is skipped; GET /api/lessons still answers with the valid ones
    source: FR7.7
  - id: BR1.3
    statement: Each valid lesson is expanded into steps. Every step carries the position before and after the move, every legal move in the position before, and the move in both SAN and UCI.
    category: calculation
    applies_to: LessonStep
    trigger: load
    logic: replay from start; for each ply record fenBefore, legalBefore (UCI, sorted), uci, san, fenAfter, side, note, alternatives
    violation: n/a
    source: FR7.1, FR7.3
  - id: BR1.4
    statement: The catalog ships the Italian Game (1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3, ECO C53) and the French Exchange, Monte Carlo Variation (1.e4 e6 2.d4 d5 3.exd5 exd5 4.c4, ECO C01). White is the default side for both.
    category: constraint
    applies_to: lessons/
    trigger: n/a
    logic: two files, lessons/italian.yaml and lessons/monte-carlo.yaml, each with a note on every move and two or three objectives
    violation: n/a
    source: FR8.1

  # BR2 — Lesson routes
  - id: BR2.1
    statement: GET /api/lessons lists the valid lessons as id, name, aliases, eco, side and number of moves, sorted by name.
    category: calculation
    applies_to: route
    trigger: request
    logic: reload when the folder changed (BR1.1); never include the problems list or file paths
    violation: n/a
    source: FR7.6
  - id: BR2.2
    statement: GET /api/lessons/{id} returns a lesson with its objectives and steps. An unknown or malformed id returns 404 "Lesson not found".
    category: validation
    applies_to: route
    trigger: request
    logic: the id must match ^[a-z0-9][a-z0-9-]{0,47}$ before any lookup; the id is never used to build a file path
    violation: 404
    source: FR7.1, FR7.7
  - id: BR2.3
    statement: For free play off the line, POST /api/position/move takes a position and a move and returns the new position, its legal moves, the SAN, whether it is check, and the outcome. It keeps no state.
    category: calculation
    applies_to: route
    trigger: request
    logic: body {fen, uci}; the fen must parse and be valid, the uci must be legal in it; reply {fen, san, legalMoves, check, outcome}; same-origin and 4 KB limits from U1 apply
    violation: 400 "Illegal move" or 400 "Invalid position"
    source: FR7.5

  # BR3 — Walkthrough
  - id: BR3.1
    statement: The walkthrough starts at the lesson's start position. Next plays the next move with the shared slide animation, highlights its from and to squares, and shows its note. Back undoes one move. Restart returns to the start.
    category: policy
    applies_to: walkthrough
    trigger: Next, Back, Restart
    logic: index runs from 0 to the number of moves; Next is disabled at the end and Back at the start; the board is not interactive; the note is shown beside the scoresheet row in book italic and announced politely
    violation: n/a
    source: FR7.1, FR7.2

  # BR4 — Practice
  - id: BR4.1
    statement: In practice the learner plays the lesson's default side, and a switch lets them practise the other side. The trainer plays the other side's scripted moves on its own.
    category: policy
    applies_to: practice
    trigger: start practice, switch side
    logic: when it is the trainer's ply, play the scripted move after 500 ms (at once with reduced motion); the board is interactive only on the learner's plies; switching side restarts practice from the start with the board turned
    violation: n/a
    source: FR7.3
  - id: BR4.2
    statement: A move by the learner is judged against the taught move for that step. A correct move is played and its note shown. An illegal move is refused with "That move isn't legal." A legal move off the line shows "Legal, but not this line", with "Keep playing freely" and "Back to the line".
    category: validation
    applies_to: practice
    trigger: learner move or rejected tap
    logic: IF the UCI equals step.uci THEN correct; ELSE IF the UCI is in step.legalBefore THEN off-line (count a miss); ELSE illegal (count a miss)
    violation: as stated; the position is unchanged until the learner chooses
    source: FR7.5
  - id: BR4.3
    statement: Hints follow misses on the same step. After the first miss, "Hint" highlights the square of the piece to move. After the third miss, the expected move is shown as a dashed brass arrow, together with its SAN and note. The count resets when the step is played.
    category: policy
    applies_to: practice
    trigger: miss
    logic: misses per step; the Hint button is always available and shows the from-square; at 3 misses draw the arrow from step.uci and show "The move is <san>. <note>"
    violation: n/a
    source: FR7.4
  - id: BR4.4
    statement: Free play continues from the off-line position with legal moves from BR2.3. The trainer stays silent, and "Back to the line" returns to the step where the learner left it.
    category: policy
    applies_to: practice
    trigger: Keep playing freely
    logic: each learner move in free play calls /api/position/move and lets the learner play both sides; the status reads "Free play — not part of the lesson"
    violation: an error reply restores the last position and shows the message
    source: FR7.5
  - id: BR4.5
    statement: At the end of the line, practice says "Line complete" and lists the objectives, with "Practise again" and "Practise as <other side>".
    category: policy
    applies_to: practice
    trigger: last step played
    logic: n/a
    violation: n/a
    source: FR7.3

  # BR5 — Where training opens
  - id: BR5.1
    statement: Training opens in two places. It runs inside the game's "Learn openings — your game keeps running" drawer, through U3's lessonsMount hook. It also runs on its own at /learn and /learn/{id}, reached from the lobby's "Learn an opening" button. The game keeps running while training is open in the drawer.
    category: policy
    applies_to: mounting
    trigger: drawer opened, lobby button, /learn URL
    logic: the trainer is one component mounted into a given element; in the drawer it uses its own board instance and never touches the game board or the game socket
    violation: n/a
    source: FR7.1, FR7.3
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | Any file in lessons/ is a lesson; reload when the folder changes | policy | FR7.6 |
| BR1.2 | Validation; bad files are skipped and reported | validation | FR7.7 |
| BR1.3 | Steps with positions and legal moves | calculation | FR7.1, FR7.3 |
| BR1.4 | Italian Game and French Exchange Monte Carlo | constraint | FR8.1 |
| BR2.1 | List route | calculation | FR7.6 |
| BR2.2 | Detail route with id validation | validation | FR7.1, FR7.7 |
| BR2.3 | Stateless position move for free play | calculation | FR7.5 |
| BR3.1 | Walkthrough: Back, Next and Restart, animated with notes | policy | FR7.1, FR7.2 |
| BR4.1 | Practice side and scripted replies | policy | FR7.3 |
| BR4.2 | Correct, illegal, or legal but off the line | validation | FR7.5 |
| BR4.3 | Hint, then the arrow and note after 3 misses | policy | FR7.4 |
| BR4.4 | Free play and back to the line | policy | FR7.5 |
| BR4.5 | Line complete | policy | FR7.3 |
| BR5.1 | Drawer and /learn mounting | policy | FR7.1, FR7.3 |
