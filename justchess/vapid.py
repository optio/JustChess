"""VAPID keys for Web Push (U5, BR2.3, NFR3a): loading at startup and a key generator.

The private key never lives in the repository or the database. It comes from,
in this order:

- ``JUSTCHESS_VAPID_PRIVATE_KEY``: a PEM private key, or a raw base64url
  32-byte P-256 private key;
- ``JUSTCHESS_VAPID_KEY_FILE``: the path of a PEM file whose real path (symlinks
  resolved) lies outside the project folder. A file inside it is refused.

``JUSTCHESS_VAPID_SUBJECT`` (a ``mailto:`` or ``https:`` URL, default
``mailto:admin@localhost``) is the contact claim sent to push services.

When no valid key is found, ``load_vapid`` returns a disabled config and logs
one warning saying why; everything else keeps working and pages fall back to
local notifications. Key material is never logged and never part of an error
message or a ``repr``.

Key generator (writes a new PEM with mode 0600 and refuses any path inside the
project or an existing file)::

    uv run python -m justchess.vapid generate ~/.config/justchess/vapid.pem
    # then put JUSTCHESS_VAPID_KEY_FILE=<that path> in the project's .env (or export it)
"""

from __future__ import annotations

import argparse
import base64
import binascii
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid02

logger = logging.getLogger("justchess.vapid")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PRIVATE_KEY = "JUSTCHESS_VAPID_PRIVATE_KEY"
ENV_KEY_FILE = "JUSTCHESS_VAPID_KEY_FILE"
ENV_SUBJECT = "JUSTCHESS_VAPID_SUBJECT"
DEFAULT_SUBJECT = "mailto:admin@localhost"
RAW_KEY_BYTES = 32
MAX_KEY_FILE_BYTES = 16 * 1024


class VapidKeyError(ValueError):
    """A key could not be used. The message never contains key material."""


@dataclass(frozen=True)
class VapidConfig:
    """The push signing keys, loaded once at startup. ``enabled`` is False without a valid key."""

    private_key: ec.EllipticCurvePrivateKey | None = field(repr=False, default=None)
    public_key: str | None = None  # base64url uncompressed P-256 point (the applicationServerKey)
    subject: str = DEFAULT_SUBJECT
    reason: str | None = None  # why push is disabled, for the startup log

    @property
    def enabled(self) -> bool:
        """True when a private key is loaded."""
        return self.private_key is not None

    def signer(self) -> Vapid02:
        """Return a py_vapid signer for this key (raises when push is disabled)."""
        if self.private_key is None:
            raise VapidKeyError("Web Push is disabled: no VAPID key is loaded")
        return Vapid02(private_key=self.private_key)


def disabled(reason: str, subject: str = DEFAULT_SUBJECT) -> VapidConfig:
    """Return a disabled config carrying the reason."""
    return VapidConfig(None, None, subject, reason)


def public_key_b64(key: ec.EllipticCurvePrivateKey) -> str:
    """Return the base64url (unpadded) uncompressed public point of ``key``."""
    point = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(point).rstrip(b"=").decode("ascii")


def config_for(key: ec.EllipticCurvePrivateKey, subject: str = DEFAULT_SUBJECT) -> VapidConfig:
    """Return an enabled config for a private key."""
    return VapidConfig(key, public_key_b64(key), subject, None)


def _require_p256(key: object) -> ec.EllipticCurvePrivateKey:
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise VapidKeyError("the key is not a P-256 (prime256v1) elliptic-curve private key")
    return key


def parse_private_key(text: str) -> ec.EllipticCurvePrivateKey:
    """Parse a PEM private key or a raw base64url 32-byte P-256 key."""
    value = (text or "").strip()
    if not value:
        raise VapidKeyError("the key is empty")
    if "-----BEGIN" in value:
        try:
            key = serialization.load_pem_private_key(value.encode("ascii"), password=None)
        except (ValueError, TypeError, UnicodeEncodeError) as exc:
            raise VapidKeyError(f"the PEM key could not be read ({type(exc).__name__})") from None
        return _require_p256(key)
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        raise VapidKeyError("the key is neither PEM nor base64url") from None
    if len(raw) != RAW_KEY_BYTES:
        raise VapidKeyError(f"a raw key must decode to {RAW_KEY_BYTES} bytes")
    try:
        return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    except ValueError:
        raise VapidKeyError("the raw key is not a valid P-256 private key") from None


