# Frontend Components — u3-game-screen

These are the component contracts for U3. The behaviour is in `functional-spec.md`, the rules in `rules.md`, and the screens and texts in `inception/refined-mockups/mockups.md` and `interaction-spec.md`. Everything is a native ES module under `static/js/`, with no build step, as in U2.

## Hierarchy

```
templates/index.html        shell: <head> boot.js + CSS, top bar, <main id="app">, live region
static/js/app.js            entry: route (/ or /r/CODE), screen state machine, wiring
├── api.js                  HTTP client (pure request building + fetch wrapper)
├── live.js                 socket client: hello/ping/visibility, backoff, events
├── seat-store.js           seat per room in long-lived storage; memory fallback
├── view-model.js           PURE: snapshot + context → everything the screen shows
├── share.js                share sheet / clipboard / field fallback
├── screens/lobby.js        lobby view
├── screens/game.js         game view: board (U2), status, claims, scoresheet, score, drawer
├── screens/overlay.js      end-of-game overlay + rematch button states
├── screens/win-sequence.js king tip, dim, ink, glow (Web Animations, reduced motion)
└── hooks.js                extension points: beforeMove (U4), notifications (U5), lessons mount (U6)
static/css/app.css          shell, top bar, lobby, game layout, status, scoresheet, overlay
```

## View model (pure)

`viewModel(snapshot, ctx) → View`, where ctx is `{connection: "open"|"reconnecting", seatSaved: boolean, seatMoved: boolean, drawerOpen: boolean}`.

| View field | Meaning |
|---|---|
| `screen` | `waiting` \| `playing` \| `gameOver` \| `watching` \| `reconnecting` |
| `board` | `{fen, orientation, legalMoves, lastMove: {from, to} \| null, check, interactive}` |
| `status` | `{text, sub, tone: "baize"\|"surface", dot: "solid"\|"hollow"\|"red"\|null}` (BR3.4) |
| `claims` | `{draw: null \| "threefold" \| "fifty_moves", win: boolean}` (BR3.7) |
| `scoresheet` | `{rows: [{number, white, black}], latest: {row, side}, result: "1–0"\|"0–1"\|"½–½"\|null}` |
| `score` | `{left: {label, wins}, right: {label, wins}, draws}` (BR3.6) |
| `overlay` | `null \| {title, subtitle, rematch: "offer"\|"waiting"\|"opponentReady"\|"lapsed"}` (BR4.2, BR4.3) |
| `notices` | list from `storageBlocked`, `seatMoved`, `seatsTaken` |
| `announce` | the live-region sentence for the newest move, or null |

`endTitle(endReason)` and `resultText(result)` are exported for tests.

## API client

`createApi(fetchImpl = fetch)` returns:
- `createRoom()` → `{code, token, slot, colour}`
- `join(code, token?)`
- `state(code, token?)`, which sends the header
- `move(code, token, uci, version)`
- `claimDraw(code, token)`
- `claimWin(code, token)`
- `rematch(code, token)`
- `continueLink(code, token)`
- `redeemContinue(code, continueToken)`

Each call resolves to `{ok: true, data}` or `{ok: false, status, message, snapshot?}`. Network failures give `{ok: false, status: 0, message: "Couldn't reach the server. Try again."}`. The client never throws for HTTP errors, and never puts a token in a URL.

## Live client

`createLive({code, token, WebSocketImpl, onState, onSeatMoved, onConnection, schedule})` returns `{close(), setToken(t)}`. The backoff is `[1000, 2000, 4000, 8000]` and then 10000 repeating, exported as `backoffDelay(attempt)`. It pings every 5000 ms while open and sends visibility on `visibilitychange`.

## Seat store

`createSeatStore(storage)` returns:
- `get(code)` → `{token, slot}` \| null
- `set(code, seat)`
- `remove(code)`
- `persistent`

`parseContinueFragment(hash)` → token \| null. The keys are `justchess.seat.<CODE>`.

## Screens

- **Lobby:** the headline, "Start a game", "Have a room code?" with Join, the framed starting board (U2 board, not interactive) and the inline error area.
- **Game:**
  - the board container (U2), then the players line;
  - the status (`role=status`), the claim buttons and the notices;
  - Game settings (U2 panel plus the continue-link row);
  - the scoresheet `<table>`, the room score and the lessons `<details>`.
- **Overlay:** a non-modal panel over the board. Focus goes to the primary button when it opens. The "Share result" button shares or copies a line such as "I won by checkmate on JustChess".

## Interaction flows

See `functional-spec.md` W1–W10. Keyboard:
- Tab order: the top bar, the board, the status actions, settings, the scoresheet, then the drawer.
- Escape closes the settings sheet.
- Every control is a native button or link.

## Form validation

There is only the room-code field. It uppercases input, accepts up to 6 characters, and must match `^[A-Z0-9]{6}$` on submit. It has a visible label, and its error text is linked through `aria-describedby`.

## API integration points

| Action | Route | Body or header |
|---|---|---|
| Start a game | `POST /api/rooms` | none |
| Join or rejoin | `POST /api/rooms/{code}/join` | `{token?}` |
| State read | `GET /api/rooms/{code}` | `X-Seat-Token` |
| Move | `POST /api/rooms/{code}/moves` | `{token, uci, version}` |
| Claim draw or win | `POST …/claim-draw`, `…/claim-win` | `{token}` |
| Rematch | `POST …/rematch` | `{token}` |
| Continue link | `POST …/continue-link` → `{continueToken}` | `{token}` |
| Redeem | `POST …/continue` → `{token, slot, colour}` | `{continueToken}` |
| Live | `WS /ws/{code}` | `hello {token?, visible}`, `ping`, `visibility` |
