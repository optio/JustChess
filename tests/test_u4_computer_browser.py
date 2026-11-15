"""P2 U4 a short game against the computer in headless Chromium (FR6.1-FR6.8, BR8.1-BR8.3).

Reuses the CDP harness of ``tests/test_game_screen.py`` (``browser``, ``Page``)
with its own server: the same Uvicorn subprocess on a temporary database, but
with Stockfish discovery patched and the fake UCI engine injected through
``create_app(engine_factory=...)`` (each reply takes 0.8 s, so the thinking
status can be seen). Skipped, with the reason, when Chromium is missing.

From the lobby's "Play the computer" panel the player picks White and
Beginner and presses Play, plays e4 (the blunder check runs first, as for any
move), sees "Computer is thinking…" and then the reply, takes back, asks for a
hint and sees its arrow, resigns through the in-page confirm, and sees the
result card with "Play again", no share controls and the level's score line.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests.test_accessibility_browser import SMALL_TARGETS
from tests.test_game_screen import PIECE_ON, ROOT, STATUS, Cdp, Page, _free_port, _wait_http, browser  # noqa: F401

VISIBLE = "!document.querySelector('[data-testid={testid}]').hidden"
TEXT = "(document.querySelector('[data-testid={testid}]')?.textContent || '')"
SERVER = (
    "import sys, uvicorn, stockfish_install; from pathlib import Path; "
    "from justchess.api import create_app; from justchess.engine import Engine; "
    "from tests.fakes.engines import NeverRandom, fake_opener; "
    "stockfish_install.ensure_stockfish = lambda _d, _e: stockfish_install.EngineResult(path=Path('fake'), source='env'); "
    "app = create_app(db_path=sys.argv[1], engine_dir=sys.argv[2], move_chooser=NeverRandom(), "
    "engine_factory=lambda: Engine(fake_opener(['--delay', '0.8']))); "
    "uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[3]), log_level='warning')"
)


@pytest.fixture
def computer_server(tmp_path):
    port = _free_port()
    env = {**os.environ, "STOCKFISH_AUTO_INSTALL": "0", "JUSTCHESS_DB": str(tmp_path / "computer.sqlite3")}
    for name in ("JUSTCHESS_ORIGIN", "JUSTCHESS_LESSONS_DIR", "JUSTCHESS_VAPID_PRIVATE_KEY", "JUSTCHESS_VAPID_KEY_FILE"):
        env.pop(name, None)
    server = subprocess.Popen([sys.executable, "-c", SERVER, str(tmp_path / "computer.sqlite3"), str(tmp_path / "engines"),
                               str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        _wait_http(f"http://127.0.0.1:{port}/", timeout=20)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def test_a_short_game_against_the_computer(computer_server: str, browser: Cdp) -> None:
    page = Page(browser, "player (phone 390 px)", viewport=(390, 844, True))  # NFR6 touch targets are checked at phone width
    page.go(computer_server + "/")
    page.wait("!!document.querySelector('[data-testid=computer-panel]')", what="the Play the computer panel")
    page.wait("!document.querySelector('[data-testid=computer-play]').disabled", what="Play enabled once the engine is up")
    assert page.js(SMALL_TARGETS) == [], "the panel's radios and Play are at least 44 x 44 px (NFR6)"
    assert page.js("document.querySelector('[data-testid=computer-colour-random]').checked"), "Random by default"
    assert page.js("document.querySelector('[data-testid=computer-level-casual]').checked"), "Casual by default"
    page.click("computer-colour-white")
    page.click("computer-level-beginner")
    page.click("computer-play")

    page.wait("/^\\/r\\/[A-Z0-9]{6}$/.test(location.pathname)", what="the room address")
    page.wait(f"{STATUS} === 'Your move'", what="the player's first move as White")
    assert page.js(TEXT.format(testid="players")) == "You play White · Computer · Beginner plays Black"
    assert page.js("document.getElementById('share').hidden"), "no invite against the computer"
    assert "token" not in page.js("location.href").lower()
    assert page.js(SMALL_TARGETS) == [], "every control of the computer game is at least 44 x 44 px (NFR6)"

    page.move("e2e4")
    page.wait(f"{STATUS} === 'Computer is thinking…'", what="the thinking status")
    page.wait(f"{STATUS} === 'Your move' && {PIECE_ON.format(square='a5')} === 'p'", what="the computer's reply a5")

    page.wait("!document.querySelector('[data-testid=computer-takeback]').disabled", what="Take back enabled")
    page.click("computer-takeback")
    page.wait(f"{PIECE_ON.format(square='e2')} === 'P' && {PIECE_ON.format(square='a7')} === 'p'", what="both moves taken back")

    page.wait("!document.querySelector('[data-testid=computer-hint]').disabled", what="Hint enabled")
    page.click("computer-hint")
    page.wait("document.querySelectorAll('[data-testid=hint-arrow] g').length === 1", what="the hint arrow")
    assert page.js(TEXT.format(testid="status-flash")).startswith("Hint: ")

    page.click("computer-resign")
    page.wait(VISIBLE.format(testid="resign-confirm"), what="the resign confirm")
    page.click("resign-confirm-yes")
    page.wait(VISIBLE.format(testid="overlay"), timeout=20, what="the result card")
    assert page.js(TEXT.format(testid="overlay-title")) == "You lost"
    assert page.js(VISIBLE.format(testid="play-again")), "Play again on the result card"
    assert page.js("document.querySelector('[data-testid=share-result]').hidden"), "no share controls"
    assert page.js(TEXT.format(testid="score")) == "This level: You 0 · Computer 1 · Draws 0"
    assert page.js("document.querySelectorAll('[data-testid=hint-arrow] g').length") == 0, "the arrow left with the game"
    assert page.problems() == [], f"the page logged errors: {page.problems()}"