def is_inside(path: Path, root: Path) -> bool:
    """True when the real path of ``path`` (symlinks resolved) is ``root`` or below it."""
    real = Path(path).expanduser().resolve(strict=False)
    real_root = Path(root).resolve(strict=False)
    return real == real_root or real_root in real.parents


def _subject(env: Mapping[str, str]) -> str:
    subject = (env.get(ENV_SUBJECT) or "").strip()
    if not subject:
        return DEFAULT_SUBJECT
    if subject.startswith(("mailto:", "https://")) and len(subject) <= 256:
        return subject
    logger.warning("%s must be a mailto: or https:// URL; using %s", ENV_SUBJECT, DEFAULT_SUBJECT)
    return DEFAULT_SUBJECT


def _read_key_file(raw_path: str, project_root: Path) -> ec.EllipticCurvePrivateKey:
    path = Path(raw_path).expanduser()
    if is_inside(path, project_root):
        raise VapidKeyError(f"{ENV_KEY_FILE} points inside the project folder ({project_root}); "
                            "keep the key outside the repository")
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_KEY_FILE_BYTES + 1)
    except OSError as exc:
        raise VapidKeyError(f"the key file {path} could not be read ({exc.strerror or type(exc).__name__})") from None
    if len(data) > MAX_KEY_FILE_BYTES:
        raise VapidKeyError(f"the key file {path} is too large to be a PEM key")
    try:
        return parse_private_key(data.decode("ascii"))
    except UnicodeDecodeError:
        raise VapidKeyError(f"the key file {path} is not a PEM file") from None


def load_vapid(env: Mapping[str, str] | None = None, project_root: Path = PROJECT_ROOT) -> VapidConfig:
    """Load the keys from the environment (BR2.3); log one line when push ends up disabled."""
    env = os.environ if env is None else env
    subject = _subject(env)
    raw = env.get(ENV_PRIVATE_KEY)
    key_file = env.get(ENV_KEY_FILE)
    try:
        if raw:
            config = config_for(parse_private_key(raw), subject)
            logger.info("Web Push is enabled (key from %s)", ENV_PRIVATE_KEY)
            return config
        if key_file:
            config = config_for(_read_key_file(key_file, project_root), subject)
            logger.info("Web Push is enabled (key file from %s)", ENV_KEY_FILE)
            return config
    except VapidKeyError as exc:
        source = ENV_PRIVATE_KEY if raw else ENV_KEY_FILE
        reason = f"{source} was refused: {exc}"
        logger.warning("Web Push is disabled: %s. Pages fall back to local notifications.", reason)
        return disabled(reason, subject)
    reason = f"neither {ENV_PRIVATE_KEY} nor {ENV_KEY_FILE} is set"
    logger.warning("Web Push is disabled: %s. Generate a key with "
                   "`uv run python -m justchess.vapid generate ~/.config/justchess/vapid.pem` "
                   "and set %s in the project's .env file.", reason, ENV_KEY_FILE)
    return disabled(reason, subject)


# --- generator ----------------------------------------------------------------

def generate(target: Path, project_root: Path = PROJECT_ROOT) -> str:
    """Write a new PEM private key at ``target`` (mode 0600); return its public key.

    Refuses a path inside the project (symlinks resolved) and an existing file,
    before anything is written.
    """
    target = Path(target).expanduser()
    if is_inside(target, project_root):
        raise VapidKeyError(f"refusing to write a key inside the project folder ({project_root}); "
                            "choose a path such as ~/.config/justchess/vapid.pem")
    if target.exists() or target.is_symlink():
        raise VapidKeyError(f"{target} already exists; remove it first or choose another path")
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    try:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(pem)
        os.chmod(target, 0o600)
    except OSError as exc:
        raise VapidKeyError(f"could not write {target} ({exc.strerror or type(exc).__name__})") from None
    return public_key_b64(key)


def main(argv: Sequence[str] | None = None) -> int:
    """Command line: ``python -m justchess.vapid generate <path>``."""
    parser = argparse.ArgumentParser(prog="python -m justchess.vapid", description="JustChess Web Push (VAPID) keys")
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate", help="write a new private key (PEM, mode 0600) outside the project")
    make.add_argument("path", type=Path, help="where to write the key, e.g. ~/.config/justchess/vapid.pem")
    args = parser.parse_args(argv)
    try:
        public = generate(args.path)
    except VapidKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote a new VAPID private key to {args.path.expanduser()} (mode 0600).")
    print(f"Public key: {public}")
    print(f"Start the app with: export {ENV_KEY_FILE}={args.path.expanduser()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
