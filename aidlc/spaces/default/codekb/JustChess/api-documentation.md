# API Documentation

> Focused merge, 2026-11-15: current findings cover player identity/presentation and persistence seams. Outside-focus descriptions are retained prior-store context and are not newly verified; see the timestamp for exact coverage.

FastAPI serves the same application shell at /, /r/{code}, /learn, /learn/{lesson_id}, /learn/tactics/{theme} and /learn/endgames/{position_id}. Static assets use /static; /sw.js has root scope and no-cache delivery.

| Surface | Operations |
|---|---|
| /api/rooms | POST create friend/computer room; POST /summaries reads 1–50 code/token pairs |
| /api/rooms/{code} | GET snapshot, POST /join, /continue-link, /continue, /mode |
| /api/rooms/{code}/join-request | POST /answer and /status |
| /api/rooms/{code} game actions | POST /moves, /check-move, /claim-draw, /claim-win, /rematch |
| /api/rooms/{code} computer actions | POST /computer-move, /takeback, /resign, /hint |
| /ws/{code} | WebSocket hello with token/visibility, heartbeat, state and computer/takeback events |
| /api/engine | GET availability, path source, version and reason |
| /api/lessons | GET catalog (optional kind), GET /{id} |
| /api/position/move | POST fen and uci; returns legal resulting position and SAN |
| /api/puzzles | GET themes, /{theme} ids/ratings, /{theme}/{id} detail; POST /check and /hint |
| /api/endgames | GET categories, /{id} detail; POST /{id}/play with complete move history |
| /api/push | GET /key; POST /subscribe and /unsubscribe |

Seat tokens are capability credentials: JSON mutations carry token in the body; snapshot reads use X-Seat-Token; sockets identify in hello rather than URL. Public watchers receive restricted snapshots. Move requests use optimistic version checks; conflict responses can include current viewer state. Continue links exchange a short-lived single-use token and replace the old seat token. Join requests return 202 while pending; creator acceptance atomically assigns B and changes room mode.

Domain refusals use JSON detail with meaningful 400/403/404/409 statuses; framework validation can return 422. Rate limits return 429. Engine-dependent operations can return 503. Database errors map to fixed 500 text. Supplied origins are checked; default bodies are capped at 4 KiB, summaries at 8 KiB. No OpenAPI contract execution or live endpoint checks were performed during this scan.


## Focused identity contract findings

POST /api/rooms/{code}/continue-link accepts {token}; returns {continueToken, expiresIn:600}. POST /api/rooms/{code}/continue accepts {continueToken}; returns {code, token, slot, colour}. Invalid/expired/reused tokens are refused with 403. Redemption invalidates the previous seat token, clears the continue hash and deletes the old seat's push subscriptions; live clients receive seat-moved. The browser consumes #continue and immediately removes it from history.

Current snapshots expose result, endReason, slot, colour, per-slot seat presence/colour and room score; no player identifier or nickname is included. No profile/nickname/recovery endpoint, profanity filter or permanent identity bookmark was found by focused source search. Any new identity endpoints must be defined by requirements; this scan does not prescribe them.

