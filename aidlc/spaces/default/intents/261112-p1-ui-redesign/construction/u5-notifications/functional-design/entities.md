# Entities — u5-notifications

These entities serve U5's rows of `inception/units-generation/unit-of-work-story-map.md` (FR6.1–FR6.8, NFR3, NFR3a), taken from `inception/requirements-analysis/requirements.md`. They belong to the Notifications component in `inception/domain-design/components.md` and follow ADR "one alert per event" in `inception/domain-design/decisions.md`. Two new tables join U1's schema.

```yaml
entities:
  - name: PushSubscription
    description: One browser push endpoint registered for one seat of one room. Minimal data only (FR6.7).
    attributes:
      - { name: id, type: integer, required: true, unique: true }
      - { name: room_code, type: string, required: true, references: Room.code }
      - { name: slot, type: enum, allowed: [A, B], required: true }
      - { name: endpoint, type: string, required: true, max: 1024, constraints: "https URL whose host is a public DNS name (no IP literal, no localhost)" }
      - { name: p256dh, type: string, required: true, max: 200, constraints: base64url }
      - { name: auth, type: string, required: true, max: 64, constraints: base64url }
      - { name: created_at, type: timestamp, required: true }
    constraints:
      - unique (room_code, slot, endpoint)
      - at most 5 subscriptions per seat; a sixth replaces the oldest
    relationships:
      - { to: Seat, cardinality: "many..1", direction: belongs-to }

  - name: AlertRecord
    description: Proof that an alert for one event was claimed for one seat. Exists before any send (FR6.6).
    attributes:
      - { name: room_code, type: string, required: true, references: Room.code }
      - { name: slot, type: enum, allowed: [A, B], required: true }
      - { name: event_key, type: string, required: true, constraints: "joined | move:<game>:<ply> | ended:<game>" }
      - { name: status, type: enum, allowed: [claimed, sent, skipped, failed], default: claimed }
      - { name: created_at, type: timestamp, required: true }
      - { name: updated_at, type: timestamp, required: true }
    constraints:
      - primary key (room_code, slot, event_key)
    relationships:
      - { to: Seat, cardinality: "many..1", direction: belongs-to }

  - name: AlertEvent
    description: An in-memory description of something that happened, handed from HttpApi to Notifications after a commit.
    attributes:
      - { name: kind, type: enum, allowed: [joined, move, ended] }
      - { name: room_code, type: string }
      - { name: target_slot, type: enum, allowed: [A, B] }
      - { name: event_key, type: string }
      - { name: title, type: string, max: 60 }
      - { name: body, type: string, max: 140 }
      - { name: url, type: string, description: "/r/<code>" }

  - name: VapidConfig
    description: The push signing keys, loaded at startup. Never stored in the database or the repository (NFR3a).
    attributes:
      - { name: private_key, type: secret, required: false, description: from JUSTCHESS_VAPID_PRIVATE_KEY or the PEM file at JUSTCHESS_VAPID_KEY_FILE }
      - { name: public_key, type: string, required: false, description: base64url uncompressed P-256 point, derived from the private key }
      - { name: subject, type: string, required: false, default: "mailto:admin@localhost", description: JUSTCHESS_VAPID_SUBJECT }
      - { name: enabled, type: boolean, description: false when no valid private key was found }
```

## Summary

- A **PushSubscription** ties a browser endpoint to one seat.
- An **AlertRecord** is the claim that stops a second alert for the same event.
- An **AlertEvent** is what HttpApi passes to Notifications once a change has been committed.
- **VapidConfig** is loaded once at startup, and push stays off when it is missing.

Both tables are removed with their room by Housekeeping, through the hook U1 left for this purpose.
