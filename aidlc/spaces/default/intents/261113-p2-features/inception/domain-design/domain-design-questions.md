# Domain Design — Questions

Intent: 261113-p2-features. Today's building blocks (code map `component-inventory.md`): Rooms (seats, tokens, room score), Games (rules, moves, versions), Live Hub (WebSockets), Analysis (blunder check), Lessons (opening files), Notifications, Housekeeping, the HTTP API that orchestrates them, and the web client. Stockfish is installed but nothing talks to it.

### Q1. How should the app talk to Stockfish?
A. One new Engine component keeps a single long-running Stockfish process and serves requests one at a time from a queue, without blocking the web server (python-chess's asynchronous engine interface)
B. Start a fresh Stockfish process for each request
C. A pool of several Stockfish processes
X. Other (please specify)

[Answer]: A

### Q2. How should a game against the computer be modelled?
A. As a normal room whose second seat belongs to the computer (rooms get a "mode"). It reuses games, the scoresheet, live updates, the ongoing-games list and resuming
B. As a separate "solo game" component with its own storage, apart from rooms
X. Other (please specify)

[Answer]: A

### Q3. Where does pass-along play and the join request live?
A. In Rooms: a room mode (waiting, pass-along, online), with the creator's seat allowed to move both colours while in pass-along, and a JoinRequest owned by Rooms
B. In a new PassAlong component that sits between the HTTP API and Rooms
X. Other (please specify)

[Answer]: A

### Q4. How should the trainers be split?
A. Lessons keeps the walkthrough-style lessons and gains kinds (opening, trap, defence). A new Puzzles component owns the curated tactics set. A new Endgames component owns the endgame positions and the pass rules, and uses Engine
B. One Trainer component for all of it
C. Lessons for everything scripted (openings, traps, defence, puzzles), plus Endgames separately
X. Other (please specify)

[Answer]: A

### Q5. The score against the computer is kept per level. Where should it live?
A. One computer room per device and level: "Play the computer" at Club reopens your Club room, and a rematch stays in it, so the room score is the score against the computer
B. On the device only (browser storage), updated when each game ends
C. A new game room every time, with the score kept in browser storage
X. Other (please specify)

[Answer]: A
