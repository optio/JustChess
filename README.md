# JustChess

**Play. Learn. Improve.** Anonymous two-player chess with room codes and interactive opening lessons.

Built with FastAPI, lightweight JavaScript, WebSockets, SQLite and python-chess, with Stockfish for games against the computer. No accounts, subscriptions or matchmaking.

## Getting started (uv)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone https://github.com/optio/JustChess.git
cd JustChess
uv sync
uv run uvicorn app:app --reload
```

Open http://localhost:8000 and play:

1. Press **Start a game**. The address changes to `/r/K7Q2PX` (your room code) and the game waits for your opponent.
2. Press **Share** in the top bar to send the invite link. A dialog opens over the game with **Copy link**, links for Email, WhatsApp, Telegram and SMS, **More…** (your device's share sheet, where there is one) and a QR code a friend can scan from your screen; Escape, Close or a click outside closes it. Your friend opens the link, or types the code under "Have a room code?", and takes the other seat. To try it alone, open the link in a private window or another browser.
3. Tap a piece to see its legal moves, then tap a target. The status line says whose move it is; the scoresheet records the game.
4. When the game ends, the overlay names the result. **Play again** starts the next game in the same room once both players have pressed it, with the colours swapped. The room score follows each player, not each colour.

Your seat is remembered in this browser, so a reload or a closed tab brings you back to it. To move your seat to another device, open **Game settings** and use **Get a private continue link** (it works once, for 10 minutes; don't share it). A third visitor watches the game read-only.

Use `uv sync --dev` to install development dependencies and `uv run pytest` to run the tests (`uv run pytest tests/core` for the game backend only). The tests use temporary databases and never open `justchess.sqlite3`. Run `uv lock` and commit the generated `uv.lock` to pin resolved dependencies for reproducible installs.

`tests/test_game_screen.py` includes a two-player run in headless Chromium (Fool's mate, the overlay and a rematch), a background-tab notification run, and an opening lesson run (walkthrough, an off-line move, the arrow, the trainer's replies and the lessons drawer) against its own server on a free port; `tests/test_u5_trainer_browser.py` checks the hub's keyboard tabs, the Tactics list and solving a fixture puzzle; `tests/test_u1_polish_browser.py` checks the board fit at seven screen sizes, the capture animation and the share dialog the same way; `tests/test_u4_computer_browser.py` plays a short game against the computer (with a fake engine). The engine tests use a small fake UCI engine (`tests/fakes/fake_uci.py`); `tests/test_engine_real.py` also runs the installed Stockfish (and checks a Maximum reply comes within 3 s) and is skipped when there is none. They are skipped, with the reason, when no Chromium is installed; set `JUSTCHESS_CHROMIUM` to choose a browser binary.

## Configuration

Settings can go in a `.env` file at the project root, which is ignored by git. Copy `.env.example` to start. `uv run fastapi dev` and `uvicorn app:app` load it at start-up. A variable already set in your shell wins over the file.

| Variable | Default | Purpose |
|---|---|---|
| `JUSTCHESS_DB` | `justchess.sqlite3` in the working directory | Path of the SQLite database file. |
| `JUSTCHESS_ORIGIN` | the request's own `Host` (scheme from `X-Forwarded-Proto` when present) | The app's public origin, such as `https://chess.example.com`. POST requests and WebSocket connections whose `Origin` header differs are refused. Set it when running behind a proxy that rewrites `Host`. |
| `JUSTCHESS_LESSONS_DIR` | `lessons/` next to `app.py` | Folder of opening lesson files; see [Opening lessons](#opening-lessons). |
| `JUSTCHESS_PUZZLES_DIR` | `puzzles/` next to `app.py` | Folder of the curated tactics puzzles, read once at start-up; see [Tactics puzzles](#tactics-puzzles). |
| `STOCKFISH_PATH`, `STOCKFISH_AUTO_INSTALL` | see [Stockfish](#stockfish) | Engine discovery. |
| `JUSTCHESS_GAMEPLAY_FILE` | `gameplay.yaml` next to `app.py` | Another gameplay settings file; see [Tuning gameplay](#tuning-gameplay). |
| `JUSTCHESS_VAPID_KEY_FILE`, `JUSTCHESS_VAPID_PRIVATE_KEY`, `JUSTCHESS_VAPID_SUBJECT`, `JUSTCHESS_PUSH_HOSTS` | push off | Web Push keys and allowed push services; see [Notifications](#notifications). |
| `JUSTCHESS_TRUSTED_PROXIES` | empty (no proxy trusted) | Comma-separated IP addresses or CIDR networks of reverse proxies on another host. Only when the connecting address is one of them do the per-address rate limits (join requests, and the computer's routes, see [Play the computer](#play-the-computer)) read `X-Forwarded-For`, taking the rightmost entry that is not a listed proxy. Invalid entries are logged and ignored. See [Client address behind a proxy](#client-address-behind-a-proxy). |

**Client address behind a proxy.** The join-request rate limit (5 requests a minute per client address, see [Pass-along and join requests](#pass-along-and-join-requests)) uses the address Uvicorn reports for the connection. Uvicorn already replaces it with the `X-Forwarded-For` address when the connection comes from an address in its own `--forwarded-allow-ips` setting (`127.0.0.1` by default, also read from `FORWARDED_ALLOW_IPS`), and needs `--proxy-headers` (on by default). So:

- **A proxy on the same machine** (Caddy or nginx on `127.0.0.1`): nothing to set; Uvicorn's default already trusts it.
- **A proxy on another host**: either start Uvicorn with `--forwarded-allow-ips <proxy address>`, which changes the client address for the whole app, or set `JUSTCHESS_TRUSTED_PROXIES` to that address, which JustChess applies to the rate limit only. Use one of the two, not both.
- **Behind a proxy with neither set**, every visitor shares the proxy's address, and so its limit.

Never list an address that untrusted clients can connect from: whoever connects from a listed address can choose the address the limit sees.

**Run one process.** Room locks and live WebSocket connections are kept in memory, so run a single Uvicorn worker (the default). Several workers or several instances would need shared locking and pub/sub, which the app does not have.

**Database upgrades.** The current schema version is 4 (room modes, computer seats, capture info and join requests). The first start after this version moves the old database to `justchess.sqlite3.old` (replacing any earlier `.old`) and starts with a fresh, empty one: nothing is migrated, so earlier rooms and scores are not carried over, and the "Your games" list drops their seats (ADR-010). The same happens to any older, unmarked or non-SQLite file. A version-4 file is kept as it is. A file with a newer version than the app refuses to start and is left where it is, and if the old file cannot be renamed, startup stops with the reason. Rooms with no activity for 30 days are deleted at startup and then hourly, with their push subscriptions, alert records and join requests.

Request bodies are limited to 4 KB and WebSocket messages to 1 KB.

## Implemented

- Room codes and invite links (`/r/{code}`); anonymous per-room seat tokens kept in the browser's long-lived storage, sent only in request bodies or the `X-Seat-Token` header, never in a URL
- Legal move validation with python-chess, including castling, en passant and promotion; automatic ends and claimable draws (threefold repetition, 50-move rule)
- The game screen: tap-to-move board, status line, scoresheet, room score per player, claim buttons, live updates over a WebSocket with automatic reconnect, end-of-game overlay with the win sequence, rematch with colours swapped, and "continue on another device"
- Game-screen polish: every capture (yours too, and en passant) shrinks and fades the taken piece on its square in 260 ms (none with reduced motion), and a captured row under the status lists what each side has taken. The board fits the screen without scrolling: it is the smaller of the width and the height left after the top bar and status (at most 640 px on desktop, edge to edge on phones under 400 px, beside the panel on a phone held sideways), with squares of at least 44 px (36 px sideways); the content below it scrolls. The share dialog's QR code is drawn in the browser by `static/js/vendor/qrcode.js` (MIT, see `static/ASSETS.md`); nothing is sent to another site
- SQLite game persistence and the room scoreboard
- Blunder warnings: before a move is sent, the server checks it (`POST /api/rooms/{code}/check-move`, python-chess only, no engine). If the move allows mate in one, or leaves a knight, bishop, rook or queen that can be taken for free, a dialog says why and asks you to confirm ("Choose another move" or "Play … anyway"). Only problems the move itself creates are warned about, and nothing is said when every legal move has the same problem. Turn it off with **Warn me before blunders** in **Game settings** (on by default, kept per device). If the check cannot be made, the move goes ahead.
- The trainer hub at `/learn` (the lobby's **Train** button): tabs for Openings, Traps, Tactics and Defence with progress kept on this device (see [Trainer hub](#trainer-hub))
- The opening trainer at `/learn/{id}` and in the game's "Learn openings" drawer: lessons from YAML or JSON files, an animated walkthrough with a note for each move, and practice against scripted replies on either side, with hints, an arrow after 3 misses, and free play off the line (see [Opening lessons](#opening-lessons))
- Tactics puzzles at `/learn/tactics/{theme}`: 1,800 curated Lichess puzzles in six themes, checked on the server (see [Tactics puzzles](#tactics-puzzles))
- Pass-along while you wait: the creator can play both colours on one device until a friend asks to join, then accept or decline the request (see [Pass-along and join requests](#pass-along-and-join-requests))
- Notifications, one alert per event: when your opponent joins, moves, or the game ends. An open page shows a banner, a background tab gets a system notification, and a closed tab gets a Web Push notification once keys are set (see [Notifications](#notifications))
- Play the computer: five levels of Stockfish from the lobby, with take back, hints, resign and a score per level (see [Play the computer](#play-the-computer))

See the [product requirements](aidlc/spaces/default/intents/261111-requirements-review/inception/requirements-analysis/requirements.md) for the full product specification, feature acceptance criteria and roadmap. Items listed there are **not necessarily implemented**. Requirements now live in the AI-DLC records under `aidlc/`; the former `REQUIREMENTS.md` has been retired.

## Pass-along and join requests

**Play here while waiting.** While nobody has joined your room, the waiting screen offers **Play here while waiting**. The room switches to pass-along: the game starts and you move both colours on this device ("Pass-along: White to move"), handing it over after each move if you like. These are practice games: the room score changes only once a friend joins, and a game that ends in pass-along shows "Practice game over". **Play again** starts the next practice game at once, colours swapped. **Wait for a friend instead** switches back, keeping the position; the side that is not yours then locks. The mode is kept with the room, so it survives a reload. A computer room has no pass-along, and once a friend has joined it is gone for good.

**Join requests.** In pass-along, opening the invite link does not take the free seat. It sends a join request, and the visitor sees "Waiting for the creator to accept. You'll play Black from the current position." (naming whichever colour is free). The creator gets a banner above the status, "Someone wants to join as Black. … Expires in 9:41.", with **Accept** and **Decline**, plus the usual notification ("Someone wants to join") when the page is in the background or closed; without notifications, the "Join request" pill in "Your games" shows it the next time you open the app.

- **Accept** gives the visitor the free seat from the current position; that game, if it is not over, now counts for the score. The visitor's page learns the answer within 3 seconds and opens the game.
- **Decline** tells the visitor "The creator declined. You can ask again later."; the same address cannot ask again in that room for 10 minutes.
- A request nobody answers lapses after **10 minutes** ("Nobody answered. Try again later."); the creator's banner hides itself when its countdown ends.
- Only one request can be pending per room: a second visitor sees "Someone else is already asking to join. Try again in a few minutes."
- One client address can send at most **5 join requests a minute** ("Too many requests. Try again shortly.", HTTP 429). Behind a reverse proxy see [Client address behind a proxy](#client-address-behind-a-proxy).

The visitor's page polls `POST /api/rooms/{code}/join-request/status` with its request token, which lives in the tab's session storage only. On acceptance that same token becomes the visitor's seat token (the server only ever stores its hash), so a refresh or a server restart loses nothing. The routes are `POST /api/rooms/{code}/mode` (`{token, mode: "pass_along" | "waiting"}`), `POST /api/rooms/{code}/join` (202 with a request token for a pass-along room), `POST /api/rooms/{code}/join-request/answer` (`{token, accept}`) and `.../join-request/status` (`{requestToken}`). Tokens travel only in request bodies and are never logged.

## Play the computer

In the lobby, **Play the computer** offers your colour (White, Black or Random) and a level. Your last choice is remembered on this device (Random and Casual the first time). **Play** reopens this device's room for that level, so each level keeps one score: an unfinished game carries on, a finished one starts the next game in the colour you chose, and the first time a new room is created. The game screen shows "Computer · Club", the computer's status, **Take back**, **Hint** and **Resign**, and "This level: You 2 · Computer 3 · Draws 1". There is no invite or share against the computer, and the blunder warning works as usual.

Each level is a Stockfish strength, a search depth limit, a think time and a chance of playing a random legal move instead of the engine's, so the easy levels make real mistakes. The shipped values (change them in [`gameplay.yaml`](#tuning-gameplay)):

| Level | Stockfish skill (0-20) | Depth limit | Think time per move | Random-move chance |
|---|---|---|---|---|
| Beginner | 0 | 1 | 0.05 s | 35 % |
| Casual | 2 | 3 | 0.1 s | 15 % |
| Club | 6 | 6 | 0.3 s | 5 % |
| Strong | 11 | 10 | 0.6 s | 0 |
| Maximum | 16 | none | 1 s | 0 |

The random move is chosen on the server with the operating system's random source.

- **Take back** removes your last move and the computer's reply, as often as you like, while the game is on (not while the computer is thinking).
- **Hint** draws an arrow for the best move at full strength (skill 20, 0.5 s of thought, never random), whatever the level; the next move or a takeback clears it.
- **Resign** asks first, in the page, and counts the game for the computer. Threefold repetition and the 50-move rule end a game against the computer automatically; there are no claim buttons.

**The engine queue.** One Stockfish process serves every room on the server (2 threads, 64 MB hash), one search at a time, in arrival order. While others are ahead the page says "Waiting for the computer… (2 ahead)", then "Computer is thinking…". At most 32 requests wait; beyond that the computer answers "The computer is busy, try again in a moment" and the page tries again (3 times, 5 s apart, then "The computer didn't answer." with **Try again**). Hints are refused once 16 requests wait, so replies keep their place, and each room can have one hint on its way. A search that runs 5 s past its think time counts as a crash.

**When the computer is unavailable.** The lobby says "Play the computer is unavailable" with the reason, and an open game says "The computer can't move right now: … You can still look through the game." You cannot move then (take back and resign still work). The reasons:

- "The computer is starting": the app has just started (or is still downloading Stockfish, see [Stockfish](#stockfish)); it clears by itself.
- "No chess engine is installed": no Stockfish was found or installed. Install one or set `STOCKFISH_PATH`, then restart the app.
- "The computer could not be started": the binary was found but would not run. Check it runs by hand, then restart the app.
- "The computer stopped working": the engine crashed twice. The first crash is restarted automatically (`engine.restarts` in `gameplay.yaml`); the second needs a person, so **restart the app** to bring the computer back. The app logs each crash.

**Limits per client address.** Creating a computer room: 10 a minute. Hints: 20 a minute. The page's "ask the computer to move" call (`computer-move`): 30 a minute. Beyond these the server answers HTTP 429 with `Retry-After: 60` and queues nothing. Your own moves are not limited, because each one waits for the computer's reply. Behind a reverse proxy on another host these limits use the same client address as the join-request limit, so `JUSTCHESS_TRUSTED_PROXIES` (or Uvicorn's `--forwarded-allow-ips`) applies to them too; see [Client address behind a proxy](#client-address-behind-a-proxy).

The numbers in this section are the shipped defaults; every one of them is in `gameplay.yaml`.

The routes: `POST /api/rooms` with `{kind: "computer", level, colour}`, `POST /api/rooms/{code}/computer-move` (`{token}`), `.../takeback`, `.../hint` and `.../resign` (`{token, version}`), and `.../rematch` with an optional `colour`. Every snapshot of a computer room carries `computer: {state, queuePosition, reason, level, available}`, and the room's socket gets `{type: "computer", state, queuePosition}` as the reply moves up the queue. Only positions replayed from the stored moves reach the engine, and tokens are never logged.

## Tuning gameplay

Gameplay numbers live in [`gameplay.yaml`](gameplay.yaml) at the project root, with a comment on every key: the computer levels (skill, depth limit, think time, random-move chance) and hint strength, the engine queue (its cap, the hint refusal threshold, the overrun grace, the restart count, the retry wait), the per-address limits (computer rooms, hints, computer-move, join requests), the join-request lifetime and decline block, the away time before a win can be claimed, the idle-room deletion age, the blunder-check time budget, and the page's own timings (capture animation, "Your games" refresh, the computer retries, the join-request poll), which the server hands to the page with the app shell.

- The file is read once at start-up: **restart the app** after editing it.
- A key you leave out keeps its default, so a short file with only your changes works too. Point `JUSTCHESS_GAMEPLAY_FILE` at it to keep `gameplay.yaml` as shipped.
- A typo, a wrong type or a value out of range stops start-up with an error naming the key, for example `gameplay.yaml: computer.levels.beginner.skill must be an integer from 0 to 20 (got 25)`.
- Without a `gameplay.yaml` the built-in defaults (the same values) are used, and the log says so. A file named by `JUSTCHESS_GAMEPLAY_FILE` must exist.

Protocol and security limits (token sizes, request and message sizes, socket timeouts) are not in the file on purpose.

## Notifications

Turn on **Notifications** in **Game settings**. The browser asks for permission only then, and turning the switch off stops every system notification on that device. You get one alert per event: "Your opponent has joined", "Your move" (with the move), or "Game over" with the reason. The game's final move gives only the "Game over" alert.

- **Page open and visible:** a banner under the status line.
- **Page in a background tab:** a system notification shown by the service worker (`/sw.js`). This works without push keys.
- **Tab closed:** a Web Push notification, when the server has VAPID keys. Push and the background-tab notification share one tag per room and event, so you never see the same alert twice.

**Push keys (VAPID).** Push stays off, with one warning line at startup, until a key is set. The key must never be in the repository. Generate one outside the project folder:

```bash
uv run python -m justchess.vapid generate ~/.config/justchess/vapid.pem
echo "JUSTCHESS_VAPID_KEY_FILE=$HOME/.config/justchess/vapid.pem" >> .env   # or export it in your shell
```

The generator writes the file with mode 0600 and refuses any path inside the project (symlinks are resolved). The app refuses a key file inside the project for the same reason. Instead of a file, `JUSTCHESS_VAPID_PRIVATE_KEY` can hold a PEM key or a raw base64url 32-byte P-256 key. `JUSTCHESS_VAPID_SUBJECT` sets the contact sent to push services (a `mailto:` or `https:` URL; default `mailto:admin@localhost`). Changing the key makes existing subscriptions fail; they are deleted when the push service reports the mismatch, and browsers subscribe again the next time the setting is on.

**Allowed push services.** Subscriptions are accepted only for `https` endpoints on port 443 at `fcm.googleapis.com`, `*.push.services.mozilla.com`, `*.notify.windows.com`, `web.push.apple.com` and `*.push.apple.com`. Add more with `JUSTCHESS_PUSH_HOSTS` (comma-separated host names; `*.domain` matches subdomains). Redirects from a push service are never followed, and endpoints are never logged (only their host).

**HTTPS (open decision).** Browsers allow service workers and push only on `https` or on `localhost`. In P1, push is verified on `localhost` (`uv run uvicorn app:app --reload`, then open `http://localhost:8000`). Anywhere else needs HTTPS, and how to host it is still open. The options are a reverse proxy with a certificate (for example Caddy or nginx with Let's Encrypt, setting `JUSTCHESS_ORIGIN`), or a tunnel that serves HTTPS (for example Cloudflare Tunnel or Tailscale Funnel).

**Manual check.** A real push needs a browser and a push service, so it is not part of the automated tests. With keys set, open a room on `localhost` in Chromium as both players, turn Notifications on as one of them, close that tab, and play a move as the other. A "Your move" notification should appear.

## Trainer hub

Press **Train** in the lobby, or open `/learn`. The hub has one tab per group: **Openings**, **Traps**, **Tactics** and **Defence** (Endgames is added later by its own unit through `registerTab` in `static/js/training/hub-tabs.js`). The tabs are an ARIA tablist: Left and Right move between them, Home and End jump to the first and last, and the selected tab is remembered on the device. Each tab shows `<done>/<total>`, and each row has a title, a subtitle, a **Done** mark and one button (**Learn** for a lesson, **Solve** for a puzzle theme).

Progress is kept per device in the browser (`localStorage`, key `justchess.trainer.v1`): a lesson counts as done when its practice reaches "Line complete" (also when the arrow was shown), and a puzzle when it is solved without **Show solution**. Nothing is sent to the server. When storage is blocked, no progress is shown and everything else works.

## Tactics puzzles

The Tactics tab lists six themes: Forks, Pins, Skewers, Discovered attacks, Mate in 1 and Mate in 2, about 300 puzzles each (`puzzles/<theme>.json`, 1,800 in all, under 300 KB). **Solve** opens the first unsolved puzzle of the theme, easier ones first. The opponent's set-up move is played, then you find the solution: a correct move gets the opponent's reply after 300 ms; a wrong move is shown, taken back after 600 ms with "Not this one. Try again.", and you can retry as often as you like. **Hint** first marks the piece to move, then draws the arrow. **Show solution** plays the rest at 800 ms per move and does not count the puzzle as solved. Any checkmate counts as a solution. Moves are checked on the server, so the page never holds the answer.

Puzzles from the Lichess puzzle database, released under CC0 (https://database.lichess.org/#puzzles). The credit is shown under the Tactics list and on the puzzle screen, and recorded in `puzzles/LICENSE.md` and `static/ASSETS.md`. Nothing is downloaded at runtime. Puzzles are loaded once at start-up (folder: `JUSTCHESS_PUZZLES_DIR`, default `puzzles/`); a puzzle that fails a check (an illegal move, a mate theme that is not mate, the wrong number of moves, the wrong theme) is skipped and logged with its id. Without the folder the Tactics tab says "Puzzles are not installed".

Routes: `GET /api/puzzles` (`[{theme, label, count}]`), `GET /api/puzzles/{theme}` (`[{id, rating}]`), `GET /api/puzzles/{theme}/{id}` (the position, the set-up move and the legal moves, never the solution), `POST /api/puzzles/{theme}/{id}/check` with `{ply, uci}` (`correct` with the reply, `solved` or `wrong`), and `POST /api/puzzles/{theme}/{id}/hint` with `{ply, level}` where level is `piece`, `move` or `solution`. An unknown theme or id is 404; a bad ply, level or illegal move is 400.

**Re-running the curation.** The set is made once by `scripts/curate_puzzles.py` from the Lichess dump (about 300 MB compressed), downloaded into the git-ignored `data/` folder:

```bash
curl -L -o data/lichess_db_puzzle.csv.zst https://database.lichess.org/lichess_db_puzzle.csv.zst
zstd -dc data/lichess_db_puzzle.csv.zst | uv run --frozen python scripts/curate_puzzles.py -
```

It keeps rows tagged with the theme with Popularity ≥ 80, NbPlays ≥ 500 and a rating from 600 to 2200, runs the same validator the app uses, then samples 300 per theme evenly across the rating range with a fixed seed (`--seed`). It writes `puzzles/*.json` and `puzzles/LICENSE.md` (date, filter and seed), and writes nothing and exits 1 when a theme ends with fewer than 250 puzzles or the files would pass 5 MB. A plain CSV path works in place of `-`. The run takes a few minutes on a Raspberry Pi 5.

## Opening lessons

Open a lesson from the hub's Openings, Traps or Defence tab, or open `/learn/{id}`. During a game the trainer opens in the **Learn openings** drawer, with its own board, while the game keeps running; the drawer lists openings only.

- **Walkthrough:** Next plays each move with its note beside the scoresheet row; Back and Restart step back.
- **Practise:** you play the lesson's side (switch with **Practise as White / Black**) and the trainer plays the replies. **Hint** marks the piece to move. After 3 misses on a move, a dashed arrow shows it, with its note. An illegal move is refused as illegal. A legal move off the line is shown as "Legal, but not this line", with **Keep playing freely** (both sides, not part of the lesson) or **Back to the line**.

The app ships 18 lessons in `lessons/`:

- **Openings (10):** `italian`, `monte-carlo`, `ruy-lopez`, `sicilian`, `french`, `caro-kann`, `queens-gambit`, `london`, `kings-indian`, `scandinavian`.
- **Traps (4):** `legals-mate`, `fried-liver`, `fishing-pole`, `englund-gambit-trap`.
- **Defence (4):** `scholars-mate-defence`, `fried-liver-defence`, `early-queen-raids`, `wayward-queen`.

The lines are standard theory and the notes are written for JustChess. `tests/test_lessons.py` loads every file and fails on any skip.

**Adding a lesson.** Put a `.yaml`, `.yml` or `.json` file in the lessons folder (`lessons/`, or the folder named by `JUSTCHESS_LESSONS_DIR`). The file name without its extension is the lesson id and its address (`lessons/caro-kann.yaml` is `/learn/caro-kann`): lowercase letters, digits and dashes, at most 48 characters. The folder is checked on each lesson request, so a new or edited file appears without a restart. A file that breaks a rule is skipped and the server log names it with the reason (for example `Skipped lesson file caro-kann.yaml: move 3: 'Nf6' is not legal in this position`); the other lessons still load.

```yaml
name: Caro-Kann Defence          # required, at most 80 characters
kind: opening                    # optional: opening (default), trap or defence; picks the hub tab
aliases: [Caro-Kann]             # optional list
eco: B10                         # optional; a letter A-E and two digits, only when verified
side: black                      # required: the side the learner practises by default
start: startpos                  # optional: startpos (default) or a FEN
moves:                           # required: 1 to 60 moves, in order from the start
  - san: e4                      # required, legal in the position
    uci: e2e4                    # optional; when given it must be the same move as the SAN
    note: White takes the centre.  # required, at most 280 characters
  - san: c6
    note: Black prepares d5, keeping the light-squared bishop free.
    alternatives:                # optional: other good moves, shown as "Also good"
      - san: e5
        note: The open game.
objectives:                      # optional: shown before the walkthrough and at the end
  - Challenge the centre with d5.
```

Unknown fields are refused (so a typo is reported, not ignored). Files over 64 KB, symlinks and anything that is not a regular file are skipped. YAML is read with `yaml.safe_load` only.

The routes: `GET /api/lessons` lists the lessons (id, name, kind, aliases, eco, side, number of moves; `?kind=opening|trap|defence` lists one kind, any other value is 400), `GET /api/lessons/{id}` returns one with its steps (each with `fenBefore`, `fenAfter`, `legalBefore`, `san`, `uci`, `note`), and `POST /api/position/move` with `{fen, uci}` plays a free-play move. That last route keeps no state, so it cannot report repetition draws.

## Stockfish

When the app starts it makes the [Stockfish](https://stockfishchess.org/) chess engine available in the background, so the app serves requests straight away. It looks for an engine in this order:

1. `STOCKFISH_PATH`, when it points to an executable file;
2. `stockfish` on the system `PATH`;
3. a copy this app installed earlier under `.engines/stockfish-sf_19/`;
4. otherwise it downloads the pinned official `sf_19` build for Linux (aarch64 or x86-64) or macOS from GitHub, checks its SHA-256 checksum before extracting anything, and installs only the engine binary into `.engines/stockfish-sf_19/`.

Set `STOCKFISH_AUTO_INSTALL=0` to turn off the download. If no engine can be found or installed, the failure is logged and the app starts normally without one. Once a binary is found the app opens one Stockfish process for [Play the computer](#play-the-computer), and stops it when the app stops. `GET /api/engine` reports whether the computer is available (the process is running), where the binary came from (`env`, `path`, `cached` or `downloaded`), its version, and the `reason` when it is unavailable. The binary's path is never exposed. The `.engines/` folder is ignored by git.

Stockfish is licensed under the GPLv3. Downloading it on the server at runtime does not redistribute it, but a published image or package that includes the binary takes on the GPLv3 obligations (shipping the licence and offering the corresponding source).

## Design system and demo page

The "Club Set" design system lives under `static/` as plain files: native ES modules and CSS with no build step and no npm dependency.

- `static/css/tokens.css`: every colour, type, radius and motion token. Light and dark themes follow the device unless `data-theme` is set; three board themes (`data-board`: `walnut-maple`, `tournament`, `rosewood`). Reduced motion sets the durations to 0.
- `static/css/base.css` and `static/css/board.css`: fonts, type roles, the four button roles, the focus ring, the logo mark, the settings controls, and the board frame, squares, labels, highlights and promotion picker.
- `static/js/board/board.js`: `createBoard(element, options)`. The caller must answer every move it emits, either with `set({ fen, ... })` or with `reject()` on any failure; until then the board stays locked.
- `static/js/settings.js` and `static/js/settings-panel.js`: the per-device settings store (`justchess.settings.v1`) and its panel. `static/js/boot.js` applies the saved theme and board before first paint; load it with a plain `<script>` in `<head>`.

The game screen is built on it, also as plain ES modules with no build step: `static/js/app.js` (routing and wiring), `api.js` (HTTP client), `live.js` (socket and reconnect), `seat-store.js`, `screen-state.js` (the screen state machine), `view-model.js` (everything the screen shows, computed from the server snapshot), `share.js`, `hooks.js` (extension points for later units), `room-flow.js` (joining a room and handling action answers), `captures.js` (the captured row, from the move list), `layout.js` (the board-fit rules, mirrored from the CSS for tests), `share-dialog.js` and `qr-canvas.js` (the share dialog and its QR code) and `static/js/screens/`. Styles are in `static/css/app.css`. The opening trainer is in `static/js/training/` (`trainer-state.js` is its pure state machine, `trainer.js` the view, `arrow.js` and `lessons-api.js`), styled by `static/css/training.css`.

With the app running, open `/static/demo/board.html` to see every board and page theme, both orientations and label modes, a scripted game, the promotion picker, the settings panel and a contrast self-check.

Tests: `node --test tests/js/` runs the JavaScript tests (Node 24, built-in runner). `uv run --frozen pytest -q` runs them too, through `tests/test_frontend_js.py`.

Credits. All assets are self-hosted and listed with their pinned source and sha256 in `static/ASSETS.md`:

- Pieces: cburnett, CC BY-SA 3.0. The chess pieces are by Colin M.L. Burnett, taken unchanged from the Lichess repository (which lists its copy as GPLv2+); see `static/pieces/cburnett/LICENSE.md`.
- Fonts: Libre Caslon Display and Libre Caslon Text (Pablo Impallari and contributors) and Atkinson Hyperlegible (Braille Institute of America), all under the SIL Open Font License 1.1, from the `@fontsource` packages, version 5.3.0. The licence texts are in `static/fonts/`.

## Current limitations

This is an unverified MVP, not a production release. Run with **one Uvicorn worker** because room locks and WebSocket fan-out use in-process memory. Multi-worker deployments require shared locking and pub/sub. Web Push for closed tabs needs VAPID keys and, beyond `localhost`, HTTPS hosting, which is still an open decision. Lessons are curated linear lines; no opponent-branching decision tree, arbitrary-move evaluation or Monaco lesson yet. A seat is lost when the browser's site data is cleared (use a continue link first to move it). For production, add abuse controls, expiry, accessibility checks and tests.
