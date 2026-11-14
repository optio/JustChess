# Architecture Decisions — JustChess P2

ADR numbers restart for this intent. The P1 ADRs (intent 261112) still apply, in particular P1 ADR-003 (HttpApi orchestrates) and ADR-006 as amended (in-place upgrade).

## ADR-001: One Stockfish process behind a queue, with levels in a separate ComputerOpponent
- **Context.**
  - Single player, hints and the endgame trainer all need Stockfish. The app is one Uvicorn process on a Raspberry Pi, and NFR1 caps the engine at one search at a time, ≤ 2 threads and ≤ 64 MB of hash.
  - Engine work must never block the event loop.
  - Nothing talks to the engine today. [Q1]
- **Decision.**
  - The Engine component owns one long-running Stockfish process, driven through python-chess's asynchronous UCI interface, with a FIFO queue.
  - The level table and the hint and reply logic live in ComputerOpponent, which only asks Engine for moves.
- **Consequences.**
  - Memory and CPU stay bounded and predictable.
  - Starting the process costs about 0.3 s once, at start-up.
  - Under load, requests wait, and the page shows "Waiting for the computer…".
  - A crashed process gets one restart, and after that the features show as unavailable.
  - **Security:** the engine binary is the checksum-verified pinned one, and positions sent to it come only from validated games, so no user text reaches UCI.
- **Alternatives rejected.**
  - A process per request: too slow to start on the Pi, and memory spikes under concurrent use.
  - A process pool: breaks the NFR1 limit and multiplies memory.

## ADR-002: A computer game is a room whose second seat belongs to the computer
- **Context.** Computer games must be saved, listed among your games, resumable, and use the same board, scoresheet, blunder warnings and live updates as friend games. [Q2]
- **Decision.**
  - Rooms gets `mode = computer` and a `computerLevel`. Seat B is the computer's and has no token, so no one can join.
  - Games gains takeback and automatic draws for computer rooms.
  - HttpApi runs the computer's reply after each player move and on resume.
- **Consequences.**
  - Almost every existing path is reused: the summaries, Housekeeping's 30-day deletion and the live updates.
  - Rooms and Games need a few mode checks: join refused, takeback allowed, draws automatic.
  - **Security:** a computer room has exactly one token-holding seat, so the existing seat authorization covers it unchanged.
- **Alternatives rejected.** A separate solo-game component with its own storage would duplicate the rules wiring, the summaries, resuming and clean-up.

## ADR-003: Pass-along and join requests are part of Rooms
- **Context.**
  - A waiting room can switch to pass-along, where the creator moves both colours, and back.
  - A visitor's join must be accepted by the creator, lapses after 10 minutes, and only one can be pending. [Q3]
- **Decision.**
  - Rooms owns the room mode (`waiting`, `pass_along`, `online`, `computer`) and the JoinRequest entity.
  - Seat authorization takes the mode into account: in `pass_along` the creator's token may move either colour.
  - Accepting a request issues seat B a fresh token and switches the mode to `online`. Games finished in pass-along are marked not counted.
- **Consequences.**
  - All seat-security logic stays in one place.
  - Rooms grows somewhat, which is acceptable because these are seat rules.
  - Housekeeping expires lapsed requests, and every read also checks expiry.
  - **Security:**
    - Only the creator's seat can answer a request.
    - The requester is identified by a random request token, stored hashed and sent only in request bodies, never in URLs.
    - Requests are rate-limited (ADR-006).
- **Alternatives rejected.** A separate PassAlong component would need to reach into seat authorization and duplicate room locking.

**Amendment (U3 functional design):** two changes to this decision.
- The joiner learns the answer by polling a status route with its request token, not over a request-scoped WebSocket.
- On accept, seat B's token hash is the request token's hash. The joiner's request token becomes its seat token, so no fresh token is issued and no plaintext token is ever held on the server.

The LiveUpdates request-socket responsibility in `components.md` is dropped for this reason.

