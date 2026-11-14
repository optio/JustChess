# Accessibility Checklist — P2 (WCAG 2.1 AA)

| # | Check | Applies to | Requirement | How it is verified |
|---|---|---|---|---|
| A1 | Every new control is reachable and usable by keyboard | Games list, setup panel, share dialog, banners, tabs, trainer boards | NFR5 | Browser test: Tab or arrow keys reach each control; Enter or Space activates it |
| A2 | The share dialog is a labelled modal: focus is trapped, Escape closes it, and focus returns to the trigger | ShareDialog | FR5.5, NFR5 | Browser test |
| A3 | Tabs follow the ARIA tablist pattern (roles, `aria-selected`, arrow keys) | TrainerHub | NFR5 | JS unit and browser test |
| A4 | The setup toggle exposes `aria-expanded`, and the segmented buttons expose `aria-pressed` | ComputerSetupPanel | NFR5 | DOM assertion |
| A5 | Tap targets are ≥ 44 × 44 px, except board squares in phone landscape (≥ 36 px) | All | FR4.2, NFR5 | Browser test measures rectangles |
| A6 | Animation is never the only signal: the move text says "takes", and the captured row's label updates | CaptureAnimation | FR2, NFR5 | DOM assertion |
| A7 | Reduced motion removes the shrink and the fades | CaptureAnimation | FR2.2 | Browser test with emulated `prefers-reduced-motion` |
| A8 | Engine states and puzzle feedback are announced politely (`aria-live="polite"`); the join request uses `role="alert"` | EngineStatus, PuzzleBoard, JoinRequest | NFR5 | DOM assertion |
| A9 | Text contrast is ≥ 4.5:1 in both themes, including baize pills and muted finished rows | All | NFR5 | `static/js/contrast.js` checks plus the existing contrast test |
| A10 | Each games-list row has one descriptive accessible name | YourGamesList | NFR5 | DOM assertion |
| A11 | Disabled features (no Stockfish, takeback) show the reason as visible text, not only a greyed button | Setup panel, game actions, trainer rows | FR6.7 | DOM assertion |
| A12 | The QR code has a text alternative, and the link is shown as text beside it | ShareDialog | NFR5 | DOM assertion |
| A13 | The board fits without scrolling at every size listed in FR4.1, at the default font size | Game screen | FR4.1, NFR3 | Browser test at 7 viewports |

## Known risks
- **Landscape squares.** At 36–43 px, board squares in phone landscape fall below the 44 px target. The user accepted this (requirements Q18). Keyboard play is still available.
- **Countdown announcements.** If the join-request countdown were announced every second it would be noisy for screen readers. It refreshes once a minute.

## Sources
- Requirements NFR5, FR2, FR4, FR5, FR6.7; `interaction-spec.md`.
