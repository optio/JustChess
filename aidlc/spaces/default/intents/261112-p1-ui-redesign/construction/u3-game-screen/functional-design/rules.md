# Screen Rules — u3-game-screen

These rules apply the U3 rows of `inception/units-generation/unit-of-work-story-map.md`, from `inception/requirements-analysis/requirements.md`. The texts and layouts come from `inception/refined-mockups/` (`mockups.md`, `interaction-spec.md`, `design-system-mapping.md`). The server facts they rely on are U1's API and snapshot (`justchess/api.py`, `justchess/games.py`). The board and settings come from U2 (`static/js/board/board.js`, `static/js/settings.js`).

```yaml
rules:
  # BR1 — Entering a room and keeping the seat
  - id: BR1.1
    statement: The lobby offers one primary action, "Start a game", and a labelled code field, "Have a room code?". Starting a game creates a room and opens its game screen at /r/{code}.
    category: policy
    applies_to: lobby
    trigger: Start a game
    logic: POST /api/rooms; on 201 store the seat (BR1.3) and navigate to /r/{code} with history.pushState, with no page reload
    violation: a 503 or a network error shows "Could not create a room. Try again." under the button
    source: FR1.1, FR10.6
  - id: BR1.2
    statement: A typed code is uppercased, must be 6 letters or digits, and opens /r/{code}. An unknown code returns to the lobby with "No room with code K7Q2PX. Check the code or start a new game."
    category: validation
    applies_to: code field, /r/{code}
    trigger: Join, or opening an invite link
    logic: IF the code does not match ^[A-Z0-9]{6}$ after uppercasing THEN show "Room code must be 6 letters or digits" and stay; ELSE go to /r/{code}, which joins (BR1.4); a 404 shows the lobby with the not-found message and the code kept in the field
    violation: inline message under the field
    source: FR1.2, FR1.3, FR10.6
  - id: BR1.3
    statement: The seat token for a room is kept in long-lived browser storage under the room code, and only there. It is sent in the request body for actions and in the X-Seat-Token header for state reads, never in a URL query.
    category: authorization
    applies_to: seat storage
    trigger: create, join, continue, seat-moved
    logic: key justchess.seat.<CODE> = {token, slot}; written on create, join and continue redeem; removed on seat-moved or a 403 "This isn't your seat" on rejoin; IF storage throws THEN keep the seat in memory for this tab and show "This browser won't remember your seat. Keep this tab open, or use Continue on another device."
    violation: n/a
    source: FR1.5, NFR2
  - id: BR1.4
    statement: Opening /r/{code} joins with the stored token when there is one. That rejoins the seat. With no token, the visitor takes the free seat, or watches with "This game already has two players." and "Start a new game".
    category: policy
    applies_to: game screen entry
    trigger: page load at /r/{code}
    logic: POST /join with {token} if stored, else {}; 200 → seat; 409 room full → watcher mode (board read-only, live updates still shown); 403 with a stored token → remove it and retry once with {}
    violation: 404 → lobby with the not-found message (BR1.2)
    source: FR1.3, FR1.5
  - id: BR1.5
    statement: A continue link /r/{code}#continue=<token> is redeemed before joining. The fragment is removed from the address bar at once and never sent to the server as a URL.
    category: authorization
    applies_to: continue on another device
    trigger: page load with #continue=
    logic: read the fragment; history.replaceState to /r/{code}; POST /continue with {continueToken}; 200 → store the new seat (BR1.3) and continue as a seat; 403 → "This continue link has expired or was already used." and fall back to BR1.4
    violation: as stated
    source: FR1.7
  - id: BR1.6
    statement: In Game settings a seat can get a private continue link. It is shown with "Anyone with this link can play your side. Don't share it." and a Copy button. The link expires after 10 minutes.
    category: policy
    applies_to: settings panel extra row
    trigger: Get a private continue link
    logic: POST /continue-link with {token}; show origin + /r/{code}#continue=<continueToken>; state that it works once and for 10 minutes
    violation: errors show "Couldn't make a link. Try again."
    source: FR1.7
  - id: BR1.7
    statement: When the socket says seat-moved, this device becomes a read-only watcher, forgets the stored seat, and shows "This game was opened on another device."
    category: policy
    applies_to: live connection
    trigger: {type:"seat-moved"}
    logic: remove the stored seat; set the board to interactive false; reconnect as a watcher (hello without a token)
    violation: n/a
    source: FR1.7

  # BR2 — Sharing
  - id: BR2.1
    statement: The Share button in the top bar opens the system share sheet when the browser supports it, with the title "Play chess with me on JustChess" and the invite link /r/{code}. Otherwise it copies the link and reads "Link copied" for 1.6 s.
    category: policy
    applies_to: Share
    trigger: tap Share
    logic: IF navigator.share exists THEN share({title, text, url}); a user cancel (AbortError) does nothing; ELSE IF navigator.clipboard.writeText exists THEN copy; ELSE select the link in a read-only field with "Copy this link"
    violation: a clipboard failure shows the read-only field fallback
    source: FR2.1, FR2.2

  # BR3 — The live game
  - id: BR3.1
    statement: The screen always shows the latest snapshot from the server. A full snapshot arrives on every socket (re)connect, and the board, scoresheet, status and buttons are drawn only from it.
    category: constraint
    applies_to: game screen
    trigger: state message, action response
    logic: keep the snapshot with the highest (game, version) pair; ignore older ones
    violation: n/a
    source: FR3.4, NFR5
  - id: BR3.2
    statement: The socket sends hello with the token, pings every 5 s and reports visibility changes. When it closes, the screen shows "Reconnecting…" with the board dimmed and retries after 1, 2, 4 and 8 s, then every 10 s.
    category: policy
    applies_to: live connection
    trigger: socket open or close, visibilitychange
    logic: on open send {type:"hello", token?, visible}; setInterval ping 5000; on close (not by us) set reconnecting and schedule a retry from the backoff list; on success clear reconnecting
    violation: n/a
    source: FR3.4, FR1.6
  - id: BR3.3
    statement: A move from the board is posted with the snapshot's version. On 200 the response snapshot is applied. On 409 the attached snapshot is applied. On 400 or 403 the board slides the piece back and the status line shows the server's message for 4 s.
    category: policy
    applies_to: moves
    trigger: board onMove
    logic: POST /moves {token, uci, version}; 200 → apply; 409 with snapshot → apply (board.set); 400/403 → board.reject() + message; network error → board.reject() + "Couldn't reach the server. Try again."
    violation: as stated
    source: FR3.2, FR3.10
  - id: BR3.4
    statement: The status line shows one state, chosen in this order. Game over: "Game over — <reason>". Reconnecting: "Reconnecting…". Waiting: "Waiting for your opponent. Send them the link." Check on your move: "Check — your move". Your move: "Your move", with the opponent's last move under it, on baize. Their move: "Waiting for White" or "Waiting for Black". An away opponent adds "<Colour> is away".
    category: calculation
    applies_to: status line
    trigger: every snapshot or connection change
    logic: first matching state wins; your-move states use the baize fill and a dot; text always carries the state (never colour alone); role=status aria-live=polite
    violation: n/a
    source: FR3.6, FR1.6, FR10.6
  - id: BR3.5
    statement: The scoresheet is a table with numbered rows and White and Black columns, filled from the snapshot's moveList. The newest move is in ink. On a phone the last 6 rows show, and the rest expands on tap. The result cell fills at game end.
    category: calculation
    applies_to: scoresheet
    trigger: every snapshot
    logic: rows = moveList; result = "1–0", "0–1" or "½–½" from result
    violation: n/a
    source: FR3.5
  - id: BR3.6
    statement: The room score is shown per player, not per colour, as "You 2 · Opponent 1 · Draws 0", using the viewer's slot. A watcher sees "Player A" and "Player B".
    category: calculation
    applies_to: room score
    trigger: every snapshot
    logic: you = score[slot], opponent = score[other slot], draws = score.draws
    violation: n/a
    source: FR4.5
  - id: BR3.7
    statement: "Claim draw" shows only while the snapshot says a draw is claimable and it is the viewer's move. Its label names the reason (threefold repetition or 50-move rule). "Claim win (opponent left)" shows only while the game is playing and the opponent's presence is abandoned.
    category: validation
    applies_to: claim buttons
    trigger: every snapshot
    logic: claim draw visible = claimableDraw AND slot on move; claim win visible = status playing AND seats[other].presence == "abandoned"; tapping posts /claim-draw or /claim-win and applies the response (409 → apply the snapshot and show the message)
    violation: n/a
    source: FR4.3, FR11.2
  - id: BR3.8
    statement: While the lessons drawer is open during a game and the opponent moves, a sticky banner says "Your move in the game. Back to the board". Activating it closes the drawer and scrolls to the board. The game keeps updating while the drawer is open.
    category: policy
    applies_to: lessons drawer
    trigger: new snapshot where it becomes the viewer's move while the drawer is open
    logic: drawer = <details>, collapsed by default during a game with the summary "Learn openings — your game keeps running"; its content area is a mount point for U6
    violation: n/a
    source: FR5.5, FR5.6

  # BR4 — Game over and rematch
  - id: BR4.1
    statement: When a game ends, the board locks and the win sequence plays once. The losing king tips 80° (700 ms), the board dims (600 ms), the result is inked into the scoresheet (250 ms per character), the overlay appears, and the winner's pieces glow brass. A draw skips the tip and the glow. Reduced motion shows the end state at once.
    category: calculation
    applies_to: end of game
    trigger: snapshot status changes from playing to finished while this screen is open
    logic: run the sequence only on the transition; a page opened on a finished game shows the end state without the sequence
    violation: n/a
    source: FR4.1, FR10.4
  - id: BR4.2
    statement: The overlay titles the reason. It shows the winner and the decisive move, then "Play again" (primary) and "Share result" (secondary). It is not modal, so the board and scoresheet stay readable. Focus moves to "Play again".
    category: calculation
    applies_to: end-of-game overlay
    trigger: game finished
    logic: titles — checkmate "Checkmate", stalemate "Stalemate", insufficient_material "Draw — not enough pieces to mate", fivefold_repetition "Draw by fivefold repetition", seventyfive_moves "Draw by the 75-move rule", threefold_claimed "Draw claimed (threefold repetition)", fifty_moves_claimed "Draw claimed (50-move rule)", abandoned "Opponent left"; subtitle "White wins with <SAN>" or "Draw"
    violation: an unknown reason shows "Game over"
    source: FR4.1, FR4.2
  - id: BR4.3
    statement: "Play again" asks for a rematch. Once this seat has asked, the button reads "Waiting for opponent" (disabled). When the opponent has asked, the button reads "Play again (your opponent is ready)". When the request has lapsed, the overlay says "Your opponent left. Share the link to play again." When a new game starts, the overlay closes and the board shows the new colours.
    category: policy
    applies_to: rematch
    trigger: Play again, snapshot rematch field
    logic: POST /rematch {token}; render from rematch.state and rematch.requestedBy versus the viewer's slot; a new game number resets the overlay and the win sequence
    violation: 409 → apply the snapshot
    source: FR4.4

  # BR5 — Layout
  - id: BR5.1
    statement: On a phone the top bar holds only the logo mark, the room code and Share, and is at most 56 px tall. The board's top edge is at most 72 px from the top, and the board fills the width minus 8 px gutters (at least 374 px on a 390 px screen). From 1024 px wide, the board is 560–640 px in the left column with the panel on the right. The lobby is hidden during a game.
    category: constraint
    applies_to: layout
    trigger: viewport
    logic: CSS grid with clamp() sizes; no script layout
    violation: n/a
    source: FR5.4, FR5.5
  - id: BR5.2
    statement: Every screen state has its own view with a next action. Lobby with no room, waiting for the opponent, reconnecting, room not found, seats taken, storage blocked, opened on another device, and game over.
    category: policy
    applies_to: screen states
    trigger: see each rule
    logic: one state machine (functional-spec.md) picks the view
    violation: n/a
    source: FR10.6
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | Lobby: Start a game | policy | FR1.1, FR10.6 |
| BR1.2 | Code validation and "room not found" | validation | FR1.2, FR1.3, FR10.6 |
| BR1.3 | Seat token in long-lived storage, never in URLs | authorization | FR1.5, NFR2 |
| BR1.4 | Invite link joins, rejoins or watches | policy | FR1.3, FR1.5 |
| BR1.5 | Continue link redeemed; fragment stripped | authorization | FR1.7 |
| BR1.6 | Get a private continue link, with warning | policy | FR1.7 |
| BR1.7 | Seat moved: become a watcher | policy | FR1.7 |
| BR2.1 | Share sheet or copy link | policy | FR2.1, FR2.2 |
| BR3.1 | Screen drawn only from the latest snapshot | constraint | FR3.4, NFR5 |
| BR3.2 | Hello, ping, visibility, reconnect backoff | policy | FR3.4, FR1.6 |
| BR3.3 | Move posting and refusals | policy | FR3.2, FR3.10 |
| BR3.4 | Status line states | calculation | FR3.6, FR1.6, FR10.6 |
| BR3.5 | Scoresheet | calculation | FR3.5 |
| BR3.6 | Score per player | calculation | FR4.5 |
| BR3.7 | Claim buttons only when valid | validation | FR4.3, FR11.2 |
| BR3.8 | Lessons drawer keeps the game live | policy | FR5.5, FR5.6 |
| BR4.1 | Win sequence | calculation | FR4.1, FR10.4 |
| BR4.2 | End-of-game overlay | calculation | FR4.1, FR4.2 |
| BR4.3 | Rematch states | policy | FR4.4 |
| BR5.1 | Layout sizes | constraint | FR5.4, FR5.5 |
| BR5.2 | Designed states | policy | FR10.6 |
