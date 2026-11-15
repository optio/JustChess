"""U3 game screen: the new shell, its assets, the old client's removal and the HTTP boundary.

* The shell is served at ``/`` and ``/r/{code}``; every stylesheet, script and
  module import it reaches returns 200, and every relative ``import`` in
  ``static/js`` points at a file that exists.
* The old client (``static/app.js``, ``static/style.css``) is gone.
* A full HTTP flow (create, join, state read with ``X-Seat-Token``) returns a
  snapshot with ``claimableDrawReason`` and without the legacy fields, and the
  refusals U3 depends on (409 with a watcher snapshot, the 403 seat message)
  keep their shape.
* ``test_two_player_browser_game`` drives headless Chromium over the DevTools
  protocol: two browser contexts play Fool's mate through the real UI, both
  see "Checkmate" and the overlay, and both press Play again to get a new game
  with the colours swapped. It starts its own Uvicorn on a free port with a
  temporary database, and skips with the reason when Chromium is missing
  (set ``JUSTCHESS_CHROMIUM`` to a browser binary to choose one).

U6 additions:

* ``/learn`` and ``/learn/{id}`` serve the same shell, with ``training.css``,
  and the trainer modules (``training/*``, ``room-flow.js``) are reached from it.
* ``test_lesson_trainer_browser_run`` goes from the lobby's "Train" button
  through the trainer hub (P2 U5) to ``/learn/italian``, plays the walkthrough to the end, then in
  practice plays a legal move off the line ("Legal, but not this line"), goes
  back to the line, misses until the arrow is drawn, plays the line with the
  trainer replying, and reaches "Line complete". It also opens the lessons
  drawer in a room and checks the trainer is mounted there and removed when
  the room is left.

U5 additions:

* ``notifications.js`` and ``notify-core.js`` are reached from the shell, and
  ``/sw.js`` is served from the root with ``Service-Worker-Allowed: /`` and
  imports nothing.
* ``test_background_tab_gets_a_local_notification``: notification permission is
  granted to player B's browser context through CDP, B turns Notifications on
  (the server has no VAPID keys, so this is local-only mode), B's page is put in
  the background by emulating ``document.visibilityState = "hidden"`` with a
  ``visibilitychange`` event, A plays e4, and B's service worker holds a
  notification tagged ``<code>:move:1:1``. No push service is involved.

U4 additions:

* ``blunder.js`` and ``screens/blunder-dialog.js`` are reached from the shell.
* ``test_two_player_browser_game`` turns "Warn me before blunders" off for
  White, so g4 in Fool's mate is sent with no dialog.
* ``test_blunder_dialog_browser_run``: after 1.f3 e5, White's g4 opens the
  alertdialog ("This allows checkmate", "Black can play Qh4#."); Escape cancels
  and the pawn is back on g2 with focus on it; "Play g4 anyway" sends the move.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import ExitStack
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pytest
from fastapi.testclient import TestClient

import stockfish_install
from justchess.api import create_app

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
BASE = "http://testserver"
LEGACY_FIELDS = ("moves", "legal", "white_score", "black_score", "outcome")

JS_IMPORT = re.compile(r"""^\s*(?:import|export)\s+(?:[^'"]*?\s+from\s+)?["']([^"']+)["']""", re.MULTILINE)
CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""")
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


class _Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self.module_scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "link" and values.get("href"):
            self.urls.append(values["href"])
        elif tag in {"script", "img"} and values.get("src"):
            self.urls.append(values["src"])
            if values.get("type") == "module":
                self.module_scripts.append(values["src"])


def _references(url: str, body: str) -> list[str]:
    path = urlsplit(url).path
    if path.endswith(".js"):
        found = JS_IMPORT.findall(body)
    elif path.endswith(".css"):
        found = [ref for ref in CSS_URL.findall(CSS_COMMENT.sub("", body)) if not ref.startswith("data:")]
    else:
        parser = _Refs()
        parser.feed(body)
        found = parser.urls
    return [urljoin(url, ref) for ref in found]


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A started app on a temporary database with Stockfish preparation disabled."""
    monkeypatch.setenv("JUSTCHESS_DB", str(tmp_path / "screen.sqlite3"))
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    with TestClient(create_app(db_path=tmp_path / "screen.sqlite3", engine_dir=tmp_path / "engines")) as started:
        yield started


def test_root_and_room_paths_serve_the_new_shell(client: TestClient) -> None:
    for path in ("/", "/r/ABC123", "/learn", "/learn/italian"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.text
        parser = _Refs()
        parser.feed(html)
        assert '<html lang="en">' in html
        assert '<main id="app"' in html and 'aria-live="polite"' in html
        assert parser.module_scripts == ["/static/js/app.js"], parser.module_scripts
        assert html.index("/static/js/boot.js") < html.index("/static/css/tokens.css"), "boot.js runs before the CSS"
        for sheet in ("tokens.css", "base.css", "board.css", "app.css", "training.css"):
            assert f"/static/css/{sheet}" in html
        assert "/static/app.js" not in html and "style.css" not in html, "the old client is not referenced"
        without_stylesheets = html.replace("/static/css/tokens.css", "")
        assert "token" not in without_stylesheets.lower(), "the shell carries no secret"
        assert not re.search(r"[A-Za-z0-9_-]{40,}", without_stylesheets), "no token-like value in the shell"


def test_every_asset_and_module_import_resolves(client: TestClient) -> None:
    queue, seen = [BASE + "/"], {}
    while queue:
        url = queue.pop()
        if url in seen or url.endswith("/") and url != BASE + "/":
            continue
        response = client.get(urlsplit(url).path)
        seen[url] = response.status_code
        if response.status_code == 200 and (url == BASE + "/" or urlsplit(url).path.endswith((".js", ".css"))):
            queue.extend(ref for ref in _references(url, response.text) if ref.startswith(BASE + "/static/"))
    missing = {url: status for url, status in seen.items() if status != 200}
    assert missing == {}, f"not served: {missing}"
    reached = {urlsplit(url).path for url in seen}
    for module in ("app", "api", "live", "seat-store", "view-model", "screen-state", "share", "hooks",
                   "screens/lobby", "screens/game", "screens/overlay", "screens/win-sequence",
                   "board/board", "settings", "settings-panel", "room-flow",
                   "training/trainer", "training/trainer-state", "training/arrow", "training/lessons-api",
                   "blunder", "screens/blunder-dialog", "notifications", "notify-core",
                   "training/hub", "training/hub-tabs", "training/puzzle", "training/puzzle-state",
                   "training/trainer-progress"):
        assert f"/static/js/{module}.js" in reached, f"{module}.js is not reached from the shell"
    assert "/static/css/training.css" in reached

    # every relative import in static/js resolves to a file, reached from the shell or not
    for source in sorted((STATIC / "js").rglob("*.js")):
        for ref in JS_IMPORT.findall(source.read_text(encoding="utf-8")):
            if ref.startswith("."):
                assert (source.parent / ref).resolve().is_file(), f"{source.relative_to(ROOT)} imports missing {ref}"


def test_service_worker_is_served_from_the_root(client: TestClient) -> None:
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["service-worker-allowed"] == "/" and response.headers["cache-control"] == "no-cache"
    assert response.headers["content-type"].startswith("text/javascript")
    assert not JS_IMPORT.findall(response.text) and "importScripts" not in response.text, \
        "the classic worker loads nothing else"
    assert client.get("/static/sw.js").status_code == 200, "the same file, also reachable as a static asset"


def test_old_client_files_are_gone(client: TestClient) -> None:
    assert not (STATIC / "app.js").exists()
    assert not (STATIC / "style.css").exists()
    assert client.get("/static/app.js").status_code == 404
    assert client.get("/static/style.css").status_code == 404


def test_http_flow_snapshot_has_claimable_reason_and_no_legacy_fields(client: TestClient) -> None:
    created = client.post("/api/rooms")
    assert created.status_code == 201
    a = created.json()
    b = client.post(f"/api/rooms/{a['code']}/join", json={}).json()
    assert (a["slot"], b["slot"], b["colour"]) == ("A", "B", "black")

    state = client.get(f"/api/rooms/{a['code']}", headers={"X-Seat-Token": a["token"]})
    assert state.status_code == 200
    snapshot = state.json()
    assert (snapshot["slot"], snapshot["colour"], snapshot["status"]) == ("A", "white", "playing")
    assert snapshot["claimableDraw"] is False and snapshot["claimableDrawReason"] is None
    assert "e2e4" in snapshot["legalMoves"]
    for legacy in LEGACY_FIELDS:
        assert legacy not in snapshot, f"legacy field {legacy} is still sent"

    watcher = client.get(f"/api/rooms/{a['code']}").json()  # no header: a watcher
    assert (watcher["slot"], watcher["legalMoves"]) == (None, [])
    assert client.get(f"/api/rooms/{a['code']}?token={a['token']}").json()["slot"] is None, \
        "a token in the query string is never read"


def test_refusals_keep_the_shape_the_screen_relies_on(client: TestClient) -> None:
    a = client.post("/api/rooms").json()
    client.post(f"/api/rooms/{a['code']}/join", json={})

    full = client.post(f"/api/rooms/{a['code']}/join", json={"token": "an-expired-seat-token"})
    assert full.status_code == 409
    assert full.json()["snapshot"]["slot"] is None, "room full attaches the watcher snapshot"

    refused = client.post(f"/api/rooms/{a['code']}/rematch", json={"token": "not-a-seat"})
    assert refused.status_code == 403
    app_js = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    assert f'SEAT_REFUSED = "{refused.json()["detail"]}"' in app_js, "app.js matches U1's seat refusal message"
    room_flow = (STATIC / "js" / "room-flow.js").read_text(encoding="utf-8")
    assert f'SEAT_REFUSED = "{refused.json()["detail"]}"' in room_flow, "room-flow.js matches U1's seat refusal message"

    missing = client.post("/api/rooms/ZZZZZ9/join", json={})
    assert missing.status_code == 404


# --- headless browser run -------------------------------------------------------

def _chromium() -> str | None:
    configured = os.environ.get("JUSTCHESS_CHROMIUM")
    if configured:
        return configured if Path(configured).is_file() else None
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_http(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"the test server did not answer at {url}")


class Cdp:
    """A minimal Chrome DevTools Protocol client over one browser WebSocket."""

    def __init__(self, ws) -> None:
        self.ws = ws
        self.next_id = 0
        self.events: list[dict] = []

    def call(self, method: str, params: dict | None = None, session: str | None = None, timeout: float = 15) -> dict:
        self.next_id += 1
        message = {"id": self.next_id, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        self.ws.send(json.dumps(message))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"no answer to {method}")
            reply = json.loads(self.ws.recv(timeout=remaining))
            if reply.get("id") == self.next_id:
                if "error" in reply:
                    raise AssertionError(f"{method} failed: {reply['error']}")
                return reply.get("result", {})
            self.events.append(reply)


class Page:
    """One tab in its own browser context."""

    def __init__(self, cdp: Cdp, name: str, viewport: tuple[int, int, bool] = (1280, 900, False)) -> None:
        self.cdp, self.name = cdp, name
        self.context = context = cdp.call("Target.createBrowserContext")["browserContextId"]
        target = cdp.call("Target.createTarget", {"url": "about:blank", "browserContextId": context})["targetId"]
        self.session = cdp.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        for domain in ("Runtime.enable", "Page.enable", "Log.enable"):
            cdp.call(domain, session=self.session)
        # Two tabs play at once: keep both active, never frozen or throttled as a background tab.
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, session=self.session)
        cdp.call("Page.setWebLifecycleState", {"state": "active"}, session=self.session)
        width, height, mobile = viewport
        cdp.call("Emulation.setDeviceMetricsOverride",
                 {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile}, session=self.session)

    def rect(self, selector: str) -> dict:
        return self.js(f"(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
                       " return {top: r.top, width: r.width, height: r.height}; })()")

    def go(self, url: str) -> None:
        self.cdp.call("Page.navigate", {"url": url}, session=self.session)

    def js(self, expression: str):
        result = self.cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True},
                               session=self.session)
        if "exceptionDetails" in result:
            raise AssertionError(f"{self.name}: {expression} threw {result['exceptionDetails']}")
        return result["result"].get("value")

    def wait(self, expression: str, timeout: float = 15, what: str = "") -> object:
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                last = self.js(expression)
            except AssertionError:
                last = None
            if last:
                return last
            time.sleep(0.1)
        status = self.js("document.querySelector('[data-testid=status-text]')?.textContent ?? '(no status)'")
        raise AssertionError(f"{self.name}: timed out waiting for {what or expression} (status: {status!r}; "
                             f"errors: {self.problems()})")

    def click(self, testid: str) -> None:
        self.js(f"document.querySelector('[data-testid={testid}]').click()")

    def move(self, uci: str) -> None:
        self.click(f"board-square-{uci[:2]}")
        self.click(f"board-square-{uci[2:4]}")

    def status(self) -> str:
        return self.js("document.querySelector('[data-testid=status-text]').textContent")

    def problems(self) -> list[str]:
        found = []
        for event in self.cdp.events:
            if event.get("sessionId") != self.session:
                continue
            params = event.get("params", {})
            if event.get("method") == "Runtime.exceptionThrown":
                found.append(str(params.get("exceptionDetails", {}).get("text")))
            elif event.get("method") == "Runtime.consoleAPICalled" and params.get("type") == "error":
                found.append(" ".join(str(arg.get("value", arg.get("description", ""))) for arg in params.get("args", [])))
        return found


STATUS = "(document.querySelector('[data-testid=status-text]')?.textContent || '')"  # parenthesised: === binds tighter than ||
DIALOG_HIDDEN = "document.querySelector('[data-testid=blunder-scrim]').hidden"
PIECE_ON = "(document.querySelector('[data-testid=board-square-{square}] img.piece:not(.piece-ghost)')?.dataset.shown || '')"


@pytest.fixture
def live_server(tmp_path):
    port = _free_port()
    env = {**os.environ, "STOCKFISH_AUTO_INSTALL": "0", "JUSTCHESS_DB": str(tmp_path / "browser.sqlite3")}
    env.pop("JUSTCHESS_ORIGIN", None)
    env.pop("JUSTCHESS_LESSONS_DIR", None)  # the browser run uses the shipped lessons/ folder
    for name in ("JUSTCHESS_VAPID_PRIVATE_KEY", "JUSTCHESS_VAPID_KEY_FILE"):
        env.pop(name, None)  # push stays off: the browser run uses local notifications only
    script = (
        "import sys, uvicorn; from justchess.api import create_app; "
        "uvicorn.run(create_app(db_path=sys.argv[1], engine_dir=sys.argv[2]), host='127.0.0.1', port=int(sys.argv[3]), log_level='warning')"
    )
    server = subprocess.Popen([sys.executable, "-c", script, str(tmp_path / "browser.sqlite3"), str(tmp_path / "engines"), str(port)],
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


@pytest.fixture
def browser(tmp_path):
    binary = _chromium()
    if binary is None:
        pytest.skip("headless Chromium is not installed (set JUSTCHESS_CHROMIUM to a browser binary to run this test)")
    process = subprocess.Popen(
        [binary, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={tmp_path / 'profile'}",
         "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-extensions",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
         "--disable-backgrounding-occluded-windows", "--disable-features=IntensiveWakeUpThrottling",
         "--window-size=1280,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    def stop() -> None:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        process.stderr.close()

    with ExitStack() as stack:
        stack.callback(stop)
        deadline = time.monotonic() + 30
        ws_url = None
        while time.monotonic() < deadline and ws_url is None:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            match = re.search(r"DevTools listening on (ws://\S+)", line)
            if match:
                ws_url = match.group(1)
        if ws_url is None:
            pytest.skip(f"Chromium at {binary} did not start a DevTools endpoint")
        from websockets.sync.client import connect

        ws = stack.enter_context(connect(ws_url, max_size=None, open_timeout=10))
        yield Cdp(ws)


def test_two_player_browser_game(live_server: str, browser: Cdp) -> None:
    white = Page(browser, "player A (desktop 1280 px)")
    black = Page(browser, "player B (phone 390 px)", viewport=(390, 844, True))

    white.go(live_server + "/")
    white.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    white.click("start-game")
    code = white.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    white.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="the waiting state")
    assert white.js("document.querySelector('[data-testid=room-code]').textContent") == code
    assert "token" not in white.js("location.href").lower()

    black.go(f"{live_server}/r/{code}")
    black.wait(f"{STATUS} === 'Waiting for White to move'", what="black's first status")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn")

    # BR5.1 layout: phone top bar <= 56 px, board top <= 72 px, board >= 374 px wide; desktop board 560-640 px
    assert black.rect(".topbar")["height"] <= 56
    phone_board = black.rect(".board-frame")
    assert phone_board["top"] <= 72 and phone_board["width"] >= 374, phone_board
    assert black.js("document.documentElement.scrollWidth") <= 390, "no horizontal scroll on the phone"
    assert 560 <= white.rect(".board-frame")["width"] <= 640

    # NFR6 touch targets at 390 px (loop-back 1): inside labels give squares of at least 46 px,
    # frame labels at least 44 px with the frame still 374 px or wider; desktop keeps U2's frame padding.
    square = "[data-testid=board-square-e2]"
    assert black.rect(square)["width"] >= 46 and black.rect(square)["height"] >= 46, black.rect(square)
    black.click("settings-labels-frame")
    black.wait("document.querySelector('.game-board .board-frame').dataset.labels === 'frame'", what="frame labels")
    assert black.rect(square)["width"] >= 44 and black.rect(square)["height"] >= 44, black.rect(square)
    assert black.rect(".board-frame")["width"] >= 374, black.rect(".board-frame")
    assert black.js("document.documentElement.scrollWidth") <= 390, "no horizontal scroll with frame labels"
    black.click("settings-labels-inside")
    black.wait("document.querySelector('.game-board .board-frame').dataset.labels === 'inside'", what="inside labels")
    assert black.rect(".topbar [data-testid=home-link]")["height"] >= 44
    assert white.js("getComputedStyle(document.querySelector('.game-board .board-frame')).paddingLeft") == "6px"

    # U4: with "Warn me before blunders" off, g4?? is sent with no dialog
    white.click("settings-blunderWarnings")
    assert white.js("document.querySelector('[data-testid=settings-blunderWarnings]').checked") is False

    for mover, waiter, uci, expected in (
        (white, black, "f2f3", "Your move"),
        (black, white, "e7e5", "Your move"),
        (white, black, "g2g4", "Your move"),
    ):
        mover.move(uci)
        waiter.wait(f"{STATUS} === '{expected}'", what=f"the turn after {uci}")
    assert white.js(DIALOG_HIDDEN), "no blunder dialog with the setting off"
    black.move("d8h4")

    for page in (white, black):
        page.wait(f"{STATUS} === 'Game over — Checkmate'", what="checkmate in the status")
        page.wait("!document.querySelector('[data-testid=overlay]').hidden", timeout=20, what="the overlay")
        assert page.js("document.querySelector('[data-testid=overlay-title]').textContent") == ("You won!" if page is black else "You lost")
        assert "Black wins with Qh4#" in page.js("document.querySelector('[data-testid=overlay-subtitle]').textContent")
        assert page.js("document.querySelector('[data-testid=result]').textContent") == "0–1"
        assert page.js("document.activeElement?.dataset.testid") == "play-again", "focus moves to Play again"
    assert white.js("document.querySelector('[data-testid=score]').textContent") == "Room score: You 0 · Opponent 1 · Draws 0"

    white.click("play-again")
    white.wait("document.querySelector('[data-testid=play-again]').textContent === 'Waiting for opponent'", what="white's waiting button")
    black.wait("document.querySelector('[data-testid=play-again]').textContent === 'Play again (your opponent is ready)'",
               what="black seeing the opponent ready")
    black.click("play-again")

    for page in (white, black):
        page.wait("document.querySelector('[data-testid=overlay]').hidden", what="the overlay closing")
        page.wait("document.querySelector('[data-testid=result]').textContent === ''", what="a clean scoresheet")
    black.wait(f"{STATUS} === 'Your move'", what="black playing white in game 2")
    white.wait(f"{STATUS} === 'Waiting for White to move'", what="white playing black in game 2")
    assert white.js("document.querySelector('.board-row .sq').dataset.square") == "h1", "player A's board is flipped"
    assert black.js("document.querySelector('.board-row .sq').dataset.square") == "a8"
    assert white.js("document.querySelector('[data-testid=players]').textContent") == "Opponent plays White · You play Black"
    assert white.js("document.querySelector('[data-testid=score]').textContent") == "Room score: You 0 · Opponent 1 · Draws 0"

    for page in (white, black):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


def test_blunder_dialog_browser_run(live_server: str, browser: Cdp) -> None:
    """U4: after 1.f3 e5, White's g4 opens the dialog; Escape cancels, "Play g4 anyway" sends it."""
    white = Page(browser, "player A (desktop 1280 px)")
    black = Page(browser, "player B (phone 390 px)", viewport=(390, 844, True))
    white.go(live_server + "/")
    white.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    white.click("start-game")
    code = white.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    black.go(f"{live_server}/r/{code}")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn")
    assert white.js("document.querySelector('[data-testid=settings-blunderWarnings]').checked") is True, "on by default"

    white.move("f2f3")
    black.wait(f"{STATUS} === 'Your move'", what="black's turn")
    black.move("e7e5")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn after e5")

    # g4 allows Qh4#: the dialog asks first, with focus on the safe default
    white.move("g2g4")
    white.wait(f"!{DIALOG_HIDDEN}", what="the blunder dialog")
    dialog = white.js("(() => { const d = document.querySelector('[data-testid=blunder-dialog]');"
                      " return {role: d.getAttribute('role'), modal: d.getAttribute('aria-modal'),"
                      " title: document.getElementById(d.getAttribute('aria-labelledby')).textContent,"
                      " body: document.getElementById(d.getAttribute('aria-describedby')).textContent,"
                      " confirm: document.querySelector('[data-testid=blunder-confirm]').textContent,"
                      " focused: document.activeElement.dataset.testid,"
                      " height: document.querySelector('[data-testid=blunder-cancel]').getBoundingClientRect().height}; })()")
    assert dialog == {"role": "alertdialog", "modal": "true", "title": "This allows checkmate", "body": "Black can play Qh4#.",
                      "confirm": "Play g4 anyway", "focused": "blunder-cancel", "height": dialog["height"]}, dialog
    assert dialog["height"] >= 44

    # Escape cancels: the pawn slides back to g2, focus returns to it, nothing was sent
    white.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape",
                                              "windowsVirtualKeyCode": 27}, session=white.session)
    white.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape",
                                              "windowsVirtualKeyCode": 27}, session=white.session)
    white.wait(DIALOG_HIDDEN, what="the dialog closing on Escape")
    white.wait(f"{PIECE_ON.format(square='g2')} === 'P' && {PIECE_ON.format(square='g4')} === ''", what="the pawn back on g2")
    assert white.js("document.activeElement?.dataset.square") == "g2", "focus returns to the from-square"
    assert white.status() == "Your move"
    assert black.status() == "Waiting for White to move"

    # "Play g4 anyway" sends the move
    white.move("g2g4")
    white.wait(f"!{DIALOG_HIDDEN}", what="the dialog again")
    white.click("blunder-confirm")
    white.wait(DIALOG_HIDDEN, what="the dialog closing on confirm")
    black.wait(f"{STATUS} === 'Your move'", what="black's turn after g4")
    assert black.js(PIECE_ON.format(square="g4")) == "P"
    black.move("d8h4")  # the mating move itself is never warned
    white.wait(f"{STATUS} === 'Game over — Checkmate'", what="checkmate")
    assert black.js(DIALOG_HIDDEN)
    for page in (white, black):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"


