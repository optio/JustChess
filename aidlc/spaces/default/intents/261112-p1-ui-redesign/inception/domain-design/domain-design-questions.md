# Domain Design — Questions

Inputs:
- `inception/requirements-analysis/requirements.md`;
- the code map `aidlc/spaces/default/codekb/JustChess/architecture.md` and `component-inventory.md`, which list today's 10 parts in one `app.py`, one `app.js` and one CSS line;
- `inception/refined-mockups/interaction-spec.md`.

Most boundaries follow directly from the requirements, so I'll decide them and you can correct them at approval:
- Rooms and seats.
- Real-time updates.
- Notifications.
- Lessons and training.
- Engine availability.
- The board UI.

These three choices have real trade-offs:

## Q1. [Developer] Where does a match of several games live?

Context: P1 adds rematch with colour swap and a scoreboard that follows the player (FR4.4, FR4.5). Today one `games` row is the room, the seats and the single game at once.

- A. Two parts. **Room** owns the code, the two seats (hashed tokens) and the match score across games. **Game** owns one game: its moves, its rules and its result. A rematch is a new Game in the same Room.
- B. One part, **Game**, that also owns seats and the score (closest to today's code)
- C. A, but the score is computed from the stored game results each time instead of being kept as a running count
- D. Not sure, you decide
- X. Other (please specify)

[Answer]: A

## Q2. [Developer] Where does blunder detection live?

Context: FR3.7 and FR3.8 add mate-in-one and hanging-piece warnings, checked on the server. Stockfish (FR9) is installed for future analysis features.

- A. A separate **Analysis** part that answers "what does this move allow?" and that later Stockfish features plug into. Game asks it before a move
- B. Inside the Game rules
- C. Not sure, you decide
- X. Other (please specify)

[Answer]: A

## Q3. [Developer] How should the new frontend be structured?

Context: today's frontend is 23 lines of minified-style JavaScript with global state. The redesign adds a board component, dialogs, settings, animations, a service worker and push. The constraints say plain JavaScript and no HTMX.

- A. Plain JavaScript split into native ES modules (board, game, lobby, training, notifications, settings), loaded straight by the browser with no build step
- B. Plain JavaScript modules, plus a small build step (esbuild) that bundles and minifies for production
- C. Not sure, you decide
- X. Other (please specify)

[Answer]: A
