# Blunder Rules — u4-blunder-warnings

These rules apply U4's rows of `inception/units-generation/unit-of-work-story-map.md`, taken from `inception/requirements-analysis/requirements.md`. The Analysis behaviour comes from `inception/domain-design/components.md`, and the dialog from `inception/refined-mockups/mockups.md` (Screen 3) and `interaction-spec.md` (Blunder dialog). The data is defined in `entities.md`.

```yaml
rules:
  # BR1 — What counts as a blunder
  - id: BR1.1
    statement: A move allows mate in one when, after it, the opponent has a legal move that checkmates.
    category: calculation
    applies_to: Warning.mate_in_one
    trigger: check-move
    logic: play the candidate; for each opponent legal move, play it and test checkmate; the first mating reply (in SAN order) is reported
    violation: n/a
    source: FR3.7
  - id: BR1.2
    statement: A knight, bishop, rook or queen of the mover is capturable without loss when the opponent, moving next, can win material on its square through the best capture sequence on that square (static exchange evaluation).
    category: calculation
    applies_to: Warning.hanging_piece
    trigger: check-move
    logic: for each mover non-pawn piece, run SEE on its square with the opponent to move, using the least valuable attacker first and PieceValue; gain > 0 means capturable without loss; for the moved piece on a capture, the capture already made counts, so warn only when the gain exceeds the value just captured (an even trade is not a blunder)
    violation: n/a
    source: FR3.8
  - id: BR1.3
    statement: Only a problem the move itself creates is reported. A piece that was already capturable before the move, and still is after it, does not cause a warning. A mate-in-one threat that already existed before the move, and still exists after it, does not cause a warning either.
    category: policy
    applies_to: Warning
    trigger: check-move
    logic: compute the hanging set and the mate-in-one threat both before the move (as if the opponent were to move, with the turn passed) and after it; the moved piece is tracked from its origin square to its destination; warn only for items in after minus before
    violation: n/a
    source: FR3.11
  - id: BR1.4
    statement: There is no warning when every legal move in the position has a problem of the same kind.
    category: policy
    applies_to: Warning
    trigger: check-move
    logic: when the candidate has a mate_in_one (or hanging_piece) warning, also check every other legal move for the same kind under BR1.1–BR1.3; when none is free of it, return no warning
    violation: n/a
    source: FR3.11
  - id: BR1.5
    statement: When a move both allows mate and hangs a piece, mate in one is reported. When several pieces hang, the most valuable is reported, and on a tie the one nearest the a1 corner in square order.
    category: calculation
    applies_to: Warning
    trigger: check-move
    logic: priority mate_in_one > hanging_piece; among hanging pieces, highest PieceValue, then lowest square index
    violation: n/a
    source: FR3.7, FR3.8

  # BR2 — The check route
  - id: BR2.1
    statement: POST /api/rooms/{code}/check-move judges a candidate move for the seat whose turn it is, against the game's current version. It changes nothing.
    category: authorization
    applies_to: route
    trigger: request
    logic: validate code and body (MoveCheck); authorise the seat with U1's seat-token rule; IF the game is not playing → 409 "Game is over" or "Waiting for an opponent"; IF version mismatch → 409 with snapshot; IF not this seat's turn → 403 "Not your turn"; IF illegal → 400 "Illegal move"; ELSE return CheckResult
    violation: as listed; same origin and 4 KB limits as U1
    source: FR3.7, FR3.8
  - id: BR2.2
    statement: The check answers within 300 ms at the 95th percentile on the Raspberry Pi host for normal middlegame positions.
    category: constraint
    applies_to: route
    trigger: request
    logic: the BR1.4 sweep runs at most once per check, and only when the candidate already has a warning
    violation: a test with a busy middlegame position fails if a check takes over 300 ms on the host
    source: NFR5

  # BR3 — The dialog and the setting
  - id: BR3.1
    statement: When blunder warnings are on, every move is checked before it is sent. With no warning, it is sent at once. With a warning, the dialog asks first.
    category: policy
    applies_to: client move hook
    trigger: board move
    logic: hooks.beforeMove(uci, snapshot) → IF settings.blunderWarnings is false THEN true; ELSE call check-move; null warning → true; warning → open the dialog and resolve with the choice
    violation: n/a
    source: FR3.9, FR3.7, FR3.8
  - id: BR3.2
    statement: The dialog names the consequence in its title and the details in its body. For mate in one the title is "This allows checkmate" and the body is "<Opponent colour> can play <mate>." For a hanging piece the title is "Your <piece> can be taken for free" and the body is "After <move>, <colour>'s <capturer> on <square> takes it and nothing takes back." When the piece is defended but still loses material, the body ends "…takes it and you lose material." instead.
    category: calculation
    applies_to: dialog text
    trigger: warning shown
    logic: buttons "Choose another move" (secondary, focused, the safe default) and "Play <move> anyway" (primary)
    violation: n/a
    source: FR3.7, FR3.8
  - id: BR3.3
    statement: The dialog is modal and accessible. Focus starts on "Choose another move" and stays inside the dialog, Escape cancels, and focus returns to the board afterwards. Cancelling leaves the position unchanged.
    category: constraint
    applies_to: dialog
    trigger: open, close
    logic: role="dialog", aria-modal="true", aria-labelledby set to the title; cancel resolves false, which makes the board slide the piece back
    violation: n/a
    source: FR3.7, FR3.8, NFR6
  - id: BR3.4
    statement: If the check cannot be made (network failure or a server error), the move goes ahead without a warning and the failure is logged in the browser console. If the check answers 409 (the board changed), the move is not sent, and the newer snapshot from the live connection takes over.
    category: policy
    applies_to: client move hook
    trigger: check failure
    logic: status 0 or 5xx → resolve true and console.warn; 409 → resolve false and apply the snapshot when one is attached; 400/403 → resolve false and show the message
    violation: n/a
    source: FR3.9
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | Allows mate in one | calculation | FR3.7 |
| BR1.2 | Non-pawn piece capturable without loss (exchange evaluation) | calculation | FR3.8 |
| BR1.3 | Only problems the move creates | policy | FR3.11 |
| BR1.4 | No warning when every move has the same problem | policy | FR3.11 |
| BR1.5 | Mate first, then the most valuable piece | calculation | FR3.7, FR3.8 |
| BR2.1 | Check route: seat, version, turn, legality; read-only | authorization | FR3.7, FR3.8 |
| BR2.2 | p95 of 300 ms or less on the host | constraint | NFR5 |
| BR3.1 | Setting on: check before sending | policy | FR3.9 |
| BR3.2 | Dialog text | calculation | FR3.7, FR3.8 |
| BR3.3 | Modal dialog, safe default, Escape | constraint | FR3.7, FR3.8, NFR6 |
| BR3.4 | A failed check never blocks play; 409 stops the move | policy | FR3.9 |
