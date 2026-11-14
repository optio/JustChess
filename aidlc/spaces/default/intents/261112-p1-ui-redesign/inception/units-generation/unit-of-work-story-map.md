# Requirement-to-Unit Map — JustChess P1

There is no `stories.md` for this work, so rows are keyed by the functional requirement IDs in `inception/requirements-analysis/requirements.md`. Units are defined in `unit-of-work.md`; components come from `inception/domain-design/components.md`.

| ID | Unit(s) | Directory |
|---|---|---|
| FR1.1 | U1 | u1-core-game |
| FR1.2 | U1; U3 | u1-core-game; u3-game-screen |
| FR1.3 | U1; U3 | u1-core-game; u3-game-screen |
| FR1.4 | U1 | u1-core-game |
| FR1.5 | U1; U3 | u1-core-game; u3-game-screen |
| FR1.7 | U1; U3 | u1-core-game; u3-game-screen |
| FR1.6 | U1; U3 | u1-core-game; u3-game-screen |
| FR2.1 | U3 | u3-game-screen |
| FR2.2 | U3 | u3-game-screen |
| FR3.1 | U2 | u2-design-system-board |
| FR3.2 | U1 | u1-core-game |
| FR3.3 | U2 | u2-design-system-board |
| FR3.4 | U1; U3 | u1-core-game; u3-game-screen |
| FR3.5 | U1; U3 | u1-core-game; u3-game-screen |
| FR3.6 | U1; U2 | u1-core-game; u2-design-system-board |
| FR3.7 | U4 | u4-blunder-warnings |
| FR3.8 | U4 | u4-blunder-warnings |
| FR3.11 | U4 | u4-blunder-warnings |
| FR3.9 | U2; U4 | u2-design-system-board; u4-blunder-warnings |
| FR3.10 | U1 | u1-core-game |
| FR4.1 | U3 | u3-game-screen |
| FR4.2 | U1 | u1-core-game |
| FR4.3 | U1; U3 | u1-core-game; u3-game-screen |
| FR4.4 | U1; U3 | u1-core-game; u3-game-screen |
| FR4.5 | U1; U3 | u1-core-game; u3-game-screen |
| FR5.1 | U2 | u2-design-system-board |
| FR5.2 | U2 | u2-design-system-board |
| FR5.3 | U2 | u2-design-system-board |
| FR5.4 | U3 | u3-game-screen |
| FR5.5 | U3 | u3-game-screen |
| FR5.6 | U3 | u3-game-screen |
| FR6.1 | U5 | u5-notifications |
| FR6.2 | U5 | u5-notifications |
| FR6.3 | U5 | u5-notifications |
| FR6.4 | U5 | u5-notifications |
| FR6.5 | U5 | u5-notifications |
| FR6.6 | U5 | u5-notifications |
| FR6.7 | U5 | u5-notifications |
| FR6.8 | U5 | u5-notifications |
| FR7.1 | U6 | u6-training |
| FR7.2 | U6 | u6-training |
| FR7.3 | U6 | u6-training |
| FR7.4 | U6 | u6-training |
| FR7.5 | U6 | u6-training |
| FR7.6 | U6 | u6-training |
| FR7.7 | U6 | u6-training |
| FR8.1 | U6 | u6-training |
| FR9.1 | U1 | u1-core-game |
| FR10.1 | U2; U3 | u2-design-system-board; u3-game-screen |
| FR10.2 | U2 | u2-design-system-board |
| FR10.3 | U2 | u2-design-system-board |
| FR10.4 | U2; U3 | u2-design-system-board; u3-game-screen |
| FR10.5 | U2 | u2-design-system-board |
| FR10.6 | U3 | u3-game-screen |
| FR11.1 | U1 | u1-core-game |
| FR11.2 | U1; U3 | u1-core-game; u3-game-screen |

## Cross-cutting rows

- **Split between U1 (server rule) and U3 (screen):** FR1.2, FR1.3, FR1.5, FR1.7, FR1.6, FR3.4, FR3.5, FR4.3, FR4.4, FR4.5, FR11.2.
- **FR3.6 (check):** U1 sets it in the snapshot; U2 draws it.
- **FR3.9:** U2 holds the setting; U4 honours it.
- **FR10.1 and FR10.4:** U2 provides the tokens and motion; U3 provides the win sequence and screen styling.
- **NFRs:**
  - NFR1, NFR2, NFR4 and NFR8a are mainly U1.
  - NFR3 and NFR3a are U5.
  - NFR6 is U2 and U3.
  - NFR9 is every unit (each unit brings its own tests).
  - NFR5 is U1 (broadcast) and U3 (rendering).

## Implementation order within each unit

- **U1:** the package and database schema, then Games, Rooms, HttpApi and LiveUpdates, then Housekeeping, then tests.
- **U2:** tokens and fonts, then pieces, the board, motion, keyboard, then the promotion picker, then settings.
- **U3:** the shell and top bar, then the lobby, the game screen, the scoresheet, the end-of-game overlay and win sequence, rematch, then the screen states.
- **U4:** Analysis, then the route, then the dialog.
- **U5:** the component and keys, then the routes and hooks, then the service worker, then the client module.
- **U6:** lesson files, then the loader, the routes, the walkthrough, then practice.

## Coverage check

All 56 FR IDs are assigned, and every unit has rows: U1 (24), U2 (15), U3 (24), U4 (4), U5 (8), U6 (8).
