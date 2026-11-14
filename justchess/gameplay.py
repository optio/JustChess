"""Gameplay settings from ``gameplay.yaml``: loaded once at start-up, validated, with built-in defaults.

    settings = load_gameplay()            # JUSTCHESS_GAMEPLAY_FILE, else gameplay.yaml at the project root
    settings.levels["club"].skill         # typed values, times in seconds
    settings.client_json()                # the page's keys, in milliseconds, for the app shell

Rules:

- The file is YAML. A key left out keeps its built-in default (``DEFAULTS``,
  identical to the shipped ``gameplay.yaml``); an unknown key, a wrong type or a
  value out of range raises ``GameplayError`` whose message names the file and
  the key (``computer.levels.beginner.skill must be an integer from 0 to 20
  (got 25)``), so a bad edit stops start-up instead of running with surprises.
- ``JUSTCHESS_GAMEPLAY_FILE`` names another file; a named file that does not
  exist is an error (it was asked for). When the default ``gameplay.yaml`` is
  missing, the built-in defaults are used and that is logged.
- Only gameplay tunables live here. Protocol and security limits (token sizes,
  body and message sizes, socket timeouts) stay in code.

The modules that use these values keep their own constants as fallbacks for
direct calls (tests and tools); the app passes the loaded values in.
"""

from __future__ import annotations

import copy
import logging
import math
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("justchess.gameplay")

ENV_VAR = "JUSTCHESS_GAMEPLAY_FILE"
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "gameplay.yaml"
LEVEL_IDS = ("beginner", "casual", "club", "strong", "maximum")
LEVEL_NAMES = {"beginner": "Beginner", "casual": "Casual", "club": "Club", "strong": "Strong", "maximum": "Maximum"}
BUILT_IN = "built-in defaults"


def _level(skill: int, depth: int | None, think: float, chance: float) -> dict:
    return {"skill": skill, "depth": depth, "think_seconds": think, "random_move_chance": chance}


# Must equal the shipped gameplay.yaml (tests/test_gameplay.py checks it).
DEFAULTS: dict = {
    "computer": {
        "levels": {
            "beginner": _level(0, 1, 0.05, 0.35),
            "casual": _level(2, 3, 0.1, 0.15),
            "club": _level(6, 6, 0.3, 0.05),
            "strong": _level(11, 10, 0.6, 0),
            "maximum": _level(16, None, 1.0, 0),
        },
        "hint": {"skill": 20, "think_seconds": 0.5},
    },
    "engine": {"queue_cap": 32, "hint_refusal_queue": 16, "overrun_grace_seconds": 5, "restarts": 1,
               "retry_backoff_seconds": 5},
    "rate_limits": {"computer_create": 10, "hint": 20, "computer_move": 30, "join_request": 5},
    "join_requests": {"lifetime_minutes": 10, "declined_block_minutes": 10, "address_book_cap": 10000},
    "rooms": {"claim_win_away_hours": 24, "idle_room_delete_days": 30},
    "blunder_check": {"time_budget_ms": 250},
    "client": {"capture_animation_ms": 260, "your_games_refresh_seconds": 60, "computer_retry_limit": 3,
               "computer_retry_delay_seconds": 5, "join_poll_seconds": 3},
    "endgames": {"defender_skill": 20, "defender_think_seconds": 1.0, "hold_moves": 30, "max_plies": 300,
                 "play_per_minute": 30, "refusal_queue": 16, "wait_limit_seconds": 30},
}


class GameplayError(ValueError):
    """The gameplay file cannot be used; the message names the file and the key."""


# --- validators ---------------------------------------------------------------

Check = Callable[[object], str | None]  # returns None when valid, else "must be ..."


def _integer(low: int, high: int) -> Check:
    def check(value: object) -> str | None:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            return f"must be an integer from {low} to {high}"
        return None
    return check


def _number(low: float, high: float) -> Check:
    def check(value: object) -> str | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not low <= value <= high:
            return f"must be a number from {low:g} to {high:g}"
        return None
    return check


def _optional(inner: Check, words: str) -> Check:
    def check(value: object) -> str | None:
        return None if value is None else (f"{inner(value)} {words}" if inner(value) else None)
    return check


_LEVEL_SPEC = {"skill": _integer(0, 20), "depth": _optional(_integer(1, 99), "or null for no limit"),
               "think_seconds": _number(0.01, 10), "random_move_chance": _number(0, 1)}

