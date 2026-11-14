"""A fake UCI engine for the U4 tests: just enough UCI for python-chess's ``popen_uci`` and ``play``.

Run as ``python tests/fakes/fake_uci.py [flags]``. It announces the options the
Engine sets (Threads, Hash, Skill Level), answers ``isready``, follows
``position startpos|fen ... moves ...`` with python-chess, and answers ``go`` with
the first legal move in UCI order (deterministic), after an optional delay.

Flags:

- ``--delay S``        wait S seconds before each ``bestmove`` (a ``stop`` answers at once)
- ``--crash-on-go N``  exit with status 1 when the Nth ``go`` arrives (1-based)
- ``--hang``           never answer ``go`` (and ignore ``stop``)
- ``--illegal``        answer ``bestmove e2e5`` whatever the position (illegal in every game)
- ``--fail-open``      exit with status 1 before ``uciok``
- ``--log FILE``       append every received line to FILE (tests read the order of commands)

It reads stdin on the main thread and answers ``go`` from a timer thread, so a
``stop`` can cut a delay short, like a real engine.
"""

from __future__ import annotations

import argparse
import sys
import threading

import chess


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--crash-on-go", type=int, default=0)
    parser.add_argument("--hang", action="store_true")
    parser.add_argument("--illegal", action="store_true")
    parser.add_argument("--fail-open", action="store_true")
    parser.add_argument("--log", default=None)
    return parser.parse_args(argv)


class FakeEngine:
    """The engine state: the current board, the pending search and the go counter."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.board = chess.Board()
        self.lock = threading.Lock()
        self.pending: threading.Event | None = None
        self.goes = 0

    def say(self, line: str) -> None:
        with self.lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def log(self, line: str) -> None:
        if self.args.log:
            with open(self.args.log, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def best_move(self) -> str:
        if self.args.illegal:
            return "e2e5"
        moves = sorted(move.uci() for move in self.board.legal_moves)
        return moves[0] if moves else "(none)"

    def position(self, tokens: list[str]) -> None:
        if tokens[:1] == ["startpos"]:
            board, rest = chess.Board(), tokens[1:]
        elif tokens[:1] == ["fen"]:
            fen_end = tokens.index("moves") if "moves" in tokens else len(tokens)
            board, rest = chess.Board(" ".join(tokens[1:fen_end])), tokens[fen_end:]
        else:
            return
        if rest[:1] == ["moves"]:
            for uci in rest[1:]:
                board.push_uci(uci)
        self.board = board

    def go(self) -> None:
        self.goes += 1
        if self.args.crash_on_go and self.goes == self.args.crash_on_go:
            self.log("crash")
            sys.stdout.flush()
            raise SystemExit(1)
        if self.args.hang:
            return
        answer = self.best_move()
        stopped = threading.Event()
        self.pending = stopped

        def finish() -> None:
            stopped.wait(self.args.delay)
            if self.pending is stopped:
                self.pending = None
            self.log(f"bestmove {answer}")
            self.say(f"bestmove {answer}")

        threading.Thread(target=finish, daemon=True).start()

    def stop(self) -> None:
        if self.pending is not None and not self.args.hang:
            self.pending.set()

    def handle(self, line: str) -> bool:
        """Handle one command; return False on ``quit``."""
        tokens = line.split()
        if not tokens:
            return True
        command = tokens[0]
        if command == "uci":
            if self.args.fail_open:
                raise SystemExit(1)
            self.say("id name FakeUCI")
            self.say("id author JustChess tests")
            self.say("option name Threads type spin default 1 min 1 max 512")
            self.say("option name Hash type spin default 16 min 1 max 33554432")
            self.say("option name Skill Level type spin default 20 min 0 max 20")
            self.say("uciok")
        elif command == "isready":
            self.say("readyok")
        elif command == "position":
            self.position(tokens[1:])
        elif command == "go":
            self.go()
        elif command == "stop":
            self.stop()
        elif command == "quit":
            return False
        return True


def main(argv: list[str] | None = None) -> int:
    engine = FakeEngine(_parse(sys.argv[1:] if argv is None else argv))
    for raw in sys.stdin:
        line = raw.strip()
        engine.log(line)
        if not engine.handle(line):
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
