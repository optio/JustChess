# Reverse Engineering Timestamp

## Run Record

- Date: 2026-11-13T14:02:42Z
- Commit: 50e87bdd5a4e3ad22903a8d49df32a0718a2853c

Focused scan at Standard depth for intent `261113-p2-features`, merged into a STALE store (the previous full scan, by intent `p1-ui-redesign` on 2026-11-12, described the pre-redesign two-file app). Deep analysis covered the backend package, the entry point, the installer, the page template, the lesson files, all browser modules, the stylesheets and the service worker, as on disk: nearly all of it is uncommitted (`justchess/`, `static/js/`, `static/css/`, `static/sw.js`, `lessons/` and `stockfish_install.py` untracked; `app.py` and `templates/index.html` modified). During the scan `app.py`, `justchess/envfile.py` (new), `justchess/vapid.py`, `tests/test_envfile.py` and `.env.example` changed on disk; the artifacts describe the state after those edits. Skimmed only: `tests/`, `pyproject.toml`, `README.md`, `uv.lock` (searched for one package), `static/demo/`, `static/ASSETS.md`. The previous run's whole-repository deep coverage could not be re-verified and is recorded as shallow. Left out unopened: `.venv/`, every `__pycache__/`, `.pytest_cache/`, `.engines/`, `.git/`, `justchess.sqlite3`, `justchess.sqlite3.old`, `.env`, the binary assets in `static/fonts/` and `static/pieces/`, and AI-DLC's own install. No tests, builds or programs were run.

## Scope of Analysis

```yaml
scope_version: 1
kind: partial
intent: 261113-p2-features
fingerprint: 44459ac9b4045738fe10ef7485be570234245a3f
analyzed:
  paths:
    - justchess/
    - static/js/
    - static/css/
    - static/sw.js
    - templates/
    - lessons/
    - app.py
    - stockfish_install.py
  components:
    - Env File Loader
    - App Entry Point
    - App Factory and Services
    - Game API
    - Lesson API
    - Push API
    - Engine Status API
    - Rooms Module
    - Games Module
    - Live Hub
    - Persistence (SQLite)
    - Housekeeping
    - Security Middleware
    - Blunder Analysis
    - Lesson Store
    - Lesson Files
    - Notifications Service
    - VAPID Keys
    - Stockfish Installer
    - Page Template
    - App Shell and Router
    - HTTP Client
    - Live Client
    - Room Flow
    - Screen State
    - View Model
    - Seat Store
    - Share Helpers
    - Hooks
    - Board Component
    - Lobby Screen
    - Game Screen
    - Blunder Warnings UI
    - Settings
    - Notifications Client
    - Service Worker
    - Opening Trainer
    - Contrast Audit
    - Stylesheets
shallow:
  paths:
    - ./
    - uv.lock
    - tests/
    - pyproject.toml
    - README.md
    - static/demo/
    - static/ASSETS.md
```
