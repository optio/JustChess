# Entities — u5-lessons-and-puzzles

Nothing new is stored in the database. Lessons and puzzles are files in the repo, loaded and validated at start-up. Progress lives on the device.

```yaml
entities:
  - name: Lesson
    description: A walkthrough-and-practice lesson file (existing format) with a new kind
    attributes:
      - { name: id, type: string, required: true, unique: true, constraints: "file stem, ^[a-z0-9][a-z0-9-]{0,47}$" }
      - { name: kind, type: enum, required: false, allowed: [opening, trap, defence], default: opening }
      - { name: name, type: string, required: true, max: 80 }
      - { name: aliases, type: list<string>, required: false }
      - { name: eco, type: string, required: false, constraints: "^[A-E][0-9]{2}$" }
      - { name: side, type: enum, required: true, allowed: [white, black] }
      - { name: start, type: string, required: true, constraints: "startpos or a legal FEN" }
      - { name: moves, type: list<LessonMove>, required: true, min: 1, max: 60 }
      - { name: objectives, type: list<string>, required: false }
    constraints:
      - "every move has a note of at most 280 characters (existing rule)"
      - "the whole line replays legally from start (existing rule)"
  - name: Puzzle
    description: One tactics puzzle from the curated Lichess subset
    attributes:
      - { name: id, type: string, required: true, unique: true, constraints: "Lichess puzzle id, 5 alphanumerics" }
      - { name: theme, type: enum, required: true, allowed: [fork, pin, skewer, discoveredAttack, mateIn1, mateIn2] }
      - { name: fen, type: string, required: true, constraints: "position BEFORE the opponent's set-up move, as in the Lichess data" }
      - { name: moves, type: list<uci>, required: true, min: 2, constraints: "first move is the opponent's set-up move; then player, reply, player..." }
      - { name: rating, type: integer, required: true, min: 400, max: 3000 }
    constraints:
      - "the whole move list is legal from fen"
      - "mateIn1/mateIn2 puzzles end in checkmate"
      - "player moves count = 1 for mateIn1, 2 for mateIn2, 1..4 otherwise"
  - name: PuzzleSet
    description: One JSON file per theme in puzzles/, plus puzzles/LICENSE.md (CC0 credit)
    attributes:
      - { name: theme, type: enum, required: true }
      - { name: source, type: string, required: true, constraints: "\"Lichess puzzle database (CC0)\"" }
      - { name: puzzles, type: list<Puzzle>, required: true, min: 1, max: 400 }
    constraints:
      - "all files together are at most 5 MB (NFR6)"
      - "puzzles sorted by rating ascending, so the list goes from easier to harder"
  - name: TrainerProgress
    description: Per-device progress in browser storage (existing settings storage pattern)
    attributes:
      - { name: key, type: string, required: true, constraints: "<group>:<itemId>, e.g. tactics:fork:00008" }
      - { name: group, type: enum, allowed: [openings, traps, endgames, tactics, defence] }
      - { name: solvedAt, type: timestamp }
    constraints:
      - "stored as one JSON object under one localStorage key; at most 5000 entries; unreadable or missing storage means no progress shown"
  - name: HubTab
    description: Client-side tab registry; U6 registers Endgames later
    attributes:
      - { name: id, type: enum, allowed: [openings, traps, endgames, tactics, defence] }
      - { name: label, type: string }
      - { name: order, type: integer }
```

## Summary

- Lessons gain an optional `kind` field, which defaults to opening so the two existing files keep working.
- Puzzles live in six theme files under `puzzles/`, curated once from the Lichess CC0 data by `scripts/curate_puzzles.py`.
- Progress is kept per device.
- The hub's tabs come from a small registry, so U6 can add Endgames without touching U5's code.
