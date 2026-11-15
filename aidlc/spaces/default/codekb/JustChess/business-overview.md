# Business Overview

> Focused merge, 2026-11-15: current findings cover player identity/presentation and persistence seams. Outside-focus descriptions are retained prior-store context and are not newly verified; see the timestamp for exact coverage.

JustChess is a self-hosted chess application for anonymous friend games, pass-along play, five Stockfish levels and browser-local training. Invitations identify a six-character room; bearer seat tokens establish control without accounts. Training includes eighteen authored lessons, six puzzle themes and twelve positions across four endgame categories.

The server persists rooms, seats, games, moves, join requests and push delivery state. Training progress, preferences and saved seat credentials remain in the browser. There is no discovered account, payment or public matchmaking subsystem. A single server worker is required by process-local coordination.

Current persistence supports SQLite and optional PostgreSQL selected by nonempty DATABASE_URL. This intent adds account-free player identity, a bookmarkable cross-device recovery link, moderated nicknames, selection growth and personalized game results/confetti. None of those identity/profile features currently exists. Existing room-specific seat transfer is single-use and lasts ten minutes; it is not a durable identity bookmark.


