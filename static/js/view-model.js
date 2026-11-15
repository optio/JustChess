/**
 * JustChess game screen view model (U3). PURE: no DOM, no network, no clock.
 *
 *   viewModel(snapshot, ctx) -> View
 *
 * Turns one server snapshot (U1, BR2.5) plus the screen context into
 * everything the game screen draws. The screen never reads the snapshot
 * directly (BR3.1), so every rule below is testable in Node.
 *
 * ctx: {
 *   connection: "open" | "reconnecting",
 *   watching:   boolean   this device holds no seat (room full, seat moved, seat lost)
 *   notices:    [{ key, colour? }]  from the screen state (screen-state.js)
 * }
 *
 * View: {
 *   board:      { fen, orientation, legalMoves, lastMove (UCI or null), check, interactive }
 *   status:     { text, sub, tone: "baize" | "surface", dot: "solid" | "hollow" | "red" | null }   BR3.4
 *   claims:     { draw: null | "threefold" | "fifty_moves" | "unknown", drawLabel, win }  BR3.7
 *   scoresheet: { rows: [{ number, white, black }], latest: { row, side } | null, result }  BR3.5
 *   score:      { left: { label, wins }, right: { label, wins }, draws, text }        BR3.6
 *   players:    { white, black }  ("You", "Opponent", "Player A", "Player B")
 *   overlay:    null | { title, subtitle, rematch, shareText }                         BR4.2, BR4.3
 *   notices:    [{ key, text, action }]
 *   yourMove:   boolean
 *   passAlong:  { playHere, waitForFriend, practiceNote }   P2 U3 (pass-along.js controlsFor)
 *   joinRequest: null | { colour, expiresAt, expiresIn }   P2 U3, seat A only
 * }
 *
 * Also exported for tests and for app.js: endTitle, resultText, colourName,
 * lastSan, announcement, noticeText and the claim labels.
 *
 * P2 U3: for seat A in a pass-along room (snapshot.mode "pass_along") it is
 * always your move while the game plays: the board is interactive with the
 * server's legal moves for either colour, and the status reads
 * "Pass-along: <colour> to move" in baize. A finished uncounted game reads
 * "Practice game over".
 *
 * P2 U4 (BR8.2): for a computer room (snapshot.mode "computer") the opponent is
 * "Computer · <level>", the status says "Computer is thinking…", "Waiting for
 * the computer… (n ahead)" or why the computer can't move (then the board is
 * not interactive), there are no claim buttons, the score reads "This level:
 * You n · Computer n · Draws n" (score.line), and the overlay offers no Share
 * result (overlay.share false). View.computer is null for friend rooms, else
 * { label, controls: { takeback, hint, resign }, hint, noAnswer } from the
 * extra ctx fields hintPending, hint ({ from, to, version }) and noAnswer; the
 * hint is shown only for the snapshot version it was computed for, on the
 * player's turn.
 */

import { controlsFor as computerControls, opponentLabel, scoreLine, statusText as computerStatusText } from "./computer.js";
import { PASS_ALONG_SUB, PRACTICE_OVER, controlsFor } from "./pass-along.js";

/** P2 U3: seat A's join-request banner facts: the joiner's colour and the expiry, or null. */
function joinRequestOf(snapshot, seat) {
  const request = snapshot.joinRequest;
  if (!seat || snapshot.slot !== "A" || !request || !Number.isFinite(request.expiresIn)) return null;
  const colour = snapshot.seats && snapshot.seats.B && snapshot.seats.B.colour === "white" ? "white" : "black";
  return { colour, expiresAt: request.expiresAt, expiresIn: request.expiresIn };
}

export const END_TITLES = Object.freeze({
  checkmate: "Checkmate",
  stalemate: "Stalemate",
  insufficient_material: "Draw — not enough pieces to mate",
  fivefold_repetition: "Draw by fivefold repetition",
  seventyfive_moves: "Draw by the 75-move rule",
  threefold_claimed: "Draw claimed (threefold repetition)",
  fifty_moves_claimed: "Draw claimed (50-move rule)",
  abandoned: "Opponent left",
  threefold_repetition: "Draw by threefold repetition",
  fifty_moves: "Draw by the 50-move rule",
  resigned: "Resigned",
});

export const FALLBACK_TITLE = "Game over";

