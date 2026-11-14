# API Documentation

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

