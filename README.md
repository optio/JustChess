# JustChess

**Play. Learn. Improve.** Anonymous two-player chess with room codes and interactive opening lessons.

Built with FastAPI, HTMX, lightweight JavaScript, WebSockets, SQLite and python-chess. No accounts, subscriptions, matchmaking or computer-opponent games.

## Getting started (uv)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone https://github.com/optio/JustChess.git
cd JustChess
uv sync
uv run uvicorn app:app --reload
```

Open http://localhost:8000 in two browser tabs. Create a room, share the six-character code and join in the second tab.

Use `uv sync --dev` to install development dependencies, and `uv run pytest` once tests are added. Run `uv lock` and commit the generated `uv.lock` to pin resolved dependencies for reproducible installs.

## Implemented in the initial prototype

- Room-code invitations and anonymous per-room player tokens stored in sessionStorage
- Legal move validation with python-chess, including castling, en passant and promotion
- Click/tap board with legal move highlights, WebSocket state updates and reconnect snapshots
- Minimal SQLite game persistence and win scoreboard
- Linear Italian Game and French Defense Monte Carlo walkthrough/practice
- Notification API alerts while the browser session is active and permission is granted

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full product specification, feature acceptance criteria and roadmap. Items listed there are **not necessarily implemented**.

## Current limitations

This is an unverified MVP, not a production release. Run with **one Uvicorn worker** because WebSocket fan-out uses in-process memory. Multi-worker deployments require shared pub/sub. No service-worker Web Push for closed tabs yet. Lessons are curated linear lines; no opponent-branching decision tree, arbitrary-move evaluation, Monaco lesson, or comprehensive automated tests yet. Room tokens are lost when the browser session storage is cleared. For production, add abuse controls, expiry, accessibility checks and tests.
