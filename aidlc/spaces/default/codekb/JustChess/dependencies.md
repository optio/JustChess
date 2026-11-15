# Dependencies

> Historical baseline retained from earlier scans. The Current footer sections below supersede conflicting identity/presentation statements. Outside-focus prose is preserved, not newly verified.

The entry point depends on envfile and the API factory. API composition depends on room/game persistence, summaries, live hub, security, limiter, catalogs, engine/computer coordination, analysis and notifications. Rooms calls game helpers; games uses python-chess and caller-owned connections. Notifications and housekeeping also execute database operations, so database adaptation is broader than db.py.

Runtime declared packages are FastAPI with standard extras, Uvicorn, Jinja2, python-chess, PyYAML, pywebpush and python-multipart. Tests use pytest and httpx. requests, cryptography and py_vapid are imported through the installed push dependency chain; python-multipart appears unused by current JSON routes. psycopg[binary]>=3.2,<4 is now declared; no SQLAlchemy is declared.

Frontend modules import local HTTP, state, storage, board, dialog and training helpers. The server embeds gameplay configuration; no CDN or external JavaScript service is required. Web push makes HTTPS requests only to validated provider destinations, without redirects. Engine download is optional; an existing executable can be configured or discovered. Puzzle curation is an offline tool consuming a local external CSV dump, not a request-time dependency.


## Focused dependency adjacency

- app.py -> envfile, API factory, db path resolver; startup resolves DATABASE_URL.
- db.py -> postgres adapter -> psycopg; rooms.py -> games and caller-owned connection.
- view-model.js -> computer.js, pass-along.js; overlay/win-sequence consume its derived result data through app.js.
- board.js -> geometry.js, interaction.js, promotion.js, gameplay.js; board.css uses tokens.css.
- settings-panel.js -> settings.js; boot.js independently duplicates settings keys/allowlists for first paint.
- share.js constructs invite/continue URLs; seat-store.js validates fragments and persists room capabilities.

A moderation dependency/service choice is unresolved. Keep nickname normalization and enforcement consistent at server boundaries; client-only filtering would be bypassable. Do not send private recovery links through public invite sharing destinations.


## Current footer dependencies

- player-identity.js -> seat-store.safeStorage; injected fetch/storage/seats/onChange; mount controller -> document, window, clipboard and currently window.confirm.
- app.js -> createPlayerIdentity/mountPlayerFooter; onChange -> footer.render (skimmed integration).
- template -> app.css footer selectors and player data-testid hooks.
- share-dialog.js -> share helpers and lazy QR module; blunder dialog -> game-specific CHOICES. Use their interaction patterns without coupling footer confirmation to unrelated sharing/board flows.

No backend dependency change is indicated for this presentation-only task.

