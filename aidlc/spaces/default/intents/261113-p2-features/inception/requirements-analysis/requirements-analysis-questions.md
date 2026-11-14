# Requirements Analysis — Questions

Intent: 261113-p2-features. The `.env` item is already done (the app loads `.env` at start-up; see `justchess/envfile.py`), so there is no question about it.

## Ongoing games on the main screen

### Q1. Which games should the main screen list?
A. Unfinished games this browser holds a seat in, newest activity first
B. Unfinished games plus games that ended in the last 7 days
C. Unfinished games only, plus a "remove from list" action per game
X. Other (please specify)

[Answer]: B

### Q2. What should each entry show?
A. Opponent name, your colour, whose turn it is, and when the last move was played
B. Same as A plus a small board thumbnail
C. Just the opponent name and whose turn it is
X. Other (please specify)

[Answer]: B

## Capture animation

### Q3. What should happen when a piece is taken (by you or by your opponent)?
A. The taken piece shrinks and fades on its square, then appears in the captured-pieces row
B. The taken piece flies from its square to the captured-pieces row
C. A short flash on the square only
X. Other (please specify)

[Answer]: A

## Pass-along game while waiting

### Q4. How does a waiting game become a pass-along game?
A. The creator presses "Play here while waiting" on the waiting screen; both sides are then played on that device
B. It switches automatically after a set waiting time
C. The creator chooses it when creating the game
X. Other (please specify)

[Answer]: A

### Q5. When someone opens the invite link during a pass-along game, what happens?
A. They take the opponent's side and the game carries on from the current position; the creator's device stops moving that side
B. Same as A, but the creator must accept the joiner first
C. The pass-along game is kept as a finished practice game and a new online game starts
X. Other (please specify)

[Answer]: B

## Board fit

### Q6. Your note ended with "L". Which screens must show the whole board without scrolling?
A. Phone portrait and desktop/tablet windows
B. Same as A, plus phone landscape (board beside the side panel)
C. Desktop/tablet only
X. Other (please specify)

[Answer]: B

## Share modal

### Q7. Which share options should the modal offer, besides the link and "Copy link"?
A. Email and WhatsApp, plus the phone's own share sheet where the browser supports it
B. Email, WhatsApp, Telegram, Signal, SMS, plus the phone's share sheet
C. Email and WhatsApp only
X. Other (please specify)

[Answer]: B

### Q8. Should the modal also show a QR code of the invite link (handy for a friend sitting next to you)?
A. Yes
B. No
X. Other (please specify)

[Answer]: A

## Single player against Stockfish

### Q9. How should the player choose the computer's strength?
A. A few named levels (for example Beginner, Casual, Club, Strong, Maximum)
B. A slider from 1 to 20
C. An approximate rating (Elo) to pick from
X. Other (please specify)

[Answer]: A

### Q10. What help should single player allow?
A. Take back moves and ask for a hint
B. Take back moves only
C. No help; play it like a real game
X. Other (please specify)

[Answer]: A

### Q11. Should single-player games appear in the ongoing-games list and be resumable later?
A. Yes, saved on the server like online games
B. No, a single-player game lives only while the page is open
X. Other (please specify)

[Answer]: A

## Opening trainer

### Q12. The trainer has the Italian and a Monte Carlo line today. What should be added?
A. More openings: Ruy Lopez, Sicilian, French, Caro-Kann, Queen's Gambit, London, King's Indian, Scandinavian
B. Opening traps and tricks to know (for example Legal's mate, Fried Liver, Fishing Pole, Englund Gambit trap)
C. Both A and B
X. Other (please specify)

[Answer]: C

## Situation trainers

### Q13. Which situations should the new trainers cover?
A. Basic endgames: mate with queen, mate with rook, king-and-pawn endings, opposition
B. Tactics: forks, pins, skewers, discovered attacks, mate in 1 and 2
C. Both A and B
D. Both, plus defending against early attacks
X. Other (please specify)

[Answer]: D

### Q14. Where should the trainer positions come from?
A. Hand-written lesson files in the repo, like the opening lessons
B. A free public puzzle collection downloaded at start-up (for example the Lichess puzzle database, which is CC0)
C. Hand-written files for the endgames, a public collection for tactics
X. Other (please specify)

[Answer]: C

### Q15. In an endgame trainer, who plays the defending side?
A. Stockfish, so the player must really win it
B. Scripted replies, like the opening practice
X. Other (please specify)

[Answer]: A

## Follow-up questions

### Q16. The full Lichess puzzle set is about 250 MB compressed and several million puzzles, which is heavy for a Raspberry Pi. How should tactics puzzles be supplied?
A. Ship a curated subset in the repo (for example about 300 puzzles per theme, from the CC0 set), no download at start-up
B. Download the full set once at first start and import a subset per theme into the database
C. Download the full set and keep it all
X. Other (please specify)

[Answer]: A

### Q17. In a pass-along game, someone opens the invite link and asks to join. What if the creator does not answer?
A. The joiner waits on a "waiting for the creator" screen; the creator gets a notification; the creator can accept or decline at any time
B. Same as A, but the request lapses after 10 minutes and the joiner is told to try again later
C. If nobody answers within 2 minutes the joiner is let in automatically
X. Other (please specify)

[Answer]: B

### Q18. Phone landscape (Q6 B) clashes with the 44 px minimum tap size from the redesign (a landscape phone is about 360 px tall). Which gives way?
A. Squares may shrink to 36 px in phone landscape only; 44 px still holds everywhere else
B. Phone landscape keeps 44 px squares and may scroll a little
C. Hide the top bar in landscape to win height; squares around 42 px
X. Other (please specify)

[Answer]: A


