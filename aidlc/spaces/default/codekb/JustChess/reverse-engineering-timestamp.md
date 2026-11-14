# Reverse Engineering Timestamp

## Run Record

- Date: 2026-11-14
- Commit: e6b8274f317f40420804aaac30b142439a5424a8
- Source snapshot: git:2ec937281d09e51a4da301de9b31b56ec5a9c86c
- Store generation reviewed: sha256:58db062a5924e6b45ab9a59a1d1526f8ebb9da52e8d2132bb66ed63c453dc65c

Application-wide runtime rescan replaces prior historical prose with current verified findings. All backend modules, frontend ES modules, authored styles, template, lesson/endgame content, installer, curator and listed configuration were read. Database and environment tests were deeply read; remaining tests, generated puzzle rows, binary assets and demo files received inventory/selected-reference coverage only. Selected dependency records and README operational sections were inspected. Consequently coverage is explicitly partial rather than claiming every root file was deeply analyzed. No application edits, tests, builds, database access, installation or publication occurred. Secrets, local database files, dependencies, caches and AI-DLC framework/workspace are excluded.

## Scope of Analysis

```yaml
scope_version: 1
kind: partial
intent: postgresql-support
fingerprint: 171b70a6d100c9743a33e3ff7945ab17d8f06c6e
analyzed:
  paths:
    - justchess/
    - static/js/
    - static/css/
    - static/sw.js
    - templates/
    - lessons/
    - endgames/
    - app.py
    - stockfish_install.py
    - scripts/curate_puzzles.py
    - gameplay.yaml
    - pyproject.toml
    - .env.example
    - tests/core/test_db.py
    - tests/core/conftest.py
    - tests/test_envfile.py
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
    - Persistence Backend
    - Database Configuration
    - Room Persistence Rules
    - Game Persistence Rules
    - Room Summaries
    - Persistence Regression Tests
    - Engine
    - Computer Coordination
    - Gameplay Settings
    - Rate Limiter
    - Puzzle Store
    - Puzzle Trainer
    - Endgame Store
    - Endgame Trainer
    - Trainer Hub
    - Trainer Progress
    - Share Dialog and QR
    - Curation Tool
shallow:
  paths:
    - tests/
    - README.md
    - uv.lock
    - puzzles/
    - static/demo/
    - static/ASSETS.md
    - static/fonts/
    - static/pieces/
```

