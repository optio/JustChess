# Dependencies

The entry point depends on envfile and the API factory. API composition depends on room/game persistence, summaries, live hub, security, limiter, catalogs, engine/computer coordination, analysis and notifications. Rooms calls game helpers; games uses python-chess and caller-owned connections. Notifications and housekeeping also execute database operations, so database adaptation is broader than db.py.

Runtime declared packages are FastAPI with standard extras, Uvicorn, Jinja2, python-chess, PyYAML, pywebpush and python-multipart. Tests use pytest and httpx. requests, cryptography and py_vapid are imported through the installed push dependency chain; python-multipart appears unused by current JSON routes. No psycopg or SQLAlchemy is declared.

Frontend modules import local HTTP, state, storage, board, dialog and training helpers. The server embeds gameplay configuration; no CDN or external JavaScript service is required. Web push makes HTTPS requests only to validated provider destinations, without redirects. Engine download is optional; an existing executable can be configured or discovered. Puzzle curation is an offline tool consuming a local external CSV dump, not a request-time dependency.

