# Frontend Components — u2-design-system-board

These are the component contracts for U2. The behaviour is in `functional-spec.md`, the rules in `rules.md`, and the values in `inception/refined-mockups/design-system-mapping.md`. Everything is a static file under `static/`, loaded as native ES modules with no build step.

## Hierarchy

```
Design system (CSS)
├── tokens        colour, type, radius, motion tokens; light and dark; 3 board themes
├── base          fonts, page ground, type scale, 4 button roles, focus ring, logo mark
└── board         frame, squares, labels, highlights, pieces, motion, picker

Modules (JS)
├── board/geometry     pure: squares, orientation, FEN, targets, promotion, move diff, focus moves, labels
├── board/board        Board component (DOM), uses geometry
├── board/promotion    Promotion picker (DOM)
├── settings           settings store (pure, storage injected) + applyToDocument
└── settings-panel     the settings controls (DOM), uses settings

Assets
├── fonts/      Libre Caslon Display, Libre Caslon Text (regular, italic), Atkinson Hyperlegible (regular, bold) as woff2 + OFL licence
├── pieces/cburnett/   12 SVGs + licence file
└── logo.svg    2×2 checker in a walnut tile with a brass inlay

Demo
└── demo/board.html    standalone page: board in every theme, both orientations, labels, a scripted game, the picker, the settings panel
```

## Board

`createBoard(element, options) → board`

| Option | Type | Default | Notes |
|---|---|---|---|
| fen | string | start position | Position to draw |
| orientation | `"white"` \| `"black"` | `"white"` | BR1.2 |
| legalMoves | string[] (UCI) | `[]` | Only these can be played (BR2.1) |
| lastMove | `{from, to}` \| null | null | Brass highlight; drives the slide (BR4.1) |
| check | boolean | false | Wash plus pulse on the side-to-move king (BR3.1, BR4.2) |
| interactive | boolean | false | false = locked |
| labels | `"inside"` \| `"frame"` | `"inside"` | BR1.3 |
| piecePath | string | `/static/pieces/cburnett/` | Base URL for the SVGs |
| onMove | (uci) → void | none | Called once per emitted move |

| Method | Effect |
|---|---|
| `set(partialOptions)` | Update any options; diffs and animates per W4 |
| `reject()` | Slides the pending piece back and unlocks (BR2.3) |
| `focus()` | Focuses the board's roving square |
| `destroy()` | Removes listeners and DOM |

Internal state: `selected`, `pending`, `promoting`, `focusSquare`, `shownPieces`, `inCheckBefore`.

DOM:
- a `div.board-frame` holding a `div[role=grid]`, with 8 `div[role=row]` and 64 `button.sq[role=gridcell]`;
- each button has `data-square`, an `aria-label` (BR3.2) and `tabindex` (roving);
- pieces are `img.piece` with an empty `alt`, because the square's label names the piece;
- an `aria-live=polite` region next to the board, which the caller fills (U3 owns the move sentence).

## Promotion picker

`openPromotion(anchorSquareEl, colour, piecePath) → Promise<"q"|"r"|"b"|"n"|null>`

It renders a `div[role=dialog][aria-label="Promote pawn to"]` with four buttons, anchored over the square and opening towards the board's centre. It resolves null on Escape or a click outside. Focus starts on the queen and returns to the square on close.

## Settings store

`createSettings(storage = safeLocalStorage()) → store`

| Key | Values | Default |
|---|---|---|
| theme | `device` \| `light` \| `dark` | `device` |
| board | `walnut-maple` \| `tournament` \| `rosewood` | `walnut-maple` |
| labels | `inside` \| `frame` | `inside` |
| blunderWarnings | boolean | `true` |
| notifications | boolean | `false` |

| Member | Effect |
|---|---|
| `get(key)` / `all()` | Current values |
| `set(key, value)` | Validates the value (an unknown value is refused with an error), saves it when possible, and notifies subscribers |
| `subscribe(fn)` → unsubscribe | `fn(key, value, all)` on each change |
| `persistent` | false when storage threw (BR6.2) |

`applyToDocument(store, root = document.documentElement)` sets `data-theme` and `data-board` and keeps them in sync. A one-line inline boot script in the page head reads the same storage key and sets the attributes before first paint.

The storage key is `justchess.settings.v1`, holding a JSON object. It is separate from the seat storage that U3 owns.

## Settings panel

`renderSettingsPanel(container, store, hooks)`

- It renders radio groups for theme, board and coordinates, and switches for blunder warnings and notifications.
- It includes the credit line "Pieces: cburnett, CC BY-SA 3.0" and the not-persistent notice when needed.
- `hooks.onNotificationsToggle(value)` lets U5 run the permission prompt before the value is stored. When there is no hook, the value is stored directly.
- `hooks.extraRows` is a slot for U3's continue-link row.

All controls are native inputs with visible labels, and each touch target is at least 44 px.

## Interaction flows

See `functional-spec.md` W2–W5. The keyboard map is:

| Key | Board | Picker |
|---|---|---|
| Arrow keys | Move focus one square in visual space | Move between pieces |
| Enter, Space | Tap the focused square | Choose |
| Escape | Clear the selection | Cancel |
| Tab | Leave the board | Cycle inside (focus trapped) |

## Form validation

The only inputs are the settings controls. Their values come from a fixed list, and the store refuses anything else (BR6.1).

## API integration points

None in U2. U3 maps U1's snapshot to the board options:

| Board option | Snapshot field |
|---|---|
| `fen` | `fen` |
| `orientation` | `colour` (watcher: white) |
| `legalMoves` | `legalMoves` |
| `lastMove` | `lastMove` |
| `check` | `check` |
| `interactive` | `status == playing` and the seat is on move |

U3 sends `onMove` to `POST /api/rooms/{code}/moves` and calls `reject()` on refusal.
