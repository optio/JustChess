# Player Identity and Game Polish Requirements

## Intent Analysis

Improve play feedback and make an anonymous player's nickname and game access portable without registration. Keep the implementation small, retaining existing FastAPI/plain-JavaScript architecture, SQLite/PostgreSQL support and single-worker operation.

## Sources

- [desc] Initial description: When selecting a piece, it should besides highlight also slightly grow. Users should have an account-free unique identity, with a footer link they can use or bookmark to preserve their identity across devices. Allow a nickname with a profanity filter. When a player wins, show confetti and clearly say they won. When a player loses, say they lost and the other player won, using nicknames when available, alongside the winning color.
- [scope] Workflow-selected scope: express; owner requested a small and quick plan.
- [Q1] Restore nickname and saved games/seats on another device, with both devices usable.
- [Q2] Identity bookmark is reusable until regenerated; regeneration invalidates the old bookmark.
- [Q3] English-only profanity filtering; reject blocked names and ask for another.
- [user-db] Owner confirms app is not yet live; database deletion/recreation is permitted and backward compatibility is not required (message 48905d0b).
- [code] Approved focused Reverse Engineering in aidlc/spaces/default/codekb/JustChess/ identifies room-specific seat credentials, viewer-relative results and existing motion/reduced-motion mechanisms.
- [handover] HANDOVER.md: isolated tests, secret handling, gameplay.yaml settings, keep only outstanding work in the handover.

## Functional Requirements

All listed requirements are Must-have.

### FR1 — Selected-piece growth

Selecting a movable piece retains its square highlight and visually enlarges the piece slightly. Deselecting, moving or changing selection restores its normal size. Selection must not move board geometry, cover controls, alter hit targets or interfere with movement/capture animation. [desc, code]

Acceptance: selecting a legal piece displays both cues; changing/deselecting restores the former piece; pointer and keyboard selection behave consistently; growth remains visible without animated transition under reduced-motion preference.

### FR2 — Automatic account-free player identity

Create a unique anonymous player identity automatically for a new browser. Persist its private credential locally and its profile/game associations server-side; refresh and restart retain it while valid. No account form, email, password or nickname uniqueness requirement is introduced. A public nickname never authorizes access. [desc, Q1, code]

Acceptance: separate new browser contexts receive distinct identities; refresh retains the same identity; an unknown credential cannot read or modify another profile or obtain seat access. If browser storage is unavailable, show a clear recovery/save limitation without breaking the board.

### FR3 — Private footer bookmark and cross-device recovery

Provide a visible footer link for saving/restoring the player, with a copy action and a clear statement that the link is private. Opening/bookmarking it on another device restores that identity's nickname and nonexpired saved games/seat access. Both devices remain usable; do not rotate the existing device's seat authority merely because identity was restored. Expired/deleted rooms stay inaccessible. [desc, Q1]

Acceptance: create/join a game on one device, restore on a second, see the same nickname and saved game, and play the authorized seat from either device subject to existing turn/version checks. Invalid links show a useful error and preserve the current identity. Explicitly restoring an identity replaces the active identity rather than silently merging unrelated identities. A bare public room code grants no private identity or seat access.

### FR4 — Regenerate the identity bookmark

An authenticated player can generate a replacement private recovery link. Old bookmarks stop restoring the identity; the new one works. Keep existing signed-in devices usable; recovery-link revocation is separate from session/seat credentials. Warn before regeneration that existing bookmarks will need updating. [Q2, Q1]

Acceptance: after regeneration, old-link redemption fails, new-link redemption succeeds and the original device can still access its games. Regeneration without the player's valid credential is rejected. The footer always exposes the current valid link on the device performing regeneration; other devices can request a replacement if their cached link is invalidated.

### FR5 — Editable nickname with English profanity filtering

Offer a clear nickname edit/save control. Nicknames are optional, not unique, and persist with the identity across devices. Apply server-side English profanity filtering and input validation; reject invalid names with a useful message while preserving the previous name. Normalize case/Unicode/spacing for moderation and cover common simple obfuscations without blanket substring rejection of innocent names. Render names as plain text. [desc, Q3]