export const CLAIM_DRAW_LABELS = Object.freeze({
  threefold: "Claim draw (threefold repetition)",
  fifty_moves: "Claim draw (50-move rule)",
  unknown: "Claim draw",
});

export const CLAIM_WIN_LABEL = "Claim win (opponent left)";

export const STATUS_TEXT = Object.freeze({
  reconnecting: "Reconnecting…",
  waiting: "Waiting for your opponent. Send them the link.",
  waitingWatcher: "Waiting for the second player.",
  yourMove: "Your move",
  check: "Check — your move",
  joining: "Joining the game…",
});

export const NOTICES = Object.freeze({
  storageBlocked: "This browser won't remember your seat. Keep this tab open, or use Continue on another device.",
  seatMoved: "This game was opened on another device.",
  seatsTaken: "This game already has two players.",
  seatLost: "This device is no longer seated in this game.",
  continueExpired: "This continue link has expired or was already used.",
});

const RESULT_GLYPHS = Object.freeze({ "1-0": "1–0", "0-1": "0–1", "1/2-1/2": "½–½" });

/** BR4.2: the overlay title for an end reason; anything unknown is "Game over". */
export function endTitle(endReason) {
  return Object.hasOwn(END_TITLES, endReason) ? END_TITLES[endReason] : FALLBACK_TITLE;
}

/** BR3.5: "1-0" -> "1–0", "0-1" -> "0–1", "1/2-1/2" -> "½–½"; anything else -> null. */
export function resultText(result) {
  return Object.hasOwn(RESULT_GLYPHS, result) ? RESULT_GLYPHS[result] : null;
}

/** "white" -> "White". */
export function colourName(colour) {
  if (colour !== "white" && colour !== "black") throw new TypeError(`not a colour: ${JSON.stringify(colour)}`);
  return colour === "white" ? "White" : "Black";
}

function otherColour(colour) {
  return colour === "white" ? "black" : "white";
}

function otherSlot(slot) {
  return slot === "A" ? "B" : "A";
}

/** The SAN of the newest half-move in a moveList, or null. */
export function lastSan(moveList) {
  if (!Array.isArray(moveList) || moveList.length === 0) return null;
  const row = moveList[moveList.length - 1];
  return row.black || row.white || null;
}

function plyCount(moveList) {
  if (!Array.isArray(moveList)) return 0;
  return moveList.reduce((n, row) => n + (row.white ? 1 : 0) + (row.black ? 1 : 0), 0);
}

/** The colour that wins a result, or null for a draw / no result. */
export function winnerOf(result) {
  if (result === "1-0") return "white";
  if (result === "0-1") return "black";
  return null;
}

function validateSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") throw new TypeError("viewModel needs a snapshot object");
  for (const key of ["fen", "turn", "status", "game", "version"]) {
    if (snapshot[key] === undefined) throw new TypeError(`snapshot is missing ${key}`);
  }
}

function isSeat(snapshot, ctx) {
  return !ctx.watching && (snapshot.slot === "A" || snapshot.slot === "B");
}

/** P2 U3 BR1.2: seat A in a pass-along room moves both colours. */
function passAlongSeat(snapshot, seat) {
  return seat && snapshot.slot === "A" && snapshot.mode === "pass_along";
}

/** P2 U3: the pass-along statuses (baize while playing: it is always your move). */
function passAlongStatus(snapshot, ctx) {
  if (snapshot.status === "finished" && snapshot.counted === false) {
    const winner = winnerOf(snapshot.result);
    return { text: PRACTICE_OVER, sub: `${endTitle(snapshot.endReason)}. ${winner ? `${colourName(winner)} wins` : "Draw"}.`, tone: "surface", dot: null };
  }
  if (snapshot.status !== "playing" || ctx.connection === "reconnecting") return null;
  const text = `Pass-along: ${colourName(snapshot.turn)} to move`;
  return { text, sub: snapshot.check ? `${colourName(snapshot.turn)} is in check` : PASS_ALONG_SUB, tone: "baize", dot: snapshot.check ? "red" : "solid" };
}

function presenceOf(snapshot, slot) {
  return snapshot.seats && snapshot.seats[slot] ? snapshot.seats[slot].presence : "empty";
}

