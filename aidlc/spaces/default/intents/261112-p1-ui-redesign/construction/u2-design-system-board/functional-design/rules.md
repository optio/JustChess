# Interface Rules — u2-design-system-board

These rules apply the U2 rows of `inception/units-generation/unit-of-work-story-map.md`, which come from `inception/requirements-analysis/requirements.md`. The values they use (colours, durations, sizes) come from `inception/refined-mockups/design-system-mapping.md`, `interaction-spec.md` and `accessibility-checklist.md`. U2 has no server data of its own. These rules govern what the board and the settings do with the inputs they are given.

```yaml
rules:
  # BR1 — Board geometry and orientation
  - id: BR1.1
    statement: A square is dark when its file index plus its rank index is even, counting a=0 and rank 1=0. So a1 is dark and h1 is light.
    category: calculation
    applies_to: square colour
    trigger: render
    logic: dark = (file + rank) % 2 == 0
    violation: n/a
    source: FR5.1
  - id: BR1.2
    statement: The board is drawn from the viewer's side. With orientation white, rank 8 is at the top and file a on the left. With orientation black, rank 1 is at the top and file h on the left.
    category: calculation
    applies_to: board layout
    trigger: render, orientation change
    logic: IF orientation is black THEN reverse both the rank order and the file order
    violation: n/a
    source: FR5.2
  - id: BR1.3
    statement: Coordinates follow the orientation. Inside mode puts file letters in the bottom row of squares and rank numbers in the left column. Frame mode engraves them in the walnut frame on the bottom and left edges.
    category: calculation
    applies_to: coordinate labels
    trigger: render, labels setting change
    logic: the label set is the visual bottom row and the visual left column after BR1.2; the label colour contrasts with its square (light label on a dark square, dark label on a light square)
    violation: n/a
    source: FR5.3

  # BR2 — Selection and moving
  - id: BR2.1
    statement: A square can be selected only when the board is interactive and the square holds a piece that has at least one legal move in the given list.
    category: validation
    applies_to: selection
    trigger: tap, click, Enter or Space on a square
    logic: IF interactive AND legal moves contains a move starting on this square THEN select it and mark exactly its target squares; ELSE IF a square is selected AND this square is one of its targets THEN move; ELSE clear the selection (or select the newly tapped own piece)
    violation: nothing happens beyond clearing the selection
    source: FR3.1
  - id: BR2.2
    statement: A move to a target that only exists as promotion moves opens the promotion picker instead of moving. The picker offers queen, rook, bishop and knight in the active piece set. Cancelling leaves the pawn where it was.
    category: policy
    applies_to: promotion
    trigger: choosing a target whose legal moves have a 5th UCI character
    logic: open the picker over the target square; the chosen piece forms the UCI move from+to+q|r|b|n; Escape or a click outside closes it with no move
    violation: n/a
    source: FR3.3
  - id: BR2.3
    statement: After the board emits a move, it locks input until the caller gives it a new position or tells it the move was refused. On refusal, the piece slides back.
    category: constraint
    applies_to: input
    trigger: move emitted
    logic: pending = true; a new position clears pending and animates the change; a reject call animates the piece back to its origin and clears pending
    violation: input is ignored while pending
    source: FR3.1
  - id: BR2.4
    statement: Keyboard play works the same as pointer play. Arrow keys move focus in the visual direction, Enter or Space acts like a tap, and Escape clears the selection. After a move, focus stays on the destination square.
    category: policy
    applies_to: keyboard
    trigger: keydown on the board
    logic: arrow keys move focus by one square in visual space (BR1.2), stopping at the edges; one square holds tabindex 0 (roving tabindex)
    violation: n/a
    source: NFR6

  # BR3 — Highlights and announcements
  - id: BR3.1
    statement: Four highlights are drawn on every board theme. The last move uses brass at 38%. The selected square has a 4 px inset ring in the accent. A legal target has a 26% dot at 32% black, or a corner ring when it holds a piece. A king in check gets a red radial wash.
    category: calculation
    applies_to: highlights
    trigger: render
    logic: check is drawn on the square of the king of the side to move, and only when the caller's check flag is true
    violation: n/a
    source: FR3.6, FR3.1
  - id: BR3.2
    statement: Every square has an accessible name with its coordinate and piece, such as "e4, white pawn" or "e4, empty". A legal target adds ", legal move". A selected square adds ", selected".
    category: calculation
    applies_to: square aria-label
    trigger: render
    logic: label = coordinate + ", " + (colour + " " + piece name | "empty") + suffixes
    violation: n/a
    source: NFR6

  # BR4 — Motion
  - id: BR4.1
    statement: When a new position differs from the shown one by a single move, the moving piece slides from its origin to its destination in 200 ms with cubic-bezier(.2,.7,.2,1). A captured piece fades and drops 6 px over 150 ms. Castling slides the rook too. En passant removes the captured pawn.
    category: calculation
    applies_to: animation
    trigger: position update with lastMove
    logic: derive the move from lastMove (from, to); IF the board cannot match the change to one move THEN redraw without animation
    violation: n/a
    source: FR10.4
  - id: BR4.2
    statement: A check gets 2 pulses of 300 ms each on the king's square, once each time check starts.
    category: calculation
    applies_to: animation
    trigger: check flag turns true
    logic: pulse only on the change from not-check to check, not on every redraw
    violation: n/a
    source: FR10.4, FR3.6
  - id: BR4.3
    statement: When the device asks for reduced motion, every animation is skipped and the end state shows at once.
    category: policy
    applies_to: all motion
    trigger: prefers-reduced-motion is reduce
    logic: duration tokens become 0 and the check pulse is not run
    violation: n/a
    source: FR10.4

  # BR5 — Themes and identity
  - id: BR5.1
    statement: Colours come only from the design tokens. Light and dark themes both exist. The theme follows the device unless the person picked Light or Dark.
    category: policy
    applies_to: theme
    trigger: page load, setting change, device change
    logic: data-theme on the root element = light | dark when picked; absent for Device, where prefers-color-scheme decides
    violation: n/a
    source: FR10.2, FR10.1
  - id: BR5.2
    statement: The board has three themes, Walnut and maple (default), Tournament green and Rosewood. Changing it changes only the square colours.
    category: policy
    applies_to: board theme
    trigger: setting change
    logic: data-board on the root element selects the light and dark square tokens; highlights are the same on all themes
    violation: n/a
    source: FR10.3
  - id: BR5.3
    statement: The interface has four distinct button roles (primary, secondary, quiet and destructive) and uses Libre Caslon and Atkinson Hyperlegible, self-hosted from the app. The logo is an SVG mark.
    category: constraint
    applies_to: shared styles
    trigger: n/a
    logic: fonts are loaded from same-origin files with font-display swap; no third-party font or script requests
    violation: n/a
    source: FR10.1
  - id: BR5.4
    statement: Pieces are the cburnett SVG set, served from the app. The licence credit "Pieces: cburnett, CC BY-SA 3.0" is shown in the settings panel and the licence file ships with the pieces.
    category: constraint
    applies_to: pieces
    trigger: n/a
    logic: one SVG per piece (wK … bP); white pieces keep their dark outline, so pieces stay at least 3:1 against both square colours on every theme
    violation: n/a
    source: FR10.5

  # BR6 — Settings
  - id: BR6.1
    statement: The settings are theme (device, light or dark), board (walnut-maple, tournament or rosewood), coordinates (inside or frame), blunder warnings (on by default) and notifications (off by default). They are stored per device and apply at once.
    category: policy
    applies_to: settings
    trigger: change
    logic: read once at load; unknown or corrupt values fall back to the default for that key only; write the whole settings object on each change; notify subscribers
    violation: n/a
    source: FR3.9, FR5.3, FR10.2, FR10.3
  - id: BR6.2
    statement: When device storage cannot be read or written, the settings still work for this tab and the panel says "Settings won't be kept after you close this tab."
    category: policy
    applies_to: settings persistence
    trigger: storage access throws
    logic: keep the values in memory; set persistent = false; the panel shows the notice
    violation: n/a
    source: FR3.9
```

