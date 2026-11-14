# Design System Mapping — P2 additions to "Club Set"

The tokens, type and board themes are unchanged from intent 261112 (`inception/refined-mockups/design-system-mapping.md`, implemented in `static/css/`). This file maps each new element onto existing tokens. No new colours or faces are added.

Some tokens used below are not named in the 261112 mapping but already exist in `static/css/tokens.css`, which the build added (review R-03):

| Token | Light | Dark |
|---|---|---|
| `--on-baize` | #F4EFE3 | #14110D |
| `--accent-fill` | #8A6A22 | #D3AE5C |
| `--scrim` | rgba(30,20,12,.45) | rgba(0,0,0,.6) |
| `--ease-out` | cubic-bezier(.2,.7,.2,1) | |

| New element | Tokens and components used | Notes |
|---|---|---|
| Your games panel | `--paper` ground, `--rule` row lines, Display face for the "Your games" heading | Same form look as the scoresheet |
| Game row thumbnail | board square tokens of the active board theme, 2 px `--walnut` border | 56 × 56 px, no coordinates |
| Turn pill | "Your move": `--baize` fill with `--on-baize` text; otherwise `--rule` outline | Baize keeps its single meaning: your move |
| Finished row | `--muted` text, thumbnail at saturate(.4) | |
| Computer setup panel | `--paper`, `--rule` border, segmented buttons (pressed = `--text` fill, `--page` text) | Same segmented style as the settings switches |
| Capture animation | motion token `--ease-out`, 260 ms shrink and fade, 200 ms settle | Under the redesign's motion budget (≤ 300 ms) |
| Captured row | Piece glyphs at 20 px, `--muted` | |
| Hint arrow | `--baize` at 85 % | Distinct from the brass last-move highlight |
| Share dialog | Existing dialog component (`--paper`, Display title, `--scrim`) | App links are secondary buttons in a grid |
| QR code | Black on white whatever the theme | Kept black on white so phone cameras can scan it |
| Join-request banner | `--paper` with a 1 px `--brass` border, `role="alert"` | Brass marks "needs your attention" |
| Pass-along status | `--baize` status (always your move) | |
| Trainer tabs | Selected tab: 3 px `--brass` underline, bold | Counts use tabular figures |
| Trainer rows | `--paper` list with `--rule` lines, Book face for titles | "Done" in `--baize` |
| Wrong-move banner | Same banner as the join request | |

## Contrast to check in the build
- `--on-baize` on `--baize` for the pill and status, in both themes (light #F4EFE3 on #2E5C49 and dark #14110D on #5A9A7E): ≥ 4.5:1. The redesign already checks this pair.
- "Join request" pill: `--text` on `--paper` with a `--brass` outline. The text pair is already checked; the outline is decorative.
- Result card and resign dialog: these reuse the existing dialog and game-over card.
- `--muted` on `--paper` for finished rows: this pair was already checked in the redesign.

## Sources
- Intent 261112 design system, `mockup.html` (this folder), requirements FR1–FR8.
