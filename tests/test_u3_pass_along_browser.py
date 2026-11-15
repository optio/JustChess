"""P2 U3 pass-along and a join request in headless Chromium (FR3.1-FR3.6, BR4.1).

Reuses the CDP harness of ``tests/test_game_screen.py`` (``live_server`` on a
temporary database, ``browser``, ``Page``). Skipped, with the reason, when
Chromium is missing.

The creator starts a room, presses "Play here while waiting" and plays one
White and one Black move. A second page opens the invite link and asks to
join; the creator accepts from the banner. The joiner's page opens the game as
Black and both boards show the same position.
"""

from __future__ import annotations

from tests.test_game_screen import PIECE_ON, STATUS, Cdp, Page, browser, live_server  # noqa: F401

JOINER_WAITING = "Waiting for the creator to accept. You'll play Black from the current position."
VISIBLE = "!document.querySelector('[data-testid={testid}]').hidden"
TEXT = "(document.querySelector('[data-testid={testid}]')?.textContent || '')"


def _pieces(page: Page) -> dict[str, str]:
    return {square: page.js(PIECE_ON.format(square=square)) for square in ("e2", "e4", "e5", "e7", "g1", "b8")}


def test_creator_plays_both_colours_then_accepts_a_join_request(live_server: str, browser: Cdp) -> None:
    creator = Page(browser, "creator (desktop 1280 px)")
    joiner = Page(browser, "joiner (phone 390 px)", viewport=(390, 844, True))

    creator.go(live_server + "/")
    creator.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    creator.click("start-game")
    code = creator.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    creator.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="the waiting state")
    creator.wait(VISIBLE.format(testid="pass-along-start"), what="the Play here while waiting button")

    creator.click("pass-along-start")
    creator.wait(f"{STATUS} === 'Pass-along: White to move'", what="pass-along with White to move")
    assert creator.js(VISIBLE.format(testid="pass-along-note")), "the practice note shows"
    assert creator.js(VISIBLE.format(testid="pass-along-stop")), "Wait for a friend instead shows"
    creator.move("e2e4")
    creator.wait(f"{STATUS} === 'Pass-along: Black to move'", what="Black to move after e4")
    creator.move("e7e5")
    creator.wait(f"{STATUS} === 'Pass-along: White to move'", what="White to move after e5")

    joiner.go(f"{live_server}/r/{code}")
    joiner.wait(f"{STATUS} === \"{JOINER_WAITING}\"", what="the joiner's waiting text")
    assert "token" not in joiner.js("location.href").lower()

    creator.wait(VISIBLE.format(testid="join-request-banner"), what="the join-request banner")
    banner = creator.js(TEXT.format(testid="join-request-text"))
    assert banner.startswith("Someone wants to join as Black. They will take over Black from this position. Expires in "), banner
    assert creator.js("document.querySelector('[data-testid=join-request-banner]').getAttribute('role')") == "alert"
    creator.click("join-request-accept")

    joiner.wait(f"{STATUS} === 'Waiting for White to move'", timeout=20, what="the joiner seated as Black")
    creator.wait(f"{STATUS} === 'Your move'", what="the creator back to plain play as White")
    creator.wait("document.querySelector('[data-testid=join-request-banner]').hidden", what="the banner gone")
    assert joiner.js("document.querySelector('.board-row .sq').dataset.square") == "h1", "the joiner's board is Black's"
    assert creator.js("document.querySelector('[data-testid=pass-along-stop]').hidden"), "pass-along controls are gone"
    expected = {"e2": "", "e4": "P", "e5": "p", "e7": "", "g1": "N", "b8": "n"}
    joiner.wait(f"{PIECE_ON.format(square='e5')} === 'p'", what="the joiner's board position")
    assert _pieces(creator) == expected, _pieces(creator)
    assert _pieces(joiner) == expected, _pieces(joiner)
    for page in (creator, joiner):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"
