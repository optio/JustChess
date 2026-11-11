# JustChess — Product requirements

Status: living specification. This file captures the requirements discussed for JustChess, including planned features. It is **not** a claim that every item is already implemented.

## 1. Product vision

A lightweight, mobile-friendly web chess app for two humans to play through a shared invitation code, plus a single-player **training** experience that teaches chess openings, variations, strategic ideas and when to change plans.

- No mandatory account, registration, subscription or payment.
- No matchmaking or computer-opponent games. The training feature may play **scripted** opponent moves to teach openings; this is not a general-purpose chess bot.
- Minimal backend storage, simple deployment and low maintenance.
- Brand: **JustChess**. Proposed tagline: “Play. Learn. Improve.” or “No accounts. No subscriptions. Just chess.”

## 2. Technical architecture

- Backend: Python 3.11+, FastAPI, Jinja2, python-chess for all authoritative chess rules.
- Frontend: server-rendered HTML + HTMX for pages/forms/partials; small dedicated JavaScript controller for chessboard interactions and animation; responsive CSS.
- Live multiplayer: WebSockets for state changes, join/wait notifications and reconnection.
- Persistence: SQLite for rooms, player identities, moves and results; lessons as version-controlled YAML/JSON.
- Dependency management: **uv** with pyproject.toml; use `uv sync` and `uv run`, not pip instructions. Commit uv.lock after resolving.
- Initial deployment: single-process modular FastAPI monolith in Docker with a persistent SQLite volume. If scaling to multiple processes, use Redis/pub-sub or equivalent for WebSocket broadcast.
- Keep backend as source of truth; never trust client-provided legal moves, player identity, game state or scores.

## 3. Multiplayer requirements

- [ ] Create a new room with a short, unpredictable, human-shareable code (e.g. six alphanumeric characters).
- [ ] Join an existing room by code, or optionally share a URL containing the code.
- [ ] Exactly two active players, assigned White/Black, with clear waiting/connected/disconnected status.
- [ ] No accounts. Issue high-entropy **private** player tokens distinct from the public room code; support rejoining the same seat after refresh/reconnect.
- [ ] Room creation and seat assignment must be race-safe. Reject a third player trying to take a seat; optionally allow read-only spectators later.
- [ ] Touch/click a piece to highlight **legal** destination squares, then select a destination to move; optional drag-and-drop on desktop.
- [ ] Validate every move on the server using python-chess: side to move, checks, castling, en passant, promotion, mate, stalemate, repetition, 50/75-move rules and insufficient material. Support claiming a draw where the rules require a claim.
- [ ] Keep both boards synchronized in real time and send an authoritative snapshot on reconnect.
- [ ] Display move history in algebraic notation and the current turn/check/game-over state.
- [ ] Provide a simple scoreboard: wins, losses and draws for a room/match series; optionally show captured material. Do not confuse material score with win count.
- [ ] Handle resignation, optional draw offers, rematches and abandoned games in later iterations.
- [ ] Prevent duplicate/out-of-order moves and simultaneous-write races using transaction/version checks.
- [ ] Persist room state and game history minimally; expire and clean up stale rooms.
- [ ] Mobile-first UI with large touch targets, clear board orientation, keyboard accessibility, contrast and screen-reader labels.

## 4. Notifications

- [ ] Show a waiting-state message when a room is created and notify Player A when Player B joins.
- [ ] Notify a player when the opponent moves and it becomes their turn.
- [ ] First stage: WebSocket events + browser Notification API for an open/connected page, with explicit user permission and sensible in-page fallback.
- [ ] Later: service worker + Web Push subscriptions for alerts when the page is closed, where browser/platform support permits. HTTPS and consent required; delivery not guaranteed.
- [ ] Store only the minimal push subscription information, allow disabling notifications and clean up invalid subscriptions.
- [ ] Avoid repeated/spammy notifications; do not claim a browser notification is delivered until the platform confirms it.

## 5. Interactive training — no chess AI required

Two primary modes:

1. **Guided walkthrough**: step forward/backward through an opening; animate/highlight moves and important squares; explain strategic goals, tactical threats and the reasoning behind each move.
2. **Practice**: user makes expected moves from memory while the trainer responds with curated, predefined opponent moves. Check legality and expected continuation, provide hints, retry and explanations.

