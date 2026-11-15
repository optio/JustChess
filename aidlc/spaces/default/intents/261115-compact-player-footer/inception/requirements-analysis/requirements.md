# Compact Player Footer Requirements

## Intent Analysis

Make the bottom player controls read as a quiet, compact footer. Reduce visual clutter and clarify how players edit their nickname and preserve their identity. This is a frontend refinement of existing behavior; no backend/schema changes are needed.

## Sources

- [desc] Initial description: Improve the bottom layout into a compact footer. Use an inline save icon in the nickname input while editing or when no nickname exists; when a nickname is set show it read-only with a pencil icon to edit. Clarify or consolidate Save my player versus Copy link. Replace the plain JavaScript confirmation for Generate new link with a proper styled modal. Make footer buttons smaller and visually consistent.
- [scope] Workflow-selected scope: express, Minimal depth/test strategy.
- [user] Keep HANDOVER.md updated at every checkpoint so another AI tool can resume when limits are reached (message c5d6bf98).
- [code] Approved focused scan: templates/index.html, static/js/player-identity.js and existing share/blunder modal patterns; current identity and browser tests.

## Functional Requirements

Additional source [user-help]: owner requests a question-mark button opening a modal explaining the player bookmark system (message 98ac7ab5).

All requirements are Must-have.

### FR1 — Compact responsive footer

Present the nickname and identity-link actions as a visually distinct footer using existing typography/colors, subtle separation, restrained spacing and smaller visual button treatment than primary gameplay controls. Keep related controls aligned on wide screens and wrap cleanly on narrow screens, without horizontal overflow or overlap with game content. Preserve existing attribution/footer content. [desc, code]

Acceptance: browser checks at narrow and desktop widths show a footer hierarchy and compact controls, no clipping or horizontal overflow; controls remain usable with touch/keyboard and on lobby/game/training routes.

### FR2 — Nickname display and inline editing

When no nickname exists, show an editable nickname input with a save icon button inside its visual field. A saved nickname appears in a noneditable display state with a pencil icon. Pencil enters edit mode and focuses/selects the input; edit mode uses the same inline save control. Save succeeds into display mode; clearing the nickname and saving returns to the empty editable state. Enter submits. Retain server validation, error messages and previous saved name on failure; prevent duplicate saves while pending. Give icon buttons accessible names and visible focus states. [desc, code]

Acceptance: empty → edit/save → display → pencil/edit → save transitions pass in a real browser. Invalid nickname stays editable with a useful message and no loss of prior saved name; pending save disables repeated submission. External profile refresh must not overwrite an in-progress nickname draft.

### FR3 — Clear identity-link actions

Consolidate the ambiguous primary actions into one clearly labeled Copy player link action, with short help explaining that this private link restores nickname and games on another device. Preserve bookmark/manual-copy access through a clearly labeled fallback/details surface when clipboard access is unavailable, rather than keeping two competing Save my player and Copy link actions. Keep the link private warning and useful copy success/failure feedback. A compact New link action remains available with wording that it replaces old bookmarks. [desc, code]

Acceptance: users see one primary recovery-link action; copy uses the existing valid private recovery URL without navigating/restoring the current player. When clipboard is denied/unavailable, a visible selectable link/bookmark alternative remains usable. No private credential appears in server URLs, logs or error text. Existing cross-device restoration still works.

### FR4 — Styled regeneration confirmation modal

Replace window.confirm/prompt with an in-app modal matching existing dialog styling. It explains that generating a new player link invalidates old saved links while keeping current signed-in devices usable. Include explicit Cancel and Generate new link actions. Confirm performs the existing regeneration API once, shows pending state, and updates the usable link on success; errors remain readable without falsely reporting success. Cancel/Escape/backdrop dismissal has no API side effect. Manage focus on open/close, constrain keyboard interaction to the modal, use an accessible name/description, and return focus to its trigger. [desc, code]

Acceptance: real browser verifies confirm/cancel/Escape/focus behavior, exactly one request while pending, success updates the current link and old-link rejection remains intact. Browser interactions must work without stubbing native JavaScript confirmation.

### FR5 — Player-link help modal

