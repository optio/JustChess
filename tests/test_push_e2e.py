"""NFR3 / FR6.5: a real Web Push reaches a closed room page on localhost.

The test generates a VAPID key in pytest's tmp_path (never inside the project),
starts a test-owned server with it, and drives headless Chromium:

1. Black opens the room, turns Notifications on, and the browser subscribes to
   the browser vendor's real push service.
2. Black's page leaves the room (no socket), so the server must use Web Push.
3. White moves; the push service delivers the push to Black's service worker,
   which shows a notification tagged ``<code>:move:1:1``.

It is skipped, with the reason, when Chromium is missing or when this Chromium
build has no push service (for example a build without vendor API keys), and
it needs network access to that push service.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import httpx
import pytest

from justchess import vapid
from tests.test_game_screen import ROOT, STATUS, WORKER_TAGS, Cdp, Page, _free_port, _wait_http, browser  # noqa: F401


@pytest.fixture
def push_server(tmp_path):
    key_file = tmp_path / "vapid" / "vapid.pem"
    vapid.generate(key_file, project_root=ROOT)
    port = _free_port()
    env = {**os.environ, "STOCKFISH_AUTO_INSTALL": "0", "JUSTCHESS_VAPID_KEY_FILE": str(key_file),
           "JUSTCHESS_VAPID_SUBJECT": "mailto:test@localhost"}
    for name in ("JUSTCHESS_ORIGIN", "JUSTCHESS_VAPID_PRIVATE_KEY"):
        env.pop(name, None)
    script = (
        "import sys, uvicorn; from justchess.api import create_app; "
        "uvicorn.run(create_app(db_path=sys.argv[1], engine_dir=sys.argv[2]), host='127.0.0.1', "
        "port=int(sys.argv[3]), log_level='warning')"
    )
    proc = subprocess.Popen([sys.executable, "-c", script, str(tmp_path / "push.sqlite3"), str(tmp_path / "engines"), str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://localhost:{port}"  # localhost: a secure context, as push requires
    try:
        _wait_http(f"http://127.0.0.1:{port}/", timeout=20)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_real_web_push_reaches_a_closed_room_page(push_server: str, browser: Cdp) -> None:
    assert httpx.get(push_server + "/api/push/key", timeout=5).status_code == 200, "push should be enabled with the key file"

    white = Page(browser, "player A")
    black = Page(browser, "player B")
    browser.call("Browser.grantPermissions", {"permissions": ["notifications"], "origin": push_server,
                                              "browserContextId": black.context})
    white.go(push_server + "/")
    white.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    white.click("start-game")
    code = white.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    black.go(f"{push_server}/r/{code}")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn")
    black.wait(f"{STATUS} === 'Waiting for White'", what="black seated")

    black.click("settings-notifications")
    black.wait("navigator.serviceWorker.getRegistration('/').then(r => !!(r && r.active))", what="the active worker")
    # Ask the browser directly, so a missing push service gives its own error text.
    probe = black.js(
        "(async () => { const r = await navigator.serviceWorker.getRegistration('/');"
        " const key = (await (await fetch('/api/push/key')).json()).publicKey;"
        " const raw = Uint8Array.from(atob(key.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - key.length % 4) % 4)), c => c.charCodeAt(0));"
        " try { const s = await Promise.race([r.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: raw}),"
        "   new Promise((_, no) => setTimeout(() => no(new Error('subscribe timed out after 20 s')), 20000))]);"
        "   return s.endpoint; } catch (e) { return 'error: ' + e.name + ': ' + e.message; } })()")
    if not str(probe).startswith("https://"):
        pytest.skip(f"this Chromium build could not subscribe to a push service: {probe}")
    subscribed = black.wait(
        "navigator.serviceWorker.getRegistration('/').then(r => r.pushManager.getSubscription())"
        ".then(s => s ? s.endpoint : '')", timeout=30, what="the app's push subscription")
    assert str(subscribed).startswith("https://")

    # Black leaves the room: no socket, so the server must push.
    black.go(push_server + "/learn")
    black.wait("location.pathname === '/learn'", what="black off the room page")
    time.sleep(1.0)  # let the server see the socket close
    white.move("e2e4")

    try:
        tags = black.wait(f"{WORKER_TAGS}.then(tags => tags.includes('{code}:move:1:1') ? tags : '')",
                          timeout=45, what="the pushed notification")
    except AssertionError as missing:
        pytest.fail(f"the push did not arrive within 45 s: {missing}")
    assert f"{code}:move:1:1" in tags.split()
