"""P2 U2 "Your games" in headless Chromium (FR1.1-FR1.3, BR3.1-BR3.5).

Reuses the CDP harness of ``tests/test_game_screen.py`` (``live_server`` on a
temporary database, ``browser``, ``Page``). Skipped, with the reason, when
Chromium is missing.

Player A starts two rooms; player B joins the second. Back on the main screen,
A's list shows both rooms (the waiting one and the one where it is A's move),
and the "Your move" row opens that game in the page.
"""

from __future__ import annotations

import json

from tests.test_game_screen import STATUS, Cdp, Page, browser, live_server  # noqa: F401

ROWS = """(() => [...document.querySelectorAll('[data-testid=your-games-row]')].map((row) => ({
  code: row.dataset.code,
  pill: row.querySelector('[data-testid=your-games-pill]').textContent,
  label: row.querySelector('.game-row-label').textContent,
  height: row.getBoundingClientRect().height,
})))()"""


def _start_room(page: Page, live: str) -> str:
    page.go(live + "/")
    page.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    page.click("start-game")
    code = page.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    page.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="the waiting state")
    return code


def test_main_screen_lists_both_rooms_and_the_your_move_row_opens_its_game(live_server: str, browser: Cdp) -> None:
    player_a = Page(browser, "player A (desktop 1280 px)")
    player_b = Page(browser, "player B (phone 390 px)", viewport=(390, 844, True))
    waiting_code = _start_room(player_a, live_server)
    playing_code = _start_room(player_a, live_server)
    player_b.go(f"{live_server}/r/{playing_code}")
    player_b.wait(f"{STATUS} === 'Waiting for White'", what="black's first status")

    player_a.go(live_server + "/")
    player_a.wait("document.querySelector('[data-testid=lobby-title], #lobby-title')?.textContent"
                  " === 'Play a friend. Play the computer. Get better.'", what="the new headline")
    player_a.wait("document.querySelectorAll('[data-testid=your-games-row]').length === 2", what="two rows")
    rows = {row["code"]: row for row in player_a.js(ROWS)}

    assert set(rows) == {waiting_code, playing_code}, json.dumps(rows)
    assert rows[playing_code]["pill"] == "Your move" and rows[playing_code]["label"] == f"Friend · {playing_code}"
    assert rows[waiting_code]["pill"] == "Waiting" and rows[waiting_code]["label"] == f"Waiting for a friend · {waiting_code}"
    assert all(row["height"] >= 72 for row in rows.values()), "each row is at least 72 px tall"
    assert player_a.js("document.querySelector('[data-testid=learn-opening]').textContent") == "Train"
    assert player_a.js(ROWS)[0]["code"] == playing_code, "the newest activity comes first"

    player_a.js(f"document.querySelector('[data-testid=your-games-row][data-code=\"{playing_code}\"]').click()")
    player_a.wait(f"location.pathname === '/r/{playing_code}'", what="the game's address")
    player_a.wait(f"{STATUS} === 'Your move'", what="the opened game")
    for page in (player_a, player_b):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"
