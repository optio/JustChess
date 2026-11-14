# Requirements Analysis — Questions

Inputs: REQUIREMENTS.md (the current spec), the code scan in `aidlc/spaces/default/codekb/JustChess/` (especially the implemented-vs-specified table in `business-overview.md`), the approved intent statement, and your observations from playing the app (message of 2026-11-11):

> "In the current code, the when a user wins, the game doessnt end. also a user is able to set themselves checkmate even when tehre are other optionsand that should be prevented with an indication to the user why. Also the notifications dont seems to work. and curing a game, the learning learn opeings is visible which is great but should be clarified that starting an opening is not stopping the ongoing game. and user should have an easy way to share teh code and deeplink for example using email whatsapp and other methods. Currently when game is ongoin the tile, subtitle, white space under it , the share code and so onall take up a lot of space before teh real board is shown. the board itself has too much spacing around it making the board smaller as it could be larger. the board should visually have clear indicate on row and column so that for example 'e5' is easily identified"

Already taken as requirements without asking (clear bugs the scan found): fix the swapped square colours (a1 must be dark), turn the board around for the player with Black, show check on screen, add join-by-link (a URL containing the room code), and add row/column labels (your request).

## Q1. [Product owner] Where should the lasting product requirements live once REQUIREMENTS.md is deleted?

Context: you chose "the pure AI-DLC methodology". In AI-DLC, this work's `requirements.md` is tied to this one piece of work. The space knowledge folder (`aidlc/spaces/default/knowledge/`) is what every future piece of work reads automatically. The reviewer flagged that this was still open.

- A. This work's `requirements.md` becomes the full product spec; future work reads it from here
- B. This work's `requirements.md` holds the full spec, and a short product vision plus the feature backlog also goes into `aidlc/spaces/default/knowledge/` so every future piece of work starts from it
- C. Only the knowledge folder; this work's `requirements.md` covers just the changes decided in this review
- D. Not yet defined
- X. Other (please specify)

[Answer]: X. Other: "as discussed before, follow the AIDLC conventins making this requirements.md obolete I think"

## Q2. [Product owner] What is the next delivery phase you want to build first?

Context: you want a clean spec before building the next phase. Your observations are all about playing a game; the spec's own phase plan puts guided lessons and branching practice after multiplayer.

- A. Polish the two-player game first: game end, layout, board, sharing, notifications. Training comes after
- B. Improve training first: scripted opponent, more openings, branching
- C. Both together in one phase
- D. Not yet defined
- X. Other (please specify)

[Answer]: C

## Q3. [Product owner] What should happen when a game is won?

Context: the server does mark the game finished on checkmate and blocks further moves. The screen only shows a small status line like "Game finished: 1-0", so it is easy to miss and looks like the game goes on. There is no resign or rematch yet.

- A. Show a clear end-of-game message naming the winner and the reason (checkmate, stalemate, draw type), and visibly lock the board
- B. A, plus a "Play again" (rematch) button that swaps colours and keeps the room's score
- C. B, plus a Resign button and a draw offer during the game
- D. Not sure it is only a display problem — investigate a reproduction first
- X. Other (please specify)

[Answer]: B

## Q4. [Product owner] What did you mean by "a user is able to set themselves checkmate"?

Context: the chess rules already forbid moves that leave your own king in check, and the server rejects them. So this most likely means a move that lets the opponent checkmate on the very next move (a blunder). Blocking that is not part of real chess rules.

- A. In a two-player game, block a move that allows mate-in-one and explain why
- B. Warn ("this lets your opponent checkmate next move") and ask to confirm, then allow it
- C. No help in real games (pure chess); only offer such warnings in training
- D. I meant something else (please describe)
- X. Other (please specify)

[Answer]: X. Other: "use the real chess rules but when the user doe a blunder ask them to confirm the move and explain why"

## Q5. [Product owner] How should notifications work?

Context: today a notification only fires if you granted permission AND the tab is not focused. On most phones (e.g. Android Chrome), a page cannot show a notification without a service worker, so it silently does nothing. That is the likely reason they "don't seem to work". Push alerts when the page is closed are not built.

- A. Reliable in-page alerts first (sound, vibration, flashing tab title, clear "your turn" banner), plus browser notifications through a service worker where supported
- B. A now, and Web Push alerts when the page is closed in a later phase
- C. Go straight to full Web Push (service worker, subscriptions, HTTPS)
- D. Drop notifications for now
- X. Other (please specify)

