"""Lessons: opening lessons loaded from files (U6, BR1.1-BR1.4, BR2.3).

Every ``.yaml``, ``.yml`` or ``.json`` file in the lessons folder is one lesson;
the file name without its extension is the lesson id. Adding a file adds a
lesson with no code change (FR7.6).

Safe file handling (functional design review):

* YAML is read only with ``yaml.safe_load`` and JSON with ``json.loads``.
* Files over 64 KB are skipped ("file too large"). Symlinks and anything that
  is not a regular file are skipped. Files are opened with ``O_NOFOLLOW`` where
  the platform has it, so a file swapped for a symlink after the listing is
  still refused.
* Files are only ever listed, never opened by a name taken from a request. The
  id from a request is checked against ``LESSON_ID`` and looked up in the
  in-memory catalog; it is never joined into a path.
* A missing or unreadable folder gives an empty catalog and one warning, not a
  crash.

Validation (BR1.2) skips a bad file and records ``{file, reason}``; each
problem is logged at warning level with the file name and the reason. Valid
files still load. Each valid lesson is expanded into steps (BR1.3) with
python-chess, so the browser needs no chess engine for the taught line.

``LessonStore.catalog()`` compares the folder's file names, sizes and
modification times (the ``dir_stamp``) with the last scan and rescans when they
differ. A rescan builds a whole new ``LessonCatalog`` and swaps it in under a
lock, so readers never see half a catalog.

``position_move`` is the stateless free-play move (BR2.3). It keeps no history,
so it cannot report repetition draws.

Lesson kinds (P2 U5, BR1.1, BR1.2): a lesson file may carry ``kind`` with one
of ``opening``, ``trap`` or ``defence``. A file without it is an opening, so
older files keep working; any other value skips the file like any other rule
break. The kind is part of the lesson and of its summary, and
``LessonCatalog.summaries(kind)`` lists one kind only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import yaml

logger = logging.getLogger("justchess.lessons")

LESSON_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
ECO_PATTERN = re.compile(r"^[A-E][0-9]{2}$")
UCI_PATTERN = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
EXTENSIONS = (".yaml", ".yml", ".json")
MAX_FILE_BYTES = 64 * 1024
MAX_MOVES = 60
NAME_MAX = 80
NOTE_MAX = 280
START_POS = "startpos"
SIDES = ("white", "black")
KINDS = ("opening", "trap", "defence")
DEFAULT_KIND = "opening"
KNOWN_FIELDS = frozenset({"name", "kind", "aliases", "eco", "side", "start", "moves", "objectives"})
MOVE_FIELDS = frozenset({"san", "uci", "note", "alternatives"})
ENV_LESSONS_DIR = "JUSTCHESS_LESSONS_DIR"

ILLEGAL_MOVE = "Illegal move"
INVALID_POSITION = "Invalid position"


class LessonError(ValueError):
    """A lesson file broke a rule; the message is the reason recorded for it."""


class PositionError(ValueError):
    """A free-play request named an invalid position or an illegal move."""


@dataclass(frozen=True)
class Problem:
    """One skipped file and why."""

    file: str
    reason: str


@dataclass(frozen=True)
class LessonCatalog:
    """The loaded set: valid lessons by id, the problems found, and the folder stamp."""

    lessons: dict[str, dict[str, Any]] = field(default_factory=dict)
    problems: tuple[Problem, ...] = ()
    loaded_at: float = 0.0
    dir_stamp: str = ""

    def summaries(self, kind: str | None = None) -> list[dict[str, Any]]:
        """BR2.1: the list shape, sorted by name (then id). No problems, no paths.

        P2 U5 BR1.2: with ``kind`` only lessons of that kind are listed; the
        caller checks the value first (``is_kind``).
        """
        chosen = [lesson for lesson in self.lessons.values() if kind is None or lesson["kind"] == kind]
        ordered = sorted(chosen, key=lambda lesson: (lesson["name"].casefold(), lesson["id"]))
        return [{"id": lesson["id"], "name": lesson["name"], "kind": lesson["kind"], "aliases": list(lesson["aliases"]),
                 "eco": lesson["eco"], "side": lesson["side"], "moves": len(lesson["steps"])}
                for lesson in ordered]

    def counts_by_kind(self) -> dict[str, int]:
        """How many valid lessons there are of each kind (every kind present, zero included)."""
        counts = dict.fromkeys(KINDS, 0)
        for lesson in self.lessons.values():
            counts[lesson["kind"]] += 1
        return counts

    def get(self, lesson_id: str) -> dict[str, Any] | None:
        """BR2.2: the lesson for a well-formed id, else None. The id never reaches the file system."""
        if not isinstance(lesson_id, str) or not LESSON_ID.fullmatch(lesson_id):
            return None
        return self.lessons.get(lesson_id)


# --- folder ---------------------------------------------------------------------

def default_lessons_dir(root: Path) -> Path:
    """``JUSTCHESS_LESSONS_DIR`` when set, else ``<root>/lessons``."""
    configured = os.environ.get(ENV_LESSONS_DIR, "").strip()
    return Path(configured) if configured else root / "lessons"


def _candidates(directory: Path) -> list[os.DirEntry]:
    """Entries with a lesson extension, sorted by name. Raises OSError when the folder can't be read."""
    with os.scandir(directory) as entries:
        found = [entry for entry in entries if entry.name.lower().endswith(EXTENSIONS)]
    return sorted(found, key=lambda entry: entry.name)