function slotOfColour(snapshot, colour) {
  if (!snapshot.seats) return null;
  for (const slot of ["A", "B"]) {
    if (snapshot.seats[slot] && snapshot.seats[slot].colour === colour) return slot;
  }
  return null;
}

/** BR3.4: one status, chosen in this order; the text always carries the state. */
function statusOf(snapshot, ctx, seat, yourMove) {
  if (snapshot.status === "finished") {
    const title = endTitle(snapshot.endReason);
    const winner = winnerOf(snapshot.result);
    const outcome = winner ? `${colourName(winner)} wins` : "Draw";
    const sub = seat ? `${outcome}. Colours swap if you play again.` : outcome;
    const text = title === FALLBACK_TITLE ? FALLBACK_TITLE : `${FALLBACK_TITLE} — ${title}`;
    return { text, sub, tone: "surface", dot: null };
  }
  if (ctx.connection === "reconnecting") {
    return { text: STATUS_TEXT.reconnecting, sub: "Your game is safe. Trying again…", tone: "surface", dot: "hollow" };
  }
  if (snapshot.status === "waiting") {
    return { text: seat ? STATUS_TEXT.waiting : STATUS_TEXT.waitingWatcher, sub: null, tone: "surface", dot: null };
  }
  const mover = otherColour(snapshot.turn);
  const san = lastSan(snapshot.moveList);
  const played = san ? `${colourName(mover)} played ${san}` : null;
  if (yourMove) {
    return snapshot.check
      ? { text: STATUS_TEXT.check, sub: played, tone: "baize", dot: "red" }
      : { text: STATUS_TEXT.yourMove, sub: played, tone: "baize", dot: "solid" };
  }
  const turnSlot = slotOfColour(snapshot, snapshot.turn);
  const away = turnSlot && ["away", "abandoned"].includes(presenceOf(snapshot, turnSlot));
  const extra = [];
  if (snapshot.check) extra.push(`${colourName(snapshot.turn)} is in check`);
  if (away) extra.push(`${colourName(snapshot.turn)} is away`);
  return {
    text: `Waiting for ${colourName(snapshot.turn)}`,
    sub: extra.length ? extra.join(" · ") : null,
    tone: "surface",
    dot: away ? "hollow" : null,
  };
}

/** P2 U4 BR8.2: a playing computer game's status while the computer is unavailable or to move, else null. */
function computerStatus(snapshot, ctx, yourMove) {
  if (snapshot.status !== "playing" || ctx.connection === "reconnecting") return null;
  const computer = snapshot.computer;
  if (computer.state === "unavailable") return { text: computerStatusText(computer), sub: null, tone: "surface", dot: "hollow" };
  if (yourMove) return null;
  const san = lastSan(snapshot.moveList);
  const played = san ? `${colourName(otherColour(snapshot.turn))} played ${san}` : null;
  return { text: computerStatusText(computer) || "Waiting for the computer", sub: played, tone: "surface", dot: null };
}

function computerViewOf(snapshot, seat, ctx) {
  const controls = computerControls(snapshot, { watching: !seat, hintPending: Boolean(ctx.hintPending) });
  const hint = ctx.hint;
  const showHint = Boolean(hint) && hint.version === snapshot.version && controls.hint.show
    && snapshot.status === "playing" && snapshot.colour === snapshot.turn;
  return {
    label: opponentLabel(snapshot.computer.level || snapshot.computerLevel),
    controls,
    hint: showHint ? { from: hint.from, to: hint.to, san: hint.san || null } : null,
    noAnswer: Boolean(ctx.noAnswer) && seat && snapshot.status === "playing",
  };
}

/** BR3.7: claim buttons only while valid. */
function claimsOf(snapshot, seat, yourMove) {
  const playing = snapshot.status === "playing";
  if (snapshot.mode === "computer") return { draw: null, drawLabel: null, win: false, winLabel: CLAIM_WIN_LABEL }; // BR3.6
  let draw = null;
  if (playing && yourMove && snapshot.claimableDraw) {
    draw = Object.hasOwn(CLAIM_DRAW_LABELS, snapshot.claimableDrawReason) ? snapshot.claimableDrawReason : "unknown";
  }
  const win = playing && seat && presenceOf(snapshot, otherSlot(snapshot.slot)) === "abandoned";
  return { draw, drawLabel: draw ? CLAIM_DRAW_LABELS[draw] : null, win: Boolean(win), winLabel: CLAIM_WIN_LABEL };
}

