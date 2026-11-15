"""Prepare the checksum-verified Stockfish binary for a Vercel deployment."""

import base64
import json
from pathlib import Path
from urllib.request import Request, urlopen

import stockfish_install


ROOT = Path(__file__).resolve().parent
PLATFORM = "linux-x86_64"  # Vercel Functions default to the x86_64 architecture.
INSTALL_DIR = ROOT / ".vercel-stockfish" / PLATFORM
LICENSE_URL = f"https://raw.githubusercontent.com/official-stockfish/Stockfish/{stockfish_install.PINNED_VERSION}/Copying.txt"
LICENSE_API_URL = (
    "https://api.github.com/repos/official-stockfish/Stockfish/contents/Copying.txt"
    f"?ref={stockfish_install.PINNED_VERSION}"
)
SOURCE_URL = f"https://github.com/official-stockfish/Stockfish/tree/{stockfish_install.PINNED_VERSION}"


def fetch_license() -> bytes:
    """Fetch GPLv3 text from the immutable source tag, with GitHub API fallback."""
    failures: list[str] = []
    for url in (LICENSE_URL, LICENSE_API_URL):
        accept = "application/vnd.github+json" if url == LICENSE_API_URL else "text/plain"
        request = Request(url, headers={"User-Agent": "JustChess-Vercel-build", "Accept": accept})
        try:
            with urlopen(request, timeout=20) as response:
                content = response.read(128 * 1024 + 1)
                content_type = response.headers.get("Content-Type", "unknown")
            if len(content) > 128 * 1024:
                failures.append(f"{url}: response exceeded 128 KiB")
                continue
            if url == LICENSE_API_URL:
                payload = json.loads(content)
                if payload.get("encoding") != "base64" or payload.get("path") != "Copying.txt":
                    failures.append(f"{url}: unexpected GitHub API response")
                    continue
                content = base64.b64decode(payload["content"], validate=False)
            normalized = content.decode("utf-8-sig").lstrip()
            first_lines = "\n".join(normalized.splitlines()[:3])
            if normalized.startswith("GNU GENERAL PUBLIC LICENSE") and "Version 3" in first_lines:
                return content
            failures.append(f"{url}: unexpected {content_type} response ({len(content)} bytes)")
        except (OSError, UnicodeDecodeError, ValueError, KeyError) as exc:
            failures.append(f"{url}: {type(exc).__name__}")
    raise RuntimeError("Could not retrieve the Stockfish GPLv3 license from the pinned tag (" + "; ".join(failures) + ")")


def main() -> None:
    binary = stockfish_install.install_pinned_stockfish(INSTALL_DIR, platform=PLATFORM)
    (INSTALL_DIR / "Copying.txt").write_bytes(fetch_license())
    (INSTALL_DIR / "Source.txt").write_text(
        f"Stockfish {stockfish_install.PINNED_VERSION} corresponding source: {SOURCE_URL}\n",
        encoding="utf-8",
    )
    print(
        f"Prepared Stockfish {stockfish_install.PINNED_VERSION} for {PLATFORM} "
        f"({binary.stat().st_size} bytes; SHA-256 verified; GPLv3 license and source pointer included)"
    )


if __name__ == "__main__":
    main()
