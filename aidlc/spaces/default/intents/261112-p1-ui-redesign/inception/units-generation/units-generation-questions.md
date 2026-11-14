# Units Generation — Questions

Inputs: `inception/domain-design/components.md` (10 components) and `decisions.md` (ADR-001 to ADR-006); `inception/requirements-analysis/requirements.md`.

Settled without asking, because it follows from the design and your setup:
- **Deployment model:** everything stays one app on the Pi (one FastAPI process serving the API, the ES modules and the service worker).
- **No walking-skeleton ceremony:** this plan has it switched off.
- **Build order:** Construction builds one unit at a time in dependency order.

## Q1. [Developer] How finely should P1 be split into units of work?

Context: each unit gets its own functional design, code plan (which you approve), code and tests. My proposal is 6 units, each a slice you can try:

1. **u1-core-game** (service): split `app.py` into modules. Covers Rooms (hashed seats, continue link, score, rematch, abandonment), Games (rules, draw claims, versions, reasons), LiveUpdates, HttpApi with origin checks, Housekeeping, and the fresh database schema.
2. **u2-design-system-board** (ui): design tokens, self-hosted fonts, SVG pieces, light/dark and board themes, the board component (colours, orientation, labels, motion, keyboard), and device settings.
3. **u3-game-screen** (ui): lobby with join by link, the game screen (top bar, status, scoresheet, share, continue link), the end-of-game overlay with the win sequence, rematch, and all the designed states.
4. **u4-blunder-warnings** (service and ui): the Analysis component, its endpoint, the confirm dialog, and the setting.
5. **u5-notifications** (service): push subscriptions, VAPID keys, de-duplication, the service worker, and the in-page banner.
6. **u6-training** (ui): lessons from YAML/JSON files, walkthrough with animation, practice with the trainer replying, side switch, and hints.

- A. The 6 units as proposed
- B. Fewer, bigger units (for example 3: backend, frontend, training) — less ceremony, larger plans to review
- C. Finer units (for example split u3 into lobby and game screen, and u1 into rooms and games) — more, smaller plans
- D. Not sure, use the proposal
- X. Other (please specify)

[Answer]: A