/** BR3.5: scoresheet rows, the newest move and the result cell. */
function scoresheetOf(snapshot) {
  const rows = (Array.isArray(snapshot.moveList) ? snapshot.moveList : []).map((row) => ({
    number: row.number,
    white: row.white || "",
    black: row.black || "",
  }));
  const last = rows.length ? rows[rows.length - 1] : null;
  const latest = last ? { row: rows.length - 1, side: last.black ? "black" : "white" } : null;
  const result = snapshot.status === "finished" ? resultText(snapshot.result) : null;
  return { rows, latest, result };
}

/** BR3.6: the score per player, using the viewer's slot. */
function scoreOf(snapshot, seat) {
  const score = snapshot.score || { A: 0, B: 0, draws: 0 };
  const left = seat ? { label: "You", wins: score[snapshot.slot] || 0 } : { label: "Player A", wins: score.A || 0 };
  const right = seat ? { label: "Opponent", wins: score[otherSlot(snapshot.slot)] || 0 } : { label: "Player B", wins: score.B || 0 };
  const draws = score.draws || 0;
  if (snapshot.mode === "computer") {
    const line = scoreLine(score); // P2 U4: the player against the computer at this level
    return { left: { label: "You", wins: score.A || 0 }, right: { label: "Computer", wins: score.B || 0 }, draws, text: line, line };
  }
  const text = `${left.label} ${left.wins} · ${right.label} ${right.wins} · Draws ${draws}`;
  return { left, right, draws, text, line: `Room score: ${text}` };
}

function playersOf(snapshot, seat) {
  const names = {};
  const computerName = snapshot.mode === "computer" ? opponentLabel(snapshot.computerLevel) : null;
  for (const slot of ["A", "B"]) {
    const colour = snapshot.seats && snapshot.seats[slot] ? snapshot.seats[slot].colour : slot === "A" ? "white" : "black";
    if (computerName && slot === "B") names[colour] = computerName;
    else if (seat) names[colour] = slot === snapshot.slot ? "You" : "Opponent";
    else names[colour] = `Player ${slot}`;
  }
  return { white: names.white || "White", black: names.black || "Black" };
}

/** BR4.3: the rematch button state from the snapshot's rematch field and the viewer's slot. */
function rematchOf(snapshot, seat) {
  if (!seat) return "none";
  const rematch = snapshot.rematch || { state: "none", requestedBy: null };
  if (rematch.state === "lapsed") return "lapsed";
  if (rematch.state === "pending") return rematch.requestedBy === snapshot.slot ? "waiting" : "opponentReady";
  return "offer";
}

function shareTextOf(snapshot, seat, title) {
  const winner = winnerOf(snapshot.result);
  if (seat && winner) {
    const won = snapshot.colour === winner;
    const how = snapshot.endReason === "checkmate" ? "by checkmate" : snapshot.endReason === "abandoned" ? "(my opponent left)" : `(${title})`;
    return `I ${won ? "won" : "lost"} ${how} on JustChess`;
  }
  return `${title} on JustChess`;
}

/** BR4.2: the overlay names the reason, the winner and the decisive move. */
function overlayOf(snapshot, seat) {
  if (snapshot.status !== "finished") return null;
  let title = endTitle(snapshot.endReason);
  const winner = winnerOf(snapshot.result);
  const san = lastSan(snapshot.moveList);
  let subtitle = "Draw";
  if (winner) {
    subtitle = snapshot.endReason === "abandoned" || !san ? `${colourName(winner)} wins` : `${colourName(winner)} wins with ${san}`;
    const winningSlot = slotOfColour(snapshot, winner);
    const losingSlot = winningSlot === "A" ? "B" : "A";
    const nameOf = slot => snapshot.mode === "computer" && slot === "B" ? "Computer" : snapshot.seats?.[slot]?.nickname || "Your opponent";
    if (seat && snapshot.mode !== "pass_along") {
      const won = snapshot.colour === winner;
      title = won ? "You won!" : "You lost";
      subtitle = won ? `You beat ${nameOf(losingSlot)}. ${subtitle}. ${endTitle(snapshot.endReason)}.`
        : `${nameOf(winningSlot)} won. ${subtitle}. ${endTitle(snapshot.endReason)}.`;
    }
  }
  return {
    title,
    subtitle,
    rematch: rematchOf(snapshot, seat),
    shareText: shareTextOf(snapshot, seat, title),
    share: snapshot.mode !== "computer", // P2 U4 BR8.2: no share controls against the computer
  };
}