Add a compact question-mark button beside the player-link controls, with an accessible name such as About your player link. Open a styled modal explaining that the private link saves access to the player's nickname and games without an account, how to copy/bookmark the actual private link and open it on another device, that anyone holding it can use the identity, and that generating a new link invalidates old bookmarks while keeping signed-in devices usable. Explain that bookmarking the ordinary page after recovery does not save the private link because recovery clears it from the address. Provide a clear Close control, Escape dismissal and focus management consistent with the other footer modals. [user-help, code]

Acceptance: the question-mark button opens readable help on mobile/desktop and by keyboard; Close/Escape returns focus to its trigger. Instructions identify the actual private link or bookmark fallback, distinguish it from the ordinary page URL, and match existing recovery behavior. Opening or closing help does not copy, regenerate or restore credentials.

## Non-Functional Requirements

### NFR1 — Accessibility and behavioral preservation

Keep touch targets usable despite compact visuals (retain the established 44px interactive target floor), accessible icon labels, contrast and keyboard navigation. Respect reduced-motion settings for any new transitions. Preserve identity/session/recovery semantics, nickname profanity filtering, cross-device game access and existing game controls. Use existing dialog/icon conventions and frontend architecture; no new dependency or backend schema is required. [desc, code]

Acceptance: representative real Chromium footer flows and existing accessibility checks pass at desktop/mobile widths; relevant Node/client checks and existing regression suite remain green. Report verification limits honestly; test servers use temporary databases.

### NFR2 — Portable handover

Update HANDOVER.md after approvals, meaningful implementation milestones and verification results with the active intent, pending question/gate, next action, exact relevant commands/results and any blockers. Remove completed to-dos while retaining useful references. [user]

Acceptance: a new AI tool can locate the record and resume the current checkpoint without redoing completed work; no obsolete task remains presented as pending.

## Constraints

- Application changes are frontend-only unless a verified blocker proves otherwise.
- Keep existing secret handling; no normal database/.env access in tests.
- No commit, push or deployment until requested for this intent.

## Assumptions & Open Questions

None. Exact spacing, icons and fallback dialog arrangement follow the existing design system and are validated in a browser.

## Out of Scope

## Deployment Extension Authorized After Footer Approval

The owner explicitly requested implementation and Preview deployment (37efb860), then reopening Code Generation (f59f2390). Earlier frontend-only scope applies to completed footer work; this extension authorizes backend/config changes for Vercel. Preserve completed FR1–FR5/NFR1–NFR2.

- VFR1: Entire FastAPI UI/API runs on Vercel Hobby with direct Neon PostgreSQL and existing secret values. Configure correct Python dependencies/static assets and verified Stockfish startup download to writable ephemeral storage when absent. Never expose secrets or reset normal Neon data automatically.
- VFR2: Replace process-only room serialization with PostgreSQL transaction-level room coordination and retained stale-version checks. Verify two independent app instances cannot commit conflicting moves. Keep local SQLite operation.
- VFR3: Preserve push-based live multiplayer across instances with WebSockets and shared database events, avoiding recurring state polling where possible. Reconnect must resync authoritative state; events contain only safe room identifiers. Direct Neon URL is available. Keep presence/rate-sensitive behavior explicit across instances.
- VFR4: Engine and related background work must be bounded/request-safe or durable/retryable rather than depend on an immortal process. Revalidate game version before committing engine results and prevent duplicate replies after instance interruption/retry. Verify computer and trainer behavior.
- VFR5: Preserve Web Push to intended subscribed recipients including closed tabs. Durable bounded global notification retries must check relevance, coalesce obsolete alerts, use claims/leases to avoid duplicates, and retain failures. Implement a protected daily cron endpoint/schedule as eventual retry/housekeeping safety net. Never replay an hour of stale turn notifications indiscriminately.
- VFR6: Configure Vercel Git Production branch to production for future pushes/merges, keeping Git link optio/JustChess. Deploy only a verified Preview now; no immediate Production deployment/production branch push or merge. Capture Preview URL and smoke results. Do not silently share destructive preview tests with normal Neon data.

Each VFR is Must-have and traces to owner messages 37efb860/f59f2390 and prior deployment answers. Tests must cover isolated SQLite/PostgreSQL multi-instance/event/engine/retry/security behavior and existing browser regression. Deployment needs a real Preview smoke verification, with any runtime limitation surfaced honestly.

- New identity/backend endpoints, authentication changes, schema reset, moderation changes or game-result redesign.
- Deployment, hosting, new libraries and unrelated handover follow-ups.
