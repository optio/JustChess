# Technology Stack

> Historical baseline retained from earlier scans. The Current footer sections below supersede conflicting identity/presentation statements. Outside-focus prose is preserved, not newly verified.

| Layer | Verified technology |
|---|---|
| Runtime | Python >=3.11; plain browser ES modules |
| Web | FastAPI 0.162.4, Starlette 1.10.0, Pydantic 2.14.3, Uvicorn 0.54.0, Jinja2 3.1.6 |
| Chess and content | python-chess 1.999 / chess 1.11.2; PyYAML 6.0.3 |
| Persistence | Python stdlib sqlite3 or psycopg[binary]>=3.2,<4, schema version 4; no ORM |
| Push | pywebpush 2.5.0 with VAPID/cryptography dependencies |
| Tooling | uv with uv.lock, non-packaged project; pytest 9.2.0 and httpx 0.28.1 |
| Frontend testing | Node built-in test runner; optional Chromium browser checks |
| Assets | Local fonts, chess pieces and authored QR encoder; no frontend package manifest/bundler |

Versions are selected resolved records verified in uv.lock, not an audit of every transitive record. No linter, formatter, type checker or coverage configuration is declared in pyproject.toml. Stockfish 19 release downloads are platform-selected and SHA-256 checked. Binary assets and installed engine binaries were not opened.


## Current focused verification

pyproject.toml retains Python >=3.11, uv package=false and pytest configuration; psycopg is now declared. Other resolved version numbers above are retained prior-store information, not refreshed from uv.lock in this scan. No profanity or confetti dependency is currently declared; browser Web Animations implements existing game motion.


## Current footer technologies

Plain ES modules and DOM APIs; native dialog.showModal is already used by sharing. Clipboard API copies private links; CSS flex wrapping styles current footer. Node built-in tests cover the client and pytest-driven Chromium checks cover real interaction. No new dependency is needed to match existing modal/icon patterns. Manifest, backend schema and lock versions above remain historical outside-focus context.