## Rules summary

| ID | Rule | Category | Source |
|---|---|---|---|
| BR1.1 | a1 dark, h1 light | calculation | FR5.1 |
| BR1.2 | Your side at the bottom | calculation | FR5.2 |
| BR1.3 | Coordinates inside or in the frame, following the orientation | calculation | FR5.3 |
| BR2.1 | Select only pieces that can move; mark exactly their targets | validation | FR3.1 |
| BR2.2 | Promotion picker with four pieces; cancelling keeps the pawn | policy | FR3.3 |
| BR2.3 | Input locked until the move is answered; slide back on refusal | constraint | FR3.1 |
| BR2.4 | Full keyboard play | policy | NFR6 |
| BR3.1 | Last-move, selection, target and check highlights | calculation | FR3.6, FR3.1 |
| BR3.2 | Accessible name on every square | calculation | NFR6 |
| BR4.1 | 200 ms slide, 150 ms capture | calculation | FR10.4 |
| BR4.2 | Check pulse twice, only on the change into check | calculation | FR10.4, FR3.6 |
| BR4.3 | Reduced motion skips all animation | policy | FR10.4 |
| BR5.1 | Token colours; light and dark following the device | policy | FR10.2, FR10.1 |
| BR5.2 | Three board themes | policy | FR10.3 |
| BR5.3 | Four button roles; self-hosted fonts; SVG logo | constraint | FR10.1 |
| BR5.4 | cburnett pieces with credit | constraint | FR10.5 |
| BR6.1 | Five per-device settings with defaults | policy | FR3.9, FR5.3, FR10.2, FR10.3 |
| BR6.2 | Blocked storage: works for this tab, with a notice | policy | FR3.9 |
