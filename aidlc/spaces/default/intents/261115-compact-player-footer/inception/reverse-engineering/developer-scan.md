## Developer Code Scan Results

### Scan Coverage

**Analyzed deeply:**
- templates/index.html
- static/js/player-identity.js
- static/js/share-dialog.js
- static/js/screens/blunder-dialog.js
- tests/js/player-identity.test.mjs
- tests/test_player_identity_browser.py

**Skimmed only:** static/css/app.css footer/dialog sections; static/css/base.css focus/control references; static/js/app.js footer mount/startup; screens/game.js resign-confirm references; README player-help excerpts. Existing CodeKB nine artifacts read for focused merge; prior deep coverage demoted.

**Left out:** backend and unrelated application areas; .env/private data/real DBs; framework/workspace, ignored dependencies, installed engines, caches and generated outputs. No broad rescan.

### Packages Found

Static ES-module client, shared Jinja2 template and CSS; Node client tests and pytest-driven Chromium tests. Backend is outside focus.

### Build System

Existing uv/pytest and Node built-in runner retained from prior store. No manifest/dependency refresh, installs, builds or program execution.

### APIs Discovered

player-identity.js provides createPlayerIdentity and mountPlayerFooter; client uses POST /api/player create/profile/restore/seats/nickname/regenerate with X-Player-Token, no-store and same-origin credentials. nickname and regenerate return operation answers; onChange requests footer rendering. No new endpoint is indicated for this UI task.

### Frameworks & Libraries

Plain DOM/ES modules, Clipboard API and native dialog.showModal precedent; custom alertdialog precedent. No additional library is needed to follow existing patterns. Backend/package versions retained as historical context only.

### Test Coverage

Deeply read tests/js/player-identity.test.mjs and tests/test_player_identity_browser.py. Node tests cover bounded recovery fragment, restoration, secrecy and regeneration preserving token; browser checks cover nickname save, cross-device recovery and link revocation. Browser regeneration currently overrides window.confirm, so it will not exercise the replacement modal unchanged. No tests ran or current pass count/coverage claim.

### Code Quality Indicators

Small identity client with injected effects; textContent for statuses; private URL isolated from public room sharing. Footer controller has no explicit edit/saved/pending state or async duplicate guard. Existing modal controllers establish focus containment, cancellation and focus return. Styling is broad wrapped rows with paragraph margins, not compact grouped controls. CI/lint/config outside focus.

### Technical Debt Signals

- templates/index.html:65–78 is the real persistent footer, separate from routed main; nickname input always editable and Save nickname is a separate submit.
- player-identity.js:95 onward binds footer; render avoids clobbering the focused input but cannot represent saved readonly versus active edit.
- Save my player anchor and Copy private link button address the same recovery URL; preserve a bookmarkable/fallback link while clarifying the main action.
- Regenerate at player-identity.js:118 uses win.confirm; replacement must retain warning that old bookmarks stop working and existing devices stay connected.
- Share modal supplies native inertness, Tab wrap, Escape/backdrop close and trigger focus return; blunder alertdialog supplies safe Cancel focus and captured Escape. Both have game-specific dependencies; only interaction patterns need carry over.
- app.css:666–670 controls footer rows/gaps/margins and 44px input; only these relevant style sections were inspected.
- Browser tests depend on player-save/player-link and direct field editing; update them for readonly/pencil, inline save and real modal actions.
- Async errors should retain editable input; pending actions should not duplicate requests; render/status updates should not erase useful error feedback.

## Handoff Summary

- Scope is the existing footer and presentation controller. Compact layout, inline accessible save icon, saved readonly nickname/pencil editing and regeneration modal can reuse current identity operations.
- Preserve private recovery/bookmark/copy fallback, old-link warning and session-retention semantics. No backend/schema change is indicated.
- Nine focused merged candidates are staged; scope-draft-JustChess.md mirrors the timestamp for conductor comparison. Outside-focus prose preserved as historical baseline.
- No app edits, tests/builds, comparison, publication, lifecycle or approval gates performed.

