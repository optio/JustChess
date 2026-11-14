"""Curate the shipped tactics puzzles from the Lichess puzzle CSV (P2 U5, W2, BR2.2).

Run once by a developer, never by the app. The source is the public Lichess
puzzle database (CC0), https://database.lichess.org/#puzzles, downloaded into
the git-ignored ``data/`` folder and streamed through ``zstd`` (no new Python
dependency)::

    curl -L -o data/lichess_db_puzzle.csv.zst https://database.lichess.org/lichess_db_puzzle.csv.zst
    zstd -dc data/lichess_db_puzzle.csv.zst | uv run --frozen python scripts/curate_puzzles.py -

The argument is a plain CSV path, or ``-`` for standard input. Columns used:
PuzzleId, FEN, Moves, Rating, Popularity, NbPlays and Themes.

For each theme (fork, pin, skewer, discoveredAttack, mateIn1, mateIn2):

1. keep rows whose ``Themes`` include the theme tag, with ``Popularity >= 80``,
   ``NbPlays >= 500`` and a rating from 600 to 2200;
2. run ``justchess.puzzles.validate_puzzle`` on every candidate, so only valid
   puzzles can ever be sampled;
3. sample 300 evenly across the rating range: the valid candidates, sorted by
   rating, are cut into 300 equal slices and one puzzle is drawn from each
   slice with a fixed seed (all are kept when there are 300 or fewer).

It writes ``puzzles/<theme>.json`` (PuzzleSet shape, sorted by rating) and
``puzzles/LICENSE.md`` (CC0 notice, source URL, date, filter and seed), prints
the counts and the total size, and writes nothing and exits 1 when a theme ends
under 250 puzzles or the total would pass 5 MB (NFR6).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import random
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # run as a plain script: make the justchess package importable

from justchess.puzzles import SOURCE, THEMES, PuzzleError, validate_puzzle  # noqa: E402

SOURCE_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
SOURCE_PAGE = "https://database.lichess.org/#puzzles"
MIN_POPULARITY = 80
MIN_PLAYS = 500
RATING_LOW, RATING_HIGH = 600, 2200
PER_THEME = 300
MIN_PER_THEME = 250
MAX_TOTAL_BYTES = 5 * 1024 * 1024
DEFAULT_SEED = 20261113
REQUIRED_COLUMNS = ("PuzzleId", "FEN", "Moves", "Rating", "Popularity", "NbPlays", "Themes")
FILTER_TEXT = (f"Themes include the theme tag; Popularity >= {MIN_POPULARITY}; NbPlays >= {MIN_PLAYS}; "
               f"Rating {RATING_LOW}-{RATING_HIGH}; then justchess.puzzles.validate_puzzle")


class CurationError(RuntimeError):
    """The curated set would break BR2.2 (too few puzzles, too large) or the input is unusable."""


@dataclass(frozen=True)
class Candidate:
    """One CSV row that passed the filter, before validation."""

    puzzle_id: str
    fen: str
    moves: tuple[str, ...]
    rating: int


# --- reading and filtering ------------------------------------------------------

def read_rows(stream: TextIO) -> Iterator[dict[str, str]]:
    """The CSV rows as dicts; raise CurationError when a required column is missing."""
    reader = csv.DictReader(stream)
    missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or ())]
    if missing:
        raise CurationError(f"the CSV has no column {missing[0]} (is this the Lichess puzzle file?)")
    yield from reader


def _number(text: str | None) -> int | None:
    try:
        return int(str(text).strip())
    except ValueError:
        return None


def passes_filter(row: dict[str, str]) -> bool:
    """BR2.2 filter: popular, often played, rated 600-2200."""
    rating, popularity, plays = _number(row.get("Rating")), _number(row.get("Popularity")), _number(row.get("NbPlays"))
    if rating is None or popularity is None or plays is None:
        return False
    return popularity >= MIN_POPULARITY and plays >= MIN_PLAYS and RATING_LOW <= rating <= RATING_HIGH


def collect_candidates(rows: Iterable[dict[str, str]]) -> dict[str, list[Candidate]]:
    """Filtered rows grouped by every shipped theme they are tagged with."""
    found: dict[str, list[Candidate]] = {theme: [] for theme in THEMES}
    for row in rows:
        tags = set((row.get("Themes") or "").split())
        wanted = [theme for theme in THEMES if theme in tags]
        if not wanted or not passes_filter(row):
            continue
        candidate = Candidate(row["PuzzleId"].strip(), row["FEN"].strip(),
                              tuple((row.get("Moves") or "").split()), int(row["Rating"]))
        for theme in wanted:
            found[theme].append(candidate)
    return found


def validate_candidates(theme: str, candidates: Iterable[Candidate]) -> list[dict[str, Any]]:
    """Only the candidates that pass the shared validator, as puzzle dicts."""
    valid = []
    for candidate in candidates:
        data = {"id": candidate.puzzle_id, "theme": theme, "fen": candidate.fen,
                "moves": list(candidate.moves), "rating": candidate.rating}
        try:
            valid.append(validate_puzzle(data, theme))
        except PuzzleError:
            continue
    return valid


# --- sampling and output --------------------------------------------------------

def sample_evenly(puzzles: list[dict[str, Any]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    """``count`` puzzles spread over the rating range (one per equal slice), sorted by rating."""
    ordered = sorted(puzzles, key=lambda puzzle: (puzzle["rating"], puzzle["id"]))
    if len(ordered) <= count:
        return ordered
    picked = []
    for index in range(count):
        start, end = index * len(ordered) // count, (index + 1) * len(ordered) // count
        picked.append(ordered[rng.randrange(start, end)])
    return picked


def curate(rows: Iterable[dict[str, str]], *, per_theme: int = PER_THEME, seed: int = DEFAULT_SEED,
           log: TextIO = sys.stderr) -> dict[str, list[dict[str, Any]]]:
    """Filter, validate, then sample each theme. Returns {theme: puzzles in rating order}."""
    candidates = collect_candidates(rows)
    sets = {}
    for theme in THEMES:
        valid = validate_candidates(theme, candidates[theme])
        sets[theme] = sample_evenly(valid, per_theme, random.Random(f"{seed}:{theme}"))
        print(f"{theme}: {len(candidates[theme])} candidates, {len(valid)} valid, {len(sets[theme])} kept", file=log)
    return sets


def render_set(theme: str, puzzles: list[dict[str, Any]]) -> str:
    """The PuzzleSet JSON text, one puzzle per line so diffs stay readable."""
    lines = [json.dumps(puzzle, separators=(",", ":")) for puzzle in puzzles]
    body = ",\n    ".join(lines)
    return (f'{{\n  "theme": {json.dumps(theme)},\n  "source": {json.dumps(SOURCE)},\n'
            f'  "puzzles": [\n    {body}\n  ]\n}}\n')


def render_license(sets: dict[str, list[dict[str, Any]]], *, seed: int, date: str) -> str:
    counts = "\n".join(f"| `{theme}.json` | {len(sets[theme])} |" for theme in THEMES)
    return f"""# Puzzles — source and licence