TRAINER_MESSAGE = "(document.querySelector('[data-testid=trainer-message]')?.textContent || '')"
TRAINER_PROMPT = "(document.querySelector('[data-testid=trainer-prompt]')?.textContent || '')"
YOUR_MOVE = f"{TRAINER_PROMPT} === 'Your move as White.'"


def test_lesson_trainer_browser_run(live_server: str, browser: Cdp) -> None:
    page = Page(browser, "learner (desktop 1280 px)")

    # the lobby's "Train" button opens the hub (P2 U5) on Openings; a lesson row's Learn updates the address
    page.go(live_server + "/")
    page.wait("!!document.querySelector('[data-testid=learn-opening]')", what="the lobby's learn button")
    page.click("learn-opening")
    page.wait("location.pathname === '/learn' && !!document.querySelector('[data-testid=hub-action-italian]')",
              what="the hub's opening list")
    assert page.js("document.querySelector('[data-testid=hub-tab-openings]').getAttribute('aria-selected')") == "true"
    page.click("hub-action-italian")
    page.wait("location.pathname === '/learn/italian'", what="the lesson address")
    page.wait("document.querySelector('[data-testid=trainer-name]')?.textContent === 'Italian Game'", what="the lesson")

    # walkthrough to the end: Next is disabled there, and every move's note is on the scoresheet
    for _ in range(7):
        page.click("trainer-next")
    page.wait("document.querySelector('[data-testid=trainer-next]').disabled", what="the end of the walkthrough")
    assert page.js("document.querySelectorAll('[data-testid=trainer-sheet-rows] tr').length") == 7
    assert page.js(f"{TRAINER_MESSAGE}.startsWith('4. c3: ')")
    assert page.js("document.querySelector('[data-testid=board-square-c3] img.piece').dataset.shown") == "P"

    # practice: a legal move off the line is shown, then back to the line
    page.click("trainer-practise")
    page.wait(YOUR_MOVE, what="the learner's first move")
    page.move("d2d4")
    page.wait(f"{TRAINER_MESSAGE} === 'Legal, but not this line'", what="the off-line message")
    page.wait("!document.querySelector('[data-testid=trainer-keep-playing]').disabled", what="the off-line position")
    assert page.js("document.querySelector('[data-testid=board-square-d4] img.piece')?.dataset.shown") == "P", \
        "the off-line move is shown on the board"
    page.click("trainer-back-to-line")
    page.wait(YOUR_MOVE, what="the way back to the line")
    assert page.js("!document.querySelector('[data-testid=board-square-d4] img.piece')"), "the lesson position is back"

    # two illegal taps make three misses on this step: the arrow and the expected move appear
    for _ in range(2):
        page.move("e2e5")
    page.wait(f"{TRAINER_MESSAGE}.startsWith('The move is e4.')", what="the expected move after 3 misses")
    assert page.js("document.querySelector('[data-testid=trainer-arrow] g')?.dataset.uci") == "e2e4"
    assert page.js("getComputedStyle(document.querySelector('[data-testid=trainer-arrow]')).pointerEvents") == "none"

    # the line itself, with the trainer replying to each move
    for uci, reply in (("e2e4", "1… e5"), ("g1f3", "2… Nc6"), ("f1c4", "3… Bc5")):
        page.move(uci)
        page.wait(f"{TRAINER_MESSAGE}.startsWith('Black plays {reply}:')", what=f"the trainer's reply {reply}")
        page.wait(YOUR_MOVE, what=f"the learner's turn after {reply}")
    assert page.js("document.querySelector('[data-testid=trainer-arrow]').childElementCount") == 0, "the arrow is gone"
    page.move("c2c3")
    page.wait(f"{TRAINER_MESSAGE}.startsWith('Line complete')", what="the end of the line")
    assert page.js("!document.querySelector('[data-testid=trainer-objectives]').hidden")
    assert page.js("document.querySelector('[data-testid=trainer-practise-other]').textContent") == "Practise as Black"
    assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"

    # the drawer in a room holds its own trainer, removed when the room is left
    player = Page(browser, "player with the drawer (phone 390 px)", viewport=(390, 844, True))
    player.go(live_server + "/")
    player.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    player.click("start-game")
    player.wait(f"{STATUS}.startsWith('Waiting for your opponent')", what="the room")
    assert player.js("document.querySelector('[data-testid=lessons-mount]').childElementCount") == 0, \
        "the trainer is mounted only when the drawer opens"
    player.js("document.querySelector('[data-testid=lessons]').open = true")
    player.wait("!!document.querySelector('[data-testid=lessons-mount] [data-testid=lesson-option-monte-carlo]')",
                what="the trainer in the drawer")
    player.click("lesson-option-monte-carlo")
    player.wait("document.querySelector('[data-testid=lessons-mount] [data-testid=trainer-name]')?.textContent"
                " === 'French Exchange: Monte Carlo Variation'", what="the lesson in the drawer")
    assert player.js("location.pathname").startswith("/r/"), "choosing a lesson in the drawer keeps the room address"
    width = player.js("document.querySelector('[data-testid=lessons-mount] [data-testid=trainer-board]').getBoundingClientRect().width")
    assert 300 <= width <= 480, width
    assert player.js("document.documentElement.scrollWidth") <= 390, "no horizontal scroll with the drawer open"
    player.click("home-link")
    player.wait("!document.querySelector('[data-testid=trainer]')", what="the drawer trainer being removed")
    assert player.problems() == [], f"{player.name} logged errors: {player.problems()}"


