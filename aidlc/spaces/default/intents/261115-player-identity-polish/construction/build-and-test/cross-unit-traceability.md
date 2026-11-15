# Cross-Unit Traceability

PASS: `aidlc engine sensor-traceability --stage build-and-test` returned pass=true, uncovered=[]. This express intent has no Units; Code Generation owns all targets.

| ID | Coverage | Owning stage | Target |
|---|---|---|---|
| FR1 | Built | code-generation | static/css/board.css |
| FR2 | Built | code-generation | justchess/players.py |
| FR3 | Built | code-generation | static/js/player-identity.js |
| FR4 | Built | code-generation | justchess/players.py |
| FR5 | Built | code-generation | justchess/players.py |
| FR6 | Built | code-generation | static/js/view-model.js |
| FR7 | Built | code-generation | static/js/screens/win-sequence.js |
| NFR1 | Built | code-generation | tests/test_player_api.py |
| NFR2 | Built | code-generation | tests/test_postgres.py |

No uncovered elements. Detailed execution evidence is recorded separately in test-results.md.
