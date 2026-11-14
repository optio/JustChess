# Design System Mapping — JustChess "Club Set"

This replaces today's generic look (scan: one dark green, beige on every control, system font, identical rounded cards). It implements FR10.1–FR10.5 of `inception/requirements-analysis/requirements.md`, and it makes the visual requirements measurable, as review finding R-01 asked: every requirement below names a concrete token, count or duration.

Source of truth for the values: the clickable mockup `mockup.html` in this folder, published at https://claude.ai/artifact/8bGfnHDmw9VNsPoovPFvoF.

## Concept

The look comes from the objects of over-the-board chess:
- The folding wooden board: a walnut frame with a brass inlay line, and coordinates engraved in the frame. This is the one bold element.
- The tournament scoresheet: the move list is a ruled form, with moves in a book serif written in "ink".
- The green baize lining of the box: used only to say "your move".

Everything else stays quiet: no card stack, no gradients, and one radius per role.

## Colour tokens

| Token | Light | Dark | Role |
|---|---|---|---|
| `--page` | #E2DACB | #1B1511 | Page ground (linen table) |
| `--surface` | #EDE6D8 | #251D17 | Quiet panels (status) |
| `--paper` | #F5F0E4 | #2D241C | Scoresheet, dialogs, inputs |
| `--rule` | #C9BBA3 | #4A3D30 | Printed form lines, secondary borders |
| `--text` | #2A2019 | #EEE5D6 | Body text |
| `--muted` | #6A5B4C | #B4A390 | Secondary text |
| `--walnut` / `--walnut-hi` | #4B3323 / #6A4A33 | #3A2719 / #57402D | Board frame |
| `--engrave` | #D9C29A | #CDB386 | Coordinates in the frame |
| `--brass` | #A9822F | #D3AE5C | Inlay line, last-move highlight, win glow |
| `--ink` | #294A93 | #93AEEA | Scoresheet ink; accent option A |
| `--baize` | #2E5C49 | #5A9A7E | "Your move" status |
| `--oxblood` | #8E2C27 | #E07A6F | Destructive actions |
| `--accent` | = `--ink` (option A) or `--brass` (option B) | same | Primary buttons, focus ring, links |

Accent decision: **brass** (chosen at this stage's approval: "Approve, Brass").
- `--accent` = brass. Ink blue stays the scoresheet ink and the colour for links.
- For contrast, filled primary buttons in light mode use a darkened brass, `--accent-fill` #8A6A22, with `--on-accent` #FBF7EE text. Dark mode keeps #D3AE5C with dark text #17120E.
- The build checks both pairs against 4.5:1 (see `accessibility-checklist.md`, Known risks).

## Board themes (FR10.3)

| Theme | Light square | Dark square | Default |
|---|---|---|---|
| Walnut and maple | #E7D0A3 | #A3713F | Yes (your answer to Q4) |
| Tournament green | #EEEDD2 | #5A8160 | |
| Rosewood | #DDBB9C | #6E3C2B | |

Highlights are the same on every theme:
- last move: brass at 38% opacity;
- selected square: 4 px inset ring in `--accent`;
- legal target: a 26% dot at 32% black;
- check: a red radial wash on the king's square.

## Type

| Role | Face | Use |
|---|---|---|
| Display | Libre Caslon Display | Logo word, lobby headline, dialog titles, game result |
| Book | Libre Caslon Text, old-style figures | Scoresheet moves, status headline, lobby lede |
| Interface | Atkinson Hyperlegible | Buttons, labels, body text |

All three are open-licence (OFL) and self-hosted in the build (constraint in the requirements). The type scale is 13, 14, 16, 18, 26, 30 and clamp(40–68) px. No all-caps labels: the room code is the one tracked string, because it is a code to read aloud.

## Components and roles

| Component | Distinct style (FR10.1: 4 button roles) |
|---|---|
| Primary button | Filled `--accent`, `--on-accent` text, 8 px radius, 44 px minimum height |
| Secondary button | Transparent, 1 px `--rule` border |
| Quiet button | Underlined text in `--accent`, no fill |
| Destructive button | Transparent, 1 px `--oxblood` border, `--oxblood` text |
| Board frame | Walnut gradient, 10 px radius, brass 1 px inlay; the only element with depth |
| Scoresheet | `--paper`, ruled rows, 4 px radius (a printed form, not a card) |
| Status | `--surface`; switches to `--baize` on your move; leading dot plus text, never colour alone |
| Dialog | `--paper`, 10 px radius, single shadow; the only floating layer |
| Logo mark | A 2×2 checker in a walnut tile with a brass inlay, drawn in SVG; replaces the "♞" glyph |

## Motion tokens (FR10.4, now measurable)

| Moment | Spec |
|---|---|
| Piece move | Slide from the origin square, 200 ms, cubic-bezier(.2,.7,.2,1) |
| Capture | The taken piece fades and drops 6 px over 150 ms, starting with the slide |
| Check | A red wash on the king's square, with 2 pulses of 300 ms each |
| Win sequence | Losing king tips 80° (700 ms); board dims (600 ms); result inked into the scoresheet (250 ms per character); end-of-game overlay; brass glow on the winner's pieces (Q2 answer "plus warm glow"). About 1.6 s in total |
| Reduced motion | Every item above is skipped; the end state shows at once |

## Pieces (FR10.5)

The build uses the cburnett SVG set (CC BY-SA 3.0), credited in the settings panel ("Pieces: cburnett, CC BY-SA 3.0"). The mockup uses a symbol font as a stand-in only.

## Sound

Not decided (your Q3 answer was "Not yet defined"). Nothing in this design depends on sound. If you add it later, it plugs into the motion moments above.
