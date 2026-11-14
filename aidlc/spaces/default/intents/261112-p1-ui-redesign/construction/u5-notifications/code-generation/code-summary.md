# Code Summary — u5-notifications

## Result

- `node --test tests/js/`: **130 passed**. There were 115 before this unit.
- `uv run --frozen pytest -q`: **169 passed**. There were 121 before. This includes the headless Chromium runs, among them a new one where a background tab shows the move notification with the tag `<code>:move:1:1`.
- Unit command: **53 passed**.

## Files

| Area | Files |
|---|---|
| Data | `justchess/db.py`: schema v3 with `push_subscriptions` and `alert_records` (both `ON DELETE CASCADE` to `rooms`); in-place v2→v3 upgrade in one transaction |
| Logic | `justchess/notifications.py`: subscriptions, allowlist validation, event builder, claim, fresh-visibility rule, sending with no redirects, result handling, housekeeping hook. `justchess/vapid.py`: key loading and `python -m justchess.vapid generate`, which refuses paths inside the project |
| API | `justchess/api.py`: `/api/push/key`, `/push/subscribe` (404 when push is off), `/push/unsubscribe` (endpoint required), `/sw.js`, dispatch as a background task after join, move and claims, subscriptions deleted on continue redeem. `justchess/live.py`: `last_heard`, `is_fresh_visible` |
| Client | `static/sw.js`, `static/js/notifications.js`, `static/js/notify-core.js`; wiring in `app.js`, `hooks.js`, `live.js` (sends `visible:false` on `pagehide`) and `screens/game.js` (banner); styles in `app.css` |
| Dependency | `pywebpush` 2.5.0 |
| Tests | `tests/test_notifications.py` (31), `tests/test_push_api.py` (11), `tests/js/notify-core.test.mjs` (9), `tests/js/notifications.test.mjs` (6); extended `tests/core/test_db.py` and `tests/test_game_screen.py` |
| Docs | README section "Notifications": key generation outside the repo, localhost versus HTTPS as an open decision, `JUSTCHESS_PUSH_HOSTS`, and the ADR-006 amendment |

## Decisions made during the build

- **ADR-006 amendment.** A version-2 database is upgraded in place to version 3, keeping its rooms. Databases older than version 2, or with no version mark, are still moved aside. The person's running dev server will upgrade `justchess.sqlite3` in place on its next reload.
- **Cascade delete.** Not in the plan. Both new tables cascade-delete with their room, so cleanup is safe even without the hook. The U5 hook still runs first.
- **Redirects.** They are never followed. A 3xx counts as a failed send, and only one request is made. Each send uses its own session, so concurrent sends are thread-safe.
- **Freshness rule.** Push is skipped only for a seat whose page is visible and was heard from within the last 6 s. Hidden pages always show a local notification. It shares the push's tag (`<code>:<key>`), so nothing stacks.
- **Service worker.** Its decision logic is copied from `notify-core.js`, and a test pins the two copies equal. Tapping a notification always opens `/r/<code>`; it never follows a URL from the payload.
- **Keys.** None were generated anywhere. Push stays off until the person runs the generator and sets `JUSTCHESS_VAPID_KEY_FILE`.

## Open points

- A real Web Push on localhost is a manual check for Build and Test, once keys exist.
- The U1 BR2.1 written check order is still pending.
