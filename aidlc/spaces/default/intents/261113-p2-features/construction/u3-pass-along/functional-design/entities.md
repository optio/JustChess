# Entities — u3-pass-along

U3 uses the version 4 schema built by U2 and adds no tables or columns. These are the entities and fields it reads or changes.

```yaml
entities:
  - name: Room
    description: mode now moves between waiting, pass_along and online
    attributes:
      - { name: code, type: string, required: true }
      - { name: mode, type: enum, allowed: [waiting, pass_along, online, computer] }
    constraints:
      - "waiting <-> pass_along only while seat B does not exist"
      - "online once seat B exists; never back to waiting or pass_along"
  - name: Game
    attributes:
      - { name: status, type: enum, allowed: [waiting, playing, finished] }
      - { name: counted, type: boolean, constraints: "false while the game has been played in pass_along and no seat B exists; becomes true when seat B is taken" }
  - name: Seat
    description: seat B for an accepted joiner takes the request token's hash as its token hash, so the joiner's request token becomes its seat token
  - name: JoinRequest
    description: table from U2; lifecycle owned here
    attributes:
      - { name: requestId, type: integer }
      - { name: roomCode, type: string }
      - { name: requesterTokenHash, type: string, constraints: "SHA-256 of a 128-bit random token issued to the visitor" }
      - { name: status, type: enum, allowed: [pending, accepted, declined, lapsed] }
      - { name: createdAt, type: timestamp }
      - { name: expiresAt, type: timestamp, constraints: "createdAt + 600 s" }
      - { name: answeredAt, type: timestamp, required: false }
    constraints:
      - "at most one pending per room (partial unique index from U2)"
  - name: RateWindow
    description: in-memory, per client address, for join requests
    attributes:
      - { name: clientAddress, type: string }
      - { name: timestamps, type: list<timestamp>, constraints: "kept for 60 s; at most 5" }
```

## Summary

- **Room mode:** gains the waiting ↔ pass_along transitions.
- **Game counted flag:** follows whether seat B exists.
- **JoinRequest:** its lifecycle lives here.
- **Seat B token:** an accepted joiner's request token becomes their seat token. The server stores only hashes and never keeps a plaintext token waiting to be picked up.
- **Rate window:** kept in memory only.
