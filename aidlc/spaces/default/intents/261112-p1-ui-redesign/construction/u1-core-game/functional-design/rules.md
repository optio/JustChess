# Business Rules — u1-core-game

These rules apply the requirements mapped to U1 in `inception/units-generation/unit-of-work-story-map.md`, from `inception/requirements-analysis/requirements.md`. They respect the component boundaries in `inception/domain-design/components.md` and the unit scope in `inception/units-generation/unit-of-work.md`.

```yaml
rules:
  # BR1 — Rooms and joining
  - id: BR1.1
    statement: A new room gets a 6-character code from A-Z and 0-9, drawn from a cryptographic random source and unique among existing rooms.
    category: constraint
    applies_to: Room.code
    trigger: create room
    logic: IF the generated code already exists THEN draw again (at most 10 tries, then fail with "Could not create a room, try again")
    violation: creation fails with a retryable error
    source: FR1.1
  - id: BR1.2
    statement: Room codes are matched case-insensitively and must match the code format.
    category: validation
    applies_to: join, state, socket
    trigger: any request naming a code
    logic: IF the code, uppercased, does not match ^[A-Z0-9]{6}$ THEN reject as invalid; IF no such room THEN "Room not found"
    violation: 400 invalid code / 404 room not found
    source: FR1.2, FR1.3
  - id: BR1.3
    statement: The creator takes seat A. The first joiner without a valid token takes seat B. A third person is refused.
    category: constraint
    applies_to: Seat
    trigger: join
    logic: IF the request carries a token matching a seat of this room THEN return that seat (rejoin); ELSE IF seat B is empty THEN create seat B and start game 1; ELSE refuse with "This game already has two players"
    violation: 409
    source: FR1.2, FR1.3, FR1.4, FR1.5
  - id: BR1.4
    statement: Seat tokens and continue tokens are random values of at least 128 bits. Only their SHA-256 hashes are stored, and they are compared in constant time.
    category: authorization
    applies_to: Seat.tokenHash, Seat.continueTokenHash
    trigger: issue or verify a token
    logic: issue = random 32 bytes, URL-safe; store sha256(token); verify = constant-time compare of sha256(given) with the stored hash
    violation: 403 "This isn't your seat"
    source: NFR2, FR1.5
  - id: BR1.5
    statement: A seat can issue a continue token. Redeeming it moves the seat to the new device by issuing a fresh seat token and invalidating both the old seat token and the continue token.
    category: policy
    applies_to: Seat
    trigger: request continue link, redeem continue link
    logic: request = authorised seat only; replaces any earlier continue token. Redeem = IF the hash matches THEN set a new tokenHash, clear continueTokenHash, broadcast "seat moved" to the old device
    violation: 403 for an invalid or used continue token
    source: FR1.7
  - id: BR1.6
    statement: Every state-changing action identifies its seat by token. A room code alone never authorises an action.
    category: authorization
    applies_to: move, claim, rematch, continue link
    trigger: any state change
    logic: IF there is no token or no seat matches THEN refuse; IF the action requires a turn and it is not this seat's colour's turn THEN refuse "Not your turn"
    violation: 403
    source: NFR1
  - id: BR1.7
    statement: A seat is "away" when it has no live socket, and "abandoned" when its lastSeenAt is more than 24 hours old.
    category: calculation
    applies_to: Seat.lastSeenAt
    trigger: snapshot, claim win, rematch
    logic: abandoned = now - lastSeenAt > 24h (server clock); presence comes from live sockets, with a disconnect detected within 10 s by heartbeat
    violation: n/a
    source: FR1.6, FR11.2

  # BR2 — Game rules
  - id: BR2.1
    statement: A move is accepted only if the game is playing, the seat holds the side to move, the move is legal in the current position, and the sender's version equals the game's version.
    category: validation
    applies_to: Game, Move
    trigger: move
    logic: IF status != playing THEN 409 "Game is over"; IF wrong side THEN 403; IF not legal THEN 400 "Illegal move"; IF version mismatch THEN 409 "The board changed, here is the latest position" with a snapshot
    violation: as listed; the position is unchanged
    source: FR3.2, FR3.10, NFR4
  - id: BR2.2
    statement: After each move, the game ends automatically on checkmate, stalemate, insufficient material, fivefold repetition or the 75-move rule, and records the reason and result.
    category: calculation
    applies_to: Game
    trigger: accepted move
    logic: evaluate the outcome without claimable draws; IF an outcome exists THEN status=finished, endReason, result, endedAt
    violation: n/a
    source: FR4.2
  - id: BR2.3
    statement: Threefold repetition and the 50-move rule never end a game automatically. They make a draw claimable by the seat to move.
    category: policy
    applies_to: Game
    trigger: snapshot, claim draw
    logic: claimable = can_claim_threefold_repetition or can_claim_fifty_moves on the current position; claim accepted only IF claimable AND it is the claiming seat's turn, THEN finished, result 1/2-1/2, endReason threefold_claimed or fifty_moves_claimed
    violation: 409 "A draw can't be claimed right now"
    source: FR4.3
  - id: BR2.4
    statement: A seat may claim a win when the opponent's seat is abandoned.
    category: policy
    applies_to: Game
    trigger: claim win
    logic: IF the game is playing AND the opponent seat is abandoned (BR1.7) THEN finished, result in the claimant's favour, endReason abandoned
    violation: 409 "Your opponent hasn't been away long enough"
    source: FR11.2
  - id: BR2.5
    statement: The snapshot carries the position, legal moves, turn, check, status, end reason, result, a numbered move list, version, claimable draw, both seats' presence, the score, rematch state, and the viewer's own slot and colour.
    category: calculation
    applies_to: snapshot
    trigger: every state read and broadcast
    logic: moves are grouped as [{number, white, black}]; the legacy fields (fen, turn, status, moves as a flat SAN list, legal, white_score, black_score, check, outcome) stay present until U3
    violation: n/a
    source: FR3.4, FR3.5, FR3.6, FR1.6

  # BR3 — Match and rematch
  - id: BR3.1
    statement: When a game ends, the room score is updated for the winning seat (or draws) in the same transaction as the game result.
    category: calculation
    applies_to: Room.winsA, winsB, draws
    trigger: game finished
    logic: map the result to a slot using whiteSlot; increment winsA, winsB or draws; one database transaction covers the game update and the score update
    violation: on any failure the whole transaction rolls back and the move is reported as failed
    source: FR4.5
  - id: BR3.2
    statement: A rematch starts when both seats have asked for one after a finished game. Colours swap.
    category: policy
    applies_to: Room.rematchRequestedBy, Game
    trigger: request rematch
    logic: IF the current game is not finished THEN refuse; IF no request is pending THEN record this seat's request; IF the other seat's request is pending THEN create Game number+1 with whiteSlot flipped, status playing, and clear the request
    violation: 409 "Finish this game first"
    source: FR4.4
  - id: BR3.3
    statement: A pending rematch request lapses when the other seat is abandoned. The snapshot reports it as lapsed.
    category: policy
    applies_to: Room.rematchRequestedBy
    trigger: snapshot, request rematch
    logic: IF rematchRequestedBy is set AND the other seat is abandoned THEN rematch state = lapsed
    violation: n/a
    source: FR4.4

  # BR4 — Lifecycle and security
  - id: BR4.1
    statement: At startup, a database without schema version 2 is moved aside to justchess.sqlite3.old and a fresh database is created. No data is migrated.
    category: policy
    applies_to: SchemaVersion
    trigger: application start
    logic: IF the file exists AND the version marker is missing or below 2 THEN rename it to .old (replacing any earlier .old), log a warning naming the file, and create the new schema
    violation: if the rename fails, startup fails with a clear error naming the file
    source: FR11.1
  - id: BR4.2
    statement: Rooms with no activity for 30 days are deleted with their seats, games and moves, hourly and at startup.
    category: policy
    applies_to: Room, Seat, Game, Move
    trigger: housekeeping tick
    logic: delete rooms where lastActivityAt < now - 30 days; Games data is removed through the Games delete-by-room operation in the same transaction
    violation: a failure is logged and retried on the next tick
    source: FR11.2
  - id: BR4.3
    statement: State-changing HTTP requests and WebSocket connections must come from the app's own origin. Request bodies are limited to 4 KB.
    category: authorization
    applies_to: all POST routes and /ws
    trigger: request
    logic: IF an Origin header is present AND it does not match the request's own scheme://host THEN refuse; IF the body is over 4 KB THEN refuse
    violation: 403 for a foreign origin, 413 for a body that is too large
    source: NFR8a
  - id: BR4.4
    statement: The WebSocket learns the viewer's seat only from a token sent in its first message, never from the URL. Without a token the viewer is a read-only watcher.
    category: authorization
    applies_to: /ws
    trigger: socket open
    logic: first message {type:"hello", token?, visible}; IF the token matches THEN mark the seat present, ELSE watcher
    violation: an invalid token means watcher, never an error
    source: NFR2, FR1.6
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | Random, unique 6-character code | constraint | FR1.1 |
| BR1.2 | Code format and case-insensitive match | validation | FR1.2, FR1.3 |
| BR1.3 | Seat A creator, seat B joiner, third refused, rejoin by token | constraint | FR1.2–FR1.5 |
| BR1.4 | 128-bit tokens, hashes only, constant-time compare | authorization | NFR2, FR1.5 |
| BR1.5 | Continue token moves the seat to a new device | policy | FR1.7 |
| BR1.6 | Every change needs a seat token | authorization | NFR1 |
| BR1.7 | Away and abandoned (24 h) | calculation | FR1.6, FR11.2 |
| BR2.1 | Move acceptance with version check | validation | FR3.2, FR3.10, NFR4 |
| BR2.2 | Automatic ends with reason | calculation | FR4.2 |
| BR2.3 | Claimable draws only on claim | policy | FR4.3 |
| BR2.4 | Claim win after abandonment | policy | FR11.2 |
| BR2.5 | Snapshot contents (plus legacy fields) | calculation | FR3.4–FR3.6, FR1.6 |
| BR3.1 | Score update in the same transaction | calculation | FR4.5 |
| BR3.2 | Rematch with both requests, colours swap | policy | FR4.4 |
| BR3.3 | Rematch request lapses on abandonment | policy | FR4.4 |
| BR4.1 | Fresh schema, old file kept as .old | policy | FR11.1 |
| BR4.2 | 30-day cleanup | policy | FR11.2 |
| BR4.3 | Origin check and 4 KB body limit | authorization | NFR8a |
| BR4.4 | Socket seat from the first message only | authorization | NFR2, FR1.6 |
