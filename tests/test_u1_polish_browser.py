"""P2 U1 game-screen polish in headless Chromium: board fit, capture animation, share dialog.

Reuses the CDP harness of ``tests/test_game_screen.py`` (``live_server`` on a
temporary database, ``browser``, ``Page``). Skipped, with the reason, when
Chromium is missing.

* FR4.1/FR4.2: at the 7 FR4.1 viewport sizes the board's bottom edge is inside
  the viewport at scroll 0, its side matches functional-spec.md W2 (mirrored by
  ``static/js/layout.js``), squares are >= 44 px (>= 36 px in phone landscape)
  and the page does not scroll sideways.
* FR2.1: a capture puts a shrink-and-fade copy of the taken piece on its own
  square, on both boards, en passant included; the captured row updates.
* FR2.2: under emulated reduced motion no copy is made and nothing fades.
* FR2.3: while a copy is running (slowed down), taps still select and move.
* FR5.1-FR5.5: the share dialog opens over an unchanged game screen with focus
  on "Copy link", keeps Tab inside, closes on Escape / Close / backdrop and
  returns focus to Share; the QR code is drawn locally; "Copied" appears and
  resets, also when the clipboard refuses (the link is selected instead).
"""

from __future__ import annotations

import json

from tests.test_game_screen import STATUS, Cdp, Page, browser, live_server  # noqa: F401

# functional-spec.md W2: (width, height, mode, board side in px)
FR41_SIZES = [
    (360, 640, "portrait", 360),
    (390, 844, "portrait", 390),
    (768, 600, "portrait", 448),
    (768, 1024, "portrait", 736),
    (1280, 720, "desktop", 610),
    (640, 360, "landscape-phone", 336),
    (844, 390, "landscape-phone", 366),
]

MEASURE = """(() => {
  const frame = document.querySelector('.game-board .board-frame').getBoundingClientRect();
  const square = document.querySelector('[data-testid=board-square-e2]').getBoundingClientRect();
  const bar = document.querySelector('.topbar').getBoundingClientRect();
  return {top: frame.top, bottom: frame.bottom, right: frame.right, width: frame.width, square: Math.min(square.width, square.height),
          barLeft: bar.left, barRight: bar.right, barBottom: bar.bottom,
          scrollX: scrollX, scrollY: scrollY, scrollWidth: document.documentElement.scrollWidth};
})()"""

GHOST_RECORDER = """(() => {
  window.__ghosts = [];
  new MutationObserver((records) => records.forEach((record) => record.addedNodes.forEach((node) => {
    if (!node.classList || !node.classList.contains('piece-ghost')) return;
    const animation = node.getAnimations()[0];
    window.__ghosts.push({square: node.parentElement.dataset.square, piece: node.getAttribute('src').split('/').pop(),
                          duration: animation ? animation.effect.getTiming().duration : null,
                          pointerEvents: getComputedStyle(node).pointerEvents});
  }))).observe(document.querySelector('[data-testid=game-board]'), {childList: true, subtree: true});
  return true;
})()"""

PIECE_ON = "(document.querySelector('[data-testid=board-square-{square}] img.piece:not(.piece-ghost)')?.dataset.shown || '')"
LABEL = "document.querySelector('[data-testid=captured-{which}]').getAttribute('aria-label')"
DIALOG_OPEN = "document.querySelector('[data-testid=share-dialog]').open"
ACTIVE = "(document.activeElement?.dataset.testid || document.activeElement?.tagName)"


def _start_room(page: Page, live: str) -> str:
    page.go(live + "/")
    page.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    page.click("start-game")
    code = page.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    page.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="the waiting state")
    return code


def _two_players(browser: Cdp, live: str, black_viewport=(390, 844, True)) -> tuple[Page, Page]:
    white = Page(browser, "player A (desktop 1280 px)")
    black = Page(browser, "player B (phone 390 px)", viewport=black_viewport)
    code = _start_room(white, live)
    black.go(f"{live}/r/{code}")
    black.wait(f"{STATUS} === 'Waiting for White to move'", what="black's first status")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn")
    for page in (white, black):  # no blunder dialog in the way of these short lines
        page.js("(() => { const s = document.querySelector('[data-testid=settings-blunderWarnings]');"
                " if (s.checked) s.click(); return true; })()")
    return white, black


