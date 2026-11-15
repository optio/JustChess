# Player Identity and Game Polish Questions

Known: selected pieces grow slightly; durable account-free identity has a bookmarkable footer link; editable nicknames require profanity filtering; winners get confetti and clear viewer-relative win/loss messages using nicknames when available. Owner permits database recreation and requires no backward compatibility. SQLite and PostgreSQL remain supported.

## Q1 — What follows the player across devices?

A. Nickname and access to their saved games/seats, with both devices usable (recommended).
B. Nickname only; room access still needs the existing room transfer links.
X. Other (please specify)

[Answer]: A. Nickname and access to their saved games/seats, with both devices usable.

## Q2 — Identity bookmark lifetime and control

Anyone holding the private bookmark can use that identity.

A. Reusable until the player regenerates it; regeneration invalidates the old bookmark (recommended).
B. Permanent reusable link, with no regeneration control in this change.
X. Other (please specify)

[Answer]: A. Reusable until the player regenerates it; regeneration invalidates the old bookmark.

## Q3 — Nickname moderation languages

Reject blocked nicknames with an explanation, allowing the user to choose another; never render nicknames as HTML.

A. Filter English and Dutch profanity (recommended for the current context).
B. Filter English profanity only.
C. Specify a different set of languages.
X. Other (please specify)

[Answer]: B. Filter English profanity only.
