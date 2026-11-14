# Mockups — JustChess P1 redesign

**Clickable mockup:** https://claude.ai/artifact/8bGfnHDmw9VNsPoovPFvoF (source: `mockup.html` in this folder).

The review controls at the top of the mockup switch:
- accent (ink blue or brass);
- theme (device, light or dark);
- board theme;
- label position;
- your seat (White or Black, which flips the board).

Requirements come from `inception/requirements-analysis/requirements.md`. Tokens and components are in `design-system-mapping.md`, and behaviour is in `interaction-spec.md`.

There were no rough wireframes for this work, so these screens are drawn from the requirements and from the current UI described in the code map.

## Screen 1: Lobby (FR1.1, FR1.2, FR10.1, FR10.6)

```
Phone (390 px)                         Desktop (>= 900 px)
+----------------------------+         +-----------------------+-----------------------+
| [mark] JustChess           |         | [mark] JustChess      |                       |
|                            |         | Play a friend.        |  +-----------------+  |
| Play a friend.             |         | Learn an opening.     |  | walnut frame    |  |
| Learn an opening.          |         | No accounts. ...      |  |  start position |  |
| No accounts. No subs...    |         | [Start a game]        |  |                 |  |
| [Start a game] [Learn ..]  |         | [Learn an opening]    |  +-----------------+  |
| Have a room code?          |         | Have a room code?     |                       |
| [K7Q2PX ] [Join]           |         | [K7Q2PX ] [Join]      |                       |
| +------------------------+ |         +-----------------------+-----------------------+
| | walnut frame, start    | |
| +------------------------+ |
+----------------------------+
```
<!-- Text fallback: on phones the headline, actions and code entry stack above the framed starting board; on desktop they sit left of it. -->

- One primary action ("Start a game"). Joining is secondary and needs the code typed.
- The framed starting position is the hero, so the first thing you see is a chess set, not a form.
- A link with a code (FR1.3) skips this screen and goes straight to the game.

## Screen 2: Game (FR3.1, FR3.5, FR3.6, FR5.1–FR5.6, FR2.1–FR2.2)

```
Phone (390 x 844)                      Desktop (>= 1024 px)
+----------------------------+         +-----------------------------------------------+
| [mark] JustChess K7Q2PX [Share]       | [mark] JustChess               K7Q2PX [Share] |
| +------------------------+ |  <=72px |  +---------------------+  You play White      |
| |                        | |         |  |                     |  [ Your move  ]baize |
| |  board 374+ px wide,   | |         |  |  board 560-640 px   |  [Replay] Settings   |
| |  walnut frame, a-h/1-8 | |         |  |                     |  +--Scoresheet-----+ |
| |  on edge squares       | |         |  |                     |  | 1 | e4  | e5    | |
| +------------------------+ |         |  +---------------------+  | 2 | Nf3 | Nc6   | |
| You play White  Opp. Black |         |                           | ...             | |
| [o Your move / White d4  ] |         |                           +-----------------+ |
| [Replay last move] Settings|         |                           Room score 2 / 1 / 0|
| +--Scoresheet------------+ |         |                           > Learn openings    |
| | 1 | e4  | e5           | |         +-----------------------------------------------+
| ...                        |
| Room score: you 2, opp 1   |
| > Learn openings (keeps running)
+----------------------------+
```
<!-- Text fallback: phone stacks a slim top bar, the full-width framed board, players, status, actions, scoresheet, score and a collapsed lessons line; desktop puts the board left and everything else in a right column. -->

- Slim top bar: mark, room code, Share (FR5.4, FR2.1). The lobby is gone during a game (FR5.5).
- Board: correct colours with a1 dark (FR5.1). Your pieces are at the bottom; the "Seat" switch shows the flip (FR5.2). Labels are on the edge squares by default, and a setting moves them into the frame (FR5.3).
- Status: "Your move" fills with baize green and has a leading dot, so it never relies on colour alone (FR3.6, NFR6). In check, the king's square is washed red and the status reads "Check".
- Scoresheet: numbered rows with White and Black columns; moves are written in ink colour (FR3.5).
- "Learn openings — your game keeps running" sits collapsed under the game (FR5.5, FR5.6).

## Screen 3: Blunder warning (FR3.7, FR3.8, FR3.9)

```
+--------------------------------------+
| Your bishop can be taken for free    |
| After Bishop to a3, White's pawn on  |
| b2 takes it and nothing takes back.  |
|      [Choose another move] [Play Ba3 anyway] |
+--------------------------------------+
```
<!-- Text fallback: a centred dialog with a plain-language title, one sentence naming the piece, square and capturer, and two buttons. -->

- The title says the consequence in plain words; the body names the piece, the square and the capturing piece.
- "Choose another move" is the safe default and has focus. "Play … anyway" is the primary button, because it is the deliberate choice to go ahead.
- For mate-in-one, the title is "This allows checkmate" and the body names the move, for example "White can play Qxf7#".
- The setting "Warn me before blunders" (on by default) is in Game settings (FR3.9).

## Screen 4: Game over (FR4.1–FR4.5, FR10.4)

```
+------------------------+   +--Scoresheet--------+
|  board dimmed,         |   | 1 | e4   | e5     |
|  black king tipped,    |   | 4 | Qxf7#|        |
|  white pieces glowing  |   | Result      1–0   |  <- inked
|  +------------------+  |   +--------------------+
|  | Checkmate        |  |   Colours swap if you play again
|  | White wins with  |  |   Room score: you 3, opponent 1, draws 0
|  | Queen takes f7   |  |
|  | [Play again] [Share result]
|  +------------------+  |
+------------------------+
```
<!-- Text fallback: after checkmate the board dims, the losing king tips over, the result is written into the scoresheet's result box, and an overlay names winner and reason with Play again and Share result. -->

- The sequence is in `design-system-mapping.md` (motion tokens): the king tips, the board dims, "1–0" is inked, the overlay appears, and the winner's pieces glow.
- The reason is always named, for example "Checkmate", "Stalemate", "Draw by fivefold repetition", "Draw claimed (threefold repetition)" or "Opponent left" (FR4.2, FR11.2).
- After you press "Play again", the button reads "Waiting for opponent" until they press it too (FR4.4).

## Other designed states (FR10.6)

| State | Screen treatment |
|---|---|
| Waiting for opponent | The game screen with an empty board in its starting position. The status reads "Waiting for your opponent. Send them the link.", with Share as the primary button |
| Reconnecting | The status reads "Reconnecting…" with the last known board shown dimmed; there is no blocking spinner |
| Room not found | Lobby, with an inline message under the code field: "No room with code K7Q2PX. Check the code or start a new game." |
| Seat can't be remembered (storage blocked) | A one-line notice under the status: "This browser won't remember your seat. Keep this tab open, or use Continue on another device." (review finding R-03) |
| Both seats taken | "This game already has two players." with "Start a new game" |
| Claim draw available | A secondary button "Claim draw (threefold repetition)" appears under the status only while a claim is valid (FR4.3) |
| Opponent away for 24 h | A secondary button "Claim win (opponent left)" (FR11.2) |

## Training (FR7.1–FR7.5)

Training uses the same frame and scoresheet. A "Practise as White / Black" switch sits above the board (FR7.3). The note for each move appears as a margin annotation beside the scoresheet row, set in book italic. After 3 misses, the expected move is drawn as a dashed arrow (FR7.4).