def _play(white: Page, black: Page, moves: list[str]) -> None:
    pages = (white, black)
    for ply, uci in enumerate(moves):
        mover, waiter = pages[ply % 2], pages[(ply + 1) % 2]
        mover.wait(f"{STATUS}.startsWith('Your move') || {STATUS}.startsWith('Check')", what=f"the turn for {uci}")
        mover.move(uci)
        waiter.wait(f"{STATUS} === 'Your move' || {STATUS}.startsWith('Check')", what=f"the turn after {uci}")


def _key(page: Page, key: str, shift: bool = False) -> None:
    codes = {"Tab": 9, "Escape": 27}
    for kind in ("keyDown", "keyUp"):
        page.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": codes[key],
                                                 "modifiers": 8 if shift else 0}, session=page.session)


def _tap(page: Page, x: float, y: float) -> None:
    for kind in ("mousePressed", "mouseReleased"):
        page.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1},
                      session=page.session)


def _centre(page: Page, selector: str) -> tuple[float, float]:
    box = page.js(f"(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
                  " return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    return box[0], box[1]


# --- FR4: the board fits above the fold ----------------------------------------------------

def test_board_fits_the_viewport_at_the_fr41_sizes(live_server: str, browser: Cdp) -> None:
    failures = []
    for width, height, mode, side in FR41_SIZES:
        page = Page(browser, f"{width} x {height} ({mode})", viewport=(width, height, width < 1024))
        _start_room(page, live_server)
        m = page.js(MEASURE)
        floor = 36 if mode == "landscape-phone" else 44
        if m["scrollY"] != 0 or m["bottom"] > height + 0.5:
            failures.append(f"{width}x{height}: board bottom {m['bottom']} below the viewport ({m})")
        if abs(m["width"] - side) > 1:
            failures.append(f"{width}x{height}: board side {m['width']}, expected {side}")
        if m["square"] < floor:
            failures.append(f"{width}x{height}: {m['square']} px squares, floor {floor}")
        if m["scrollWidth"] > width:
            failures.append(f"{width}x{height}: the page scrolls sideways ({m['scrollWidth']} px)")
        if mode == "landscape-phone" and (m["barLeft"] < m["right"] or m["barRight"] > width):
            failures.append(f"{width}x{height}: the top bar overlaps the board or leaves the screen ({m})")
        if mode != "landscape-phone" and m["top"] < m["barBottom"]:
            failures.append(f"{width}x{height}: the board starts under the top bar ({m})")
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"
    assert failures == [], "\n".join(failures)


# --- FR2: the capture animation -------------------------------------------------------------

def test_capture_animates_on_the_taken_square_including_en_passant(live_server: str, browser: Cdp) -> None:
    white, black = _two_players(browser, live_server)
    for page in (white, black):
        page.js(GHOST_RECORDER)

    # 1.e4 a6 2.e5 d5 3.exd6 e.p.: the black pawn on d5 is taken, not anything on d6
    _play(white, black, ["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"])
    for page in (white, black):
        ghosts = page.wait("window.__ghosts.length ? window.__ghosts : null", what="the capture copy")
        assert ghosts[0]["square"] == "d5" and ghosts[0]["piece"] == "bP.svg", ghosts
        assert ghosts[0]["duration"] == 260 and ghosts[0]["pointerEvents"] == "none", ghosts
        page.wait(f"{PIECE_ON.format(square='d5')} === '' && {PIECE_ON.format(square='d6')} === 'P'", what="the en passant result")
        page.wait("!document.querySelector('img.piece-ghost')", what="the copy being removed")
    assert len(white.js("window.__ghosts")) == 1, "the player's own capture animates once, not again on confirmation"
    white.wait(f"{LABEL.format(which='top')} === 'Pieces you captured: black pawn'", what="white's captured row")
    black.wait(f"{LABEL.format(which='bottom')} === 'Pieces your opponent captured: black pawn'", what="black's captured row")

    # a normal capture by the other side: 3...Qxd6
    _play(black, white, ["d8d6"])
    ghosts = white.wait("window.__ghosts.length === 2 ? window.__ghosts : null", what="the second capture copy")
    assert ghosts[1]["square"] == "d6" and ghosts[1]["piece"] == "wP.svg", ghosts
    white.wait(f"{LABEL.format(which='bottom')} === 'Pieces your opponent captured: white pawn'", what="the opponent's row")
    for page in (white, black):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


def test_no_capture_animation_under_reduced_motion(live_server: str, browser: Cdp) -> None:
    white, black = _two_players(browser, live_server)
    for page in (white, black):
        page.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]},
                      session=page.session)
        page.js(GHOST_RECORDER)
    _play(white, black, ["e2e4", "d7d5", "e4d5"])
    for page in (white, black):
        page.wait(f"{PIECE_ON.format(square='d5')} === 'P'", what="the capture drawn at once")
    white.wait(f"{LABEL.format(which='top')} === 'Pieces you captured: black pawn'", what="the row updated without motion")
    black.wait(f"{LABEL.format(which='bottom')} === 'Pieces your opponent captured: black pawn'", what="black's row")
    for page in (white, black):
        assert page.js("window.__ghosts") == [], f"{page.name}: no copy under reduced motion"
        assert page.js("document.querySelectorAll('.captured-piece.is-new').length") == 0, "nothing fades"
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


