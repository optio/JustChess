# Notification Rules — u5-notifications

These rules apply U5's rows of `inception/units-generation/unit-of-work-story-map.md`, taken from `inception/requirements-analysis/requirements.md`. They follow the Notifications component in `inception/domain-design/components.md` and the one-alert-per-event ADR in `inception/domain-design/decisions.md`. The data is defined in `entities.md`.

```yaml
rules:
  # BR1 — Which events alert whom
  - id: BR1.1
    statement: Three events produce alerts. When seat B joins, seat A gets "Your opponent has joined". When a move is played, the opponent of the mover gets "Your move" with the move. When a game ends, the seat that did not cause the end gets "Game over" with the reason. Nothing else alerts.
    category: policy
    applies_to: AlertEvent
    trigger: after the HttpApi transaction for join, move, claim-draw or claim-win commits
    logic: joined → target A, key "joined"; move → target = other slot, key "move:<game>:<ply>"; game ended by a move → target = other slot, key "ended:<game>" (instead of the move alert, so the final move alerts once); claim → target = other slot, key "ended:<game>"
    violation: n/a
    source: FR6.1, FR6.2, FR6.8
  - id: BR1.2
    statement: An alert key is claimed before anything is sent, and a key that is already claimed is never sent again.
    category: constraint
    applies_to: AlertRecord
    trigger: each AlertEvent
    logic: INSERT OR IGNORE (room, slot, key) status claimed; IF no row was inserted THEN stop
    violation: the second attempt does nothing
    source: FR6.6, FR6.8
  - id: BR1.3
    statement: Web Push is sent only when the target seat has no connected socket, or none of its sockets reports a visible page. Otherwise the claim is marked skipped, because the open page shows its own banner.
    category: policy
    applies_to: push send
    trigger: after a claim
    logic: read presence and visibility from LiveUpdates; connected AND visible → status skipped; else send to each subscription of the seat
    violation: n/a
    source: FR6.4, FR6.5, FR6.6
  - id: BR1.4
    statement: A claim is marked sent only after the push service accepts at least one send (HTTP 2xx). When the push service answers 404 or 410, that subscription is deleted. Any other failure marks the claim failed and is logged without the endpoint. There are no retries in P1.
    category: policy
    applies_to: push send
    trigger: push response
    logic: any 2xx → sent; 404/410 → delete subscription; all subscriptions failed → failed
    violation: n/a
    source: FR6.7, FR6.8

  # BR2 — Subscriptions and keys
  - id: BR2.1
    statement: Only a seat can subscribe, and only for itself. The endpoint must be an https URL whose host is a public DNS name, and the keys must be base64url of the expected lengths. Each seat keeps at most 5 endpoints.
    category: validation
    applies_to: PushSubscription
    trigger: POST /api/rooms/{code}/push/subscribe
    logic: authorise the seat token; validate the endpoint (scheme https; host has a dot, is not an IP literal, and is not localhost or *.local); p256dh decodes to 65 bytes, auth to 16 bytes; upsert on (room, slot, endpoint); trim to the 5 newest
    violation: 400 "Invalid push subscription", 403 for the seat
    source: FR6.5, FR6.7
  - id: BR2.2
    statement: A seat can turn notifications off. That deletes its subscription for the given endpoint, or all of the seat's subscriptions when no endpoint is given.
    category: policy
    applies_to: PushSubscription
    trigger: POST /api/rooms/{code}/push/unsubscribe
    logic: authorise the seat; delete the matching rows; answer 200 even when nothing matched
    violation: 403 for the seat
    source: FR6.7
  - id: BR2.3
    statement: The VAPID keys come only from JUSTCHESS_VAPID_PRIVATE_KEY, or from the PEM file named by JUSTCHESS_VAPID_KEY_FILE, which must be outside the project folder. When neither gives a valid key, push is disabled and one clear warning is logged at startup.
    category: constraint
    applies_to: VapidConfig
    trigger: startup
    logic: GET /api/push/key answers {publicKey} when enabled and 404 {enabled:false} when not; a key file inside the project folder is refused, with a log line saying why
    violation: push disabled; everything else still works
    source: NFR3a, FR6.5
  - id: BR2.4
    statement: Removing a room also removes its subscriptions and alert records.
    category: policy
    applies_to: PushSubscription, AlertRecord
    trigger: housekeeping deletes a room
    logic: a cleanup hook deletes by room code in the same transaction
    violation: n/a
    source: FR6.7

  # BR3 — The browser side
  - id: BR3.1
    statement: The page asks for notification permission only right after the person turns the Notifications setting on. When permission is granted, it registers the service worker and, when push is enabled, subscribes and sends the subscription for the current seat.
    category: policy
    applies_to: notifications module
    trigger: settings toggle on (user action)
    logic: Notification.requestPermission() inside the click handler; granted → register /sw.js, then pushManager.subscribe with the VAPID key, then POST subscribe; returns true when permission is granted, even when push is unavailable (local notifications only); denied → false, and the panel says "Notifications are blocked in this browser"
    violation: n/a
    source: FR6.3, FR6.4, FR6.5
  - id: BR3.2
    statement: The open page shows its own alert when a new snapshot means "your move", "your opponent has joined" or "game over". With the page visible, this is an in-page banner. With the page hidden, permission granted and no push subscription active, a local notification is shown through the service worker. With the page hidden and push active, the page shows nothing, because the push covers it.
    category: policy
    applies_to: notifications module
    trigger: snapshot change
    logic: derive the event key exactly as the server does (BR1.1); remember the last key shown per room in sessionStorage; never show the same key twice
    violation: n/a
    source: FR6.1, FR6.2, FR6.3, FR6.4, FR6.6
  - id: BR3.3
    statement: The service worker shows each push with a tag equal to its event key, so a repeat replaces instead of stacking. It skips showing it when a visible page for the same room exists. Tapping the notification focuses that room's page, or opens /r/<code>.
    category: policy
    applies_to: service worker
    trigger: push, notificationclick
    logic: clients.matchAll({type:"window", includeUncontrolled:true}) → any visible client whose URL path is /r/<code> → skip; else showNotification(title, {body, tag, data:{url}}); click → focus the matching client or openWindow(url)
    violation: n/a
    source: FR6.4, FR6.5, FR6.6
  - id: BR3.4
    statement: Turning Notifications off unsubscribes the browser, deletes the seat's server subscription, and stops all alerts on that device, including in-page banners for background events.
    category: policy
    applies_to: notifications module
    trigger: settings toggle off
    logic: pushManager.getSubscription()?.unsubscribe(); POST unsubscribe {token, endpoint}; the visible-page banner stays, since it is part of the game screen, but no system notifications are shown
    violation: n/a
    source: FR6.7
  - id: BR3.5
    statement: Push is verified on localhost in P1. HTTPS hosting is an open decision. Browsers only allow service workers and push on https or localhost.
    category: constraint
    applies_to: deployment
    trigger: n/a
    logic: the README records the requirement and the HTTPS options (reverse proxy with a certificate, or a tunnel), as an open decision
    violation: n/a
    source: NFR3
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | Join, move and end events, and who gets each | policy | FR6.1, FR6.2, FR6.8 |
| BR1.2 | Claim the key before sending; never twice | constraint | FR6.6, FR6.8 |
| BR1.3 | Push only when the seat is away or hidden | policy | FR6.4, FR6.5, FR6.6 |
| BR1.4 | Marked sent only on 2xx; delete on 404/410 | policy | FR6.7, FR6.8 |
| BR2.1 | Subscribe validation; public https endpoints only | validation | FR6.5, FR6.7 |
| BR2.2 | Unsubscribe | policy | FR6.7 |
| BR2.3 | VAPID keys from the environment or an outside file; disabled when missing | constraint | NFR3a, FR6.5 |
| BR2.4 | Cleanup with the room | policy | FR6.7 |
| BR3.1 | Ask for permission only after the toggle | policy | FR6.3, FR6.4, FR6.5 |
| BR3.2 | In-page banner or local notification, keyed like the server | policy | FR6.1–FR6.4, FR6.6 |
| BR3.3 | Service worker: tag, skip when visible, open on tap | policy | FR6.4–FR6.6 |
| BR3.4 | Turning it off stops everything on the device | policy | FR6.7 |
| BR3.5 | Localhost for P1; HTTPS still to decide | constraint | NFR3 |
