# Requirements Analysis — Questions (P1 and UI redesign)

Inputs:
- The approved P1 spec: `aidlc/spaces/default/intents/261111-requirements-review/inception/requirements-analysis/requirements.md`.
- Its reviewer's open findings. They concern:
  - existing data;
  - seat identity across tabs and notifications;
  - the learner's side;
  - HTTPS, push keys and retention;
  - blunder corner cases;
  - rematch with an absent opponent;
  - undefined numbers;
  - dropped CSRF and brand;
  - board size with outside labels.
- The refreshed code map (`aidlc/spaces/default/codekb/JustChess/business-overview.md`, section "User Experience Today").
- Your request: "Continue and also challenge the AI typical ui and improve it".

These have sensible defaults, so I'll write them as requirements or assumptions you can correct at approval instead of asking:
- Blunder warnings appear only when the move itself creates the problem, and are skipped when every legal move has it.
- The rematch offer lapses when the opponent has left.
- CSRF and origin checks are carried over.
- The brand and tagline are kept.
- The board-size rule covers outside labels.
- The hint is revealed after 3 misses.

## Q1. [Designer] What should JustChess feel like, instead of the generic look it has today?

Context: today it is one dark-green palette with a beige accent on every control, system font, stacked rounded cards, Unicode pieces and no motion. That is the "AI default" look you want to move away from. The mockups stage will draw this out in full; this sets its direction.

- A. Classic and warm: a real wooden set and a club scoresheet. Warm wood and paper tones, a serif display face, and the moves written like a scoresheet
- B. Editorial and minimal: the board is the hero, with strong typography, a near-monochrome palette with one sharp accent, and almost no chrome
- C. Playful and tactile: bold colours, chunky shapes, and satisfying piece and win animations
- D. Show me 2–3 distinct directions in the mockups and I'll pick there
- X. Other (please specify)

[Answer]: X. Other: "Classic and warm with satisfying piece and win animations"

## Q2. [Designer] Light and dark?

Context: today there is only a dark theme, with no light mode and no system preference support.

- A. Light and dark, following the device setting, with a toggle
- B. One carefully designed theme only
- C. A and D: light/dark plus a choice of board colour themes
- D. One theme plus a choice of board colour themes
- X. Other (please specify)

[Answer]: C

## Q3. [Designer] How should the pieces be drawn?

Context: today the pieces are Unicode characters (♔♕…). They look different on every phone and are hard to style.

- A. A proper SVG piece set with an open licence (for example "cburnett", CC BY-SA, used by many open chess sites)
- B. Keep Unicode characters, just styled better
- C. A custom-designed set matching the chosen style (more work)
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Q4. [Product owner] How will JustChess be reached over HTTPS from outside your home network?

Context: Web Push (FR6.5) only works over HTTPS. For local testing, browsers also accept `localhost`. Your Pi runs the app today on a plain HTTP port.

- A. Caddy reverse proxy on the Pi with automatic Let's Encrypt certificates (needs a domain name and ports 80/443 forwarded)
- B. Cloudflare Tunnel (no open ports; needs a Cloudflare account and a domain)
- C. Tailscale (Serve or Funnel)
- D. Not decided yet: build and test push on localhost now, choose hosting later
- X. Other (please specify)

[Answer]: D

## Q5. [Product owner] What happens to rooms and games already stored when the new data model arrives?

Context: P1 moves from one `games` table with plaintext seat tokens to separate tables with hashed tokens (NFR2). The reviewer asked what happens to existing data.

- A. Start fresh: existing rooms are discarded on upgrade (no real users yet)
- B. Migrate in place: copy the rooms over and hash the tokens, so open games keep working
- C. Keep the old file as a backup and start a new database
- D. Not sure
- X. Other (please specify)

[Answer]: A

## Q6. [Product owner] Where should a player's seat be remembered?

Context: today the seat token lives in `sessionStorage`, so it is lost when the tab closes. A tap on a push notification opens a new tab, which would lose the seat (reviewer finding). Putting the token in a link exposes it to anyone who sees the link.

- A. In the browser's long-lived storage (`localStorage`): survives closed tabs, restarts and notification taps on the same browser and device
- B. A, plus a private "continue on another device" link the player can ask for (it contains the secret, with a warning not to share it)
- C. Keep tab-only storage (the seat is lost when the tab closes)
- D. Not yet defined
- X. Other (please specify)

[Answer]: B

## Q7. [Product owner] In practice mode, which side does the learner play?

Context: you chose "the trainer plays the opponent's moves". Both catalog lessons (Italian Game, French Exchange — Monte Carlo with 4.c4) are lines White chooses. Later openings, such as the Sicilian or the King's Indian, are Black's.

- A. Each lesson file states the side the line is taught from; the learner plays that side
- B. The learner picks White or Black for any lesson
- C. A as the default, with a switch to try the other side
- D. Not yet defined
- X. Other (please specify)

[Answer]: C

## Q8. [Product owner] How long should inactive rooms and their notification subscriptions be kept?

Context: the spec asks for room expiry and push-subscription cleanup but gave no numbers (reviewer finding). This also decides when an absent opponent's game counts as abandoned.

- A. Rooms kept 7 days after the last move; a game is "abandoned" after 10 minutes with the opponent disconnected
- B. Rooms kept 30 days; abandoned after 24 hours (suits slow, correspondence-style games with push alerts)
- C. Rooms kept 24 hours; abandoned after 5 minutes
- D. Not yet defined
- X. Other (please specify)

[Answer]: B