def test_taps_during_a_capture_animation_still_select_and_move(live_server: str, browser: Cdp) -> None:
    white, black = _two_players(browser, live_server)
    black.cdp.call("Animation.enable", session=black.session)
    black.cdp.call("Animation.setPlaybackRate", {"playbackRate": 0.05}, session=black.session)  # 260 ms -> 5.2 s
    _play(white, black, ["e2e4", "d7d5", "e4d5"])
    black.wait("!!document.querySelector('[data-testid=board-square-d5] img.piece-ghost')", what="black's capture copy")

    # real pointer taps: select the queen, then tap d5 right through the running copy
    _tap(black, *_centre(black, "[data-testid=board-square-d8]"))
    assert black.js("document.querySelector('[data-testid=board-square-d8]').classList.contains('is-selected')"), \
        "the tap during the animation selected the queen"
    assert black.js("!!document.querySelector('[data-testid=board-square-d5] img.piece-ghost')"), "the copy is still running"
    _tap(black, *_centre(black, "[data-testid=board-square-d5]"))
    white.wait(f"{STATUS} === 'Your move'", what="white's turn after Qxd5")
    assert white.js(PIECE_ON.format(square="d5")) == "q"
    for page in (white, black):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


# --- FR5: the share dialog --------------------------------------------------------------------

def test_share_dialog_focus_keyboard_and_unchanged_game_screen(live_server: str, browser: Cdp) -> None:
    page = Page(browser, "host (phone 390 px)", viewport=(390, 844, True))
    _start_room(page, live_server)
    before = page.js("document.querySelector('[data-testid=game]').outerHTML")
    frame_before = page.js(MEASURE)

    page.js("(() => { const b = document.querySelector('[data-testid=share]'); b.focus(); b.click(); return true; })()")
    page.wait(DIALOG_OPEN, what="the dialog opening")
    assert page.js(ACTIVE) == "share-copy", "focus starts on Copy link"
    assert page.js("document.querySelector('[data-testid=share-title]').textContent") == "Invite a friend"
    assert page.js("document.querySelector('[data-testid=share-line]').textContent") == \
        "Send this link. Whoever opens it first plays black."
    assert page.js("document.querySelector('[data-testid=share-link]').value").endswith("/r/" + page.js("location.pathname.slice(3)"))
    assert page.js(MEASURE) == frame_before, "the board did not move behind the dialog"

    inside = "document.querySelector('[data-testid=share-dialog]').contains(document.activeElement)"
    for _ in range(12):
        _key(page, "Tab")
        assert page.js(inside), f"Tab left the dialog (focus on {page.js(ACTIVE)})"
    for _ in range(4):
        _key(page, "Tab", shift=True)
        assert page.js(inside), f"Shift+Tab left the dialog (focus on {page.js(ACTIVE)})"

    _key(page, "Escape")
    page.wait(f"!{DIALOG_OPEN}", what="Escape closing the dialog")
    assert page.js(ACTIVE) == "share", "focus returns to Share"
    assert page.js("document.querySelector('[data-testid=game]').outerHTML") == before, "the game screen is unchanged"
    assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