## ADR-004: Trainers split into Lessons (with kinds), Puzzles and Endgames
- **Context.** The new trainers differ in content shape and in whether they need an opponent. Lessons are scripted lines with notes. Puzzles are a position plus a solution line, about 1,800 of them from a CC0 source. Endgames need a live, full-strength defender and pass rules. [Q4]
- **Decision.**
  - Lessons gains a `kind` (opening, trap or defence) and stays file-based.
  - A new Puzzles component loads the curated puzzle files and checks moves.
  - A new Endgames component loads the positions, asks Engine for the defender's moves and judges the goal.
- **Consequences.**
  - Each component validates its own format and can be tested alone.
  - The client gets three APIs behind one trainer hub.
  - Endgames depends on Engine, so it is unavailable without Stockfish.
  - **Security:** all content ships in the repo and is validated at load. Nothing is downloaded at runtime (NFR6).
- **Alternatives rejected.**
  - One Trainer component would mix three formats and two runtime models.
  - Puzzles as lessons would force about 1,800 single-line "lessons" through a loader built for annotated walkthroughs.

## ADR-005: One computer room per device and level holds the score against the computer
- **Context.** The score against the computer is kept per level, and there are no accounts. [Q5]
- **Decision.**
  - The device remembers its computer room for each level as a SavedSeat with `kind = computer` and the level.
  - "Play the computer" at a level reopens that room. If its game is finished it starts a rematch, colours swapped. If no saved room exists, it creates one.
  - The room score is the score against the computer at that level.
- **Consequences.**
  - No new storage is needed, and the score survives across sessions on that device.
  - Clearing browser data starts a fresh score, which is the same behaviour as friend rooms.
  - A computer room idle for 30 days is deleted, like any room.
  - "Continue on another device" moves a computer room too.
  - **Security:** nothing new, because the existing seat tokens are used.
- **Alternatives rejected.** Browser-only scores would duplicate result counting in the client, and they could disagree with the server's game results.

## ADR-006: Join-request rate limit by client IP address, in memory, in HttpApi
- **Context.**
  - NFR4 asks for at most 5 join requests per minute per client.
  - Review finding R-09 asked how a client is identified. Visitors have no token before they join.
- **Decision.**
  - HttpApi keeps an in-memory sliding window (60 s) per client IP address.
  - A new optional setting, `JUSTCHESS_TRUSTED_PROXIES`, holds a comma-separated list of proxy IP addresses or CIDR ranges. It goes in `.env` and `.env.example`, and defaults to empty.
  - When it is empty, the client address is always the socket peer address, and `X-Forwarded-For` is ignored.
  - When it is set and the peer address is in the list, the client address is the rightmost `X-Forwarded-For` entry that is not itself a trusted proxy. When the peer is not in the list, the header is ignored.
  - `JUSTCHESS_ORIGIN` keeps its one meaning, the expected origin for the origin check. (This corrects the first draft, review R-02.)
- **Consequences.**
  - The limit is simple and has no storage cost. It resets on restart, which is acceptable for a nuisance limit.
  - Players sharing one network address share the limit, which is acceptable at 5 per minute.
  - Behind a reverse proxy, the operator must set the new setting, or every visitor shares the proxy's limit. The README documents this.
  - **Security:**
    - The header is never trusted by default, and when trusted only from listed proxies, so a client cannot spoof its address past the limit.
    - The existing unconditional use of `X-Forwarded-Proto` for the origin check is left as it is. It decides only whether the expected origin is http or https, never who the client is. The NFR review should look at it.
- **Alternatives rejected.**
  - A browser cookie is trivially cleared.
  - A database-backed limiter adds writes for little gain in a single process.

## ADR-007: Schema version 4 upgrades in place (SUPERSEDED by ADR-010)
- **Context.** New columns (room mode and level, game counted flag, move capture info) and the new join_requests table. P1 ADR-006, as amended, upgrades version 2 to 3 in place. NFR7 keeps rooms, games and scores.
- **Decision.**
  - Schema version 4. The single-step upgrade in `justchess/db.py` (`UPGRADABLE_VERSION = 2` to `SCHEMA_VERSION = 3`) becomes a chain of step functions, 2→3 and 3→4.
  - All needed steps run inside one transaction, so a version-2 file goes 2→3→4 atomically.
  - Step 3→4 adds the columns with defaults (`mode = 'online'` for rooms with two seats, otherwise `'waiting'`; `counted = 1`; `is_computer = 0`; seat `token_hash` becomes nullable) and creates `join_requests`.
  - SQLite cannot drop NOT NULL in place, so the seats table is rebuilt (create new, copy, drop, rename) inside the same transaction.
  - Old moves keep empty capture info.
