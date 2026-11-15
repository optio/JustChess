# Code Quality Assessment

> Focused merge, 2026-11-15: current findings cover player identity/presentation and persistence seams. Outside-focus descriptions are retained prior-store context and are not newly verified; see the timestamp for exact coverage.

## Verified strengths

Server-authoritative legal moves and replayed histories preserve repetition and outcomes. Version checks, short explicit transactions and per-room locks protect local mutation ordering. Tokens are hashed at rest and omitted from invitation links/logging. Origin/body controls, push destination checks and safe content loaders constrain input. Engine results are revalidated after asynchronous computation. Frontend pure reducers and injected clocks/network/storage support isolated tests.

## Current risks and intent implications

SQLite and PostgreSQL now share schema version 4 and a deliberately small compatibility adapter. New schema/SQL must work on both: the adapter handles qmarks outside single-quoted literals but explicitly assumes no comments or dollar-quoted SQL. New identity tables/columns require a version/startup strategy. SQLite archives/replaces older or unmarked files; PostgreSQL refuses unsupported or occupied unversioned schemas unchanged. A naïve version bump would archive existing SQLite rooms and refuse existing PostgreSQL startup. The user explicitly permits deletion/recreation because the app is not live and requires no backward compatibility. A migration is unnecessary for this feature, but recreation must be deliberately supported for both backends. No database was touched during this scan.

One worker remains required. Synchronous DB operations may block async requests; a remote database adds latency. api.py and the frontend shell have substantial orchestration responsibilities. Push event claims intentionally have no retry after a crash. In-memory rate/decline records reset on restart. These are observed limits, not changes made here.

## Verification boundary

The runtime, frontend, content loaders, authored lesson/endgame content and configuration were deeply read. Database/environment regression files were deeply read; remaining Python/Node/browser tests were inventoried and selected test names inspected. Tests include temporary SQLite fixtures, fake UCI, optional real-engine/browser/push checks. SQLite introspection/IntegrityError assertions should remain backend-specific. No test, build, live database, coverage measurement or security audit ran. README historical pass counts are not current verification. No committed deployment automation was discovered in the root inventory.


## Focused quality findings (2026-11-15)

Naming and explicit error handling: good in inspected storage/domain helpers. Function size: fair; large app/game/API orchestrators were only skimmed. Test presence: good for existing storage and settings, with broader browser/room/result coverage located. Duplication: fair; board choices appear in settings.js, boot.js, settings-panel.js and tokens.css. Dead code was not exhaustively assessed.

Personalized outcomes must distinguish watchers, pass-along uncounted practice, computer rooms, rematches with swapped colours and finished pages reopened later. Existing end lifecycle animates only a newly ended game and cancels on rematch. Confetti should preserve that lifecycle and reduced-motion behavior. Existing renderers use textContent, a suitable seam for untrusted nicknames; moderation rules (languages, normalization, length, false positives, updates) remain undecided.

No tests/builds or database connections ran in this focused scan. Only the two listed JavaScript storage/settings tests were deeply read; prior broad verification prose above is historical and demoted in the timestamp scope. No current test pass counts or code coverage are claimed.

