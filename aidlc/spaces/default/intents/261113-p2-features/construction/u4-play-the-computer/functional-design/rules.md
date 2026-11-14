# Business Rules — u4-play-the-computer

```yaml
rules:
  # --- Engine (NFR1, ADR-001) -------------------------------------------------
  - id: BR1.1
    statement: At most one engine search runs at a time; requests are served in arrival order.
    category: constraint
    applies_to: Engine
    trigger: a reply or hint request
    logic: IF a search is running THEN the request joins the FIFO queue and learns its position (requests ahead + 1) ELSE it starts at once; the process runs with Threads = 2 and Hash = 64 MB; the engine is driven asynchronously so the web server's event loop never waits on it
    violation: two searches at once, or a later request served first
    source: NFR1, FR6.2
  - id: BR1.2
    statement: The queue is bounded.
    category: constraint
    applies_to: Engine
    trigger: a request arrives while 32 are already queued
    logic: IF 32 requests are queued THEN refuse the new one as busy (the caller answers 503 "The computer is busy, try again in a moment") and queue nothing
    violation: unbounded memory and waits on the Pi
    source: NFR1
  - id: BR1.3
    statement: A crashed engine is restarted once; after that the computer is unavailable until the app restarts.
    category: policy
    applies_to: Engine, EngineStatus
    trigger: the process exits, stops answering, or a search fails
    logic: IF restartsUsed = 0 THEN restart the process, set restartsUsed = 1, and fail only the request that was running (queued requests continue on the new process) ELSE mark unavailable with the reason "The computer stopped working", fail the running and every queued request, and refuse new ones; restartsUsed is never reset while the app runs, so two crashes over any period leave the computer unavailable until the operator restarts the app (accepted, ADR-001: a repeatedly crashing engine on the Pi needs a person's attention)
    violation: endless restart loop, or a dead engine that still accepts requests
    source: FR6.7, ADR-001
  - id: BR1.4
    statement: A search that overruns its think time by more than 5 s counts as a crash.
    category: policy
    applies_to: Engine
    trigger: a search still running at thinkSeconds + 5 s
    logic: IF the time is exceeded THEN stop waiting, kill the process and apply BR1.3
    violation: a hung engine blocks every room
    source: NFR1
  - id: BR1.5
    statement: The engine starts with the app and stops with it.
    category: policy
    applies_to: Engine lifecycle
    trigger: app start-up and shutdown
    logic: from start-up until the process is open the engine is unavailable with the reason "The computer is starting" (ensure_stockfish may still be downloading); after Stockfish is found (existing ensure_stockfish), open one process; IF no binary was found or the process fails to open THEN mark unavailable with the reason "No chess engine is installed" or "The computer could not be started"; at shutdown, fail queued requests, ask the process to quit, and kill it after 2 s
    violation: orphaned engine process, or app start-up blocked by the engine
    source: NFR1, FR6.7
  - id: BR1.6
    statement: Only positions replayed from a game's validated stored moves reach the engine.
    category: validation
    applies_to: Engine, ComputerOpponent
    trigger: any engine request
    logic: the board sent is rebuilt from stored moves (replay_board); no client-supplied FEN, move text or option value is ever passed to the engine; the returned move is checked to be legal before use
    violation: user text reaching UCI, or an illegal engine move stored
    source: NFR1, ADR-001

  # --- ComputerOpponent (FR6.2, FR6.4) ---------------------------------------
  - id: BR2.1
    statement: Each level is a fixed skill and think time.
    category: calculation
    applies_to: ComputerOpponent.reply
    trigger: the computer is to move
    logic: beginner = skill 0 / 0.1 s; casual = 5 / 0.3 s; club = 10 / 0.6 s; strong = 15 / 1 s; maximum = 20 / 2 s; the skill is set on the engine before each search because hints use a different one
    violation: wrong strength for the level
    source: FR6.2
  - id: BR2.2
    statement: Hints always use full strength for 0.5 s.
    category: calculation
    applies_to: ComputerOpponent.hint
    trigger: a hint request
    logic: skill 20, 0.5 s, whatever the room's level
    violation: weak or slow hints
    source: FR6.4

  # --- Computer rooms (FR6.1, FR6.5, FR6.9, ADR-002, ADR-005) ----------------
  - id: BR3.1
    statement: A computer room is created with a level and the player's colour, and its game starts at once.
    category: policy
    applies_to: POST /api/rooms
    trigger: "Play" in the "Play the computer" panel
    logic: body {kind: computer, level, colour: white|black|random}; random is resolved on the server with a secure random choice; IF the engine is unavailable THEN refuse with 503 and the reason, creating nothing; ELSE create the room (mode computer, the level), seat A with a fresh token, seat B as the computer (no token), and game 1 in status playing with whiteSlot A for white or B for black; the response is {code, token, slot A, colour, computer}; IF the computer is white THEN its reply is asked for at once (BR5.1); a body without kind, or with kind friend, creates a friend room exactly as before
    violation: 400 for an unknown level or colour; 503 when unavailable
    source: FR6.1, FR6.5, ADR-002
  - id: BR3.2
    statement: Nobody can join a computer room.
    category: authorization
    applies_to: POST /api/rooms/{code}/join, mode route
    trigger: a visitor opens a computer room's link without its seat token
    logic: IF the room is a computer room AND the presented token is not seat A's THEN 409 "This room plays the computer"; seat A's own token still rejoins as today; the mode route already refuses computer rooms (U3)
    violation: a second person takes the computer's seat
    source: FR6.5, ADR-002
  - id: BR3.3
    statement: The room score is the score against the computer at that level, and it never touches another room.
    category: calculation
    applies_to: record_result in computer rooms
    trigger: a computer game ends
    logic: winsA = the player's wins, winsB = the computer's wins, draws; every computer game is counted; no other room's score changes
    violation: online scores altered, or computer games uncounted
    source: FR6.9, ADR-005
  - id: BR3.4
    statement: Rematch in a computer room starts the next game at once, at the same level.
    category: policy
    applies_to: POST /api/rooms/{code}/rematch
    trigger: "Play again", or "Play" in the panel for a level whose saved game is finished
    logic: IF the room is a computer room AND the token is seat A's AND the game is finished THEN start the next game in status playing; colours swap, unless the body names colour white or black, which the player then takes (random swaps); IF the computer is white in the new game THEN ask for its reply (BR5.1); the engine being unavailable does not block a rematch, but the game then waits (BR5.6)
    violation: 409 "The game isn't over yet" when the game is still playing
    source: FR6.8, ADR-005
  - id: BR3.5
    statement: A device keeps one computer room per level and reopens it.
    category: policy
    applies_to: WebClient panel, SavedSeat
    trigger: "Play" in the panel
    logic: IF a saved seat with kind computer exists for the chosen level THEN open that room (if its game is unfinished, resume it and ignore the colour choice; if finished, rematch with the chosen colour, BR3.4) ELSE create a new room (BR3.1) and save its seat with kind computer and the level; a saved seat that the server answers "not found" for is dropped, and a new room is created
    violation: scores split across several rooms for one level
    source: FR6.5, FR6.9, ADR-005
  - id: BR3.6
    statement: Friend-only actions do not apply in computer rooms.
    category: policy
    applies_to: claim-draw, claim-win, push alerts, invite and share
    trigger: those routes and events in a computer room
    logic: claim-draw and claim-win answer 409 "Not available against the computer" (draws there are automatic, BR4.2, and the computer is never away); no push alert is ever scheduled for a computer room; the snapshot reports seat B's presence as computer
    violation: claim buttons or alerts that make no sense against the computer
    source: FR6.8, ADR-002

  # --- Games (FR6.3, FR6.8) ---------------------------------------------------
  - id: BR4.1
    statement: The player can take back moves while the game is playing.
    category: policy
    applies_to: POST /api/rooms/{code}/takeback
    trigger: "Take back"
    logic: body {token, version}; only seat A in a computer room; only while the game is playing; the version must match (409 with the snapshot otherwise); IF a reply is in flight THEN 409 "Wait for the computer's move"; IF it is the player's turn AND the player has made at least one move THEN remove the last two plies (the computer's reply and the player's move before it); IF it is the computer's turn with no reply in flight (the engine is unavailable) THEN remove the player's last move only; ELSE 409 "Nothing to take back"; the position is rebuilt by replaying the remaining moves, version + 1; unlimited
    violation: takeback in a friend room (409 "Takeback is only for games against the computer"), or a takeback racing a reply
    source: FR6.3
  - id: BR4.2
    statement: Threefold repetition and the 50-move rule end a computer game automatically.
    category: calculation
    applies_to: apply_move in computer rooms
    trigger: any move (player's or computer's)
    logic: IF the room is a computer room THEN after the move check the position on the board with is_repetition(3) (end reason threefold_repetition) and is_fifty_moves() (end reason fifty_moves), in addition to checkmate, stalemate, insufficient material and the fivefold and 75-move ends; a draw the next move could merely reach does not end the game; this path is taken only when the room mode is computer, and friend rooms keep the existing automatic_end and the claim rule unchanged
    violation: a computer game that goes on in a drawn repetition
    source: FR6.8
  - id: BR4.3
    statement: The player can resign a computer game.
    category: policy
    applies_to: POST /api/rooms/{code}/resign
    trigger: "Resign", confirmed in the page's own dialog
    logic: body {token, version}; seat A in a computer room; game playing; version must match; the game ends with end reason resigned and the computer winning; the score is recorded in the same transaction; a reply in flight is then discarded by BR5.2
    violation: 409 when the game is over; 409 "Resigning is only for games against the computer" in a friend room
    source: FR6.8

  # --- Reply flow (ADR-009) ---------------------------------------------------
  - id: BR5.1
    statement: After the player's move, the computer's reply is asked for without holding the room lock.
    category: policy
    applies_to: move, create, rematch and resume routes
    trigger: a commit that leaves the computer to move in a playing computer game
    logic: in the same request, after the commit, note the game id and version; release the lock; enqueue the reply request with Engine synchronously, which returns its requestId and its initial state (queued with its position, or thinking) or refuses it at once (busy or unavailable); on acceptance set ReplyInFlight {gameId, version, requestId} for the room, replacing any earlier flag (a rematch's new game supersedes the old game's reply, whose result BR5.2 then discards); a task that awaits the result is created and held in a strong reference set until it ends, and it clears ReplyInFlight in a finally block (only if the flag still carries its requestId), on success, failure, exception or cancellation; the HTTP answer includes the initial computer state; IF Engine refuses at once THEN no flag is set and the answer carries that state
    violation: the lock held for seconds, or a reply never asked for
    source: FR6.2, NFR1, ADR-009
  - id: BR5.2
    statement: A reply is applied only to the unchanged game.
    category: constraint
    applies_to: reply completion
    trigger: Engine returns a move
    logic: re-take the room lock; IF the current game's id equals the noted gameId AND its version equals the noted version AND the game is playing AND it is seat B's turn AND the move is legal THEN apply it as seat B (BR4.2 checks for an end and the score is recorded); ELSE discard it; in both cases clear ReplyInFlight only if it still carries this requestId (a newer request's flag is left alone), and broadcast; a resign leaves the flag until the search ends and the reply is then discarded (game finished); a rematch replaces the flag at once (BR5.1), so the new game's reply is asked for without waiting for the stale search
    violation: a stale reply applied after a takeback, resign or rematch
    source: ADR-009
  - id: BR5.3
    statement: While a reply is in flight, takebacks are refused and a second reply is not asked for.
    category: constraint
    applies_to: ReplyInFlight
    trigger: takeback or resume during a reply
    logic: IF ReplyInFlight is set for the room AND its gameId is the current game's THEN takeback answers 409 (BR4.1) and resume returns the current state without a new request; a flag left from an earlier game never blocks the current one
    violation: two replies for one position
    source: FR6.3, ADR-009
  - id: BR5.4
    statement: Opening a game where the computer is to move asks for its reply.
    category: policy
    applies_to: POST /api/rooms/{code}/computer-move
    trigger: the client opens or reloads a computer game whose snapshot shows the computer to move and state idle
    logic: body {token}; seat A only; IF the game is playing AND it is seat B's turn AND no reply is in flight for this game AND the room has no RetryBackoff in force AND the engine is available THEN apply BR5.1; ELSE return the current state unchanged; idempotent; the client calls it when the page opens on the computer's turn, and after a failure or busy answer retries at most 3 times, 5 s apart, then shows "The computer didn't answer." with a "Try again" button that calls it once more
    violation: a game stuck on the computer's turn after a restart
    source: FR6.5, ADR-009
  - id: BR5.5
    statement: The player cannot move while the computer is unavailable.
    category: policy
    applies_to: move route in computer rooms
    trigger: a move request while EngineStatus.available is false
    logic: IF the room is a computer room AND the engine is unavailable THEN 503 "The computer is not available right now"; viewing, takeback and resign still work
    violation: the player moves, and the game waits forever on the computer's turn
    source: FR6.7
  - id: BR5.6
    statement: A failed reply leaves the game as it was and says why.
    category: policy
    applies_to: reply completion
    trigger: Engine fails the request (crash, timeout, unavailable, shutdown)
    logic: clear ReplyInFlight (if it carries this requestId); change nothing in the game; for a failure other than busy, set RetryBackoff for the room to now + 5 s, so a failure that repeats (for example an illegal engine move) costs at most one search per 5 s; broadcast with state unavailable and its reason when the engine is now unavailable, else state idle (the client then retries within its cap, BR5.4); log the failure without positions or tokens
    violation: a silent stall
    source: FR6.7

  # --- Hint (FR6.4) -----------------------------------------------------------
  - id: BR6.1
    statement: The player can ask for a hint on their own turn.
    category: policy
    applies_to: POST /api/rooms/{code}/hint
    trigger: "Hint"
    logic: body {token, version}; seat A in a computer room; game playing; the player's turn; version matches; engine available; at most one hint in flight per room (409 "A hint is already on its way"); hints are refused with 503 "The computer is busy, try again in a moment" when 16 or more requests are already queued, so replies keep their place; the hint goes through the same queue (BR1.1, BR2.2), enqueued synchronously; HintInFlight is cleared in a finally block, including when the HTTP client disconnects while the hint waits (the queued request is then cancelled, or its result dropped if already thinking); the answer is {uci, from, to, san, version}; IF the version changed while the hint was computed THEN answer 409 with the snapshot; hints are unlimited apart from BR6.2 and change nothing in the game
    violation: 409 on the computer's turn; 503 when unavailable or busy
    source: FR6.4

  - id: BR6.2
    statement: Engine-consuming routes are rate-limited per client address.
    category: constraint
    applies_to: POST /api/rooms (kind computer), POST …/hint, POST …/computer-move
    trigger: any of those requests
    logic: reuse ratelimit.RateLimiter and client_address (U3, honouring JUSTCHESS_TRUSTED_PROXIES) with one sliding 60 s window per route and address — computer room creation 10 per minute, hint 20 per minute, computer-move 30 per minute; over the limit answer 429 with Retry-After 60 and queue nothing; player moves are not limited here because each one needs the computer's reply first, so one room can hold at most one reply and one hint; friend room creation is unchanged
    violation: one client fills the shared engine queue and every other player waits or gets busy
    source: NFR1

  # --- LiveUpdates (review R-01) ----------------------------------------------
  - id: BR7.1
    statement: Every snapshot of a computer room carries the computer's state.
    category: policy
    applies_to: snapshot
    trigger: any snapshot or HTTP answer of a computer room
    logic: computer = {state: idle|queued|thinking|unavailable, queuePosition (queued only), reason (unavailable only), level, available}; friend rooms carry computer = null
    violation: the page cannot show thinking or unavailable after a reload
    source: FR6.2, FR6.7, NFR1
  - id: BR7.2
    statement: Queue progress and takebacks reach the page's socket as events.
    category: policy
    applies_to: LiveHub
    trigger: queue position changes, a search starts, a takeback commits
    logic: send {type: computer, state, queuePosition} to the room's sockets when the reply request's position changes or its search starts; send {type: takeback} before the new state after a takeback; hint requests send nothing to the socket (the hint answer is the HTTP response)
    violation: "Waiting for the computer" never updates
    source: NFR1, FR6.3

  # --- WebClient --------------------------------------------------------------
  - id: BR8.1
    statement: The lobby offers "Play the computer" with a colour and one of five named levels, remembered on the device.
    category: policy
    applies_to: lobby panel
    trigger: opening the lobby
    logic: colour White | Black | Random and level Beginner | Casual | Club | Strong | Maximum are radio groups, defaulting to Random and Casual; the last choice is remembered in local storage (read and written in try/catch); "Play" applies BR3.5; IF /api/engine says unavailable THEN the panel shows "Play the computer is unavailable" with the reason and a disabled Play
    violation: choices lost on every visit
    source: FR6.1, FR6.7
  - id: BR8.2
    statement: The game screen of a computer room shows the computer's controls and states.
    category: policy
    applies_to: game screen
    trigger: a snapshot with mode computer
    logic: |
      - The opponent is labelled "Computer · <level name>".
      - The status reads "Computer is thinking…" while thinking, "Waiting for the computer… (<n> ahead)" while queued, and "The computer can't move right now: <reason>. You can still look through the game." while unavailable.
      - Buttons: Take back (enabled when BR4.1 allows), Hint (enabled on the player's turn when available and no hint is pending) and Resign (opens an in-page confirm).
      - The hint arrow is drawn from the hint's from and to squares and cleared by the next move, a takeback or a new snapshot version.
      - When the game is over, a result card with "Play again".
      - The score line reads "This level: You <winsA> · Computer <winsB> · Draws <draws>".
      - Share and invite controls are hidden; "Continue on another device" stays.
    violation: friend-game controls shown against the computer
    source: FR6.2, FR6.3, FR6.4, FR6.7, FR6.8, FR6.9
  - id: BR8.3
    statement: The blunder warning works in computer games.
    category: policy
    applies_to: check-move route and blunder dialog
    trigger: the player's move with the warning setting on
    logic: the existing check-move flow runs unchanged for seat A on its turn; it needs no engine
    violation: no warning against the computer
    source: FR6.6
  - id: BR8.4
    statement: Computer games appear in Your games with their level.
    category: policy
    applies_to: summaries and Your games
    trigger: listing saved seats
    logic: the U2 summary already reports kind computer and the level; the list labels it "Computer, <level name>"; this unit saves the seat with kind computer so it is listed
    violation: computer games missing from the list
    source: FR1.5
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | One search at a time, FIFO, 2 threads, 64 MB | constraint | NFR1, FR6.2 |
| BR1.2 | Queue capped at 32, then busy | constraint | NFR1 |
| BR1.3 | One restart, then unavailable | policy | FR6.7 |
| BR1.4 | Overrun of think time + 5 s counts as a crash | policy | NFR1 |
| BR1.5 | Starts and stops with the app | policy | NFR1, FR6.7 |
| BR1.6 | Only replayed, validated positions reach the engine | validation | NFR1 |
| BR2.1 | Level table | calculation | FR6.2 |
| BR2.2 | Hint at full strength, 0.5 s | calculation | FR6.4 |
| BR3.1 | Create a computer room with level and colour | policy | FR6.1, FR6.5 |
| BR3.2 | Nobody joins a computer room | authorization | FR6.5 |
| BR3.3 | Score is against the computer only | calculation | FR6.9 |
| BR3.4 | One-seat rematch, same level, optional colour | policy | FR6.8 |
| BR3.5 | One saved room per level, reopened | policy | FR6.5, FR6.9 |
| BR3.6 | No claims, no alerts, no invite | policy | FR6.8 |
| BR4.1 | Takeback rules | policy | FR6.3 |
| BR4.2 | Automatic repetition and 50-move draws | calculation | FR6.8 |
| BR4.3 | Resign | policy | FR6.8 |
| BR5.1 | Reply asked for after commit, no lock held | policy | FR6.2, ADR-009 |
| BR5.2 | Reply applied only to the unchanged game | constraint | ADR-009 |
| BR5.3 | Reply in flight blocks takeback and a second ask | constraint | FR6.3 |
| BR5.4 | Resume asks for the reply | policy | FR6.5 |
| BR5.5 | No player moves while unavailable | policy | FR6.7 |
| BR5.6 | Failed reply changes nothing and says why | policy | FR6.7 |
| BR6.1 | Hint route, refused above 16 queued | policy | FR6.4 |
| BR6.2 | Per-address limits on engine routes | constraint | NFR1 |
| BR7.1 | Snapshot carries the computer state | policy | FR6.2, FR6.7 |
| BR7.2 | Queue and takeback socket events | policy | NFR1, FR6.3 |
| BR8.1 | Lobby panel, remembered choices | policy | FR6.1, FR6.7 |
| BR8.2 | Computer game screen | policy | FR6.2–FR6.4, FR6.7–FR6.9 |
| BR8.3 | Blunder warning applies | policy | FR6.6 |
| BR8.4 | Listed in Your games | policy | FR1.5 |
