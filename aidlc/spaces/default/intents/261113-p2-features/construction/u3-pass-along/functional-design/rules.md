# Business Rules — u3-pass-along

```yaml
rules:
  - id: BR1.1
    statement: The creator can switch a room without an opponent to pass-along, and back.
    category: authorization
    applies_to: POST /api/rooms/{code}/mode
    trigger: "Play here while waiting" or "Wait for a friend instead"
    logic: body {token, mode: pass_along|waiting}; only seat A's token; only while seat B does not exist and the room is not a computer room; entering pass_along on a game in status waiting starts it (status playing) with counted = false; leaving keeps the position and game status, and in the same transaction declines any pending join request (the joiner sees "declined")
    violation: 403 for a token that is not seat A, 409 "A friend has already joined" when seat B exists
    source: FR3.1, FR3.9
  - id: BR1.5
    statement: After a pass-along game ends, the creator can start another pass-along game alone.
    category: policy
    applies_to: rematch route
    trigger: "Play again" in pass_along
    logic: IF room.mode = pass_along AND the token is seat A's AND the game is finished THEN start the next game at once (colours swap as usual, counted = false), with no request from the other seat; in other modes the existing two-seat rematch rule applies
    violation: creator stuck after a practice game
    source: FR3.2, FR3.8
  - id: BR1.2
    statement: In pass-along mode the creator's token may move both colours.
    category: authorization
    applies_to: move, claim-draw and check-move routes
    trigger: a move request
    logic: IF room.mode = pass_along AND the token is seat A's THEN the side to move is allowed whatever colour it is; ELSE the normal rule applies (only the seat whose colour is to move)
    violation: 403 "Not your move"
    source: FR3.2
  - id: BR1.3
    statement: Pass-along mode is stored with the room, so it survives a reload.
    category: constraint
    applies_to: Room.mode, snapshot
    trigger: any snapshot
    logic: the snapshot carries mode; the client renders pass-along controls from it after a reload
    violation: mode lost on reload
    source: FR3.9
  - id: BR1.4
    statement: Games played in pass-along count only once a friend has joined.
    category: calculation
    applies_to: Game.counted, room score
    trigger: game end; seat B taken
    logic: counted = false while in pass_along without seat B; taking seat B (by accepted request, or by a direct join after leaving pass-along) sets counted = true for the current game in the same transaction only if that game is not finished; a practice game that already finished stays uncounted, and the next game (rematch) starts counted; record_result adds to the room score only when counted
    violation: practice game changes the score
    source: FR3.8
  - id: BR2.1
    statement: Opening the invite link of a pass-along room creates a join request instead of taking seat B.
    category: policy
    applies_to: POST /api/rooms/{code}/join
    trigger: visitor without a seat token
    logic: |
      The existing seat-token rejoin check runs first: a request carrying a valid seat token rejoins as today, so the creator reopening the link never creates a request. A visitor whose stored request token is still pending gets its existing request back (same expiresAt) instead of a new one.
      IF room.mode = pass_along:
        IF a pending, unexpired request exists THEN 409 {error: "busy"}.
        IF this client address had a request declined in this room within the last 10 minutes THEN 409 {error: "declined_recently"}, shown as "The creator declined. You can ask again later."
        ELSE insert a JoinRequest with a new 128-bit request token (only its hash stored) and expiresAt = now + 600 s; answer 202 {requestPending: true, requestToken, expiresAt}.
      A waiting room still gives seat B directly, as today.
    violation: visitor takes seat B without the creator's consent
    source: FR3.3, FR3.7
  - id: BR2.2
    statement: Only the creator can accept or decline a pending request.
    category: authorization
    applies_to: POST /api/rooms/{code}/join-request/answer
    trigger: Accept / Decline
    logic: body {token, accept}; token must be seat A's; the request must be pending and unexpired, the room must still be in pass_along and seat B must not exist (otherwise 409 "No pending request"). Accept, in one transaction under the room lock, does all of: create seat B with token_hash = requesterTokenHash, set mode online, set the current game counted = true if it is not finished (BR1.4), set request status accepted. Decline sets status declined and remembers the requester's client address for the room for 10 minutes (BR2.1).
    violation: 403 for a token that is not seat A, 409 "No pending request" otherwise
    source: FR3.5, FR3.6
  - id: BR2.3
    statement: The joiner learns the answer by polling with its request token.
    category: policy
    applies_to: POST /api/rooms/{code}/join-request/status
    trigger: every 3 s while the joiner's waiting screen is open
    logic: body {requestToken}; answers {status: pending|accepted|declined|lapsed, expiresAt}; on accepted the joiner stores its request token as its seat token for slot B and opens the game; an unknown token answers {status: "unknown"}; this route writes nothing except the lapse of BR2.4
    violation: joiner stuck or token leaked
    source: FR3.3, FR3.6
  - id: BR2.4
    statement: A request lapses 10 minutes after it was made.
    category: constraint
    applies_to: JoinRequest
    trigger: read after expiresAt; hourly housekeeping
    logic: any read of a pending request past expiresAt (status poll, snapshot, join, answer) marks it lapsed in a transaction under the room lock and broadcasts the room, so the creator's banner clears; the creator's page also hides the banner locally when its countdown reaches zero; housekeeping marks leftover expired requests lapsed without broadcasting (the on-read lapse is the source of truth); a lapsed request frees the room for a new one
    violation: request never lapses
    source: FR3.6
  - id: BR2.5
    statement: The creator hears about a request through the live update and a notification.
    category: policy
    applies_to: LiveUpdates, Notifications
    trigger: request created; request answered or lapsed
    logic: |
      Request created: broadcast a fresh snapshot to the room, carrying joinRequest {expiresAt}, visible to seat A only, and send the notification event "join-request:<requestId>" to seat A (title "Someone wants to join", one-alert rule).
      Answered or lapsed: broadcast again.
      Without push: the summary's pendingJoinRequest (U2) and the snapshot show the request when the creator next opens the game or main screen.
    violation: creator not told
    source: FR3.4
  - id: BR3.1
    statement: A client address may send at most 5 join requests per minute.
    category: validation
    applies_to: POST /api/rooms/{code}/join for pass-along rooms
    trigger: request creation attempt
    logic: |
      Sliding 60 s window per client address in memory. A 6th attempt within 60 s answers 429 {error: "too_many"}. Windows with no entries are dropped, and at most 10,000 addresses are tracked (the oldest is evicted).
      The client address is the ASGI client address the server reports (request.client.host). Uvicorn already rewrites it from X-Forwarded-For when the peer is in its own forwarded-allow-ips, which is 127.0.0.1 by default. JustChess adds no second header parsing unless JUSTCHESS_TRUSTED_PROXIES is set.
      When JUSTCHESS_TRUSTED_PROXIES is set (comma-separated IPs or CIDRs, default empty) and the reported address is one of them, the rightmost X-Forwarded-For entry that is not a trusted proxy is used. Invalid entries are logged and ignored.
      The README documents both: Uvicorn's own setting, and when to use JUSTCHESS_TRUSTED_PROXIES instead (a proxy on another host).
    violation: unlimited requests, or a spoofed header bypassing the limit
    source: NFR4
  - id: BR3.2
    statement: The new setting is documented.
    category: policy
    applies_to: .env.example, README, env-file test
    trigger: build
    logic: JUSTCHESS_TRUSTED_PROXIES appears in .env.example (commented, empty), the README configuration table and the env-file test's allowed list
    violation: undocumented setting
    source: FR9.1, FR9.2
  - id: BR4.1
    statement: The screens follow the mockups.
    category: policy
    applies_to: WebClient
    trigger: render
    logic: |
      Waiting screen:
        - "Play here while waiting" and Share.
      Pass-along:
        - Baize status "Pass-along: <colour> to move".
        - "Wait for a friend instead".
        - Practice note.
      Request banner (seat A, role alert):
        - "Someone wants to join as <colour>. Expires in <m>:<ss>".
        - Countdown text refreshed each minute.
        - Accept / Decline.
      Joiner screen statuses:
        - waiting
        - declined: "The creator declined. You can ask again later."
        - lapsed: "Nobody answered. Try again later."
        - busy: "Someone else is already asking to join. Try again in a few minutes."
        - too many: "Too many requests. Try again shortly."
      Your games:
        - "Join request" pill (from U2's summary).
    violation: missing state
    source: FR3.1, FR3.3, FR3.4, FR3.6, FR3.7
```

## Summary

| ID | Rule | Source |
|---|---|---|
| BR1.1 | Creator switches waiting ↔ pass-along (seat A only, no seat B) | FR3.1, FR3.9 |
| BR1.2 | In pass-along the creator moves both colours | FR3.2 |
| BR1.3 | Mode survives a reload (in the snapshot) | FR3.9 |
| BR1.4 | A game counts only once seat B exists | FR3.8 |
| BR2.1 | Invite link on a pass-along room gives a join request (202) or "busy" | FR3.3, FR3.7 |
| BR2.2 | Creator accepts or declines; on accept the request token becomes seat B's token | FR3.5, FR3.6 |
| BR2.3 | Joiner polls status with the request token | FR3.3, FR3.6 |
| BR2.4 | Requests lapse after 10 minutes | FR3.6 |
| BR2.5 | Live update and notification to the creator, with a fallback on next open | FR3.4 |
| BR3.1 | 5 join requests per minute per client address; trusted proxies only | NFR4 |
| BR3.2 | `JUSTCHESS_TRUSTED_PROXIES` documented | FR9.1, FR9.2 |
| BR4.1 | Screens and messages per the mockups | FR3.1, FR3.3, FR3.4, FR3.6, FR3.7 |