Puzzles from the Lichess puzzle database, released under CC0.

- Source: the Lichess puzzle database, {SOURCE_PAGE}
  (file {SOURCE_URL}).
- Licence: Creative Commons CC0 1.0 Universal (public domain dedication),
  https://creativecommons.org/publicdomain/zero/1.0/. No attribution is
  required; JustChess credits Lichess anyway, under the Tactics list and on the
  puzzle screen.
- Curated on {date} by `scripts/curate_puzzles.py` with seed {seed}.
- Filter: {FILTER_TEXT}. Up to {PER_THEME} per theme are sampled evenly across
  the rating range; each file is sorted by rating.

The positions and moves are unchanged from the Lichess data: `fen` is the
position before the opponent's set-up move `moves[0]`, and the player finds the
rest.

| File | Puzzles |
|---|---|
{counts}
"""


def build_output(sets: dict[str, list[dict[str, Any]]], *, min_per_theme: int, seed: int, date: str,
                 max_bytes: int = MAX_TOTAL_BYTES) -> dict[str, str]:
    """File name -> text for every output file; raise CurationError when BR2.2 would be broken."""
    short = [f"{theme} ({len(sets[theme])})" for theme in THEMES if len(sets[theme]) < min_per_theme]
    if short:
        raise CurationError(f"fewer than {min_per_theme} valid puzzles for: {', '.join(short)}")
    files = {f"{theme}.json": render_set(theme, sets[theme]) for theme in THEMES}
    files["LICENSE.md"] = render_license(sets, seed=seed, date=date)
    total = sum(len(text.encode("utf-8")) for text in files.values())
    if total > max_bytes:
        raise CurationError(f"the puzzle files would take {total} bytes, over the {max_bytes}-byte limit")
    return files


def write_output(out_dir: Path, files: dict[str, str]) -> int:
    """Write the files and return the total size in bytes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    return sum(len(text.encode("utf-8")) for text in files.values())


def _open_source(source: str) -> TextIO:
    if source == "-":
        return io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", newline="")
    return open(source, encoding="utf-8", newline="")  # noqa: SIM115 - closed by the caller


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Curate puzzles/ from the Lichess puzzle CSV.")
    parser.add_argument("source", help="path to lichess_db_puzzle.csv, or - for standard input")
    parser.add_argument("--out", type=Path, default=ROOT / "puzzles", help="output folder (default: puzzles/)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--per-theme", type=int, default=PER_THEME)
    parser.add_argument("--min-per-theme", type=int, default=MIN_PER_THEME)
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="date written to LICENSE.md")
    args = parser.parse_args(argv)
    try:
        stream = _open_source(args.source)
    except OSError as error:
        print(f"Could not open {args.source}: {error.strerror or error}", file=sys.stderr)
        return 1
    try:
        with stream:
            sets = curate(read_rows(stream), per_theme=args.per_theme, seed=args.seed)
        files = build_output(sets, min_per_theme=args.min_per_theme, seed=args.seed, date=args.date)
    except (CurationError, csv.Error, UnicodeDecodeError) as error:
        print(f"Curation failed, nothing written: {error}", file=sys.stderr)
        return 1
    total = write_output(args.out, files)
    count = sum(len(sets[theme]) for theme in THEMES)
    print(f"Wrote {count} puzzles in {len(THEMES)} files to {args.out} ({total} bytes in total)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