SPEC: dict = {
    "computer": {
        "levels": {level: dict(_LEVEL_SPEC) for level in LEVEL_IDS},
        "hint": {"skill": _integer(0, 20), "think_seconds": _number(0.05, 10)},
    },
    "engine": {"queue_cap": _integer(1, 1000), "hint_refusal_queue": _integer(0, 1000),
               "overrun_grace_seconds": _number(0.1, 60), "restarts": _integer(0, 10),
               "retry_backoff_seconds": _number(0, 600)},
    "rate_limits": {key: _integer(1, 10000) for key in ("computer_create", "hint", "computer_move", "join_request")},
    "join_requests": {"lifetime_minutes": _number(0.5, 1440), "declined_block_minutes": _number(0, 1440),
                      "address_book_cap": _integer(100, 1_000_000)},
    "rooms": {"claim_win_away_hours": _number(0.01, 8760), "idle_room_delete_days": _number(1, 3650)},
    "blunder_check": {"time_budget_ms": _integer(10, 10000)},
    "client": {"capture_animation_ms": _integer(0, 2000), "your_games_refresh_seconds": _number(10, 3600),
               "computer_retry_limit": _integer(0, 20), "computer_retry_delay_seconds": _number(1, 300),
               "join_poll_seconds": _number(1, 60)},
    "endgames": {"defender_skill": _integer(0, 20), "defender_think_seconds": _number(0.05, 10),
                 "hold_moves": _integer(1, 200), "max_plies": _integer(10, 1000), "play_per_minute": _integer(1, 1000),
                 "refusal_queue": _integer(0, 1000), "wait_limit_seconds": _number(1, 300)},
}


def _merge(spec: dict, defaults: dict, given: object, path: str, source: str) -> dict:
    """Validate ``given`` against ``spec`` and return ``defaults`` with it laid over them."""
    if given is None:
        return copy.deepcopy(defaults)
    if not isinstance(given, Mapping):
        raise GameplayError(f"{source}: {path or 'the file'} must be a mapping of keys to values")
    merged = copy.deepcopy(defaults)
    for key, value in given.items():
        where = f"{path}.{key}" if path else str(key)
        if key not in spec:
            raise GameplayError(f"{source}: unknown key {where}")
        rule = spec[key]
        if isinstance(rule, dict):
            merged[key] = _merge(rule, defaults[key], value, where, source)
            continue
        problem = rule(value)
        if problem:
            raise GameplayError(f"{source}: {where} {problem} (got {value!r})")
        merged[key] = value
    return merged


# --- typed settings -----------------------------------------------------------

@dataclass(frozen=True)
class Level:
    """One computer level: name, Stockfish skill, think time, optional depth limit, random-move chance."""

    id: str
    name: str
    skill: int
    think: float
    depth: int | None = None
    random_move_chance: float = 0.0


@dataclass(frozen=True)
class EndgameSettings:
    """P2 U6: the endgame trainer's defender, hold target, attempt cap, limits and wait (times in seconds)."""

    defender_skill: int = 20
    defender_think: float = 1.0
    hold_moves: int = 30
    max_plies: int = 300
    play_per_minute: int = 30
    refusal_queue: int = 16
    wait_limit: float = 30.0


@dataclass(frozen=True)
class Gameplay:
    """The loaded settings, times in seconds, plus where they came from."""

    levels: dict[str, Level]
    hint_skill: int
    hint_think: float
    queue_cap: int
    hint_queue_limit: int
    overrun_grace: float
    restarts: int
    retry_backoff: float
    create_per_minute: int
    hint_per_minute: int
    computer_move_per_minute: int
    join_requests_per_minute: int
    join_request_ttl: float
    decline_memory: float
    address_book_cap: int
    abandon_after: float
    idle_room_retention: float
    blunder_budget_ms: int
    client: dict[str, int] = field(default_factory=dict)
    endgames: EndgameSettings = field(default_factory=EndgameSettings)
    source: str = BUILT_IN

    def client_json(self) -> dict[str, int]:
        """The page's settings (milliseconds and counts), safe to put in the app shell."""
        return dict(self.client)


