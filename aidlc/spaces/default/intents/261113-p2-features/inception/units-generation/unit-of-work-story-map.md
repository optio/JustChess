# Requirement-to-Unit Map — JustChess P2

There is no `stories.md` for this work, so rows are keyed by the functional requirement IDs in `inception/requirements-analysis/requirements.md`. Units are defined in `unit-of-work.md`.

| ID | Unit(s) | Directory |
|---|---|---|
| FR1.1 | U2 | u2-data-and-your-games |
| FR1.2 | U2 | u2-data-and-your-games |
| FR1.3 | U2 | u2-data-and-your-games |
| FR1.4 | U2 | u2-data-and-your-games |
| FR1.5 | U4 | u4-play-the-computer |
| FR2.1 | U1; U2 | u1-game-screen-polish; u2-data-and-your-games |
| FR2.2 | U1 | u1-game-screen-polish |
| FR2.3 | U1 | u1-game-screen-polish |
| FR3.1 | U3 | u3-pass-along |
| FR3.2 | U3 | u3-pass-along |
| FR3.3 | U3 | u3-pass-along |
| FR3.4 | U3 | u3-pass-along |
| FR3.5 | U3 | u3-pass-along |
| FR3.6 | U3 | u3-pass-along |
| FR3.7 | U3 | u3-pass-along |
| FR3.8 | U3 | u3-pass-along |
| FR3.9 | U3 | u3-pass-along |
| FR4.1 | U1 | u1-game-screen-polish |
| FR4.2 | U1 | u1-game-screen-polish |
| FR4.3 | U1 | u1-game-screen-polish |
| FR5.1 | U1 | u1-game-screen-polish |
| FR5.2 | U1 | u1-game-screen-polish |
| FR5.3 | U1 | u1-game-screen-polish |
| FR5.4 | U1 | u1-game-screen-polish |
| FR5.5 | U1 | u1-game-screen-polish |
| FR6.1 | U4 | u4-play-the-computer |
| FR6.2 | U4 | u4-play-the-computer |
| FR6.3 | U4 | u4-play-the-computer |
| FR6.4 | U4 | u4-play-the-computer |
| FR6.5 | U4 | u4-play-the-computer |
| FR6.6 | U4 | u4-play-the-computer |
| FR6.7 | U4; U6 | u4-play-the-computer; u6-endgame-trainer |
| FR6.8 | U4 | u4-play-the-computer |
| FR6.9 | U4 | u4-play-the-computer |
| FR7.1 | U5 | u5-lessons-and-puzzles |
| FR7.2 | U5 | u5-lessons-and-puzzles |
| FR7.3 | U5 | u5-lessons-and-puzzles |
| FR8.1 | U5; U6 | u5-lessons-and-puzzles; u6-endgame-trainer |
| FR8.2 | U6 | u6-endgame-trainer |
| FR8.3 | U5 | u5-lessons-and-puzzles |
| FR8.4 | U5 | u5-lessons-and-puzzles |
| FR8.5 | U5 | u5-lessons-and-puzzles |
| FR8.6 | U5 | u5-lessons-and-puzzles |
| FR9.1 | U3 | u3-pass-along |
| FR9.2 | U3 | u3-pass-along |

## Rows spanning units
- **FR2.1:** U2 stores and exposes capture info, and U1 animates it. U1 can also detect captures from positions alone, so it does not have to wait for U2.
- **FR6.7:** U4 handles "Play the computer" and hints without Stockfish, and U6 handles the endgame trainer without it.
- **FR8.1:** U5 builds the hub with four groups, and U6 adds the Endgames tab.
- **FR9.1 and FR9.2:** the `.env` loader is already built. U3 adds the one new setting, `JUSTCHESS_TRUSTED_PROXIES`, and keeps `.env.example` and its test complete.

## Implementation order within each unit
- **U1:** capture detection and animation, then board fit, then the share dialog and QR code.
- **U2:** the fresh version-4 schema and its tests, then Games capture info, then the summaries route, then the Your games list and headline.
- **U3:** Rooms modes and authorization, then JoinRequest, then the rate limit and trusted proxies, then LiveUpdates and Notifications, then the screens.
- **U4:** the Engine queue, then ComputerOpponent, then computer rooms and Games rules, then the HttpApi flows, then the screens.
- **U5:** lesson kinds and content, then the puzzle curation script and data, then the Puzzles routes, then the hub and puzzle screen.
- **U6:** position files and judging, then the routes, then the tab and screen.

## Coverage check
- All 45 FR IDs are assigned, and each unit has rows. U1 has 11, U2 5, U3 11, U4 10, U5 8 and U6 3: 48 assignments, because three IDs span two units.
- NFRs are traced in Functional Design:
  - NFR1 in U4 and U6
  - NFR2 and NFR3 in U1
  - NFR4 in U2 and U3
  - NFR5 in U1–U6
  - NFR6 in U5
  - NFR7 in U2
  - NFR8 in all units

## Sources
- `inception/requirements-analysis/requirements.md`; `unit-of-work.md`
