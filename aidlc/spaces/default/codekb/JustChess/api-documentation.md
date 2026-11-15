# API Documentation

> Historical baseline retained from earlier scans. The Current footer sections below supersede conflicting identity/presentation statements. Outside-focus prose is preserved, not newly verified.

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


## Current player client contract (footer scan)

createPlayerIdentity calls POST /api/player/create, /profile, /restore, /seats, /nickname and /regenerate with same-origin credentials and no-store requests. Authentication uses X-Player-Token; restore sends {recovery} in the JSON body. nickname sends {nickname}; successful responses replace the client profile. regenerate returns recovery and keeps this device's existing token. Client errors return {ok:false,message}; network errors preserve the current player.

The recovery URL is origin/#player=<43-character token>, distinct from public room invitations and old one-use seat transfer links. Existing footer anchor and copy button address the same private recovery URL. Their presentation can consolidate without changing its semantics. Server implementation/status codes were outside this focused scan.