/** Notice keys from the screen state to their sentences. */
export function noticeText(notice) {
  if (!notice || typeof notice.key !== "string") return null;
  if (notice.key === "staleSeat") {
    return notice.colour === "white" || notice.colour === "black"
      ? `Your old seat had expired, so you joined as ${notice.colour}.`
      : "Your old seat had expired, so you joined with a new seat.";
  }
  return Object.hasOwn(NOTICES, notice.key) ? NOTICES[notice.key] : null;
}

function noticesOf(ctx) {
  return (ctx.notices || [])
    .map((notice) => ({ key: notice.key, text: noticeText(notice), action: notice.key === "seatsTaken" ? "startNew" : null }))
    .filter((notice) => notice.text);
}

export function viewModel(snapshot, ctx = {}) {
  validateSnapshot(snapshot);
  const context = { connection: "open", watching: false, notices: [], ...ctx };
  const seat = isSeat(snapshot, context);
  const playing = snapshot.status === "playing";
  const passAlong = passAlongSeat(snapshot, seat);
  const computerRoom = snapshot.mode === "computer" && Boolean(snapshot.computer) && typeof snapshot.computer === "object";
  const yourMove = seat && playing && (snapshot.colour === snapshot.turn || passAlong);
  const computerDown = computerRoom && snapshot.computer.state === "unavailable"; // BR5.5: no moves while it can't answer
  const interactive = yourMove && context.connection === "open" && !computerDown;
  const status = (passAlong && passAlongStatus(snapshot, context))
    || (computerRoom && computerStatus(snapshot, context, yourMove))
    || statusOf(snapshot, context, seat, yourMove);
  return {
    board: {
      fen: snapshot.fen,
      orientation: seat && snapshot.colour === "black" ? "black" : "white",
      legalMoves: interactive && Array.isArray(snapshot.legalMoves) ? [...snapshot.legalMoves] : [],
      lastMove: typeof snapshot.lastMove === "string" ? snapshot.lastMove : null,
      check: Boolean(snapshot.check),
      interactive,
    },
    status,
    claims: claimsOf(snapshot, seat, yourMove),
    scoresheet: scoresheetOf(snapshot),
    score: scoreOf(snapshot, seat),
    players: playersOf(snapshot, seat),
    overlay: overlayOf(snapshot, seat),
    notices: noticesOf(context),
    yourMove,
    seat,
    passAlong: controlsFor(snapshot, { watching: !seat }),
    joinRequest: joinRequestOf(snapshot, seat),
    computer: computerRoom ? computerViewOf(snapshot, seat, context) : null,
  };
}

/**
 * The live-region sentence for what changed between two snapshots, or null.
 * "White played d4. Your move." / "You played e4." / a game end / a new game.
 * viewerColour is null for a watcher.
 */
export function announcement(previous, next, viewerColour = null) {
  if (!next) return null;
  if (previous && next.game > previous.game) {
    return viewerColour ? `New game. You play ${viewerColour}.` : "New game.";
  }
  if (!previous || previous.game !== next.game) return null;
  const parts = [];
  const before = plyCount(previous.moveList);
  const after = plyCount(next.moveList);
  if (after > before) {
    const san = lastSan(next.moveList);
    const mover = otherColour(next.turn);
    if (viewerColour === mover) parts.push(`You played ${san}.`);
    else parts.push(`${colourName(mover)} played ${san}.`);
    if (next.status === "playing" && viewerColour && viewerColour === next.turn) {
      parts.push(next.check ? "Check. Your move." : "Your move.");
    }
  }
  if (previous.status !== "finished" && next.status === "finished") {
    const title = endTitle(next.endReason);
    const winner = winnerOf(next.result);
    parts.push(`Game over — ${title}. ${winner ? `${colourName(winner)} wins.` : "Draw."}`);
  } else if (previous.status === "waiting" && next.status === "playing") {
    parts.push("Your opponent joined.");
  }
  return parts.length ? parts.join(" ") : null;
}
