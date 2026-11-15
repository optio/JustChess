# Reverse Engineering Timestamp

## Run Record

- Date: 2026-11-15
- Commit: dea733e7c58ba3cd77ff83b949bad7af51149469
- Source snapshot: git:313ee8a3022a241d0717b454c0b7ab4a38575bac
- Store generation reviewed: sha256:bd927864438cdec34b4c7d530d9b3dc21671a490d6a7feb6bb6f38a62f175403

Minimal focused footer scan. Six complete files below were deeply read; app.css footer/dialog sections, app.js mount/startup references, game resign-confirm references and README player-help excerpts were skimmed. Existing STALE store outside-focus prose is preserved as historical baseline; current footer sections supersede earlier identity absence findings. Prior deep paths are demoted to shallow. No application edits, tests/builds, database access, lifecycle commands, comparison or publication occurred. Secrets, real databases/backups, framework/workspace, ignored dependencies, generated outputs and caches were excluded.

## Scope of Analysis

```yaml
scope_version: 1
kind: partial
intent: compact-player-footer
fingerprint: d4ad79d171a08cf4808f2819102168c15d3dc5b6
analyzed:
  paths:
    - templates/index.html
    - static/js/player-identity.js
    - static/js/share-dialog.js
    - static/js/screens/blunder-dialog.js
    - tests/js/player-identity.test.mjs
    - tests/test_player_identity_browser.py
  components:
    - Player Identity Client
    - Player Footer
    - Modal Patterns
    - Player Footer Regression Tests
shallow:
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
    - justchess/
    - static/js/
    - static/css/
    - static/sw.js
    - templates/
    - lessons/
    - endgames/
    - stockfish_install.py
    - scripts/curate_puzzles.py
    - gameplay.yaml
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