GO_BACKGROUND = (
    "(() => { Object.defineProperty(document, 'visibilityState', {configurable: true, get: () => 'hidden'});"
    " Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});"
    " document.dispatchEvent(new Event('visibilitychange')); return document.visibilityState; })()"
)
WORKER_TAGS = ("navigator.serviceWorker.getRegistration('/')"
               ".then(r => r ? r.getNotifications() : []).then(list => list.map(n => n.tag).join(' '))")


def test_background_tab_gets_a_local_notification(live_server: str, browser: Cdp) -> None:
    """U5: B's page in the background gets a service-worker notification tagged <code>:move:1:1."""
    white = Page(browser, "player A (desktop 1280 px)")
    black = Page(browser, "player B (background tab)")
    browser.call("Browser.grantPermissions", {"permissions": ["notifications"], "origin": live_server,
                                              "browserContextId": black.context})

    white.go(live_server + "/")
    white.wait("!!document.querySelector('[data-testid=start-game]')", what="the lobby")
    white.click("start-game")
    code = white.wait("(location.pathname.match(/^\\/r\\/([A-Z0-9]{6})$/) || [])[1]", what="the room address")
    black.go(f"{live_server}/r/{code}")
    white.wait(f"{STATUS} === 'Your move'", what="white's turn")
    black.wait(f"{STATUS} === 'Waiting for White to move'", what="black's first status")

    # turning Notifications on: permission is already granted, the server has no VAPID key -> local only
    black.click("settings-notifications")
    black.wait("document.querySelector('[data-testid=settings-notifications]').checked"
               " && !document.querySelector('[data-testid=settings-notifications]').disabled", what="the switch on")
    assert black.js("document.querySelector('[data-testid=settings-alert]').textContent") == ""
    black.wait("navigator.serviceWorker.getRegistration('/').then(r => !!(r && r.active))", what="the active worker")
    assert black.js("fetch('/api/push/key').then(r => r.status)") == 404

    assert black.js(GO_BACKGROUND) == "hidden"
    white.move("e2e4")
    black.wait(f"{STATUS} === 'Your move'", what="black's turn in the background page")
    tags = black.wait(f"{WORKER_TAGS}.then(tags => tags.includes('{code}:move:1:1') ? tags : '')",
                      what="the worker's notification")
    assert tags.split() == [f"{code}:move:1:1"], tags
    assert black.js("document.querySelector('[data-testid=notify-banner]').hidden"), "a hidden page shows no banner"
    assert black.js("sessionStorage.getItem('justchess.notify.shown.v1')") == json.dumps([f"{code}:move:1:1"]).replace(" ", "")

    # back in front, Black's reply makes White's visible page show its banner instead
    black.move("e7e5")
    white.wait("!document.querySelector('[data-testid=notify-banner]').hidden"
               " && document.querySelector('[data-testid=notify-banner]').textContent === 'Your move'",
               what="white's in-page banner")
    for page in (white, black):
        assert page.problems() == [], f"{page.name} logged errors: {page.problems()}"