Acceptance: a valid name saves and appears to the opponent; clearing returns to a neutral fallback; blocked/case-varied/simple-obfuscated profanity and invalid input are rejected by direct API calls as well as the UI; ordinary names containing a blocked substring remain usable where not actually profane. Concurrent devices read the saved value rather than treating local-only state as authoritative. Implementation chooses a documented bounded length and maintained/local English vocabulary without claiming perfect moderation.

### FR6 — Clear personalized outcomes

When an online or computer game ends, explicitly tell the winning viewer they won and the losing viewer they lost, identify the other player and retain the winning-color information. Use each player's nickname when available, with neutral fallbacks and a clear computer label. Draws, watchers and pass-along sessions use suitable neutral outcome text rather than assigning an unjustified personal win/loss. [desc, code]

Acceptance: both seat/color assignments yield correct viewer-relative messages for wins, resignations and other decisive results; missing or duplicate nicknames remain understandable; draw/watch/pass-along messages are correct; result text is available without animation and announced accessibly. Reopening a finished game retains clear result text.

### FR7 — Winner confetti

Show finite confetti for the winning player's newly observed game completion, alongside the clear result. Do not show winner confetti to the loser or watcher, on draws, or repeatedly when snapshots refresh/reconnect or a finished game is reopened. Cancel effects when leaving the game. Honor reduced-motion preferences by suppressing confetti while retaining result text. [desc, code]

Acceptance: one eligible win triggers one bounded effect; loss/draw/watch/reopened-finished cases do not; navigation cancels it; reduced-motion mode retains a usable outcome without confetti.

## Non-Functional Requirements

### NFR1 — Private identity and seat authority

Use high-entropy private identity/recovery credentials and hash secret verification material server-side. Recovery secrets stay in URL fragments, never request paths/query strings, access logs, analytics or error bodies; redemption sends them only in a protected request body and clears them from the visible address after processing. Provide a dedicated copy/bookmark link despite fragment cleanup. Preserve existing seat authorization and stale-version protection, existing origin/body guards and bounded/rate-limited identity/profile mutation endpoints. [Q1, Q2, code, handover]

Acceptance: tests show copied-link restoration works without a secret-bearing server URL; errors/logs do not contain sentinel credentials; nickname/identity APIs cannot claim arbitrary seats; two-device stale moves still fail safely. A private-link holder is trusted to access that identity, as explained in the UI.

### NFR2 — Compatibility, accessibility and isolated verification

Keep SQLite and PostgreSQL working, and keep one server worker. Database recreation for this feature is allowed; no legacy migration/import is required. Tests use temporary SQLite files and dedicated disposable PostgreSQL schemas, never normal app data. Existing regressions stay green. New visual effects respect reduced motion and existing input modes. New gameplay timing/scale knobs, if configurable, belong in gameplay.yaml. [user-db, code, handover]

Acceptance: identity/profile/domain scenarios pass against both backends; existing Python/JavaScript suites pass; representative real-browser checks verify selection growth, footer/nickname flows and personalized outcome/confetti behavior. Report any unavailable browser or PostgreSQL verification explicitly.

## Constraints

- Extend the existing app rather than adding an external account service.
- No backward compatibility or data transfer required; do not weaken test isolation.
- No commit, push or deployment until requested for this intent.
- Keep HANDOVER.md current and remove completed work as it finishes.

## Assumptions & Open Questions

None. Implementation details (credential/session layout, vocabulary source, exact visual scale, limits and endpoint shapes) are resolved in the code plan against these criteria.

## Out of Scope

- Accounts, email/password recovery, identity merging, unique-name reservations and administrative moderation tools.
- Cross-device synchronization of training progress/preferences beyond the requested nickname and saved game/seat access.
- Distributed/multi-worker coordination, perfect multilingual moderation and unrelated handover follow-ups.
- Deployment/server provisioning and migration of existing databases.
