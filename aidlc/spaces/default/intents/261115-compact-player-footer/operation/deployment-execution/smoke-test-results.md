# Smoke Test Results — Production

## Sources

- Live headless-Chrome runs against https://justchess.mijnesite.be (owner-approved Q1, 0f73dfc4); scripts kept in the session scratchpad, built on `tests/test_game_screen.py`'s `Page` harness.

## Scenario

Two browsers (desktop + 390 px phone): create a room, second browser joins, one move each; then a second room switches to "Play the computer while waiting", the creator plays e4, the computer replies, a friend opens the link and takes over Black, creator plays Nf3 and the friend gets the move.

## Results

| Check | Before fix (`a5e2ccf`, iad1) | After fix (`ad09526`, fra1) |
|---|---|---|
| Join, moves, takeover, no page errors | Pass | Pass (3 runs) |
| Move delivery to opponent | 13.6 s | ≤ 0.12 s |
| Reply delivery | 4.8 s | 0.11–0.13 s |
| Computer reply (stand-in) | 11.2 s | 0.21–0.22 s |
| Whole scenario | 146.5 s | 12.5–19.6 s |
| "Your opponent has joined" on takeover | Pass | Pass |
| Share stays visible with the stand-in | Pass | Pass |

Throwaway rooms created in Production: Z49Z28, BKQDSW, KKDZBY, WS5C5I and later probe rooms; daily cleanup removes them.

## Known issue (follow-up)

If White moves within ~1 s of Black joining, before Black's live socket has connected, White's status says "Black is away" without the hourglass until the next update. Presence in the database is correct ("connected" ~0.6 s after the join, confirmed through the public API); the correcting broadcast sometimes doesn't reach White in that window. Cosmetic; gameplay unaffected. Each update also arrives twice (local plus LISTEN resync) — harmless, could be deduplicated.
