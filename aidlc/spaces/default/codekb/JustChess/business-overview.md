# Business Overview

JustChess is a self-hosted chess application for anonymous friend games, pass-along play, five Stockfish levels and browser-local training. Invitations identify a six-character room; bearer seat tokens establish control without accounts. Training includes eighteen authored lessons, six puzzle themes and twelve positions across four endgame categories.

The server persists rooms, seats, games, moves, join requests and push delivery state. Training progress, preferences and saved seat credentials remain in the browser. There is no discovered account, payment or public matchmaking subsystem. A single server worker is required by process-local coordination.

The requested change is optional PostgreSQL selection through DATABASE_URL loaded from .env, retaining SQLite when absent. Current source implements only SQLite. Requirements must settle external schema initialization/version policy and whether transferring existing SQLite data is included.

