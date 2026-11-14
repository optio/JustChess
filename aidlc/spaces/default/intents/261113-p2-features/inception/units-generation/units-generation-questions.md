# Units Generation — Questions

Intent: 261113-p2-features. Deployment is fixed: everything ships in the one FastAPI process on the Raspberry Pi (no unit deploys on its own).

### Q1. How should the work be split into units?
A. Six feature units:
   - U1 game-screen polish (capture animation, board fit, share dialog with QR code; front end only)
   - U2 data foundation and Your games (schema v4, room modes, batch summaries, the main-screen list)
   - U3 pass-along and join requests
   - U4 engine and play the computer
   - U5 lessons and puzzles (new openings, traps, defence lessons, tactics, trainer hub)
   - U6 endgame trainer
B. Three larger units: U1 polish and Your games, U2 pass-along and computer play, U3 all trainers
C. By layer: database, back end, front end
X. Other (please specify)

[Answer]: A

### Q2. Units with no dependency between them could be built in parallel copies of the project. How should Construction run them?
A. One unit at a time, in dependency order (simplest to review; same as last time)
B. Allow independent units in parallel
X. Other (please specify)

[Answer]: A
