# Accessibility Checklist — WCAG 2.1 AA (NFR6)

Applies to every screen in `mockups.md`, using the tokens in `design-system-mapping.md`. It traces to NFR6 and FR10.2 in `inception/requirements-analysis/requirements.md`.

## Perceivable

- [ ] Body text (`--text` on `--page`, `--paper`, `--surface`) is at least 4.5:1 in both themes. Planned values: light #2A2019 on #E2DACB ≈ 11:1; dark #EEE5D6 on #1B1511 ≈ 14:1.
- [ ] Muted text (`--muted`) is at least 4.5:1 on `--page` and `--paper` in both themes. This is to be verified in Build and Test with an automated checker.
- [ ] Primary button text (`--on-accent` on `--accent`) is at least 4.5:1 for both accent options (ink blue and brass) in both themes.
- [ ] "Your move" text on `--baize` is at least 4.5:1.
- [ ] Pieces against both square colours of every board theme are at least 3:1 (non-text contrast), helped by the outline on white pieces and the edge on black (review finding R-04).
- [ ] The last-move, selection, legal-target and check highlights are at least 3:1 against the squares they sit on, on every board theme.
- [ ] Status is never shown by colour alone: every state has text, and "your move" also has a dot.
- [ ] The logo mark is decorative and its link is labelled "JustChess home".
- [ ] Nothing flashes more than 3 times per second; check uses 2 pulses.

## Operable

- [ ] The whole game is playable by keyboard: arrows move between squares, Enter or Space selects and moves, Escape cancels.
- [ ] Every control shows a visible focus ring: 3 px in `--accent`, 2 px offset.
- [ ] Touch targets are at least 44 × 44 px: buttons have a 44 px minimum height, and the smallest square is 46 px on 374 px boards.
- [ ] Dialogs trap focus and close with Escape, and focus returns to the board.
- [ ] There are no time limits. The 24 h abandon window (FR11.2) is far longer than any interaction.
- [ ] Reduced motion turns off every animation, including the win sequence.

## Understandable

- [ ] The page declares `lang="en"`.
- [ ] The room code field has a visible label ("Have a room code?"), not only a placeholder.
- [ ] Errors say what happened and what to do next ("No room with code K7Q2PX. Check the code or start a new game.").
- [ ] The blunder dialog names the consequence and offers a safe default.
- [ ] The same action keeps the same name throughout, for example "Play again", then "Waiting for opponent".

## Robust

- [ ] Native elements are used: `button` for squares and actions, `table` for the scoresheet, `details` for the lessons drawer.
- [ ] The board uses `role="grid"`, and each square has an `aria-label` with its coordinate and piece.
- [ ] Moves, check, game end and the opponent's arrival are announced through polite live regions.
- [ ] Checked with axe or Lighthouse, a keyboard-only pass, and a TalkBack or VoiceOver spot check in Build and Test.

## Known risks

- Brass as an accent (option B) is the closest to failing text contrast in light mode: brass #A9822F with light text. If you pick brass, the build must darken it to about #8A6A22 for filled buttons, or use dark text on it.
