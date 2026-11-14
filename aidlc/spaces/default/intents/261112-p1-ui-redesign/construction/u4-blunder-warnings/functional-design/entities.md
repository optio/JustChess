# Entities — u4-blunder-warnings

These entities serve U4's rows of `inception/units-generation/unit-of-work-story-map.md`. Those are FR3.7, FR3.8, FR3.11 and the reading side of FR3.9, all from `inception/requirements-analysis/requirements.md`. They sit inside the Analysis component of `inception/domain-design/components.md`. Nothing is stored. Every value is computed from the game position U1 already keeps.

```yaml
entities:
  - name: MoveCheck
    description: A request to judge one candidate move in the current game position.
    attributes:
      - { name: code, type: string, required: true, constraints: "^[A-Z0-9]{6}$" }
      - { name: token, type: string, required: true, description: seat token, body only }
      - { name: uci, type: string, required: true, constraints: "^[a-h][1-8][a-h][1-8][qrbn]?$" }
      - { name: version, type: integer, required: true, min: 0 }

  - name: Warning
    description: What the candidate move allows, or nothing.
    attributes:
      - { name: kind, type: enum, allowed: [mate_in_one, hanging_piece], required: true }
      - { name: move, type: string, required: true, description: SAN of the candidate move }
      - { name: mate, type: string, required: false, description: "SAN of the opponent's mating reply (mate_in_one)" }
      - { name: piece, type: enum, allowed: [knight, bishop, rook, queen], required: false, description: the piece left capturable (hanging_piece) }
      - { name: square, type: string, required: false, description: where that piece stands after the move }
      - { name: capturer, type: "{piece, square}", required: false, description: the opponent piece that takes first }
      - { name: defended, type: boolean, required: false, description: whether something can take back (changes the wording) }
    constraints:
      - mate_in_one carries mate; hanging_piece carries piece, square and capturer

  - name: CheckResult
    description: The answer to a MoveCheck.
    attributes:
      - { name: warning, type: "Warning | null", required: true }
      - { name: san, type: string, required: true }
      - { name: version, type: integer, required: true, description: the game version the check used }
    relationships:
      - { to: Warning, cardinality: "0..1", direction: contains }

  - name: PieceValue
    description: Fixed material values used to judge exchanges.
    attributes:
      - { name: pawn, type: integer, default: 1 }
      - { name: knight, type: integer, default: 3 }
      - { name: bishop, type: integer, default: 3 }
      - { name: rook, type: integer, default: 5 }
      - { name: queen, type: integer, default: 9 }
      - { name: king, type: integer, default: 1000, description: only as an attacker of last resort }
```

## Summary

A **MoveCheck** comes in, and a **CheckResult** goes out, holding at most one **Warning**. **PieceValue** is the fixed scale used for exchanges. Analysis keeps no state and saves nothing.
