# Cross-Unit Traceability (final coverage gate)

**Verdict: FAIL as reported by the coverage check: 1 of 73 IDs built.** The uncovered IDs were deferred by your choice of build scope ("1,  but also include the stockfish install upon boot"): this work retires REQUIREMENTS.md and adds the Stockfish install. They are not defects in what was built.

Source: `aidlc engine sensor-traceability --stage build-and-test`. Zero-Unit work.

## Covered

| ID | Owning stage | Target file |
|---|---|---|
| FR9.1 | code-generation | `stockfish_install.py` (tests: `tests/test_stockfish_install.py`) |

## Uncovered (deferred to a future piece of work)

| Group | IDs | Note |
|---|---|---|
| FR1 Rooms and joining | FR1.1–FR1.8 | Some of these already work in the existing code (scan). They are not rebuilt or re-verified here |
| FR2 Sharing | FR2.1–FR2.2 | P1 |
| FR3 Playing a game | FR3.1–FR3.12 | Includes the blunder warnings (P1) |
| FR4 Game end and match | FR4.1–FR4.8 | P1/P2 |
| FR5 Board and game screen | FR5.1–FR5.6 | P1 |
| FR6 Notifications | FR6.1–FR6.8 | P1 |
| FR7 Training | FR7.1–FR7.12 | P1–P3 |
| FR8 Opening catalog | FR8.1–FR8.6 | P1–P3 |
| Non-functional | NFR1–NFR10 | P1/P2 |

Every uncovered ID is owned by the next piece of work: the P1 delivery phase described in `inception/requirements-analysis/requirements.md`.