def test_share_dialog_links_local_qr_and_closing(live_server: str, browser: Cdp) -> None:
    page = Page(browser, "host (desktop 1280 px)")
    _start_room(page, live_server)
    page.click("share")
    page.wait(DIALOG_OPEN, what="the dialog opening")

    links = page.js("[...document.querySelectorAll('[data-testid=share-apps] a')].map(a => [a.textContent, a.getAttribute('href')])")
    assert [label for label, _ in links] == ["Email", "WhatsApp", "Telegram", "SMS"]
    assert [href.split(":")[0] for _, href in links] == ["mailto", "https", "https", "sms"]
    assert links[1][1].startswith("https://wa.me/?text=") and links[2][1].startswith("https://t.me/share/url?url=")
    assert page.js("document.querySelector('[data-testid=share-more]').hidden") == \
        page.js("typeof navigator.share !== 'function'"), "More… only with a share sheet"

    # the QR code is drawn locally: dark modules on the canvas, and no request leaves the origin
    dark = page.wait("""(() => { const c = document.querySelector('[data-testid=share-qr]');
        if (!c.width) return 0; const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] < 50) n += 1; return n; })()""", what="the QR code")
    assert dark > 100, dark
    assert page.js("document.querySelector('[data-testid=share-qr-note]').textContent") != "QR code unavailable"
    assert page.js("performance.getEntriesByType('resource').every(e => e.name.startsWith(location.origin))"), \
        "no request to another origin"

    # Close, then a click on the backdrop, both close it
    page.click("share-close")
    page.wait(f"!{DIALOG_OPEN}", what="Close closing the dialog")
    page.click("share")
    page.wait(DIALOG_OPEN, what="the dialog again")
    _tap(page, 8, 8)
    page.wait(f"!{DIALOG_OPEN}", what="a backdrop click closing the dialog")
    assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


def test_copy_link_shows_copied_and_resets_also_when_the_clipboard_refuses(live_server: str, browser: Cdp) -> None:
    page = Page(browser, "host (desktop 1280 px)")
    browser.call("Browser.grantPermissions", {"permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"],
                                              "origin": live_server, "browserContextId": page.context})
    _start_room(page, live_server)
    page.click("share")
    page.wait(DIALOG_OPEN, what="the dialog opening")
    copy_label = "document.querySelector('[data-testid=share-copy]').textContent"

    page.js("(() => { window.__copied = []; navigator.clipboard.writeText = async (t) => { window.__copied.push(t); };"
            " return true; })()")
    page.click("share-copy")
    page.wait(f"{copy_label} === 'Copied'", what="Copied")
    assert page.js("window.__copied") == [page.js("document.querySelector('[data-testid=share-link]').value")]
    page.wait(f"{copy_label} === 'Copy link'", timeout=5, what="the label resetting after 1.6 s")

    # a refused clipboard: the link is selected for a manual copy and the label still confirms
    page.js("(() => { navigator.clipboard.writeText = async () => { throw new DOMException('denied', 'NotAllowedError'); };"
            " return true; })()")
    page.click("share-copy")
    page.wait(f"{copy_label} === 'Copied'", what="Copied after a refusal")
    selected = page.js("(() => { const f = document.querySelector('[data-testid=share-link]');"
                       " return document.activeElement === f && f.selectionStart === 0 && f.selectionEnd === f.value.length; })()")
    assert selected, "the link field is selected when the clipboard refuses"
    page.wait(f"{copy_label} === 'Copy link'", timeout=5, what="the label resetting")
    problems = [p for p in page.problems() if "copying to the clipboard failed" not in p]
    assert problems == [], f"{page.name} logged errors: {problems}"
