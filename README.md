# JustChess

Minimal anonymous multiplayer chess with FastAPI, HTMX, WebSockets, SQLite and python-chess.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://localhost:8000 in two browser tabs. Create a room, share its code, and join from the other tab. Players are identified by private per-room browser tokens, not accounts.

## MVP features

- Legal move highlights, castling, en passant, promotion, checkmate and draws through python-chess
- Live two-player updates with WebSockets and reconnect snapshots
- Room-code invitations and session scoreboard
- Guided Italian Game and Monte Carlo opening practice
- In-tab notifications when a player joins or moves (requires permission)

## Limitations

Run a **single Uvicorn worker**: WebSocket fan-out is in-process. For multiple workers, add Redis pub/sub. SQLite persists games, but not WebSocket connections. Browser push when the tab is closed is not implemented. Training lines are curated; unknown opponent moves are not evaluated by an engine. No accounts or matchmaking. Room tokens are stored in sessionStorage and are lost when that browser session is cleared.
