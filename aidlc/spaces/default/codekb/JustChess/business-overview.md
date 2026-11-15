# Business Overview

> Historical baseline retained from earlier scans. The Current footer sections below supersede conflicting identity/presentation statements. Outside-focus prose is preserved, not newly verified.

JustChess is a self-hosted chess application for anonymous friend games, pass-along play, five Stockfish levels and browser-local training. Invitations identify a six-character room; bearer seat tokens establish control without accounts. Training includes eighteen authored lessons, six puzzle themes and twelve positions across four endgame categories.

The server persists rooms, seats, games, moves, join requests and push delivery state. Training progress, preferences and saved seat credentials remain in the browser. There is no discovered account, payment or public matchmaking subsystem. A single server worker is required by process-local coordination.

Current persistence supports SQLite and optional PostgreSQL selected by nonempty DATABASE_URL. This intent adds account-free player identity, a bookmarkable cross-device recovery link, moderated nicknames, selection growth and personalized game results/confetti. That earlier absence finding is historical; the current footer section records the implemented client. Existing room-specific seat transfer is single-use and lasts ten minutes; it is not a durable identity bookmark.



## Current compact-footer focus

Account-free identity is now implemented: the shared footer sets a nickname and exposes a durable private recovery link. Recovery restores nickname and game seats across devices; link regeneration changes recovery without ending existing sessions. This intent improves footer density and clarity, adds explicit saved/edit nickname states and replaces native confirmation. It does not require a new player API contract.

