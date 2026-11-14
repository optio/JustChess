# Business Rules — u2-data-and-your-games

```yaml
rules:
  - id: BR1.1
    statement: The database is schema version 4; any other file is moved aside and a fresh database is created.
    category: policy
    applies_to: startup
    trigger: app start
    logic: IF the file carries version 4 THEN use it; ELSE IF it carries a version newer than 4 THEN refuse to start (a newer app wrote it; nothing is moved); ELSE IF the file exists (versions 1-3, unmarked, not SQLite) THEN rename it to <name>.old (replacing an earlier .old, as today) and create the version-4 schema; IF no file THEN create it. A failed rename stops start-up with the reason. No data is migrated.
    violation: start-up stops with DatabaseStartupError and the reason
    source: NFR7
  - id: BR1.2
    statement: New friend rooms start in mode waiting and become online when the second seat is taken.
    category: constraint
    applies_to: Room.mode
    trigger: room created; join succeeds
    logic: create sets mode = waiting; a successful join (seat B taken) sets mode = online in the same transaction. U3 adds pass_along transitions; U4 adds computer rooms.
    violation: a room with two seats left in waiting
    source: FR1.2
  - id: BR1.3
    statement: Every stored move records the piece it captured and that piece's square.
    category: calculation
    applies_to: Move
    trigger: a move is applied
    logic: before pushing the move, IF it is en passant THEN capturedSquare = the passed pawn's square and capturedPiece = that pawn; ELSE IF the arrival square holds a piece THEN that piece and square; ELSE both empty. The snapshot exposes them for the last move as lastCapture = {piece, square} or null.
    violation: a capture without capture info
    source: FR2.1
  - id: BR2.1
    statement: Room summaries are requested in one POST with the room code and seat token pairs in the body.
    category: validation
    applies_to: POST /api/rooms/summaries
    trigger: the main screen loads or refreshes the list
    logic: body = {seats:[{code, token}]} with 1..50 entries; each code 6 chars A-Z0-9 and each token 1..128 chars; the request is origin-checked; the body limit for this one route is 8 KB (the size-limit middleware takes a per-path override table; every other route keeps 4 KB); entries are deduplicated by the (code, token) pair, so one browser holding both seats of a room gets one summary per seat. Tokens are never logged and never appear in a URL. The client validates each stored seat's shape before sending and skips (and removes) malformed entries, so one bad entry cannot block the list.
    violation: 400 with the fixed message "Invalid summary request" (never echoing submitted values) for a malformed body; 413 when too large
    source: FR1.4, NFR4
  - id: BR2.2
    statement: Each summary describes the seat holder's view of the room's current game.
    category: calculation
    applies_to: RoomSummary
    trigger: BR2.1
    logic: IF the room is missing or the token does not match a seat in it THEN {code, found:false}. ELSE found:true with kind (computer if mode = computer else friend), computerLevel, opponent (computer / joined if the other seat exists / waiting), colour of the seat in the current game, status, yourTurn (status playing and the side to move is this seat's colour), result from this seat's view (won/lost/drawn) when finished, lastActivityAt, endedAt, current fen, pendingJoinRequest (a pending, unexpired JoinRequest exists and this seat is A).
    violation: a summary leaking data of a room the token does not belong to
    source: FR1.2, FR1.4, FR1.5
  - id: BR2.3
    statement: Summaries are read without changing the room.
    category: constraint
    applies_to: POST /api/rooms/summaries
    trigger: BR2.1
    logic: one read transaction; last-seen and last-activity are not updated (asking for a summary is not being present in the game)
    violation: summaries keeping idle rooms alive
    source: FR1.4
  - id: BR3.1
    statement: The list shows unfinished games and games finished in the last 7 days, newest activity first.
    category: policy
    applies_to: YourGamesList
    trigger: summaries received
    logic: keep found summaries with status != finished, or finished with endedAt within 7 x 24 h of now; sort unfinished by lastActivityAt descending, then finished by endedAt descending; rows with pendingJoinRequest sort first among unfinished
    violation: an old finished game listed, or wrong order
    source: FR1.1
  - id: BR3.2
    statement: Each row shows who you play, your colour, whose turn or the result, when, and a thumbnail.
    category: policy
    applies_to: YourGamesList row
    trigger: render
    logic: |
      Label:
        - friend room joined: "Friend · <CODE>"
        - friend room waiting: "Waiting for a friend · <CODE>"
        - computer room: "Computer, <Level>"
      Meta: "You play <colour> · last move <relative time>", or "Ended <relative time> · <reason>" when finished.
      Pill:
        - "Your move" in baize
        - "<Their> move"
        - "Waiting" for a game in status waiting (no opponent yet)
        - "Join request" with a brass outline
        - "You won" / "You lost" / "Draw"
        - "Ended" for a finished game with no result
      Thumbnail: 8 x 8 from the fen, using the board theme colours.
    violation: missing field
    source: FR1.2
  - id: BR3.3
    statement: A stored seat is dropped only when the server answers found:false for it.
    category: policy
    applies_to: seat store
    trigger: summaries received or request failed
    logic: IF found:false THEN remove that seat from the store; IF the request fails (network, 5xx, 4xx other than the body errors) THEN keep every seat, render the stored seats as "Couldn't refresh" rows without live data, and show Retry
    violation: seats lost on a network error
    source: FR1.4
  - id: BR3.4
    statement: The list refreshes on load, when the tab becomes visible, and every 60 s while visible.
    category: policy
    applies_to: YourGamesList
    trigger: timers and visibility
    logic: no refresh while hidden; at most one request in flight; a refresh replaces the list in place without moving focus
    violation: duplicate requests or focus jumps
    source: FR1.1
  - id: BR3.5
    statement: Tapping a row opens that game; an empty list invites the player to start one.
    category: policy
    applies_to: YourGamesList
    trigger: activation; no rows
    logic: each row is one link to /r/<code>; with no rows the panel shows "No games yet. Start one above or play the computer."; while the first request runs it shows "Loading your games…"
    violation: dead row, or blank panel
    source: FR1.3
  - id: BR3.6
    statement: The main screen headline and Train button change.
    category: policy
    applies_to: lobby
    trigger: render
    logic: headline "Play a friend. Play the computer. Get better."; the "Learn an opening" button becomes "Train" and opens /learn until u5 lands
    violation: old copy
    source: FR1.1
```

## Summary

| ID | Rule | Source |
|---|---|---|
| BR1.1 | Version 4 created fresh; other files moved to `.old` | NFR7 |
| BR1.2 | Friend rooms: waiting, then online on join | FR1.2 |
| BR1.3 | Moves store their captured piece and square; the snapshot exposes `lastCapture` | FR2.1 |
| BR2.1 | Batch summaries in a POST body, 1–50 seats, origin-checked, size-limited | FR1.4, NFR4 |
| BR2.2 | Summary fields from the seat's view; `found:false` for a wrong token or missing room | FR1.2, FR1.4, FR1.5 |
| BR2.3 | Summaries are read-only and keep no room alive | FR1.4 |
| BR3.1 | Unfinished games plus games finished in the last 7 days, newest first; join requests first | FR1.1 |
| BR3.2 | Row label, meta line, pill and thumbnail | FR1.2 |
| BR3.3 | A seat is dropped only on `found:false` | FR1.4 |
| BR3.4 | Refresh on load, on focus and every 60 s while visible | FR1.1 |
| BR3.5 | Rows open the game; empty and loading states | FR1.3 |
| BR3.6 | New headline and "Train" button | FR1.1 |
