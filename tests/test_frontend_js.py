"""Bridge the U2 frontend checks into the approved ``uv run --frozen pytest -q`` command.

* ``test_node_suite_passes`` runs the Node test suite (``node --test tests/js/``)
  and fails on a non-zero exit. It skips, saying why, when ``node`` is missing.
* ``test_demo_page_and_assets_are_served`` loads ``/static/demo/board.html``
  through the FastAPI app (TestClient, no server process) and follows every
  stylesheet, script, module import, image and CSS ``url()`` it references,
  failing on any response other than 200.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pytest
from fastapi.testclient import TestClient

from justchess.api import create_app

ROOT = Path(__file__).resolve().parent.parent
NODE_TEST_COMMAND = ["node", "--test", "tests/js/"]
NODE_TIMEOUT_SECONDS = 120
DEMO_PAGE = "/static/demo/board.html"

JS_IMPORT = re.compile(r"""^\s*import\s+(?:[^'"]*?\s+from\s+)?["']([^"']+)["']""", re.MULTILINE)
JS_ASSET_URL = re.compile(r"""new URL\(\s*["']([^"']+)["']\s*,\s*import\.meta\.url\s*\)""")
CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""")
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def test_node_suite_passes() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed, so the JavaScript tests in tests/js/ cannot run")
    result = subprocess.run(
        [node, *NODE_TEST_COMMAND[1:]],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=NODE_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, (
        f"`{' '.join(NODE_TEST_COMMAND)}` failed with exit code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


class _PageReferences(HTMLParser):
    """Collect the same-page resource URLs a browser would request."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "link" and values.get("href"):
            self.urls.append(values["href"])
        elif tag in {"script", "img"} and values.get("src"):
            self.urls.append(values["src"])


def _references(url: str, body: str) -> list[str]:
    path = urlsplit(url).path
    if path.endswith(".html"):
        parser = _PageReferences()
        parser.feed(body)
        found = parser.urls
    elif path.endswith(".js"):
        found = JS_IMPORT.findall(body) + JS_ASSET_URL.findall(body)
    elif path.endswith(".css"):
        found = [ref for ref in CSS_URL.findall(CSS_COMMENT.sub("", body)) if not ref.startswith("data:")]
    else:
        found = []
    return [urljoin(url, ref) for ref in found]


@pytest.fixture
def static_client(tmp_path, monkeypatch) -> TestClient:
    """An app on a temporary database; the lifespan is not started, so no DB or engine work runs."""
    monkeypatch.setenv("JUSTCHESS_DB", str(tmp_path / "frontend.sqlite3"))
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    return TestClient(create_app(db_path=tmp_path / "frontend.sqlite3", engine_dir=tmp_path / "engines"))


def test_demo_page_and_assets_are_served(static_client: TestClient) -> None:
    base = "http://testserver"
    queue = [base + DEMO_PAGE]
    seen: dict[str, int] = {}
    piece_bases: set[str] = set()
    while queue:
        url = queue.pop()
        if url in seen or url in piece_bases:
            continue
        if url.endswith("/"):  # a base path such as the piece folder: check its files below
            piece_bases.add(url)
            continue
        response = static_client.get(urlsplit(url).path)
        seen[url] = response.status_code
        if response.status_code == 200 and urlsplit(url).path.endswith((".html", ".js", ".css")):
            queue.extend(ref for ref in _references(url, response.text) if ref.startswith(base + "/static/"))
    assert piece_bases == {base + "/static/pieces/cburnett/"}, piece_bases
    for colour in "wb":
        for piece in "KQRBNP":
            url = f"{base}/static/pieces/cburnett/{colour}{piece}.svg"
            seen[url] = static_client.get(urlsplit(url).path).status_code
    missing = {url: status for url, status in seen.items() if status != 200}
    assert missing == {}, f"resources not served: {missing}"
    paths = {urlsplit(url).path for url in seen}
    for expected in (
        "/static/js/board/board.js",
        "/static/js/board/geometry.js",
        "/static/js/board/interaction.js",
        "/static/js/board/promotion.js",
        "/static/js/settings-panel.js",
        "/static/js/contrast.js",
        "/static/js/boot.js",
        "/static/css/tokens.css",
        "/static/fonts/atkinson-hyperlegible-latin-700-normal.woff2",
        "/static/logo.svg",
    ):
        assert expected in paths, f"{expected} was not reached from {DEMO_PAGE}"
