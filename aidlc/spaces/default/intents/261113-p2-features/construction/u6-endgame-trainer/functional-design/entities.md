# Entities — u6-endgame-trainer

U6 adds no database tables. Endgame positions are hand-written YAML files in the repo, read once at start-up. An attempt lives only in the browser, and the server is stateless (the client sends the move list each time).

```yaml
entities:
  - name: EndgamePosition
    description: one training position, loaded from endgames/<category>.yaml
    attributes:
      - { name: positionId, type: string, required: true, unique: true, constraints: "lower-case letters, digits and hyphens, 3 to 40 characters; unique across all files" }
      - { name: category, type: enum, required: true, allowed: [queen-mate, rook-mate, king-pawn, opposition], constraints: "taken from the file name, never from the position" }
      - { name: title, type: string, required: true, constraints: "1 to 60 characters" }
      - { name: fen, type: string, required: true, constraints: "a legal position (python-chess Board.is_valid), not already over, with the player to move" }
      - { name: goal, type: enum, required: true, allowed: [mate, promote, draw] }
      - { name: hint, type: string, required: true, constraints: "1 to 200 characters, in our own words, plain text" }
      - { name: order, type: integer, required: true, constraints: "position within its category, from file order" }
    constraints:
      - "the player is the side to move in the FEN"
      - "goal mate: the player has a queen or a rook; goal promote: the player has at least one pawn"
      - "at least 3 positions per category (checked at load; fewer is logged, not fatal)"
  - name: EndgameCatalog
    description: in memory; all valid positions, built at start-up
    attributes:
      - { name: positions, type: list<EndgamePosition>, constraints: "ordered by category (queen-mate, rook-mate, king-pawn, opposition), then by order" }
      - { name: installed, type: boolean, constraints: "false when the folder is missing or no position is valid" }
  - name: Attempt
    description: client-only; the move list of one try at a position
    attributes:
      - { name: positionId, type: string }
      - { name: moves, type: list<string>, constraints: "UCI moves from the start position: the player's moves at even indexes, the defender's replies at odd indexes; at most 300 plies" }
  - name: Verdict
    description: the answer to one play request; not stored
    attributes:
      - { name: status, type: enum, allowed: [playing, passed, failed] }
      - { name: reason, type: enum, required: false, allowed: [checkmate, promoted, held_moves, threefold_repetition, fifty_moves, stalemate, insufficient_material, player_mated, pawns_lost, too_long], constraints: "a draw is always reported by its specific kind; status says whether it passed (draw goal) or failed (mate or promote goal)" }
      - { name: reply, type: object, required: false, constraints: "{uci, san} of the defender's move, when one was played" }
      - { name: playerMoves, type: integer, constraints: "the player's moves counted so far, including the one just sent" }
      - { name: movesLeft, type: integer, required: false, constraints: "goal draw only: hold target minus playerMoves, never below 0" }
  - name: EndgameSettings
    description: the endgames section of gameplay.yaml
    attributes:
      - { name: defenderSkill, type: integer, min: 0, max: 20, default: 20 }
      - { name: defenderThinkSeconds, type: decimal, min: 0.05, max: 10, default: 1.0 }
      - { name: holdMoves, type: integer, min: 1, max: 200, default: 30 }
      - { name: maxPlies, type: integer, min: 10, max: 1000, default: 300 }
      - { name: playPerMinute, type: integer, min: 1, max: 1000, default: 30, constraints: "per client address" }
      - { name: refusalQueue, type: integer, min: 0, default: 16, constraints: "endgame plays are refused as busy once this many engine requests wait; at most engine.queue_cap" }
      - { name: waitLimitSeconds, type: decimal, min: 1, max: 300, default: 30, constraints: "a play still waiting for the engine after this long is cancelled and answered busy" }
relationships:
  - "EndgameCatalog 1 — n EndgamePosition"
  - "Attempt n — 1 EndgamePosition (by positionId)"
  - "Verdict 1 — 1 Attempt (computed per request)"
```

## Summary

- **EndgamePosition** is the only content entity. There are four category files with at least three positions each, and each position has a FEN, a goal and a hint.
- **EndgameCatalog** holds the valid positions in memory.
- **Attempt** lives only in the browser. Each play request sends its moves, and the server answers with a **Verdict**.
- **EndgameSettings** comes from the new `endgames` section of `gameplay.yaml`: the defender's strength and think time, the number of moves needed to hold a draw, the longest allowed attempt, and the per-address request limit.