def _build(values: dict, source: str) -> Gameplay:
    engine, limits, requests = values["engine"], values["rate_limits"], values["join_requests"]
    if engine["hint_refusal_queue"] > engine["queue_cap"]:
        raise GameplayError(f"{source}: engine.hint_refusal_queue must not be above engine.queue_cap "
                            f"(got {engine['hint_refusal_queue']} > {engine['queue_cap']})")
    endgame = values["endgames"]
    if endgame["refusal_queue"] > engine["queue_cap"]:
        raise GameplayError(f"{source}: endgames.refusal_queue must not be above engine.queue_cap "
                            f"(got {endgame['refusal_queue']} > {engine['queue_cap']})")
    levels = {level: Level(level, LEVEL_NAMES[level], row["skill"], float(row["think_seconds"]), row["depth"],
                           float(row["random_move_chance"]))
              for level, row in values["computer"]["levels"].items()}
    client = values["client"]
    return Gameplay(
        levels=levels,
        hint_skill=values["computer"]["hint"]["skill"],
        hint_think=float(values["computer"]["hint"]["think_seconds"]),
        queue_cap=engine["queue_cap"],
        hint_queue_limit=engine["hint_refusal_queue"],
        overrun_grace=float(engine["overrun_grace_seconds"]),
        restarts=engine["restarts"],
        retry_backoff=float(engine["retry_backoff_seconds"]),
        create_per_minute=limits["computer_create"],
        hint_per_minute=limits["hint"],
        computer_move_per_minute=limits["computer_move"],
        join_requests_per_minute=limits["join_request"],
        join_request_ttl=requests["lifetime_minutes"] * 60.0,
        decline_memory=requests["declined_block_minutes"] * 60.0,
        address_book_cap=requests["address_book_cap"],
        abandon_after=values["rooms"]["claim_win_away_hours"] * 3600.0,
        idle_room_retention=values["rooms"]["idle_room_delete_days"] * 24 * 3600.0,
        blunder_budget_ms=values["blunder_check"]["time_budget_ms"],
        client={
            "captureAnimationMs": client["capture_animation_ms"],
            "yourGamesRefreshMs": round(client["your_games_refresh_seconds"] * 1000),
            "computerRetryLimit": client["computer_retry_limit"],
            "computerRetryDelayMs": round(client["computer_retry_delay_seconds"] * 1000),
            "joinPollMs": round(client["join_poll_seconds"] * 1000),
        },
        endgames=EndgameSettings(
            defender_skill=endgame["defender_skill"],
            defender_think=float(endgame["defender_think_seconds"]),
            hold_moves=endgame["hold_moves"],
            max_plies=endgame["max_plies"],
            play_per_minute=endgame["play_per_minute"],
            refusal_queue=endgame["refusal_queue"],
            wait_limit=float(endgame["wait_limit_seconds"]),
        ),
        source=source,
    )


def from_mapping(given: object, source: str = "gameplay settings") -> Gameplay:
    """Validate a parsed mapping (keys left out keep their defaults) and build the settings."""
    return _build(_merge(SPEC, DEFAULTS, given, "", source), source)


DEFAULT_GAMEPLAY = _build(copy.deepcopy(DEFAULTS), BUILT_IN)


def load_gameplay(path: Path | str | None = None, env: Mapping[str, str] | None = None) -> Gameplay:
    """Load the settings once: ``path``, else ``JUSTCHESS_GAMEPLAY_FILE``, else ``gameplay.yaml``.

    A missing default file falls back to the built-in defaults (logged); a file
    that was named and is missing, unreadable YAML or a bad value raises GameplayError.
    """
    env = os.environ if env is None else env
    named = path if path is not None else (env.get(ENV_VAR) or "").strip() or None
    target = Path(named).expanduser() if named else DEFAULT_FILE
    if not target.is_file():
        if named:
            raise GameplayError(f"{target}: the gameplay file asked for (argument or {ENV_VAR}) does not exist")
        logger.warning("No gameplay file at %s; using the built-in defaults", target)
        return DEFAULT_GAMEPLAY
    try:
        given = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise GameplayError(f"{target}: cannot be read ({exc})") from exc
    except yaml.YAMLError as exc:
        raise GameplayError(f"{target}: is not valid YAML ({exc})") from exc
    settings = from_mapping(given, str(target))
    logger.info("Gameplay settings loaded from %s", target)
    return settings
