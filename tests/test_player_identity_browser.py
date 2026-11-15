"""Real Chromium checks for portable players, selection and winner feedback."""
from tests.test_game_screen import STATUS, Cdp, Page, browser, live_server  # noqa: F401
from tests.test_u1_polish_browser import _start_room, _two_players, _play


def _nickname(page, value):
    import json
    page.js(f"document.querySelector('[data-testid=player-nickname]').value = {json.dumps(value)}")
    page.click("player-save")
    page.wait("document.querySelector('[data-testid=player-message]').textContent === 'Nickname saved'", what="nickname saved")


def test_player_bookmark_restores_games_keeps_devices_and_revokes_old_link(live_server, browser):
    first = Page(browser, "original device")
    code = _start_room(first, live_server)
    _nickname(first, "Alice")
    link = first.js("document.querySelector('[data-testid=player-link]').href")
    assert "#player=" in link and "?" not in link
    second = Page(browser, "restored device")
    second.go(link)
    second.wait("document.querySelector('[data-testid=player-nickname]').value === 'Alice'", what="restored nickname")
    assert second.js("location.hash") == ""
    second.wait(f"!!document.querySelector('[data-testid=your-games] a[href=\"/r/{code}\"]')", what="restored saved game")
    second.go(f"{live_server}/r/{code}")
    second.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="restored seat")
    third = Page(browser, "opponent")
    third.go(f"{live_server}/r/{code}")
    first.wait(f"{STATUS} === 'Your move'", what="original device still authorized")
    second.wait(f"{STATUS} === 'Your move'", what="second device authorized")
    first.move("e2e4")
    second.wait(f"{STATUS} === 'Waiting for Black'", what="shared seat update")
    # Regeneration leaves both sessions valid and makes old bookmarks unusable.
    first.js("window.confirm = () => true")
    first.click("player-regenerate")
    fresh = first.wait(f"document.querySelector('[data-testid=player-link]').href !== {link!r} && document.querySelector('[data-testid=player-link]').href", what="replacement link")
    rejected = Page(browser, "old bookmark")
    rejected.go(link)
    rejected.wait("document.querySelector('[data-testid=player-message]').textContent.includes('invalid or has been replaced')", what="old link rejected")
    fourth = Page(browser, "new bookmark")
    fourth.go(fresh)
    fourth.wait("document.querySelector('[data-testid=player-nickname]').value === 'Alice'", what="replacement link restored")
    for page in (first, second, third, fourth):
        assert page.problems() == []


def test_selected_piece_growth_and_named_winner_confetti(live_server, browser):
    white, black = _two_players(browser, live_server)
    _nickname(white, "Alice")
    _nickname(black, "Bob")
    white.click("board-square-f2")
    white.wait("getComputedStyle(document.querySelector('[data-testid=board-square-f2] img.piece')).scale === '1.1'", what="selected piece growth")
    white.click("board-square-e2")
    assert white.js("getComputedStyle(document.querySelector('[data-testid=board-square-f2] img.piece')).scale") == "none"
    white.click("board-square-e2")
    _play(white, black, ["f2f3", "e7e5", "g2g4"])
    black.move("d8h4")
    for page in (white, black):
        page.wait("!document.querySelector('[data-testid=overlay]').hidden", timeout=20, what="result overlay")
    assert white.js("document.querySelector('[data-testid=overlay-title]').textContent") == "You lost"
    assert "Bob won" in white.js("document.querySelector('[data-testid=overlay-subtitle]').textContent")
    assert black.js("document.querySelector('[data-testid=overlay-title]').textContent") == "You won!"
    assert "Alice" in black.js("document.querySelector('[data-testid=overlay-subtitle]').textContent")
    black.wait("!!document.querySelector('[data-testid=winner-confetti]')", what="winner confetti")
    assert not white.js("!!document.querySelector('[data-testid=winner-confetti]')")
    black.wait("!document.querySelector('[data-testid=winner-confetti]')", what="bounded effect ends")
    black.go(black.js("location.href"))
    black.wait("!document.querySelector('[data-testid=overlay]').hidden", what="reopened result")
    assert not black.js("!!document.querySelector('[data-testid=winner-confetti]')")


def test_reduced_motion_keeps_result_without_confetti(live_server, browser):
    white, black = _two_players(browser, live_server)
    for page in (white, black):
        page.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, session=page.session)
    _play(white, black, ["f2f3", "e7e5", "g2g4"])
    black.move("d8h4")
    black.wait("document.querySelector('[data-testid=overlay-title]').textContent === 'You won!'", what="reduced-motion result")
    assert not black.js("!!document.querySelector('[data-testid=winner-confetti]')")
