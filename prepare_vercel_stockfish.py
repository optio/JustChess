"""Prepare the checksum-verified Stockfish binary for a Vercel deployment."""

from pathlib import Path
from urllib.request import urlopen

import stockfish_install


ROOT = Path(__file__).resolve().parent
PLATFORM = "linux-x86_64"  # Vercel Functions default to the x86_64 architecture.
INSTALL_DIR = ROOT / ".vercel-stockfish" / PLATFORM
LICENSE_URL = f"https://raw.githubusercontent.com/official-stockfish/Stockfish/{stockfish_install.PINNED_VERSION}/Copying.txt"
SOURCE_URL = f"https://github.com/official-stockfish/Stockfish/tree/{stockfish_install.PINNED_VERSION}"


def main() -> None:
    binary = stockfish_install.install_pinned_stockfish(INSTALL_DIR, platform=PLATFORM)
    with urlopen(LICENSE_URL, timeout=20) as response:
        license_text = response.read(128 * 1024 + 1)
    if len(license_text) > 128 * 1024 or not license_text.startswith(b"GNU GENERAL PUBLIC LICENSE"):
        raise RuntimeError("Could not retrieve the Stockfish GPLv3 license")
    (INSTALL_DIR / "Copying.txt").write_bytes(license_text)
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
