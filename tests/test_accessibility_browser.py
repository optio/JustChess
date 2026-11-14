"""NFR6 checks in a real browser engine (headless Chromium), at phone width.

- Every visible button, link, input and board square on the game screen is at
  least 44 x 44 CSS px (touch targets).
- Every board square has an accessible name with its coordinate.
- The board can be played by keyboard: focus a square, move with the arrow
  keys, select and move with Enter.

Skipped, with the reason, when Chromium is missing.
"""

from __future__ import annotations

import json

from tests.test_game_screen import STATUS, Cdp, Page, browser, live_server  # noqa: F401

SMALL_TARGETS = """(() => {
  const els = [...document.querySelectorAll('button, a[href], input, select, summary, [role=gridcell]')]
    .filter(el => { const s = getComputedStyle(el); const r = el.getBoundingClientRect();
                    return s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0
                           && !el.closest('[hidden]'); });
  return els.map(el => { const r = el.getBoundingClientRect();
      return {what: (el.dataset.testid || el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 40),
              w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10}; })
    .filter(t => t.w < 44 || t.h < 44);
})()"""


def _key(page: Page, key: str) -> None:
    code = {"ArrowUp": 38, "ArrowDown": 40, "ArrowLeft": 37, "ArrowRight": 39, "Enter": 13}[key]
    # A real Enter key press carries the "\r" text; without it Chromium sends no
    # keypress, so a focused <button> is never activated as it is for a person.
    text = {"text": "\r", "unmodifiedText": "\r"} if key == "Enter" else {}
    for kind in ("keyDown", "keyUp"):
        page.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key,
                                                 "windowsVirtualKeyCode": code, **(text if kind == "keyDown" else {})},
                      session=page.session)


def test_touch_targets_labels_and_keyboard_play_at_phone_width(live_server: str, browser: Cdp) -> None:
    white = Page(browser, "player A (390 px phone)", viewport=(390, 844, True))
    black = Page(browser, "player B")
    white.go(live_server + "/")
    white.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    small_lobby = white.js(SMALL_TARGETS)
    white.click("start-game")
    code = white.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    black.go(f"{live_server}/r/{code}")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn")

    small_game = white.js(SMALL_TARGETS)
    assert small_lobby == [] and small_game == [], json.dumps({"lobby": small_lobby, "game": small_game}, indent=1)

    labels = white.js("[...document.querySelectorAll('[role=gridcell]')].map(e => e.getAttribute('aria-label'))")
    assert len(labels) == 64
    assert all(label and label[:2] in {f + r for f in 'abcdefgh' for r in '12345678'} for label in labels), labels[:5]
    assert "e2, white pawn" in labels

    # Keyboard: focus e2, select with Enter, arrow up twice to e4, Enter to move.
    white.js("document.querySelector('[data-testid=board-square-e2]').focus()")
    _key(white, "Enter")
    _key(white, "ArrowUp")
    _key(white, "ArrowUp")
    focused = white.js("document.activeElement.dataset.square || document.activeElement.dataset.testid")
    assert focused in ("e4", "board-square-e4"), focused
    _key(white, "Enter")
    black.wait(f"{STATUS} === 'Your move'", what="black's turn after the keyboard move")
    assert white.js("document.querySelector('[data-testid=board-square-e4]').getAttribute('aria-label')").startswith("e4, white pawn")
    for page in (white, black):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"
