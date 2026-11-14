# Interaction Specification

Component specifications for the P1 redesign, in the format of the component spec template. They trace to `inception/requirements-analysis/requirements.md` and use the tokens in `design-system-mapping.md`.

Breakpoints:
- mobile: below 768 px;
- tablet: 768–1023 px;
- desktop: 1024 px and wider.

---

## Board

| Field | Value |
|---|---|
| Component | Board |
| Description | The playable 8×8 board in its walnut frame |
| Category | input / display |

### States

| State | Description | Trigger |
|---|---|---|
| default | Position shown, your pieces at the bottom (FR5.2) | page load, state update |
| your-turn | Your pieces can be selected | server says it is your turn |
| selected | Ring on the chosen piece; dots on its legal targets (FR3.1) | tap, click, or Enter on a square holding your piece |
| moving | Piece slides 200 ms; input is blocked until the server answers | tap on a target |
| check | Red wash and 2 pulses on the king's square (FR3.6) | state has check |
| locked | No selection possible; board dimmed after game end (FR4.1) | game finished |
| reconnecting | Board dimmed, last known position kept | WebSocket lost |
| error | Move rejected: the piece slides back and the status explains why | server refuses the move |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| fen | string | yes | — | Position |
| orientation | white / black | yes | your side | Which side is at the bottom |
| legal | string[] (UCI) | yes | [] | Legal moves from the server |
| lastMove | [from, to] | no | — | Brass highlight |
| labels | inside / frame | no | inside | Coordinate position (FR5.3), remembered per device |
| boardTheme | walnut-maple / tournament / rosewood | no | walnut-maple | FR10.3 |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| mobile | Full width minus the 16 px gutters: at least 374 px on 390 px phones with inside labels (FR5.4); with frame labels, the frame plus labels is at least 374 px |
| tablet | The board is as wide as the shorter viewport side allows, at most 640 px |
| desktop | 560–640 px in the left column; the side panel is on the right |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `grid` on the board; each square is a `button` |
| Keyboard interaction | Arrow keys move focus between squares, Enter or Space selects or moves, Escape clears the selection |
| Label / aria-label | Every square: "e4, white pawn" or "e4, empty"; with a selection, legal targets add ", legal move" |
| Contrast ratio | Pieces against both square colours of every board theme at least 3:1, with a dark outline on white pieces and a light edge on black (review finding R-04); highlights at least 3:1 |
| Screen reader | After each move, a polite live region announces "White played d4. Your move." |
| Focus management | Focus stays on the destination square after a move |

---

## Promotion picker (FR3.3)

| Field | Value |
|---|---|
| Component | Promotion picker |
| Description | Four pieces from the active set, anchored over the promotion square |
| Category | input |

| State | Description | Trigger |
|---|---|---|
| open | Queen, rook, bishop and knight in a column; focus on the queen | a pawn reaches the last rank |
| closed | Move cancelled; the pawn returns | Escape, or a tap outside |

Accessibility: `role="dialog"`, labelled "Promote pawn to". Arrow keys move between the pieces, Enter picks one.

---

## Blunder dialog (FR3.7, FR3.8, FR3.11, FR3.9)

| Field | Value |
|---|---|
| Component | Blunder dialog |
| Description | Asks to confirm a move that allows mate in one or hangs a piece, and says why |
| Category | feedback |

| State | Description | Trigger |
|---|---|---|
| open | Title states the consequence; the body names the move, piece and square | The server's check for the selected move reports a blunder |
| confirmed | The move is sent | "Play … anyway" |
| cancelled | The selection is cleared and the position is unchanged | "Choose another move", or Escape |

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| kind | mate-in-one / hanging-piece | yes | — | Which warning |
| move | SAN | yes | — | The move being confirmed |
| detail | string | yes | — | For example "White can play Qxf7#" |

Where the check runs: on the server, against the same game version as the move, so the warning and the move see the same position (review finding R-02). The client asks for it before sending a move only while "Warn me before blunders" is on.

Accessibility: `role="dialog"`, `aria-modal="true"`. Focus starts on "Choose another move" and is trapped inside; Escape cancels; focus returns to the board.

---

## Status line

| State | Text | Style |
|---|---|---|
| waiting | "Waiting for your opponent. Send them the link." | surface |
| your move | "Your move", with the opponent's last move under it | baize fill and dot |
| their move | "Waiting for Black" (or White) | surface |
| check | "Check — your move" | baize, red dot |
| opponent disconnected | "Black is away" | surface, hollow dot |
| reconnecting | "Reconnecting…" | surface |
| game over | "Game over", with the reason | surface |

Accessibility: `role="status"` and `aria-live="polite"`. State is carried by the text, not only by colour.

---

## Share control (FR2.1, FR2.2, FR1.7)

| State | Behaviour |
|---|---|
| default | The "Share" primary button sits in the top bar |
| share sheet | When the browser supports it, opens the system sheet with "Play chess with me on JustChess" and the invite link |
| fallback | Copies the invite link; the button reads "Link copied" for 1.6 s |
| continue on another device | In Game settings: "Get a private continue link". Shows the link with the warning "Anyone with this link can play your side. Don't share it." and Copy (FR1.7) |

When the continue link is opened on a second device while the first is still connected, the seat moves to the newest device. The first device shows "This game was opened on another device" and becomes read-only (review finding R-03).

---

## Scoresheet (FR3.5)

Numbered rows with White and Black columns; the latest move is in ink colour. On a phone it shows the last 6 rows and expands on tap. The result box fills at game end, with the ink stroke described in the motion tokens.

Accessibility: a native `<table>` with column headers. The result is announced in the game-over live region.

---

## End-of-game overlay (FR4.1, FR4.4)

| State | Content |
|---|---|
| shown | The reason as the title, then the winner and decisive move, then "Play again" (primary) and "Share result" (secondary) |
| waiting for rematch | "Play again" becomes "Waiting for opponent" (disabled) |
| rematch lapsed | "Your opponent left. Share the link to play again." |

Accessibility: not modal, so the board and scoresheet stay readable. Focus moves to "Play again", and the title is announced.

---

## Learn openings drawer (FR5.5, FR5.6)

A collapsed `<details>` element: "Learn openings — your game keeps running". It opens inline below the game. When the opponent moves while it is open, a sticky banner appears: "Your move in the game. Back to the board". Activating it scrolls back to the board and closes the drawer.

---

## Game settings (FR3.9, FR5.3, FR10.2, FR10.3, FR6.7)

A sheet that opens from "Game settings":
- Theme: Device, Light or Dark.
- Board: Walnut and maple, Tournament green or Rosewood.
- Coordinates: On squares or In the frame.
- Warn me before blunders: on or off.
- Notifications: on or off.
- Get a private continue link.

Every choice applies at once and is remembered on the device. If storage is blocked, the sheet says "Settings won't be kept after you close this tab."

The credit "Pieces: cburnett, CC BY-SA 3.0" appears at the bottom (FR10.5).
