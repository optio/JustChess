"""P2 U5 curation script (``scripts/curate_puzzles.py``): W2, BR2.2.

Runs on the small hand-checked fixture ``tests/fixtures/puzzles_sample.csv``
(Lichess format, with rows that the filter drops and rows that the validator
refuses). It never needs the real download and writes only into ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import io
import json
import random
import sys
from pathlib import Path

import pytest

from justchess.puzzles import SOURCE, THEMES, load_puzzles

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "tests" / "fixtures" / "puzzles_sample.csv"


def _load_script():
    spec = importlib.util.spec_from_file_location("curate_puzzles", ROOT / "scripts" / "curate_puzzles.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up while the class is built
    spec.loader.exec_module(module)
    return module


curate_puzzles = _load_script()


def rows() -> list[dict[str, str]]:
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        return list(curate_puzzles.read_rows(handle))


def test_the_filter_keeps_popular_often_played_puzzles_in_the_rating_range() -> None:
    found = curate_puzzles.collect_candidates(rows())
    mate_ids = {candidate.puzzle_id for candidate in found["mateIn1"]}
    assert mate_ids == {"M1a01", "M1a02", "M1a03", "M1a04", "M1x01", "M1x02"}, \
        "low popularity, few plays and ratings outside 600-2200 are dropped"
    assert {c.puzzle_id for c in found["fork"]} == {"Fk1a1", "Fk1a2", "Fk1a3", "Fk1x1", "Mx1a1"}
    assert "Mx1a1" in {c.puzzle_id for c in found["pin"]}, "a row tagged with two themes is a candidate for both"
    every = {c.puzzle_id for theme in THEMES for c in found[theme]}
    assert "Ot1a1" not in every and "Bd1a1" not in every and "Fk1f1" not in every
    with pytest.raises(curate_puzzles.CurationError, match="no column"):
        list(curate_puzzles.read_rows(io.StringIO("PuzzleId,FEN\nx,y\n")))


def test_validators_run_before_sampling_so_only_valid_puzzles_are_kept() -> None:
    sets = curate_puzzles.curate(rows(), per_theme=4, seed=1, log=io.StringIO())
    assert [p["id"] for p in sets["mateIn1"]] == ["M1a01", "M1a02", "M1a03", "M1a04"], \
        "4 of the 6 candidates are valid, and all 4 are kept: invalid ones never take a sample slot"
    assert [p["id"] for p in sets["mateIn2"]] == ["M2a01", "M2a02", "M2a03"]
    assert "Fk1x1" not in {p["id"] for p in sets["fork"]}
    # sampling spreads over the rating range and is repeatable with the seed
    pool = [{"id": f"P{i:04d}", "rating": 600 + i} for i in range(100)]
    picked = curate_puzzles.sample_evenly(pool, 10, random.Random(7))
    assert len(picked) == 10 and [p["rating"] for p in picked] == sorted(p["rating"] for p in picked)
    assert all(600 + 10 * k <= p["rating"] < 600 + 10 * (k + 1) for k, p in enumerate(picked)), "one per slice"
    assert picked == curate_puzzles.sample_evenly(pool, 10, random.Random(7))


def test_the_output_has_the_puzzle_set_shape_and_loads_cleanly(tmp_path: Path) -> None:
    out = tmp_path / "puzzles"
    code = curate_puzzles.main([str(SAMPLE), "--out", str(out), "--per-theme", "2", "--min-per-theme", "1",
                                "--date", "2026-01-02"])
    assert code == 0
    assert sorted(path.name for path in out.iterdir()) == sorted([f"{t}.json" for t in THEMES] + ["LICENSE.md"])
    for theme in THEMES:
        data = json.loads((out / f"{theme}.json").read_text(encoding="utf-8"))
        assert set(data) == {"theme", "source", "puzzles"} and data["theme"] == theme and data["source"] == SOURCE
        assert 1 <= len(data["puzzles"]) <= 2
        assert all(set(p) == {"id", "theme", "fen", "moves", "rating"} for p in data["puzzles"])
        assert [p["rating"] for p in data["puzzles"]] == sorted(p["rating"] for p in data["puzzles"])
    licence = (out / "LICENSE.md").read_text(encoding="utf-8")
    assert "CC0" in licence and curate_puzzles.SOURCE_URL in licence and "2026-01-02" in licence
    assert "Popularity >= 80" in licence and "NbPlays >= 500" in licence
    catalog = load_puzzles(out)
    assert catalog.skipped == 0 and all(entry["count"] >= 1 for entry in catalog.theme_list())


def test_fewer_than_250_per_theme_fails_and_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    out = tmp_path / "puzzles"
    assert curate_puzzles.main([str(SAMPLE), "--out", str(out)]) == 1
    assert not out.exists(), "nothing is written when the set is too small"
    assert "fewer than 250 valid puzzles" in capsys.readouterr().err
    sets = {theme: [] for theme in THEMES}
    with pytest.raises(curate_puzzles.CurationError, match="fewer than 1"):
        curate_puzzles.build_output(sets, min_per_theme=1, seed=1, date="x")
    big = {theme: [{"id": "AAAAA", "theme": theme, "fen": "x" * 90, "moves": ["e2e4"] * 8, "rating": 1000}] * 3
           for theme in THEMES}
    with pytest.raises(curate_puzzles.CurationError, match="over the"):
        curate_puzzles.build_output(big, min_per_theme=1, seed=1, date="x", max_bytes=1000)
