"""Real Chromium checks for portable players, selection and winner feedback."""
from tests.test_game_screen import STATUS, Cdp, Page, browser, live_server  # noqa: F401
from tests.test_u1_polish_browser import _start_room, _two_players, _play


def _nickname(page, value):
    import json
    if page.js("!document.querySelector('[data-testid=player-display]').hidden"):
        page.click("player-edit")
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
    first.click("player-regenerate")
    first.wait("document.querySelector('[data-testid=player-regenerate-dialog]').open", what="styled regeneration dialog")
    first.click("player-regenerate-confirm")
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


def _active(page):
    return page.js("document.activeElement?.dataset.testid || ''")


def _footer_screenshot(page, name):
    """Review artifact: mask even disposable recovery credentials before capture."""
    import base64
    from pathlib import Path
    page.js("(() => { const f = document.querySelector('[data-testid=player-link-field]'); window.__screenshotLink = f.value; f.value = 'Private player link hidden for review'; return true; })()")
    data = page.cdp.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, session=page.session)
    path = Path(__file__).resolve().parent.parent / "aidlc/spaces/default/intents/261115-compact-player-footer/construction/code-generation/screenshots" / name
    path.write_bytes(base64.b64decode(data["data"]))
    page.js("document.querySelector('[data-testid=player-link-field]').value = window.__screenshotLink")


def test_compact_footer_responsive_help_and_clipboard_fallback(live_server, browser):
    from tests.test_u1_polish_browser import _key
    for width in (320, 375, 1280):
        page = Page(browser, f"compact footer {width}", viewport=(width, 844 if width < 1000 else 900, width < 1000))
        page.go(live_server + "/")
        page.wait("!!document.querySelector('[data-testid=start-game]')", what="ready lobby")
        page.js("document.querySelector('[data-testid=player-footer]').scrollIntoView({block:'center'})")
        layout = page.js("""(() => { const f = document.querySelector('[data-testid=player-footer]');
          const r = f.getBoundingClientRect(); const targets = [...f.querySelectorAll('button,input')].filter(e => !e.closest('[hidden]')).map(e => ({id:e.dataset.testid,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}));
          return {width:innerWidth,scroll:document.documentElement.scrollWidth,left:r.left,right:r.right,height:r.height,targets}; })()""")
        assert layout["scroll"] <= width and layout["left"] >= 0 and layout["right"] <= width
        assert all(target["w"] >= 44 and target["h"] >= 44 for target in layout["targets"]), layout
        assert layout["height"] < (200 if width < 1000 else 130), layout
        assert page.js("document.querySelector('[data-testid=player-copy]').textContent") == "Copy player link"
        assert page.js("document.querySelector('[data-testid=player-save] svg') !== null")
        _footer_screenshot(page, f"footer-{width}.png")
        if width == 375:
            page.js("document.documentElement.dataset.theme = 'dark'")
            _footer_screenshot(page, "footer-dark-375.png")
            page.js("document.documentElement.dataset.theme = 'light'")
        page.click("player-help")
        page.wait("document.querySelector('[data-testid=player-help-dialog]').open", what="help modal")
        assert _active(page) == "player-help-close"
        text = page.js("document.querySelector('[data-testid=player-help-dialog]').textContent")
        for phrase in ("without an account", "another device", "anyone holding it", "already signed in", "ordinary page", "Bookmark my player"):
            assert phrase in text
        assert page.js("document.querySelector('[data-testid=player-help-dialog]').getBoundingClientRect().width") <= width
        _footer_screenshot(page, f"help-{width}.png")
        for _ in range(5):
            _key(page, "Tab")
            assert page.js("document.querySelector('[data-testid=player-help-dialog]').contains(document.activeElement)")
        _key(page, "Escape")
        page.wait("!document.querySelector('[data-testid=player-help-dialog]').open", what="help Escape dismissal")
        assert _active(page) == "player-help"
        page.js("navigator.clipboard.writeText = async () => { throw new DOMException('blocked', 'NotAllowedError'); }")
        page.click("player-copy")
        page.wait("document.querySelector('[data-testid=player-help-dialog]').open", what="clipboard fallback")
        assert _active(page) == "player-link-field"
        assert page.js("(() => {const f=document.querySelector('[data-testid=player-link-field]'); return f.selectionStart === 0 && f.selectionEnd === f.value.length;})()")
        assert "#player=" in page.js("document.querySelector('[data-testid=player-link]').href")
        page.click("player-help-close")
        page.wait("!document.querySelector('[data-testid=player-help-dialog]').open", what="fallback closes")
        assert _active(page) == "player-copy"
        assert page.problems() == []