Further requirements:

- [ ] Model openings as a **branching decision tree / position graph** rather than only a linear SAN list.
- [ ] Support multiple opponent replies, randomized scripted responses and different recommendations for each.
- [ ] Explain when an intended opening plan should be abandoned, changed to a variation or replaced by another plan after the opponent deviates.
- [ ] Distinguish “legal but outside the taught repertoire” from “illegal”; offer to continue in free exploration or return to a known branch.
- [ ] Recognize move-order transpositions by normalized board position (FEN-derived position identity), not solely by move history.
- [ ] Store opening name, aliases, ECO classification where verified, start position, SAN/UCI moves, explanatory notes, alternative lines and learning objectives.
- [ ] Explain traps and common mistakes for both sides; optional quizzes and variation recognition.
- [ ] Persist training progress only if needed, preferably locally at first.
- [ ] Curated lines can teach known deviations; **without an engine**, do not claim to evaluate arbitrary moves or identify the objectively best strategy. Stockfish is optional future work, not a requirement.

## 6. Opening catalog

Start with verified, curated examples, then expand:

| Group | Openings and variations |
| --- | --- |
| Foundational | Italian Game, Ruy Lopez (Spanish Opening), Sicilian Defense, French Defense, Queen's Gambit, London System, King's Indian Defense, Vienna Game |
| Named lines and tactics | French Defense Exchange — **Monte Carlo Variation** (`1.e4 e6 2.d4 d5 3.exd5 exd5 4.c4`), Albin Countergambit, Traxler Counterattack, Fried Liver Attack, Vienna Gambit |
| Unusual openings | Danish Gambit, Bird's Opening, Grob's Attack, Orangutan Opening |
| Name to research | **Monaco Variation** — include in the catalog plan, but verify the exact opening, aliases and move order before publishing a lesson; do not invent a line |

For every opening: ideal sequence, purpose, typical responses, branching continuations, common mistakes, traps and a “when to switch plans” explanation. Training content should be editable through YAML/JSON without application code changes.

## 7. Data model (suggested)

- `games`: room code, FEN, status, side to move, timestamps, version.
- `game_players`: private player token hash, assigned side, optional display name and reconnect metadata.
- `moves`: ordered UCI/SAN move records, timestamps.
- `results`: winner/draw and match-series score.
- `push_subscriptions`: optional endpoints/keys, retention and revocation.
- Lessons: version-controlled JSON/YAML; no DB required.
- Consider hashing private tokens at rest and avoiding their appearance in URLs or logs.

## 8. Security and operational requirements

- [ ] Enforce seat authorization on every move; public room codes must not grant control of a seat.
- [ ] Generate unpredictable room codes and private tokens; use HTTPS/WSS in production.
- [ ] Limit creation/join/move rates; validate inputs and bound request sizes.
- [ ] Protect state changes against cross-origin abuse and unintended CSRF where cookie auth is introduced; validate WebSocket Origin.
- [ ] Ensure atomic game state updates and correct result calculation; handle reconnect and disconnect cleanly.
- [ ] Define data retention, room expiration, backup policy and basic observability.
- [ ] Test chess rules, move validation, race conditions, training branches, mobile UI and notification permissions.

## 9. Delivery phases

1. **Board MVP**: responsive board, touch selection, legal highlights, promotion and terminal states.
2. **Anonymous multiplayer**: room codes, private tokens, live WebSockets, reconnection and simple scoreboard.
3. **Guided lessons**: verified opening catalog, explanations, back/next/restart and animations.
4. **Branching practice**: scripted opponent alternatives, hints, deviations, plan switching and transposition recognition.
5. **Polish**: in-page notifications, Web Push, accessibility, security, retention, automated tests and deployment.

## 10. Definition of done for a production-ready first release

Two users can reliably play a complete legal game using only a shared code on desktop or mobile, survive a reconnect, receive appropriate open-page alerts, see a correct result, and complete at least one branching opening lesson with guided and practice modes. Automated tests cover critical move rules, identity checks and training transitions; deployment has persistent storage, HTTPS and basic operational safeguards.
