# Puzzles — source and licence

Puzzles from the Lichess puzzle database, released under CC0.

- Source: the Lichess puzzle database, https://database.lichess.org/#puzzles
  (file https://database.lichess.org/lichess_db_puzzle.csv.zst).
- Licence: Creative Commons CC0 1.0 Universal (public domain dedication),
  https://creativecommons.org/publicdomain/zero/1.0/. No attribution is
  required; JustChess credits Lichess anyway, under the Tactics list and on the
  puzzle screen.
- Curated on 2026-11-13 by `scripts/curate_puzzles.py` with seed 20261113.
- Filter: Themes include the theme tag; Popularity >= 80; NbPlays >= 500; Rating 600-2200; then justchess.puzzles.validate_puzzle. Up to 300 per theme are sampled evenly across
  the rating range; each file is sorted by rating.

The positions and moves are unchanged from the Lichess data: `fen` is the
position before the opponent's set-up move `moves[0]`, and the player finds the
rest.

| File | Puzzles |
|---|---|
| `fork.json` | 300 |
| `pin.json` | 300 |
| `skewer.json` | 300 |
| `discoveredAttack.json` | 300 |
| `mateIn1.json` | 300 |
| `mateIn2.json` | 300 |
