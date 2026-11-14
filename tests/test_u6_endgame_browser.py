"""P2 U6 endgame trainer in headless Chromium (FR8.1, FR8.2): from the hub's Endgames tab to a passed position.

Reuses the CDP harness of ``tests/test_game_screen.py`` (``browser``, ``Page``)
with its own Uvicorn: Stockfish discovery is patched and the U4 fake UCI engine
is injected through ``create_app(engine_factory=...)`` (each reply takes 0.6 s,
so "Computer is thinking…" can be seen), and ``endgames_dir`` is a one-position
folder. The fake answers with the first legal move in UCI order, so the line is
known: 1.Qh1+ Kb8 2.Qh8#. Skipped, with the reason, when Chromium is missing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import chess
import pytest

from tests.test_game_screen import PIECE_ON, ROOT, Cdp, Page, _free_port, _wait_http, browser  # noqa: F401

POSITION_ID = "queen-browser-test"
FEN = "k7/8/1K6/8/8/8/8/2Q5 w - - 0 1"
LINE = ["c1h1", "a8b8", "h1h8"]
TEXT = "(document.querySelector('[data-testid={testid}]')?.textContent || '')"
PHASE = "document.querySelector('[data-testid=endgame]')?.dataset.phase"
SERVER = (
    "import sys, uvicorn, stockfish_install; from pathlib import Path; "
    "from justchess.api import create_app; from justchess.engine import Engine; "
    "from tests.fakes.engines import fake_opener; "
    "stockfish_install.ensure_stockfish = lambda _d, _e: stockfish_install.EngineResult(path=Path('fake'), source='env'); "
    "app = create_app(db_path=sys.argv[1], engine_dir=sys.argv[2], endgames_dir=sys.argv[4], "
    "engine_factory=lambda: Engine(fake_opener(['--delay', '0.6']))); "
    "uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[3]), log_level='warning')"
)


def write_endgames(folder: Path) -> Path:
    board = chess.Board(FEN)
    for index, uci in enumerate(LINE):
        if index % 2:  # the fake defender's reply: the first legal move in UCI order
            assert uci == sorted(move.uci() for move in board.legal_moves)[0]
        board.push_uci(uci)
    assert board.is_checkmate(), "the fixture line ends in mate"
    folder.mkdir(parents=True)
    (folder / "queen-mate.yaml").write_text(
        f"positions:\n  - id: {POSITION_ID}\n    title: Corner mate\n    fen: {FEN}\n    goal: mate\n"
        "    hint: Check from the long diagonal, then mate on the back rank.\n", encoding="utf-8")
    return folder


@pytest.fixture
def endgame_server(tmp_path: Path):
    port = _free_port()
    folder = write_endgames(tmp_path / "endgames")
    env = {**os.environ, "STOCKFISH_AUTO_INSTALL": "0", "JUSTCHESS_DB": str(tmp_path / "u6.sqlite3")}
    for name in ("JUSTCHESS_ORIGIN", "JUSTCHESS_LESSONS_DIR", "JUSTCHESS_VAPID_PRIVATE_KEY", "JUSTCHESS_VAPID_KEY_FILE"):
        env.pop(name, None)
    server = subprocess.Popen([sys.executable, "-c", SERVER, str(tmp_path / "u6.sqlite3"), str(tmp_path / "engines"),
                               str(port), str(folder)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        _wait_http(f"http://127.0.0.1:{port}/", timeout=20)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def test_a_queen_mate_is_played_against_the_computer_and_counted(endgame_server: str, browser: Cdp) -> None:
    page = Page(browser, "endgame player (phone 390 px)", viewport=(390, 844, True))
    page.go(endgame_server + "/learn")
    page.wait("!!document.querySelector('[data-testid=hub-tab-endgames]')", what="the Endgames tab")
    assert page.js("[...document.querySelectorAll('[role=tab]')].map((t) => t.dataset.tab)") == \
        ["openings", "traps", "endgames", "tactics", "defence"]
    page.click("hub-tab-endgames")
    page.wait(f"!!document.querySelector('[data-testid=hub-action-{POSITION_ID}]')", what="the endgame row")
    page.wait(f"!document.querySelector('[data-testid=hub-action-{POSITION_ID}]').disabled", what="Play enabled")
    assert page.js(TEXT.format(testid="hub-count-endgames")) == "0/1"
    page.click(f"hub-action-{POSITION_ID}")

    page.wait(f"location.pathname === '/learn/endgames/{POSITION_ID}'", what="the endgame address")
    page.wait(f"{TEXT.format(testid='endgame-status')} === 'Mate with the queen. Goal: checkmate. Position 1 of 1.'",
              what="the goal status")
    page.wait(f"{PHASE} === 'playing'", what="the player's turn")
    page.click("endgame-hint-button")
    assert page.js(TEXT.format(testid="endgame-hint")) == "Check from the long diagonal, then mate on the back rank."

    page.move("c1h1")
    page.wait(f"{TEXT.format(testid='endgame-message')} === 'Computer is thinking…'", what="the thinking message")
    page.wait(f"{PHASE} === 'playing' && {PIECE_ON.format(square='b8')} === 'k'", what="the defender's reply Kb8")
    page.move("h1h8")
    page.wait(f"{PHASE} === 'passed' && {TEXT.format(testid='endgame-message')} === 'Done! Mate in 2 moves.'",
              what="the passed position")
    assert page.js("!document.querySelector('[data-testid=endgame-next]').hidden"), "Next position is offered"
    assert page.js("document.documentElement.scrollWidth") <= 390, "no horizontal scroll on the phone"

    page.click("endgame-back")
    page.wait(f"location.pathname === '/learn/endgames' && !!document.querySelector('[data-testid=hub-done-{POSITION_ID}]')",
              what="the hub's Endgames tab")
    page.wait(f"!document.querySelector('[data-testid=hub-done-{POSITION_ID}]').hidden", what="Done on the row")
    assert page.js(TEXT.format(testid="hub-count-endgames")) == "1/1"
    assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"
