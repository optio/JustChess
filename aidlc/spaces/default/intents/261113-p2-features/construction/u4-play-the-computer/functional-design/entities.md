# Entities — u4-play-the-computer

U4 uses the version 4 schema from U2 and adds no tables or columns. Below are the stored fields it reads or writes, then the in-memory entities it adds. The in-memory entities are lost on restart, by design (ADR-009).

```yaml
entities:
  - name: Room
    description: a computer room is a room in mode computer (ADR-002)
    attributes:
      - { name: code, type: string, required: true, unique: true }
      - { name: mode, type: enum, allowed: [waiting, pass_along, online, computer], constraints: "computer is set at creation and never changes" }
      - { name: computerLevel, type: enum, allowed: [beginner, casual, club, strong, maximum], required: false, constraints: "set exactly when mode = computer (schema CHECK)" }
      - { name: winsA, type: integer, default: 0, constraints: "in a computer room: the player's wins at this level" }
      - { name: winsB, type: integer, default: 0, constraints: "in a computer room: the computer's wins" }
      - { name: draws, type: integer, default: 0 }
    constraints:
      - "a computer room has seat A (the player, with a token) and seat B (the computer, no token) from creation"
  - name: Seat
    attributes:
      - { name: slot, type: enum, allowed: [A, B] }
      - { name: isComputer, type: boolean, default: false, constraints: "true only for seat B of a computer room" }
      - { name: tokenHash, type: string, required: false, constraints: "null exactly when isComputer (schema CHECK); no presented token can match it" }
  - name: Game
    attributes:
      - { name: whiteSlot, type: enum, allowed: [A, B], constraints: "chosen at creation from the player's colour; swapped on rematch unless the player picks a colour" }
      - { name: version, type: integer, constraints: "increments on every move, takeback and end; the reply check compares it (ADR-009)" }
      - { name: status, type: enum, allowed: [playing, finished], constraints: "a computer game starts playing at once; it is never waiting" }
      - { name: endReason, type: enum, allowed: [checkmate, stalemate, insufficient_material, threefold_repetition, fifty_moves, fivefold_repetition, seventyfive_moves, resigned] }
      - { name: counted, type: boolean, default: true, constraints: "always true in computer rooms" }
  - name: Move
    description: rows removed by a takeback; the remaining rows are unchanged
    attributes:
      - { name: ply, type: integer }
      - { name: uci, type: string }
      - { name: san, type: string }
      - { name: capturedPiece, type: string, required: false }
      - { name: capturedSquare, type: string, required: false }
  - name: Level
    description: fixed table in ComputerOpponent (FR6.2); a value object, not stored apart from Room.computerLevel
    attributes:
      - { name: id, type: enum, allowed: [beginner, casual, club, strong, maximum] }
      - { name: name, type: string, constraints: "Beginner, Casual, Club, Strong, Maximum" }
      - { name: skill, type: integer, min: 0, max: 20, constraints: "0, 5, 10, 15, 20" }
      - { name: thinkSeconds, type: decimal, constraints: "0.1, 0.3, 0.6, 1.0, 2.0" }
  - name: EngineRequest
    description: in memory; one entry in Engine's FIFO queue
    attributes:
      - { name: requestId, type: integer, unique: true }
      - { name: roomCode, type: string }
      - { name: purpose, type: enum, allowed: [reply, hint] }
      - { name: position, type: string, constraints: "FEN plus move history replayed from stored moves; never user text" }
      - { name: skill, type: integer, min: 0, max: 20 }
      - { name: thinkSeconds, type: decimal, min: 0.1, max: 2.0 }
      - { name: state, type: enum, allowed: [queued, thinking, done, failed] }
    constraints:
      - "at most one in state thinking at any time (NFR1)"
      - "at most 32 queued; a further request is refused as busy"
  - name: EngineStatus
    description: in memory; Engine's health
    attributes:
      - { name: available, type: boolean, constraints: "false while starting, when no binary was found, or after a crash that the one restart did not cure" }
      - { name: reason, type: string, required: false, constraints: "a short text for the person, never the binary path; \"The computer is starting\" until the process is open" }
      - { name: restartsUsed, type: integer, min: 0, max: 1, constraints: "never reset while the app runs (accepted, ADR-001)" }
  - name: EngineRateWindow
    description: in memory, per client address, for engine-consuming routes (reuses ratelimit.RateLimiter)
    attributes:
      - { name: clientAddress, type: string }
      - { name: route, type: enum, allowed: [create, hint, computer-move] }
      - { name: timestamps, type: list<timestamp>, constraints: "kept for 60 s" }
  - name: RetryBackoff
    description: in memory, per room; set after a failed reply (not busy)
    attributes:
      - { name: roomCode, type: string, unique: true }
      - { name: until, type: timestamp, constraints: "failure time + 5 s; computer-move before then returns the state without asking" }
  - name: ReplyInFlight
    description: in memory, per room (ADR-009)
    attributes:
      - { name: roomCode, type: string, unique: true }
      - { name: gameId, type: integer, constraints: "the game the reply was asked for; a new game starts at version 0, so version alone cannot tell games apart" }
      - { name: version, type: integer, constraints: "the game version noted when the reply was asked for" }
      - { name: requestId, type: integer, constraints: "only the completion of this request may clear the flag" }
  - name: HintInFlight
    description: in memory, per room
    attributes:
      - { name: roomCode, type: string, unique: true }
  - name: ComputerState
    description: derived for the snapshot and the socket event; not stored
    attributes:
      - { name: state, type: enum, allowed: [idle, queued, thinking, unavailable] }
      - { name: queuePosition, type: integer, required: false, min: 1, constraints: "requests ahead plus one; only while queued" }
      - { name: reason, type: string, required: false, constraints: "only while unavailable" }
relationships:
  - "Room 1 — 2 Seat (A: player, B: computer)"
  - "Room 1 — n Game (one current)"
  - "Game 1 — n Move"
  - "Room 1 — 0..1 ReplyInFlight; Room 1 — 0..1 HintInFlight"
  - "ReplyInFlight / HintInFlight 1 — 1 EngineRequest"
  - "Room.computerLevel n — 1 Level"
```

## Summary

- **Stored entities.** Room, Seat, Game and Move are the existing rows. A computer room has `mode = computer`, a level, and a tokenless seat B. Its score columns count the player against the computer.
- **Removed rows.** A takeback deletes the last one or two Move rows and recomputes the game's position.
- **Level.** A fixed five-row table with the skill levels and think times from FR6.2.
- **In-memory entities:**
  - EngineRequest and EngineStatus belong to Engine.
  - ReplyInFlight and HintInFlight are kept per room by HttpApi.
  - ComputerState is computed for the snapshot and the socket events.

  None of these survive a restart. After one, resume asks for the reply again.