[Answer]: X. Other: "ok lets go with that" — local notifications through the service worker plus full Web Push, built together with de-duplication (one tag per event, service worker skips the system notification when the room is visible, server pushes only when the player is disconnected or has not seen the move, one alert per move number), so a player gets at most one alert per opponent move

## Q6. [Product owner] How should sharing the room work?

Context: today there is only a "Copy code" button, and a link containing the code does not work yet (join-by-link is now a requirement).

- A. A "Share" button that opens the phone's native share sheet (WhatsApp, email, SMS, …) with the invite link, plus "Copy link" as the fallback on desktop
- B. A, plus direct WhatsApp and email buttons
- C. A, plus a QR code for someone sitting next to you
- D. Just "Copy link"
- X. Other (please specify)

[Answer]: A

## Q7. [Product owner] Where the spec and the code disagree, which should the requirements follow?

Context: the scan found four disagreements. (1) The spec says the UI uses HTMX; HTMX is loaded but unused and the UI is plain JavaScript. (2) The spec describes separate tables for players, moves and results; the code has one `games` table and stores seat tokens unhashed. (3) The spec says draws by repetition or the 50-move rule must be claimed; the code ends the game automatically. (4) The spec says lessons live in YAML/JSON files; they are hard-coded in `app.py`.

- A. Follow the code where it is simpler (plain JS, one table, automatic draws). Keep the spec where it matters for security or content (hash tokens, lessons in data files)
- B. Follow the spec everywhere: the code must change
- C. Follow the code everywhere: update the spec
- D. Not yet defined
- X. Other (please specify)

[Answer]: X. Other: "specs everywhere unless the specs are overengineered"

## Q8. [Product owner] In practice mode, who plays the opponent's moves?

Context: the spec says the trainer replies with scripted opponent moves. Today the learner has to play both sides.

- A. The trainer plays the opponent's moves; the learner plays only their side
- B. A, and the learner can pick which side to learn (White or Black)
- C. Keep playing both sides
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Q9. [Product owner] What happens to the larger features in the spec that are not built yet?

Context: these include branching opening trees, transpositions, the full opening catalog (about 17 lines), quizzes, Web Push, spectators, drag-and-drop, captured material, Docker deployment, rate limits, room expiry and backups. Keeping everything as "must" makes the spec hard to trust.

- A. Keep them all, but give each a priority (Must / Should / Could) and a phase
- B. Keep only what the next phase needs as requirements; move the rest to a "Later" backlog section
- C. Cut the rest entirely
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Q10. [Designer] How should the screen look during a game?

Context: during a game, the title, subtitle, spacing, room heading and copy button all sit above the board, and the board has generous padding around it. On a phone that pushes the board down and shrinks it.

- A. Slim top bar (logo, room code, share button on one line), board right under it and as wide as the screen allows, status and moves below the board
- B. A, and the lobby and the "Learn openings" section are hidden or collapsed while a game is on
- C. A, plus a "focus mode" that shows only the board and the status
- D. Not yet defined
- X. Other (please specify)

[Answer]: B

## Q11. [Designer] Where should the row and column labels (a–h, 1–8) go?

Context: you want a square like e5 to be easy to find.

- A. Small letters and numbers inside the edge squares (bottom row letters, left column numbers), so the board loses no size
- B. Labels outside the board along the bottom and left edges
- C. A, and the name of the selected square is shown (e.g. "e2 → e4") while moving
- D. Not yet defined
- X. Other (please specify)

[Answer]: X. Other: "Alallow user to choose, default inside"

## Q12. [Designer] How should "Learn openings" behave while a game is going on?

Context: you like having lessons visible during a game, but it must be clear that starting a lesson does not stop the game.

- A. Keep it below the game, with a clear note: "Practice an opening — your game keeps running"
- B. Open lessons in a separate panel or tab while the game stays visible, with a "your turn" signal if the opponent moves meanwhile
- C. A, and show a small "Back to your game (your turn!)" banner when the opponent moves while you are in a lesson
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Q13. [Product owner] Which moves count as a "blunder" that triggers the confirm-and-explain warning?