def test_nickname_display_edit_draft_pending_and_validation(live_server, browser):
    page = Page(browser, "nickname editor")
    page.go(live_server + "/")
    page.wait("!!document.querySelector('[data-testid=start-game]')", what="lobby")
    assert not page.js("document.querySelector('[data-testid=player-editor]').hidden")
    _nickname(page, "Alice")
    assert page.js("document.querySelector('[data-testid=player-editor]').hidden")
    assert page.js("document.querySelector('[data-testid=player-name]').textContent") == "Alice"
    page.js("document.querySelector('[data-testid=player-footer]').scrollIntoView({block:'center'})")
    _footer_screenshot(page, "footer-saved-1280.png")
    page.click("player-edit")
    assert _active(page) == "player-nickname"
    assert page.js("document.querySelector('[data-testid=player-nickname]').selectionEnd") == 5
    page.js("(() => {const f=document.querySelector('[data-testid=player-nickname]'); f.value='f.u.c.k'; f.dispatchEvent(new Event('input')); return true;})()")
    page.click("player-save")
    page.wait("document.querySelector('[data-testid=player-message]').textContent.includes('profanity')", what="validation feedback")
    assert page.js("document.querySelector('[data-testid=player-name]').textContent") == "Alice"
    assert not page.js("document.querySelector('[data-testid=player-editor]').hidden")
    page.js("""(() => { window.__nicknameCalls=0; const original=window.fetch.bind(window);
      window.fetch=(url, init) => {if (url === '/api/player/nickname') {window.__nicknameCalls++; return new Promise(resolve => {window.__finishNickname=() => resolve(original(url,init));});} return original(url,init);};
      const f=document.querySelector('[data-testid=player-nickname]'); f.value='Draft'; f.dispatchEvent(new Event('input')); return true; })()""")
    page.js("window.dispatchEvent(new Event('focus'))")
    page.click("player-help")
    page.click("player-help-close")
    assert page.js("document.querySelector('[data-testid=player-nickname]').value") == "Draft"
    # Enter uses form submission and pending prevents a second request.
    page.js("document.querySelector('[data-testid=player-nickname]').focus()")
    for kind in ("keyDown", "keyUp"):
        page.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, **({"text": "\r"} if kind == "keyDown" else {})}, session=page.session)
    page.wait("document.querySelector('[data-testid=player-save]').disabled", what="pending save")
    page.js("document.querySelector('.player-name-form').requestSubmit()")
    assert page.js("window.__nicknameCalls") == 1
    page.js("window.__finishNickname()")
    page.wait("document.querySelector('[data-testid=player-name]').textContent === 'Draft' && document.querySelector('[data-testid=player-editor]').hidden", what="saved display state")
    # Clearing follows the same pending-save path and returns to editable empty.
    page.click("player-edit")
    page.js("document.querySelector('[data-testid=player-nickname]').value = ''")
    page.click("player-save")
    page.wait("window.__nicknameCalls === 2", what="clear request")
    page.js("window.__finishNickname()")
    page.wait("!document.querySelector('[data-testid=player-editor]').hidden && document.querySelector('[data-testid=player-name]').textContent === ''", what="empty editable state")


def test_regeneration_dialog_cancel_focus_pending_failure_and_success(live_server, browser):
    from tests.test_u1_polish_browser import _key, _tap
    page = Page(browser, "regeneration modal")
    page.go(live_server + "/")
    page.wait("!!document.querySelector('[data-testid=start-game]')", what="lobby")
    old = page.js("document.querySelector('[data-testid=player-link]').href")
    page.js("""(() => { window.__regenerateCalls=0; const original=window.fetch.bind(window);
      window.fetch=(url,init) => { if (url === '/api/player/regenerate') window.__regenerateCalls++; return original(url,init);}; return true; })()""")
    for dismissal in ("cancel", "escape", "backdrop"):
        page.click("player-regenerate")
        page.wait("document.querySelector('[data-testid=player-regenerate-dialog]').open", what="regeneration modal")
        assert _active(page) == "player-regenerate-cancel"
        if dismissal == "cancel": _footer_screenshot(page, "regenerate-1280.png")
        if dismissal == "cancel": page.click("player-regenerate-cancel")
        elif dismissal == "escape": _key(page, "Escape")
        else: _tap(page, 1, 1)
        page.wait("!document.querySelector('[data-testid=player-regenerate-dialog]').open", what="cancelled modal")
        assert _active(page) == "player-regenerate"
    assert page.js("window.__regenerateCalls") == 0
    assert page.js("document.querySelector('[data-testid=player-link]').href") == old
    page.js("""(() => { window.__regenerationAttempts=0; const original=window.fetch.bind(window); window.fetch=(url,init) => {
      if (url === '/api/player/regenerate') {window.__regenerationAttempts++; return new Promise(resolve => {window.__finishRegenerate=(fail=false) => resolve(fail ? new Response(JSON.stringify({detail:'Try again later'}),{status:503,headers:{'Content-Type':'application/json'}}) : original(url,init));});}
      return original(url,init);}; return true; })()""")
    page.click("player-regenerate")
    page.click("player-regenerate-confirm")
    page.wait("document.querySelector('[data-testid=player-regenerate-confirm]').disabled", what="pending regeneration")
    page.click("player-regenerate-confirm")
    assert page.js("window.__regenerateCalls") == 0
    assert page.js("window.__regenerationAttempts") == 1
    page.js("window.__finishRegenerate(true)")
    page.wait("document.querySelector('[data-testid=player-regenerate-message]').textContent === 'Try again later'", what="regeneration error")
    assert page.js("document.querySelector('[data-testid=player-regenerate-dialog]').open")
    assert page.js("document.querySelector('[data-testid=player-link]').href") == old
    page.click("player-regenerate-confirm")
    page.js("window.__finishRegenerate()")
    page.wait("!document.querySelector('[data-testid=player-regenerate-dialog]').open", what="successful regeneration")
    assert page.js("window.__regenerateCalls") == 1
    assert page.js("document.querySelector('[data-testid=player-link]').href") != old
    assert _active(page) == "player-regenerate"