- **Consequences.**
  - Existing rooms keep working.
  - If any step fails, the whole transaction rolls back, the file keeps its original version (2 or 3), and start-up stops with the reason, as in P1.
  - Older or unmarked files are still moved aside, as in P1.
  - **Security:** no data leaves the database, and token hashes are untouched.
- **Alternatives rejected.** A fresh schema would lose players' rooms and scores, which NFR7 forbids.

## ADR-008: QR codes are drawn in the browser by a small vendored encoder
- **Context.** FR5.4 requires a QR code with no outside service. The client has no build step (P1 ADR-004).
- **Decision.** Vendor a small MIT-licensed QR encoder as an ES module under `static/js/vendor/`, credited in `static/ASSETS.md`, and draw the code on a canvas.
- **Consequences.**
  - Works offline.
  - About 10 KB more JavaScript, loaded only when the share dialog opens.
  - **Security:** no third-party request leaks the invite link.
- **Alternatives rejected.**
  - A QR image API would leak the link to a third party.
  - Generating the code on the server would add a Python dependency and an extra endpoint for something the browser can do.

## ADR-009: Computer replies are applied only to an unchanged game, with no lock held across the engine wait
- **Context.**
  - The reply takes up to 2 s plus any queue wait.
  - A resume, a racing move or a takeback could try to produce or invalidate a reply at the same time (review R-03).
  - The per-room lock must not be held for seconds.
- **Decision.**
  - HttpApi notes the game version after the player's move commits, releases the room lock, and waits for the engine.
  - It then re-takes the lock and applies the reply only if the version is unchanged and it is the computer's turn. Otherwise it discards the reply.
  - An in-memory per-room "reply in flight" flag refuses takebacks until the reply is applied or discarded, and stops resume from asking a second time.
- **Consequences.**
  - At most one reply per position, and other rooms are never blocked.
  - A discarded reply costs one wasted search.
  - After a restart the flag is gone, and resume asks again if it is the computer's turn.
  - **Security:** none beyond the existing version check, which already rejects stale moves.
- **Alternatives rejected.**
  - Holding the room lock during the search would block the player's own reads and other requests for seconds.
  - A database flag would add writes and could get stuck after a crash.

## ADR-010: Schema version 4 is created fresh; older files are moved aside
- **Context.**
  - The user decided after Domain Design approval that no backward compatibility is needed and the database may be destroyed and recreated.
  - The in-place upgrade in ADR-007 (a 2→3→4 chain plus a seats-table rebuild) was the riskiest part of U2.
- **Decision.**
  - `SCHEMA_VERSION` becomes 4, and the in-place upgrade path (`UPGRADABLE_VERSION`, `_upgrade_in_place`) is removed.
  - At start-up, any existing file whose version is not 4 is renamed to `justchess.sqlite3.old`, replacing any earlier `.old`. A fresh version-4 schema is then created. This is the P1 behaviour for unknown files, now applied to every older version.
  - The schema is written directly with the final columns: seat `token_hash` nullable, `is_computer`, room `mode` and `computer_level`, game `counted`, move capture columns, and the `join_requests` table.
- **Consequences.**
  - The schema code is simpler and there is no migration to test.
  - Rooms, games, scores and seat links from before are lost at the first start after U2. Players' stored seats then come back as "not found" and drop off Your games.
  - The README states this.
  - **Security:** the old file is kept as `.old` rather than deleted, so nothing is silently destroyed. Tests never touch the real file.
- **Alternatives rejected.**
  - The in-place upgrade (ADR-007) is no longer needed.
  - Deleting the old file outright would leave no recovery copy for the operator.

## Sources
- `inception/requirements-analysis/requirements.md` (FR1–FR9, NFR1–NFR8, review R-09)
- `domain-design-questions.md` [Q1]–[Q5]
- Intent 261112 `inception/domain-design/decisions.md`
