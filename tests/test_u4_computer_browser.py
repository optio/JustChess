"""P2 U4 a short game against the computer in headless Chromium (FR6.1-FR6.8, BR8.1-BR8.3).

Reuses the CDP harness of ``tests/test_game_screen.py`` (``browser``, ``Page``)
with its own server: the same Uvicorn subprocess on a temporary database, but
with Stockfish discovery patched and the fake UCI engine injected through
``create_app(engine_factory=...)`` (each reply takes 0.8 s, so the thinking
status can be seen). Skipped, with the reason, when Chromium is missing.

Since 2026-11-15 the lobby has no "Play the computer" panel: the player starts
a game, presses "Play the computer" on the waiting screen and picks the level
in the difficulty dialog. The player then plays e4 (the blunder check is off),
sees "Computer is thinking…" and the reply, takes back, asks for a hint and
sees its arrow, resigns through the in-page confirm and sees the result card.
Switching sides with the computer and the friend takeover have their own runs.
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


def _start_against_computer(page: Page, server: str, level: str = "beginner") -> str:
    """Start a game, press "Play the computer" and pick ``level`` in the difficulty dialog."""
    page.go(server + "/")
    page.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    assert not page.js("!!document.querySelector('[data-testid=computer-panel]')"), "the lobby panel is gone"
    page.click("start-game")
    code = page.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    page.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="the waiting state")
    page.js("(() => { const s = document.querySelector('[data-testid=settings-blunderWarnings]'); if (s.checked) s.click(); return true; })()")
    assert page.js(TEXT.format(testid="pass-along-start")) == "Play pass-along"
    assert page.js(TEXT.format(testid="stand-in-start")) == "Play the computer"
    page.click("stand-in-start")
    page.wait("document.querySelector('[data-testid=level-dialog]').open", what="the difficulty dialog")
    assert page.js("document.querySelector('[data-testid=level-choice-casual]').checked"), "Casual by default"
    page.click(f"level-choice-{level}")
    page.click("level-play")
    page.wait("!document.querySelector('[data-testid=level-dialog]').open", what="the dialog closes")
    return code


def test_a_short_game_against_the_computer(computer_server: str, browser: Cdp) -> None:
    page = Page(browser, "player (phone 390 px)", viewport=(390, 844, True))  # NFR6 touch targets are checked at phone width
    _start_against_computer(page, computer_server)
    page.wait(f"{STATUS} === 'Your move'", what="the player's first move as White")
    assert page.js(TEXT.format(testid="players")) == "You play White · Computer · Beginner plays Black"
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
    assert page.js("document.querySelectorAll('[data-testid=hint-arrow] g').length") == 0, "the arrow left with the game"
    assert page.problems() == [], f"the page logged errors: {page.problems()}"


def test_switch_sides_with_the_computer_any_time(computer_server: str, browser: Cdp) -> None:
    page = Page(browser, "switcher")
    _start_against_computer(page, computer_server)
    page.wait(f"{STATUS} === 'Your move'", what="White to move")
    assert page.js(TEXT.format(testid="switch-side")) == "Switch colour"
    page.move("e2e4")
    page.wait(f"{STATUS} === 'Your move' && {PIECE_ON.format(square='a5')} === 'p'", what="the computer's reply")
    page.click("switch-side")
    page.wait(f"{TEXT.format(testid='players')}.includes('You play Black')", what="the player now plays Black")
    page.wait(f"document.querySelectorAll('[data-testid=scoresheet-rows] tr').length === 2 && {STATUS} === 'Your move'",
              timeout=20, what="the computer moved White's pieces, then Black to move")
    assert page.js(TEXT.format(testid="switch-side")) == "Switch colour"
    assert page.problems() == [], page.problems()


def test_waiting_room_plays_the_computer_until_a_friend_takes_over(computer_server: str, browser: Cdp) -> None:
    """2026-11-15 follow-up: the computer stands in for the friend, who then takes over seat B."""
    creator = Page(browser, "creator (phone 390 px)", viewport=(390, 844, True))
    creator.go(computer_server + "/")
    creator.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    creator.click("start-game")
    code = creator.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    creator.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="the waiting state")
    creator.js("(() => { const s = document.querySelector('[data-testid=settings-blunderWarnings]'); if (s.checked) s.click(); return true; })()")
    creator.wait(VISIBLE.format(testid="stand-in-start"), what="Play the computer while waiting")
    creator.click("stand-in-start")
    creator.wait("document.querySelector('[data-testid=level-dialog]').open", what="the difficulty dialog")
    creator.click("level-play")
    creator.wait(f"{STATUS} === 'Your move'", what="the creator's first move against the computer")
    assert not creator.js("document.getElementById('share').hidden"), "the invite stays available"
    assert "joined" not in creator.js(TEXT.format(testid="notify-banner")), "the computer is no friend joining"
    assert creator.js(VISIBLE.format(testid="pass-along-stop")), "Wait for a friend instead"
    assert "take over" in creator.js(TEXT.format(testid="pass-along-note"))
    assert creator.js(VISIBLE.format(testid="computer-controls"))
    assert creator.js(SMALL_TARGETS) == []
    creator.move("e2e4")
    creator.wait(f"{STATUS} === 'Your move' && {PIECE_ON.format(square='a5')} === 'p'", what="the computer's reply")

    friend = Page(browser, "friend (desktop)")
    friend.go(f"{computer_server}/r/{code}")
    friend.wait(f"{STATUS} === 'Waiting for White to move'", what="the friend took over Black")
    assert friend.js(PIECE_ON.format(square="a5")) == "p", "the friend continues from the same position"
    creator.wait("!document.querySelector('[data-testid=computer-controls]') || document.querySelector('[data-testid=computer-controls]').hidden",
                 what="the computer controls left")
    assert creator.js("document.querySelector('[data-testid=pass-along]').hidden")
    creator.wait(f"{TEXT.format(testid='notify-banner')}.includes('joined')", what="the takeover is announced")
    creator.move("g1f3")
    friend.wait(f"{STATUS} === 'Your move'", what="the friend now answers the moves")
    assert creator.js(PIECE_ON.format(square="f3")) == "N"
    for page in (creator, friend):
        assert page.problems() == [], page.problems()
