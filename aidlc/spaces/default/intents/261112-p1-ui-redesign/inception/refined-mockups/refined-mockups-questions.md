# Refined Mockups — Questions

Inputs:
- `inception/requirements-analysis/requirements.md`, mainly FR5 (board and game screen), FR10 (visual identity and motion), FR10.6 (screen states), NFR6 (accessibility).
- The current UI as described in the code map (`aidlc/spaces/default/codekb/JustChess/business-overview.md` § User Experience Today).

There are no rough wireframes or user flow for this work; the plan skipped Rough Mockups. The mockups are drawn directly from the requirements and the current screens.

## My design proposal (context for the questions)

I take the look from the objects of over-the-board chess rather than from generic "warm app" styling:
- **The folding wooden board.** The board sits in a walnut frame with a thin brass inlay line and the coordinates engraved into the frame. This is the one bold element; everything around it stays quiet.
- **The tournament scoresheet.** The move list is a printed form: two columns, numbered rows, ruled lines. Moves are set in a book serif with old-style figures, as in chess literature.
- **The green baize lining** of a chess box, used sparingly for the "your move" state.

Proposed type:
- **Libre Caslon** (display and moves): a book face with chess-literature heritage.
- **Atkinson Hyperlegible** (interface text): built for legibility, which suits a screen people glance at mid-game.

Both are open-licence and self-hosted.

## Q1. [Designer] Which accent colour should carry "your action" (primary buttons, your-turn signal, links)?

Context: warm apps often reach for a terracotta or clay accent, which reads as generic. These options come from the chess-set and scoresheet world instead.

- A. Scoresheet ink blue (the blue of a ballpoint on a tournament form), with brass for highlights
- B. Polished brass/gold, with ink blue for links only
- C. Green baize, with brass for highlights
- D. Let me see A and B side by side in the mockup first
- X. Other (please specify)

[Answer]: D

## Q2. [Designer] What should the win moment be?

Context: FR10.4 asks for a celebratory end-of-game animation. Confetti is the default choice almost everywhere.

- A. The losing king tips over on its square, the board dims slightly, and the result is "written" into the scoresheet's result box (1–0, ½–½) with an ink stroke
- B. A, plus a short warm glow sweeping over the winner's pieces
- C. Confetti burst over the board
- D. Something minimal: the result appears with a short fade only
- X. Other (please specify)

[Answer]: B

## Q3. [Product owner] Should moves make a sound?

Context: sound is a big part of what makes piece moves feel "satisfying" on chess sites (the wooden click). The requirements do not mention sound, so this would be a new requirement.

- A. Yes: a soft wooden click for moves, a sharper one for captures, a muted chime for check and game end; off by default, with a toggle
- B. Yes, the same sounds, but on by default with a toggle
- C. No sound
- D. Not yet defined
- X. Other (please specify)

[Answer]: D

## Q4. [Designer] Which board theme should be the default?

Context: FR10.3 asks for at least 3 board themes. Proposed set: Walnut and maple (warm, classic), Tournament green (the vinyl roll-up board of club play), and Rosewood (darker, rich).

- A. Walnut and maple
- B. Tournament green
- C. Rosewood
- D. Not yet defined
- X. Other (please specify)

[Answer]: A
