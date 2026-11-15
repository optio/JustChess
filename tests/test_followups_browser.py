"""Real Chromium checks for the 2026-11-15 UI follow-ups: header nickname,
move saving/waiting progress, lobby refresh from the home icon, Share height."""
from tests.test_game_screen import STATUS, TRAINER_MESSAGE, YOUR_MOVE, Cdp, Page, browser, live_server  # noqa: F401
from tests.test_u1_polish_browser import _start_room, _two_players

DOT = "document.querySelector('[data-testid=status]').dataset.dot"


def test_move_shows_saving_then_hourglass_until_the_opponent_answers(live_server, browser):
    white, black = _two_players(browser, live_server)
    # Hold the move request so the saving state can be seen.
    white.js("""(() => { const original = window.fetch.bind(window); window.__moveCalls = 0;
      window.fetch = (url, init) => { if (String(url).endsWith('/moves')) { window.__moveCalls++;
        return new Promise(resolve => { window.__releaseMove = () => resolve(original(url, init)); }); }
        return original(url, init); }; return true; })()""")
    white.move("e2e4")
    white.wait(f"{STATUS} === 'Saving your move…'", what="saving status")
    assert white.js(DOT) == "saving"
    assert white.js("document.querySelector('[data-testid=status]').getAttribute('aria-busy')") == "true"
    assert white.js("window.__moveCalls") == 1
    white.js("window.__releaseMove()")
    white.wait(f"{STATUS} === 'Waiting for Black'", what="waiting status")
    assert white.js(DOT) == "hourglass"
    assert white.js("document.querySelector('[data-testid=status]').getAttribute('aria-busy')") == "false"
    black.wait(f"{STATUS} === 'Your move'", what="black to move")
    black.move("e7e5")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn again")
    assert white.js(DOT) == "solid"
    for page in (white, black):
        assert page.problems() == []


def test_refused_move_restores_the_status(live_server, browser):
    white, black = _two_players(browser, live_server)
    white.js("""(() => { const original = window.fetch.bind(window);
      window.fetch = (url, init) => String(url).endsWith('/moves')
        ? Promise.resolve(new Response(JSON.stringify({detail: 'Not now'}), {status: 400, headers: {'Content-Type': 'application/json'}}))
        : original(url, init); return true; })()""")
    white.move("e2e4")
    white.wait(f"{STATUS} === 'Your move'", what="status restored after refusal")
    assert white.js(DOT) == "solid"


def test_home_icon_refreshes_your_games_past_the_request_cap(live_server, browser):
    page = Page(browser, "lobby refresh")
    _start_room(page, live_server)
    page.click("home-link")
    page.wait("!!document.querySelector('[data-testid=your-games] a.game-row')", what="listed game")
    page.js("""(() => { const original = window.fetch.bind(window); window.__summaryCalls = 0;
      window.fetch = (url, init) => { if (String(url).includes('/api/rooms/summaries')) window.__summaryCalls++; return original(url, init); };
      return true; })()""")
    page.js("document.querySelector('a.game-row').click()")
    page.wait("!document.querySelector('#room-bar').hidden", what="back in the room")
    page.click("home-link")
    page.wait("window.__summaryCalls >= 1", what="forced refresh on return")
    assert page.problems() == []


def test_header_nickname_and_share_height(live_server, browser):
    for width in (320, 390, 1280):
        page = Page(browser, f"header {width}", viewport=(width, 800, width < 1000))
        _start_room(page, live_server)
        page.wait("!document.querySelector('[data-testid=topbar-player]').hidden", what="header nickname")
        assert page.js("!!document.querySelector('.topbar [data-testid=player-nickname]')")
        assert not page.js("!!document.querySelector('[data-testid=player-footer] [data-testid=player-nickname]')")
        code, share = page.rect("#room-code"), page.rect("#share")
        assert code["height"] == share["height"] >= 44, (code, share)
        assert page.rect(".topbar")["height"] <= 56
        assert page.problems() == []


def test_battery_lesson_is_listed_and_plays_to_mate(live_server, browser):
    page = Page(browser, "battery lesson")
    page.go(live_server + "/learn")
    page.wait("!!document.querySelector('[data-testid=hub-tab-traps]')", what="the hub")
    page.click("hub-tab-traps")
    page.wait("!!document.querySelector('[data-testid=hub-action-battery-mate]')", what="the battery lesson in the list")
    page.click("hub-action-battery-mate")
    page.wait("document.querySelector('[data-testid=trainer-name]')?.textContent === 'Batteries: queen and bishop mate'", what="the lesson")
    assert page.js("document.querySelector('[data-testid=board-square-c2] img.piece').dataset.shown") == "B"
    page.click("trainer-practise")
    page.wait(YOUR_MOVE, what="the learner's first move")
    for uci, reply in (("d1d3", "Nf6"), ("f1e1", "Ng4")):
        page.move(uci)
        page.wait(f"{TRAINER_MESSAGE}.includes('{reply}')", what=f"the trainer's reply {reply}")
        page.wait(YOUR_MOVE, what=f"the learner's turn after {reply}")
    page.move("d3h7")
    page.wait(f"{TRAINER_MESSAGE}.startsWith('Line complete')", what="the mate completes the line")
    assert page.problems() == []
