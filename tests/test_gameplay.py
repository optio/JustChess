"""Gameplay settings (gameplay.yaml, justchess.gameplay): defaults, an override file, bad values, a missing file.

Also checks that the module fallbacks equal the built-in defaults, that the app
uses the loaded settings, and that the page gets only the client keys.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re

import pytest
import yaml

import stockfish_install
from justchess import analysis, computer, engine, gameplay, housekeeping, ratelimit, rooms
from justchess.api import create_app
from justchess.gameplay import DEFAULT_GAMEPLAY, GameplayError, load_gameplay

SHIPPED = gameplay.DEFAULT_FILE


def without_source(settings: gameplay.Gameplay) -> dict:
    values = dataclasses.asdict(settings)
    values.pop("source")
    return values


def test_the_shipped_file_equals_the_built_in_defaults_and_every_key_has_a_comment() -> None:
    assert yaml.safe_load(SHIPPED.read_text(encoding="utf-8")) == gameplay.DEFAULTS
    assert without_source(load_gameplay(SHIPPED, env={})) == without_source(DEFAULT_GAMEPLAY)
    for line in SHIPPED.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\s+\w+:\s*\S", line):  # a key with a value
            assert "#" in line, f"no comment on: {line.strip()}"


def test_the_module_fallbacks_equal_the_defaults() -> None:
    settings = DEFAULT_GAMEPLAY
    assert (engine.MAX_QUEUE, engine.GRACE_SECONDS, engine.RESTARTS) == (
        settings.queue_cap, settings.overrun_grace, settings.restarts)
    assert (computer.HINT_QUEUE_LIMIT, computer.BACKOFF_SECONDS) == (settings.hint_queue_limit, settings.retry_backoff)
    assert (rooms.REQUEST_TTL, rooms.DECLINE_MEMORY, rooms.MAX_REMEMBERED_ADDRESSES, rooms.ABANDON_AFTER) == (
        settings.join_request_ttl, settings.decline_memory, settings.address_book_cap, settings.abandon_after)
    assert ratelimit.MAX_ATTEMPTS == settings.join_requests_per_minute
    assert housekeeping.RETENTION == settings.idle_room_retention
    assert analysis.DEFAULT_BUDGET_MS == settings.blunder_budget_ms
    assert settings.client_json() == {"selectedPiecePercent": 110, "confettiMs": 1800, "captureAnimationMs": 260, "yourGamesRefreshMs": 60000, "computerRetryLimit": 3,
                                      "computerRetryDelayMs": 5000, "joinPollMs": 3000}


def test_an_override_file_through_the_env_var(tmp_path) -> None:
    override = tmp_path / "easy.yaml"
    override.write_text("computer:\n  levels:\n    beginner:\n      random_move_chance: 0.6\n      depth: null\n"
                        "rate_limits:\n  hint: 50\n"
                        "rooms:\n  claim_win_away_hours: 2\n"
                        "client:\n  join_poll_seconds: 2\n", encoding="utf-8")
    settings = load_gameplay(env={gameplay.ENV_VAR: str(override)})
    assert settings.source == str(override)
    beginner = settings.levels["beginner"]
    assert (beginner.random_move_chance, beginner.depth, beginner.skill) == (0.6, None, 0), "unnamed keys keep defaults"
    assert (settings.hint_per_minute, settings.abandon_after) == (50, 7200.0)
    assert settings.client_json()["joinPollMs"] == 2000
    assert settings.levels["club"] == DEFAULT_GAMEPLAY.levels["club"]


@pytest.mark.parametrize(("text", "named"), [
    ("computer:\n  levels:\n    beginner:\n      skill: 25\n", "computer.levels.beginner.skill must be an integer from 0 to 20"),
    ("computer:\n  levels:\n    beginner:\n      random_move_chance: 1.5\n", "computer.levels.beginner.random_move_chance"),
    ("computer:\n  levels:\n    grandmaster:\n      skill: 5\n", "unknown key computer.levels.grandmaster"),
    ("engine:\n  queue_cap: true\n", "engine.queue_cap must be an integer"),
    ("engine:\n  queue_cap: 8\n  hint_refusal_queue: 9\n", "engine.hint_refusal_queue must not be above engine.queue_cap"),
    ("rate_limits:\n  hint: '20'\n", "rate_limits.hint must be an integer"),
    ("rooms: 24\n", "rooms must be a mapping"),
    ("client:\n  capture_animtion_ms: 100\n", "unknown key client.capture_animtion_ms"),
    ("engine: [unclosed\n", "is not valid YAML"),
])
def test_a_bad_value_is_rejected_with_the_key_named(tmp_path, text, named) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(text, encoding="utf-8")
    with pytest.raises(GameplayError) as refused:
        load_gameplay(bad)
    assert named in str(refused.value)
    assert str(bad) in str(refused.value), "the message names the file"


def test_the_endgames_section_is_validated_and_typed(tmp_path) -> None:
    """P2 U6: endgames.* keys, their fallbacks in justchess.endgames, and the queue_cap cross-check."""
    from justchess import endgames

    defaults = DEFAULT_GAMEPLAY.endgames
    assert (defaults.defender_skill, defaults.defender_think, defaults.hold_moves, defaults.max_plies,
            defaults.play_per_minute, defaults.refusal_queue, defaults.wait_limit) == (20, 1.0, 30, 300, 30, 16, 30.0)
    assert (endgames.DEFAULT_HOLD_MOVES, endgames.DEFAULT_MAX_PLIES) == (defaults.hold_moves, defaults.max_plies)
    tuned = gameplay.from_mapping({"endgames": {"hold_moves": 10, "wait_limit_seconds": 2.5}})
    assert (tuned.endgames.hold_moves, tuned.endgames.wait_limit, tuned.endgames.max_plies) == (10, 2.5, 300)
    for text, named in (("endgames:\n  defender_skill: 21\n", "endgames.defender_skill must be an integer from 0 to 20"),
                        ("endgames:\n  wait_limit_seconds: 0.5\n", "endgames.wait_limit_seconds must be a number"),
                        ("endgames:\n  refusal_queue: 40\n", "endgames.refusal_queue must not be above engine.queue_cap"),
                        ("endgames:\n  depth: 3\n", "unknown key endgames.depth")):
        bad = tmp_path / "bad.yaml"
        bad.write_text(text, encoding="utf-8")
        with pytest.raises(GameplayError, match=re.escape(named)):
            load_gameplay(bad)


def test_a_missing_file_falls_back_to_the_defaults_and_says_so(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setattr(gameplay, "DEFAULT_FILE", tmp_path / "gameplay.yaml")
    with caplog.at_level(logging.WARNING, logger="justchess.gameplay"):
        settings = load_gameplay(env={})
    assert settings is DEFAULT_GAMEPLAY and settings.source == gameplay.BUILT_IN
    assert "using the built-in defaults" in caplog.text
    with pytest.raises(GameplayError, match="does not exist"):
        load_gameplay(env={gameplay.ENV_VAR: str(tmp_path / "typo.yaml")})  # a file that was asked for must exist


def test_the_app_uses_the_loaded_settings_and_serves_only_the_client_keys(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    override = tmp_path / "app.yaml"
    override.write_text("rate_limits:\n  join_request: 7\nclient:\n  computer_retry_limit: 5\n", encoding="utf-8")
    monkeypatch.setenv(gameplay.ENV_VAR, str(override))
    monkeypatch.setenv("JUSTCHESS_DB", str(tmp_path / "app.sqlite3"))
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    with TestClient(create_app(engine_dir=tmp_path / "engines")) as client:
        assert client.app.state.services.join_limiter.limit == 7
        assert client.app.state.services.request_addresses.limit == DEFAULT_GAMEPLAY.address_book_cap
        shell = client.get("/").text
    found = re.search(r'<script type="application/json" id="gameplay-config">(.*?)</script>', shell)
    assert found, "the shell carries the page's gameplay settings"
    assert json.loads(found.group(1)) == {**DEFAULT_GAMEPLAY.client_json(), "computerRetryLimit": 5}

    monkeypatch.setenv(gameplay.ENV_VAR, str(tmp_path / "missing.yaml"))
    with pytest.raises(GameplayError):
        create_app(engine_dir=tmp_path / "engines")  # a bad setting stops the app before it serves anything
