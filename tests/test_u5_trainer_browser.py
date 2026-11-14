"""P2 U5 trainer hub and puzzle screen in headless Chromium (FR8.1, FR8.3, FR8.5, FR8.6).

Reuses the CDP harness of ``tests/test_game_screen.py`` (``browser``, ``Page``)
with its own Uvicorn whose ``JUSTCHESS_PUZZLES_DIR`` is the fixture set from
``tests/fixtures/puzzle_set.py`` (two puzzles per theme); lessons come from the
shipped ``lessons/`` folder. Skipped, with the reason, when Chromium is missing.

* The hub's tabs switch by keyboard (Right, End, Home, Left wrapping), the
  Tactics tab lists the six themes with the Lichess credit, and the selected
  tab is remembered after a reload.
* A fixture mate-in-1 is solved through the real board: Hint highlights the
  piece, the mating move says "Solved", and back on the hub the Tactics count
  and the theme row show one solved puzzle; the next visit opens the other one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.puzzle_set import write_puzzle_dir
from tests.test_game_screen import ROOT, Cdp, Page, _free_port, _wait_http, browser  # noqa: F401

CREDIT = "Puzzles from the Lichess puzzle database, released under CC0."
KEY_CODES = {"ArrowRight": 39, "ArrowLeft": 37, "Home": 36, "End": 35}
SELECTED = "document.querySelector('[role=tab][aria-selected=true]')?.dataset.tab"
FOCUSED = "document.activeElement?.dataset.tab"
PHASE = "document.querySelector('[data-testid=puzzle]')?.dataset.phase"
MESSAGE = "(document.querySelector('[data-testid=puzzle-message]')?.textContent || '')"


@pytest.fixture
def trainer_server(tmp_path: Path):
    port = _free_port()
    puzzles_dir = write_puzzle_dir(tmp_path / "puzzles")
    env = {**os.environ, "STOCKFISH_AUTO_INSTALL": "0", "JUSTCHESS_DB": str(tmp_path / "u5.sqlite3"),
           "JUSTCHESS_PUZZLES_DIR": str(puzzles_dir)}
    for name in ("JUSTCHESS_ORIGIN", "JUSTCHESS_LESSONS_DIR", "JUSTCHESS_VAPID_PRIVATE_KEY", "JUSTCHESS_VAPID_KEY_FILE"):
        env.pop(name, None)
    script = (
        "import sys, uvicorn; from justchess.api import create_app; "
        "uvicorn.run(create_app(db_path=sys.argv[1], engine_dir=sys.argv[2]), host='127.0.0.1', port=int(sys.argv[3]), log_level='warning')"
    )
    server = subprocess.Popen([sys.executable, "-c", script, str(tmp_path / "u5.sqlite3"), str(tmp_path / "engines"), str(port)],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        _wait_http(f"http://127.0.0.1:{port}/", timeout=20)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def press(page: Page, key: str) -> None:
    for kind in ("keyDown", "keyUp"):
        page.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key,
                                                 "windowsVirtualKeyCode": KEY_CODES[key]}, session=page.session)


def test_hub_tabs_work_by_keyboard_and_tactics_lists_its_themes(trainer_server: str, browser: Cdp) -> None:
    page = Page(browser, "learner (desktop 1280 px)")
    page.go(trainer_server + "/learn")
    page.wait("!!document.querySelector('[data-testid=hub-action-italian]')", what="the Openings rows")
    assert page.js(SELECTED) == "openings", "the hub opens on Openings"
    assert page.js("[...document.querySelectorAll('[role=tab]')].map((t) => t.dataset.tab)") == \
        ["openings", "traps", "tactics", "defence"]
    page.wait("document.querySelector('[data-testid=hub-count-openings]').textContent === '0/10'", what="the Openings count")

    page.js("document.querySelector('[data-testid=hub-tab-openings]').focus()")
    for key, expected in (("ArrowRight", "traps"), ("End", "defence"), ("Home", "openings"), ("ArrowLeft", "defence")):
        press(page, key)
        page.wait(f"{SELECTED} === '{expected}' && {FOCUSED} === '{expected}'", what=f"{key} -> {expected}")
    page.wait("!!document.querySelector('[data-testid=hub-action-wayward-queen]')", what="the Defence rows")
    assert page.js("document.querySelector('[data-testid=hub-panel]').getAttribute('aria-labelledby')") == "hub-tab-defence"
    assert page.js("[...document.querySelectorAll('[role=tab]')].filter((t) => t.tabIndex === 0).length") == 1, \
        "one tab in the tab order"

    page.click("hub-tab-tactics")
    page.wait("document.querySelectorAll('[data-testid=hub-rows] li').length === 6", what="six theme rows")
    rows = page.js("[...document.querySelectorAll('[data-testid=hub-rows] li')].map((li) => li.dataset.testid)")
    assert rows == [f"hub-row-{t}" for t in ("fork", "pin", "skewer", "discoveredAttack", "mateIn1", "mateIn2")]
    assert page.js("document.querySelector('[data-testid=hub-row-fork] .hub-row-subtitle').textContent") == "2 puzzles · 0 solved"
    assert page.js("document.querySelector('[data-testid=hub-credit]').textContent") == CREDIT
    assert page.js("document.querySelector('[data-testid=hub-count-tactics]').textContent") == "0/12"

    page.go(trainer_server + "/learn")
    page.wait(f"{SELECTED} === 'tactics'", what="the remembered Tactics tab after a reload")
    assert page.js("document.documentElement.scrollWidth") <= 1280
    assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


def test_a_fixture_puzzle_is_solved_and_counted(trainer_server: str, browser: Cdp) -> None:
    page = Page(browser, "solver (phone 390 px)", viewport=(390, 844, True))
    page.go(trainer_server + "/learn/tactics/mateIn1")
    page.wait("document.querySelector('[data-testid=puzzle-status]')?.textContent === 'White to move: find mate in 1'",
              what="the puzzle status")
    assert page.js("document.querySelector('[data-testid=puzzle-sub]').textContent") == "Mate in 1 · puzzle 1 of 2"
    assert page.js("document.querySelector('[data-testid=puzzle-credit]').textContent") == CREDIT
    page.wait(f"{PHASE} === 'yourMove'", what="the set-up move and the player's turn")
    assert page.js("document.querySelector('[data-testid=board-square-a6] img.piece')?.dataset.shown") == "p", \
        "the opponent's set-up move a6 was played"

    page.click("puzzle-hint")
    page.wait(f"{MESSAGE} === 'Move the piece on d1.'", what="the first hint")
    assert page.js("document.querySelector('[data-testid=board-square-d1]').classList.contains('is-hint')")

    page.move("d1d8")
    page.wait(f"{PHASE} === 'solved' && {MESSAGE} === 'Solved'", what="the solved puzzle")
    assert page.js("document.documentElement.scrollWidth") <= 390, "no horizontal scroll on the phone"

    page.click("puzzle-back")
    page.wait("location.pathname === '/learn/tactics' && !!document.querySelector('[data-testid=hub-row-mateIn1]')",
              what="the hub's Tactics tab")
    page.wait("document.querySelector('[data-testid=hub-count-tactics]').textContent === '1/12'", what="one solved puzzle")
    assert page.js("document.querySelector('[data-testid=hub-row-mateIn1] .hub-row-subtitle').textContent") == \
        "2 puzzles · 1 solved"

    page.click("hub-action-mateIn1")
    page.wait("document.querySelector('[data-testid=puzzle-sub]')?.textContent === 'Mate in 1 · puzzle 2 of 2'",
              what="the next unsolved puzzle")
    page.wait("document.querySelector('[data-testid=puzzle-status]').textContent === 'Black to move: find mate in 1'",
              what="the Fool's mate puzzle, played as Black")
    assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"