def dir_stamp(directory: Path) -> str:
    """File names, sizes and modification times of the lesson files; changes whenever a lesson file does."""
    try:
        parts = []
        for entry in _candidates(directory):
            try:
                info = entry.stat(follow_symlinks=False)
                parts.append(f"{entry.name}:{info.st_size}:{info.st_mtime_ns}:{stat.S_IFMT(info.st_mode)}")
            except OSError:
                parts.append(f"{entry.name}:gone")
        return "|".join(parts) or "empty"
    except FileNotFoundError:
        return "missing"
    except OSError as error:
        return f"unreadable:{type(error).__name__}"


def _read_file(entry: os.DirEntry) -> bytes:
    """Read a regular lesson file of at most MAX_FILE_BYTES; raise LessonError otherwise."""
    if entry.is_symlink():
        raise LessonError("symlinks are not read")
    if not entry.is_file(follow_symlinks=False):
        raise LessonError("not a regular file")
    if entry.stat(follow_symlinks=False).st_size > MAX_FILE_BYTES:
        raise LessonError("file too large")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(entry.path, flags)
    except OSError as error:
        raise LessonError(f"could not open the file ({error.strerror or type(error).__name__})") from None
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise LessonError("not a regular file")
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise LessonError("file too large")
    return data


def _parse(name: str, data: bytes) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise LessonError("the file is not UTF-8 text") from None
    try:
        if name.lower().endswith(".json"):
            return json.loads(text)
        return yaml.safe_load(text)
    except json.JSONDecodeError as error:
        raise LessonError(f"invalid JSON (line {error.lineno}: {error.msg})") from None
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f"line {mark.line + 1}: " if mark is not None else ""
        raise LessonError(f"invalid YAML ({where}{getattr(error, 'problem', None) or 'could not parse'})") from None


# --- validation (BR1.2) ---------------------------------------------------------

