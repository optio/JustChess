# Reverse Engineering Timestamp

## Run Record

- Date: 2026-11-15
- Commit: 7f067bce9170c0ed6c11814c9d220a5a6a9e7844
- Source snapshot: git:6ae78113d92a97a36fbd60e54bf7d76864102847
- Store generation reviewed: sha256:73420b1b3a34b105078f9c53829ed0ee2bc1d1049355351515fef94509e71b1e

Focused Minimal scan for player identity and presentation. Existing STALE store prose outside focus is preserved as historical context; conflicting persistence statements were corrected from current source. Deep coverage below names only complete files read during this run. API continue routes, game snapshot, frontend wiring/private-link row, README and selected tests were skimmed. Prior directory coverage is demoted to shallow; overlaps indicate historical broader coverage rather than rescanning every descendant. No app edits, tests, builds, database connections, installations or publication occurred. Secrets, real DBs/backups, dependencies, generated outputs/caches and AI-DLC installation/workspace are excluded from application analysis.

## Scope of Analysis

```yaml
scope_version: 1
kind: partial
intent: player-identity-polish
fingerprint: a66ecfdba8056522eab488785d2d3114a3abe776
analyzed:
  paths:
    - justchess/db.py
    - justchess/postgres.py
    - justchess/rooms.py
    - static/js/seat-store.js
    - static/js/settings.js
    - static/js/settings-panel.js
    - static/js/boot.js
    - static/js/share.js
    - static/js/view-model.js
    - static/js/board/board.js
    - static/js/board/interaction.js
    - static/js/layout.js
    - static/js/screens/overlay.js
    - static/js/screens/win-sequence.js
    - static/css/board.css
    - static/css/tokens.css
    - templates/index.html
    - app.py
    - pyproject.toml
    - .env.example
    - tests/js/settings.test.mjs
    - tests/js/seat-store.test.mjs
  components:
    - Rooms Module
    - Page Template
    - View Model
    - Seat Store
    - Share Helpers
    - Board Component
    - Settings
    - Persistence Backend
    - Database Configuration
    - PostgreSQL Adapter
    - Account-free Identity Seam
    - Result Presentation and Motion
    - Selection and Board Theme Settings
    - Focused Browser Storage Tests
shallow:
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
    - tests/
    - README.md
    - uv.lock
    - puzzles/
    - static/demo/
    - static/ASSETS.md
```

