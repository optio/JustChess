# Entities — u2-data-and-your-games

Schema version 4, created fresh (ADR-010). These tables replace the version-3 schema in `justchess/db.py`. Push subscriptions and alert records keep their version-3 shape. Logical types are given here; SQLite types are chosen in Code Generation.

```yaml
entities:
  - name: Room
    description: One room; it outlives its games and holds the score
    attributes:
      - { name: code, type: string, required: true, unique: true, constraints: "6 chars A-Z0-9" }
      - { name: mode, type: enum, required: true, allowed: [waiting, pass_along, online, computer], default: waiting }
      - { name: computerLevel, type: enum, required: false, allowed: [beginner, casual, club, strong, maximum], constraints: "set if and only if mode = computer" }
      - { name: createdAt, type: timestamp, required: true }
      - { name: lastActivityAt, type: timestamp, required: true }
      - { name: winsA, type: integer, required: true, default: 0, min: 0 }
      - { name: winsB, type: integer, required: true, default: 0, min: 0 }
      - { name: draws, type: integer, required: true, default: 0, min: 0 }
      - { name: rematchRequestedBy, type: enum, required: false, allowed: [A, B] }
      - { name: rematchRequestedAt, type: timestamp, required: false }
    constraints:
      - "computerLevel is present exactly when mode = computer"
    relationships:
      - { to: Seat, cardinality: "1 to 0..2", direction: "Room owns Seats" }
      - { to: Game, cardinality: "1 to 1..n", direction: "Room owns Games" }
      - { to: JoinRequest, cardinality: "1 to 0..n", direction: "Room owns JoinRequests" }
  - name: Seat
    description: One of the two seats; the computer's seat has no token
    attributes:
      - { name: seatId, type: integer, required: true, unique: true }
      - { name: roomCode, type: string, required: true, references: Room.code }
      - { name: slot, type: enum, required: true, allowed: [A, B] }
      - { name: isComputer, type: boolean, required: true, default: false }
      - { name: tokenHash, type: string, required: false, unique: true, constraints: "SHA-256 hex; null if and only if isComputer" }
      - { name: continueTokenHash, type: string, required: false, unique: true }
      - { name: continueExpiresAt, type: timestamp, required: false }
      - { name: lastSeenAt, type: timestamp, required: true }
    constraints:
      - "(roomCode, slot) unique"
      - "isComputer = true implies tokenHash is null and slot = B"
  - name: Game
    description: One game in a room
    attributes:
      - { name: gameId, type: integer, required: true, unique: true }
      - { name: roomCode, type: string, required: true, references: Room.code }
      - { name: number, type: integer, required: true, min: 1 }
      - { name: whiteSlot, type: enum, required: true, allowed: [A, B] }
      - { name: fen, type: string, required: true }
      - { name: version, type: integer, required: true, default: 0, min: 0 }
      - { name: status, type: enum, required: true, allowed: [waiting, playing, finished], default: waiting }
      - { name: endReason, type: enum, required: false, allowed: [checkmate, stalemate, insufficient_material, fivefold_repetition, seventyfive_moves, threefold_claimed, fifty_moves_claimed, threefold_repetition, fifty_moves, abandoned, resigned] }
      - { name: result, type: enum, required: false, allowed: ["1-0", "0-1", "1/2-1/2"] }
      - { name: counted, type: boolean, required: true, default: true }
      - { name: startedAt, type: timestamp, required: false }
      - { name: endedAt, type: timestamp, required: false }
    constraints:
      - "(roomCode, number) unique"
  - name: Move
    description: One ply of a game, with what it captured
    attributes:
      - { name: gameId, type: integer, required: true, references: Game.gameId }
      - { name: ply, type: integer, required: true, min: 1 }
      - { name: uci, type: string, required: true }
      - { name: san, type: string, required: true }
      - { name: capturedPiece, type: string, required: false, constraints: "one of pnbrqPNBRQ (FEN letter; uppercase = white piece)" }
      - { name: capturedSquare, type: string, required: false, constraints: "a1..h8; differs from the arrival square for en passant" }
      - { name: playedAt, type: timestamp, required: true }
    constraints:
      - "(gameId, ply) unique"
      - "capturedPiece and capturedSquare are both present or both absent"
  - name: JoinRequest
    description: A visitor's request to join a pass-along room (table created here, used by u3)
    attributes:
      - { name: requestId, type: integer, required: true, unique: true }
      - { name: roomCode, type: string, required: true, references: Room.code }
      - { name: requesterTokenHash, type: string, required: true, unique: true }
      - { name: status, type: enum, required: true, allowed: [pending, accepted, declined, lapsed], default: pending }
      - { name: createdAt, type: timestamp, required: true }
      - { name: expiresAt, type: timestamp, required: true }
      - { name: answeredAt, type: timestamp, required: false }
    constraints:
      - "at most one pending JoinRequest per roomCode"
      - "rows are deleted with their room"
  - name: RoomSummary
    description: Read model returned by the batch summary request; not stored
    attributes:
      - { name: code, type: string, required: true }
      - { name: found, type: boolean, required: true }
      - { name: kind, type: enum, allowed: [friend, computer] }
      - { name: computerLevel, type: enum, required: false }
      - { name: opponent, type: enum, allowed: [waiting, joined, computer] }
      - { name: colour, type: enum, allowed: [white, black] }
      - { name: status, type: enum, allowed: [waiting, playing, finished] }
      - { name: yourTurn, type: boolean }
      - { name: result, type: enum, required: false, allowed: [won, lost, drawn] }
      - { name: lastActivityAt, type: timestamp }
      - { name: endedAt, type: timestamp, required: false }
      - { name: fen, type: string }
      - { name: pendingJoinRequest, type: boolean }
  - name: SavedSeat
    description: Browser-side record of a seat (seat store); extended with kind and level
    attributes:
      - { name: code, type: string, required: true }
      - { name: token, type: string, required: true }
      - { name: slot, type: enum, allowed: [A, B] }
      - { name: kind, type: enum, allowed: [friend, computer], default: friend }
      - { name: computerLevel, type: enum, required: false }
      - { name: savedAt, type: timestamp }
```

## Summary

- **Room** gains `mode` and `computerLevel`.
- **Seat** gains `isComputer`, and its token is nullable for the computer's seat.
- **Game** gains `counted`, plus two end reasons used later by U4 (`threefold_repetition` and `fifty_moves`, the automatic draws, and `resigned`).
- **Move** gains `capturedPiece` and `capturedSquare`.
- **JoinRequest** is created now so that U3 needs no schema change.
- **RoomSummary** is the read model behind the "Your games" list.
- **SavedSeat** in the browser gains `kind` and `computerLevel`, so U4 can find a level's room.

There are no player names in JustChess. The list labels a friend room by its state ("Waiting for a friend", "Friend") and its room code; see BR2.2.