def _text(value: Any, what: str, limit: int, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LessonError(f"{what} must be non-empty text")
    value = value.strip()
    if len(value) > limit:
        raise LessonError(f"{what} is longer than {limit} characters")
    return value


def _text_list(value: Any, what: str, limit: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise LessonError(f"{what} must be a list of text")
    return [_text(item, f"{what} item {index + 1}", limit) for index, item in enumerate(value)]


def _start_board(start: Any) -> tuple[str, chess.Board]:
    if start is None or start == START_POS:
        return START_POS, chess.Board()
    if not isinstance(start, str):
        raise LessonError("start must be 'startpos' or a FEN")
    try:
        board = chess.Board(start.strip())
    except ValueError:
        raise LessonError("start is not a valid FEN") from None
    if not board.is_valid():
        raise LessonError("start is not a legal position")
    return start.strip(), board


def is_kind(value: Any) -> bool:
    """True for one of the lesson kinds (BR1.1)."""
    return isinstance(value, str) and value in KINDS


def _kind(value: Any) -> str:
    """BR1.1: a missing kind is an opening; anything outside KINDS breaks the rule."""
    if value is None:
        return DEFAULT_KIND
    if not is_kind(value):
        raise LessonError("kind must be 'opening', 'trap' or 'defence'")
    return value


def _check_fields(data: dict, known: frozenset[str], where: str) -> None:
    unknown = sorted(str(key) for key in data if key not in known)
    if unknown:
        raise LessonError(f"{where}unknown field '{unknown[0]}'")


def validate(lesson_id: str, data: Any) -> dict[str, Any]:
    """Check one parsed file and return the lesson with its expanded steps; raise LessonError."""
    if not LESSON_ID.fullmatch(lesson_id):
        raise LessonError("the file name is not a valid lesson id (lowercase letters, digits and dashes, at most 48)")
    if not isinstance(data, dict):
        raise LessonError("the file must hold a mapping of fields")
    _check_fields(data, KNOWN_FIELDS, "")
    if "name" not in data:
        raise LessonError("missing required field 'name'")
    if "side" not in data:
        raise LessonError("missing required field 'side'")
    if "moves" not in data:
        raise LessonError("missing required field 'moves'")
    name = _text(data["name"], "name", NAME_MAX)
    kind = _kind(data.get("kind"))
    side = data["side"]
    if side not in SIDES:
        raise LessonError("side must be 'white' or 'black'")
    eco = data.get("eco")
    if eco is not None and (not isinstance(eco, str) or not ECO_PATTERN.fullmatch(eco)):
        raise LessonError("eco must look like C53 (a letter A-E and two digits)")
    start, board = _start_board(data.get("start"))
    moves = data["moves"]
    if not isinstance(moves, list) or not moves:
        raise LessonError("moves must be a list with at least 1 move")
    if len(moves) > MAX_MOVES:
        raise LessonError(f"moves has more than {MAX_MOVES} moves")
    return {
        "id": lesson_id,
        "name": name,
        "kind": kind,
        "aliases": _text_list(data.get("aliases"), "aliases", NAME_MAX),
        "eco": eco,
        "side": side,
        "start": start,
        "objectives": _text_list(data.get("objectives"), "objectives", NOTE_MAX),
        "steps": expand(board, moves),
    }


# --- expansion (BR1.3) ----------------------------------------------------------

def _parse_san(board: chess.Board, san: str, where: str) -> chess.Move:
    try:
        return board.parse_san(san)
    except ValueError:
        raise LessonError(f"{where}: '{san}' is not legal in this position") from None


def _alternatives(board: chess.Board, value: Any, main: chess.Move, where: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise LessonError(f"{where}: alternatives must be a list")
    found = []
    for index, item in enumerate(value):
        label = f"{where} alternative {index + 1}"
        if not isinstance(item, dict):
            raise LessonError(f"{label} must have san and note")
        _check_fields(item, frozenset({"san", "note"}), f"{label}: ")
        san = _text(item.get("san"), f"{label} san", 16)
        move = _parse_san(board, san, label)
        if move == main:
            raise LessonError(f"{label}: '{san}' is the taught move itself")
        found.append({"san": board.san(move), "note": _text(item.get("note"), f"{label} note", NOTE_MAX)})
    return found


def _move_of(board: chess.Board, item: Any, where: str) -> chess.Move:
    if not isinstance(item, dict):
        raise LessonError(f"{where} must have san and note")
    _check_fields(item, MOVE_FIELDS, f"{where}: ")
    if "san" not in item:
        raise LessonError(f"{where}: missing required field 'san'")
    if "note" not in item:
        raise LessonError(f"{where}: missing required field 'note'")
    san = _text(item["san"], f"{where} san", 16)
    move = _parse_san(board, san, where)
    uci = item.get("uci")
    if uci is not None:
        if not isinstance(uci, str) or not UCI_PATTERN.fullmatch(uci):
            raise LessonError(f"{where}: uci '{uci}' is not a UCI move")
        if chess.Move.from_uci(uci) != move:
            raise LessonError(f"{where}: SAN '{san}' and UCI '{uci}' disagree (the SAN is {move.uci()})")
    return move


def expand(board: chess.Board, moves: list) -> list[dict[str, Any]]:
    """Replay ``moves`` from ``board`` and return one step per ply; raise LessonError on any bad move."""
    board = board.copy(stack=False)
    steps = []
    for ply, item in enumerate(moves):
        where = f"move {ply + 1}"
        move = _move_of(board, item, where)
        steps.append({
            "ply": ply,
            "side": "white" if board.turn == chess.WHITE else "black",
            "san": board.san(move),
            "uci": move.uci(),
            "note": _text(item["note"], f"{where} note", NOTE_MAX),
            "fenBefore": board.fen(),
            "legalBefore": sorted(legal.uci() for legal in board.legal_moves),
            "alternatives": _alternatives(board, item.get("alternatives"), move, where),
        })
        board.push(move)
        steps[-1]["fenAfter"] = board.fen()
    return steps


# --- catalog (BR1.1) ------------------------------------------------------------

def _record(problems: list[Problem], name: str, reason: str) -> None:
    problems.append(Problem(name, reason))
    logger.warning("Skipped lesson file %s: %s", name, reason)


def load_catalog(directory: Path, stamp: str | None = None, clock: Callable[[], float] = time.time) -> LessonCatalog:
    """Scan ``directory`` and build a new catalog. Never raises for a bad file or folder."""
    stamp = dir_stamp(directory) if stamp is None else stamp
    lessons: dict[str, dict[str, Any]] = {}
    origin: dict[str, str] = {}
    problems: list[Problem] = []
    try:
        entries = _candidates(directory)
    except FileNotFoundError:
        logger.warning("The lessons folder %s does not exist; no lessons are loaded", directory)
        return LessonCatalog({}, (), clock(), stamp)
    except OSError as error:
        logger.warning("The lessons folder %s could not be read (%s); no lessons are loaded", directory, type(error).__name__)
        return LessonCatalog({}, (), clock(), stamp)
    for entry in entries:
        lesson_id = entry.name.rsplit(".", 1)[0]
        try:
            if lesson_id in origin:
                raise LessonError(f"duplicate id '{lesson_id}' (already loaded from {origin[lesson_id]})")
            lesson = validate(lesson_id, _parse(entry.name, _read_file(entry)))
        except LessonError as error:
            _record(problems, entry.name, str(error))
            continue
        except OSError as error:
            _record(problems, entry.name, f"could not read the file ({type(error).__name__})")
            continue
        lessons[lesson_id] = lesson
        origin[lesson_id] = entry.name
    logger.info("Loaded %d lesson(s) from %s, skipped %d", len(lessons), directory, len(problems))
    return LessonCatalog(lessons, tuple(problems), clock(), stamp)


class LessonStore:
    """Holds the current catalog and reloads it when the folder changes."""

    def __init__(self, directory: Path, clock: Callable[[], float] = time.time) -> None:
        self.directory = Path(directory)
        self._clock = clock
        self._lock = threading.Lock()
        self._catalog: LessonCatalog | None = None

    def catalog(self) -> LessonCatalog:
        """The catalog for the folder as it is now; rescans only when the stamp changed."""
        stamp = dir_stamp(self.directory)
        current = self._catalog
        if current is not None and current.dir_stamp == stamp:
            return current
        with self._lock:
            current = self._catalog
            if current is not None and current.dir_stamp == stamp:
                return current
            fresh = load_catalog(self.directory, stamp, self._clock)
            self._catalog = fresh
            return fresh


# --- free play (BR2.3) ----------------------------------------------------------

def _outcome(board: chess.Board) -> str | None:
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "insufficient_material"
    if board.is_seventyfive_moves():
        return "seventyfive_moves"
    if board.can_claim_fifty_moves():
        return "fifty_moves"
    return None


def position_move(fen: str, uci: str) -> dict[str, Any]:
    """Play ``uci`` in ``fen``; return the new position. Raise PositionError for a bad position or move."""
    if not isinstance(uci, str) or not UCI_PATTERN.fullmatch(uci):
        raise PositionError(ILLEGAL_MOVE)
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError):
        raise PositionError(INVALID_POSITION) from None
    if not board.is_valid():
        raise PositionError(INVALID_POSITION)
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise PositionError(ILLEGAL_MOVE)
    san = board.san(move)
    board.push(move)
    return {
        "fen": board.fen(),
        "san": san,
        "legalMoves": sorted(legal.uci() for legal in board.legal_moves),
        "check": board.is_check(),
        "outcome": _outcome(board),
    }
