# Technology Stack

| Layer | Verified technology |
|---|---|
| Runtime | Python >=3.11; plain browser ES modules |
| Web | FastAPI 0.162.4, Starlette 1.10.0, Pydantic 2.14.3, Uvicorn 0.54.0, Jinja2 3.1.6 |
| Chess and content | python-chess 1.999 / chess 1.11.2; PyYAML 6.0.3 |
| Persistence | Python stdlib sqlite3, schema version 4; no ORM or PostgreSQL driver |
| Push | pywebpush 2.5.0 with VAPID/cryptography dependencies |
| Tooling | uv with uv.lock, non-packaged project; pytest 9.2.0 and httpx 0.28.1 |
| Frontend testing | Node built-in test runner; optional Chromium browser checks |
| Assets | Local fonts, chess pieces and authored QR encoder; no frontend package manifest/bundler |

Versions are selected resolved records verified in uv.lock, not an audit of every transitive record. No linter, formatter, type checker or coverage configuration is declared in pyproject.toml. Stockfish 19 release downloads are platform-selected and SHA-256 checked. Binary assets and installed engine binaries were not opened.

