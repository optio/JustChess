# Business Rules — u6-endgame-trainer

```yaml
rules:
  # --- Content -----------------------------------------------------------------
  - id: BR1.1
    statement: Endgame positions are loaded once from hand-written files and validated.
    category: validation
    applies_to: EndgameCatalog
    trigger: app start-up
    logic: read endgames/<category>.yaml for the four categories only (files are listed, never opened by a name from a request); each position must pass the EndgamePosition constraints (legal, not over, player to move, goal-appropriate material, unique id, text lengths); a failing position is skipped with one warning naming its id; an unreadable file is skipped whole; a missing folder gives an empty catalog marked not installed; fewer than 3 valid positions in a category is logged as a warning
    violation: a broken position reaches the player
    source: FR8.2
  - id: BR1.2
    statement: The repo ships at least 3 positions for each of queen mate, rook mate, king and pawn, and opposition.
    category: constraint
    applies_to: endgames/*.yaml
    trigger: content authoring and the content test
    logic: queen-mate and rook-mate positions have goal mate; king-pawn positions have goal promote or draw; opposition positions have goal promote or draw; every hint is written in our own words; a test loads the shipped folder and requires at least 3 valid positions per category and no skipped position
    violation: missing or invalid content
    source: FR8.2

  # --- Judging -----------------------------------------------------------------
  - id: BR2.1
    statement: A mate goal passes when the defender is checkmated, and fails on any draw or loss.
    category: calculation
    applies_to: Verdict for goal mate
    trigger: after each player move and each defender reply
    logic: IF the defender is checkmated THEN passed (checkmate); ELSE IF the player is checkmated THEN failed (player_mated); ELSE IF the position is stalemate, insufficient material, a threefold repetition (is_repetition(3)) or the fifty-move rule (is_fifty_moves()) THEN failed with that draw as the reason (stalemate, insufficient_material, threefold_repetition or fifty_moves); ELSE playing
    violation: a drawn mate attempt counted as done
    source: FR8.2
  - id: BR2.2
    statement: A promote goal passes when the player promotes a pawn, and fails when that is no longer possible.
    category: calculation
    applies_to: Verdict for goal promote
    trigger: after each player move and each defender reply
    logic: IF the player's last move was a promotion THEN passed (promoted); ELSE IF the defender is checkmated THEN passed (checkmate — winning outright meets the goal); ELSE IF the player is checkmated THEN failed (player_mated); ELSE IF the player has no pawns left THEN failed (pawns_lost); ELSE IF the position is a draw by stalemate, insufficient material, threefold repetition or the fifty-move rule THEN failed with that draw as the reason; ELSE playing
    violation: a promotion goal that can never be reached keeps going
    source: FR8.2
  - id: BR2.3
    statement: A hold-the-draw goal passes after the set number of player moves without losing, or on a draw by the rules.
    category: calculation
    applies_to: Verdict for goal draw
    trigger: after each player move and each defender reply
    logic: IF the defender is checkmated THEN passed (checkmate — better than a draw); ELSE IF the player is checkmated THEN failed (player_mated); ELSE IF the position is a threefold repetition, the fifty-move rule, stalemate or insufficient material THEN passed (with that reason); ELSE IF playerMoves ≥ holdMoves (30 by default) AND the defender's reply did not checkmate THEN passed (held_moves); ELSE playing with movesLeft = holdMoves − playerMoves
    violation: a held draw not recognised
    source: FR8.2
  - id: BR2.4
    statement: An attempt has a maximum length.
    category: constraint
    applies_to: play route
    trigger: a move list longer than maxPlies (300)
    logic: IF the list is longer than maxPlies THEN 400 "This attempt is too long; start again"; an attempt that reaches maxPlies while still playing ends failed (too_long)
    violation: unbounded replay work per request
    source: FR8.2
  - id: BR2.6
    statement: A finished board is never sent to the engine.
    category: constraint
    applies_to: play route
    trigger: judging after the player's move
    logic: after the goal rules, IF the board is over for any reason (board.is_game_over with claimable draws, or no legal moves) and no goal rule decided it THEN the attempt ends failed with the end as the reason; the engine is asked only when the board has legal moves for the defender
    violation: the engine is asked for a move on a finished board and the attempt never ends
    source: FR8.2
  - id: BR2.5
    statement: The defender plays at full strength.
    category: calculation
    applies_to: defender reply
    trigger: the attempt is still playing after the player's move
    logic: ask Engine (the U4 queue) for a move with defenderSkill (20) and defenderThinkSeconds (1.0), no depth limit and no random moves, on the board replayed from the start FEN and the validated move list; check the move is legal; apply it and judge again (BR2.1–BR2.3)
    violation: a weak or illegal defence
    source: FR8.2, NFR1

  # --- HTTP --------------------------------------------------------------------
  - id: BR3.1
    statement: The catalog routes list and return positions, and report whether the engine is available.
    category: policy
    applies_to: GET /api/endgames, GET /api/endgames/{positionId}
    trigger: the hub tab or the endgame screen
    logic: the list returns {installed, available, reason, categories: [{id, label, positions: [{id, title, goal, order}]}]}; one position returns {id, category, title, fen, goal, hint, holdMoves (goal draw only), index, count}; an unknown id gives 404 "No such position"; both work without the engine
    violation: the tab cannot show "Needs Stockfish"
    source: FR8.1, FR8.2, FR6.7
  - id: BR3.2
    statement: The play route validates the attempt, adds the defender's reply and returns a verdict.
    category: validation
    applies_to: POST /api/endgames/{positionId}/play
    trigger: each player move
    logic: |
      - The body is {moves: [uci...]}, origin-checked, within the existing default 4 KB body limit (a 300-ply list is about 2.7 KB).
      - Each move must be 4 or 5 characters of UCI and legal in order from the start FEN (400 "Illegal move" naming its index).
      - The list must end with a player move, so its length is odd (400 otherwise).
      - Judge after the player's last move. When the attempt is still playing, ask for the defender's reply (BR2.5) and judge again.
      - The answer is {status, reason, reply, playerMoves, movesLeft}.
      - The server keeps no session. Because progress is per device and nothing is scored on the server, earlier defender moves in the list are replayed as given and not re-checked against the engine.
    violation: an illegal or malformed attempt judged
    source: FR8.2
  - id: BR3.3
    statement: The play route is refused when the computer cannot answer.
    category: policy
    applies_to: play route
    trigger: the engine is unavailable or busy, or the address is over its limit
    logic: |
      - Unavailable gives 503 with the reason.
      - Busy gives 503 "The computer is busy, try again in a moment". An endgame play is busy when the queue is full, and also once refusalQueue requests are already waiting (endgames.refusal_queue in gameplay.yaml, default 16, like hints). That way live computer games keep their place in the queue.
      - The wait is bounded. A request still waiting after waitLimitSeconds (endgames.wait_limit_seconds, default 30) is cancelled and answered as busy.
      - The wait uses a neutral helper shared with hints. It cancels the engine request on client disconnect, with no hint wording.
      - More than playPerMinute (30) requests per minute from one address gives 429 with Retry-After 60. This reuses ratelimit.RateLimiter and client_address.
      - An attempt already passed or failed after the player's move is answered without asking the engine.
      - When the client disconnects while the request waits, the queued request is cancelled.
    violation: one client fills the engine queue
    source: FR6.7, NFR1

  # --- WebClient ---------------------------------------------------------------
  - id: BR4.1
    statement: The hub gets an Endgames tab.
    category: policy
    applies_to: static/js/training (hub-tabs registry)
    trigger: opening /learn
    logic: |
      - Register the "endgames" tab with a loader. It shows the four categories with their positions, Done for each position solved on this device (trainer-progress group endgames), and the count.
      - When the engine is unavailable, the tab shows "Needs Stockfish" with the reason, and the Play buttons are disabled.
      - When the catalog is not installed, it shows "No endgame positions are installed".
    violation: endgames unreachable from the hub
    source: FR8.1, FR6.7
  - id: BR4.2
    statement: The endgame screen lets the player try a position against the defender.
    category: policy
    applies_to: /learn/endgames/{positionId}
    trigger: Play in the Endgames tab
    logic: |
      - The status shows the goal: "Mate with the rook. Goal: checkmate. Position 1 of 3." or "Goal: hold the draw (30 moves, repetition or 50-move rule)".
      - For a draw goal it also shows "Move n of 30".
      - "Computer is thinking…" shows while a play request is pending, and the board is locked during that time.
      - Hint reveals the position's hint text.
      - Start again resets the attempt.
      - When passed: "Done! Mate in n moves.", "Done! Pawn promoted in n moves." or "Done! Draw held." The position is marked solved on this device, and a Next position button appears.
      - When failed: "The computer escaped. Start again." for a draw against a mate or promote goal, and "The computer won. Start again." when the player is mated.
      - 503 shows the unavailable or busy message, and 429 shows "Too many moves too fast. Wait a moment."
      - The attempt is kept in session storage (read and written in try/catch), so a reload continues it.
    violation: the trainer cannot be completed
    source: FR8.2
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | Load and validate endgame files once | validation | FR8.2 |
| BR1.2 | At least 3 positions per category, shipped | constraint | FR8.2 |
| BR2.1 | Mate goal judging | calculation | FR8.2 |
| BR2.2 | Promote goal judging | calculation | FR8.2 |
| BR2.3 | Hold-the-draw judging (30 moves, repetition, 50-move) | calculation | FR8.2 |
| BR2.4 | Attempt length cap | constraint | FR8.2 |
| BR2.5 | Full-strength defender through the U4 engine queue | calculation | FR8.2, NFR1 |
| BR2.6 | A finished board never reaches the engine | constraint | FR8.2 |
| BR3.1 | List and get routes with availability | policy | FR8.1, FR8.2, FR6.7 |
| BR3.2 | Play route: validate, reply, verdict | validation | FR8.2 |
| BR3.3 | Unavailable, busy and rate limits | policy | FR6.7, NFR1 |
| BR4.1 | Endgames tab in the hub | policy | FR8.1, FR6.7 |
| BR4.2 | Endgame screen | policy | FR8.2 |