Context (follow-up to Q4): the spec says no chess engine. Without one, the app can reliably detect a move that lets the opponent checkmate next move, and with simple checks a move that leaves a piece undefended where it can be taken for free. Judging deeper mistakes needs an engine such as Stockfish.

- A. Only moves that allow checkmate on the next move
- B. A, plus moves that leave a piece (not a pawn) undefended where the opponent can take it for free
- C. Any significant mistake, which means adding an engine (e.g. Stockfish) to the requirements
- D. Not yet defined
- X. Other (please specify)

[Answer]: X. Other: "mate-in-one and ootiinally also hanging pieces"

## Q14. [Product owner] Which spec items count as over-engineered for JustChess?

Context (follow-up to Q7, "specs everywhere unless the specs are overengineered"): this is my proposal for each disagreement. HTMX: drop it. The UI is a small plain-JavaScript controller, so adding HTMX would add a dependency without benefit. Database tables: follow the spec. Rematch (Q3) and Web Push (Q5) need separate players, moves, results and push-subscription data anyway, and tokens are stored hashed. Draws: follow the official chess rules. The game ends automatically on fivefold repetition and the 75-move rule, and a player may claim a draw on threefold repetition or the 50-move rule. Lessons: follow the spec and store them in YAML/JSON data files.

- A. Agree with this proposal
- B. Agree, but keep draws automatic as they are today (no claim button)
- C. Agree, but keep the single `games` table (only add token hashing)
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Q15. [Product owner] What does "optionally also hanging pieces" mean for the blunder warning?

Context (follow-up to Q13): the mate-in-one warning is always on.

- A. Hanging-piece warnings are a setting each player can switch on or off (mate-in-one warning always on)
- B. Hanging-piece warnings are a later "nice to have", not part of the next phase
- C. Both warnings are one setting the player can switch off entirely
- D. Not yet defined
- X. Other (please specify)

[Answer]: C

## Q16. [Designer] Two of your layout answers pull in different directions — which wins?

Context (contradiction between Q10 and Q12): in Q10 you chose to hide the lobby and "Learn openings" while a game is on. In Q12 you chose to keep "Learn openings" below the game with a note that the game keeps running.

- A. Hide the lobby during a game. Keep "Learn openings" below the game, collapsed to a single line ("Learn openings — your game keeps running"), and open it with a tap
- B. Hide both during a game; lessons are reachable only after the game or from a menu
- C. Hide only the lobby; keep "Learn openings" fully open below the game with the note
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Where the spec lives: follow AI-DLC conventions. This work's `requirements.md` becomes the product spec and makes REQUIREMENTS.md obsolete; nothing extra goes into the knowledge folder (Q1).
- Next phase: two-player polish and training improvements together, in one phase (Q2).
- End of game: a clear end-of-game message naming the winner and the reason, a visibly locked board, and a "Play again" rematch that swaps colours and keeps the room score (Q3).
- Blunders: real chess rules. A move that allows checkmate next move, or leaves a non-pawn piece hanging for free, asks the player to confirm and explains why. One player setting switches both warnings off (Q4, Q13, Q15).
- Notifications: local notifications through a service worker plus full Web Push, built together, with de-duplication so a player gets at most one alert per opponent move (Q5).
- Sharing: a native share sheet with the invite link, plus "Copy link" as the fallback; joining by link works (Q6).
- Spec vs code: follow the spec unless it is over-engineered. Drop HTMX (plain JavaScript). Use separate players, moves, results and push-subscription data, with hashed tokens. Follow official draw rules (automatic at fivefold repetition and the 75-move rule; claim at threefold repetition and the 50-move rule). Lessons live in YAML/JSON files (Q7, Q14).
- Practice mode: the trainer plays the opponent's scripted moves; the learner plays only their side (Q8).
- Unbuilt spec features stay, each with a priority (Must/Should/Could) and a phase (Q9).
- Game screen: a slim top bar (logo, room code, share), the board right under it and as large as possible, the lobby hidden during a game, and "Learn openings" collapsed to one tappable line below the game with "your game keeps running" (Q10, Q12, Q16).
- Board labels: a–h and 1–8 inside the edge squares by default; the player can switch them to outside the board (Q11).
- Already settled from the scan: fix the swapped square colours, turn the board for Black, show check, and add join-by-link.

Does this all look correct before I generate the requirements artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
