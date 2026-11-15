/**
 * JustChess "Your games" list logic (P2 U2, BR3.1-BR3.3): pure functions, no DOM.
 *
 * Summaries come from POST /api/rooms/summaries (see justchess/summaries.py);
 * their times (lastActivityAt, endedAt) are server epoch seconds. ``now`` is
 * always passed in, in milliseconds, so every function here is deterministic.
 *
 *   seatsToSend(seats)              distinct (code, token) seats, the 50 most recently saved
 *   reconcile(store, sent, answer)  -> { ok, kept: [{ seat, summary }] }
 *                                   drops a stored seat only when its summary says
 *                                   found:false (BR3.3); an answer that does not
 *                                   line up with what was sent changes nothing
 *   filterAndSort(entries, now)     unfinished games, then games finished in the
 *                                   last 7 days (BR3.1); entries are summaries or
 *                                   { seat, summary } pairs
 *   rowModel(summary, now)          { code, href, label, meta, pill, finished, squares, ariaLabel }
 *   staleRowModel(seat)             the row for a stored seat without live data
 *   relativeTime(thenMs, nowMs)     "just now", "4 min ago", "2 h ago", "yesterday", "3 days ago"
 *   thumbnailSquares(fen, colour)   64 { dark, piece } cells, the player's side at the bottom
 *
 * Tokens never leave the seat objects: no model, label or key carries one.
 */

export const MAX_SEATS = 50;
export const DAY_MS = 24 * 60 * 60 * 1000;
export const RECENT_FINISHED_MS = 7 * DAY_MS;

const LEVEL_NAMES = { beginner: "Beginner", casual: "Casual", club: "Club", strong: "Strong", maximum: "Maximum" };
const END_REASONS = {
  checkmate: "checkmate",
  stalemate: "stalemate",
  insufficient_material: "insufficient material",
  fivefold_repetition: "fivefold repetition",
  seventyfive_moves: "75-move rule",
  threefold_claimed: "threefold repetition",
  fifty_moves_claimed: "50-move rule",
  threefold_repetition: "threefold repetition",
  fifty_moves: "50-move rule",
  abandoned: "abandoned",
  resigned: "resigned",
};
const RESULT_PILLS = { won: "You won", lost: "You lost", drawn: "Draw" };

function capitalise(word) {
  return word ? word[0].toUpperCase() + word.slice(1) : "";
}

function secondsToMs(value) {
  return Number.isFinite(value) ? value * 1000 : null;
}

/** Distinct, well-formed (code, token) seats in the given order (most recently saved first), at most 50. */
export function seatsToSend(seats) {
  const seen = new Set();
  const chosen = [];
  for (const seat of seats) {
    if (!seat || !/^[A-Z0-9]{6}$/.test(seat.code) || typeof seat.token !== "string" || seat.token.length < 1 || seat.token.length > 128) continue;
    const key = `${seat.code}\n${seat.token}`;
    if (seen.has(key)) continue;
    seen.add(key);
    chosen.push(seat);
    if (chosen.length === MAX_SEATS) break;
  }
  return chosen;
}

/**
 * Pair each sent seat with its summary (the server answers in request order) and
 * drop the seats that came back found:false. Nothing is dropped unless the answer
 * lines up exactly with what was sent (BR3.3).
 */
export function reconcile(store, sent, answer) {
  if (!Array.isArray(answer) || answer.length !== sent.length) return { ok: false, kept: [] };
  if (answer.some((summary, index) => !summary || summary.code !== sent[index].code)) return { ok: false, kept: [] };
  const kept = [];
  sent.forEach((seat, index) => {
    const summary = answer[index];
    if (summary.found === false) store.remove(seat.code, seat.token);
    else if (summary.found === true) kept.push({ seat, summary });
  });
  return { ok: true, kept };
}

function summaryOf(entry) {
  return entry && entry.summary ? entry.summary : entry;
}

function isRecent(summary, now) {
  if (summary.status !== "finished") return true;
  const ended = secondsToMs(summary.endedAt);
  return ended !== null && now - ended <= RECENT_FINISHED_MS;
}

/** BR3.1: unfinished (join requests first, then newest activity), then finished in the last 7 days (newest end). */
export function filterAndSort(entries, now) {
  const listed = entries.filter((entry) => {
    const summary = summaryOf(entry);
    return summary && summary.found === true && isRecent(summary, now);
  });
  const rank = (summary) => (summary.status === "finished" ? 2 : summary.pendingJoinRequest ? 0 : 1);
  const time = (summary) => (summary.status === "finished" ? summary.endedAt : summary.lastActivityAt) || 0;
  return listed.sort((left, right) => {
    const a = summaryOf(left);
    const b = summaryOf(right);
    return rank(a) - rank(b) || time(b) - time(a) || a.code.localeCompare(b.code);
  });
}

export function relativeTime(thenMs, nowMs) {
  if (!Number.isFinite(thenMs)) return "";
  const elapsed = Math.max(0, nowMs - thenMs);
  const minutes = Math.floor(elapsed / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

function label(summary) {
  if (summary.kind === "computer") return `Computer, ${LEVEL_NAMES[summary.computerLevel] || "unknown level"}`;
  if (summary.passAlong) return `Pass-along · ${summary.code}`;
  if (summary.opponent !== "joined") return `Waiting for a friend · ${summary.code}`;
  const name = typeof summary.opponentNickname === "string" ? summary.opponentNickname.trim() : "";
  return name ? `${name} · ${summary.code}` : `Friend · ${summary.code}`;
}

function pill(summary) {
  if (summary.pendingJoinRequest && summary.status !== "finished") return { text: "Join request", tone: "request" };
  if (summary.status === "finished") {
    const text = RESULT_PILLS[summary.result];
    return text ? { text, tone: summary.result } : { text: "Ended", tone: "ended" };
  }
  // A friend room nobody joined yet still waits, also after a left pass-along game.
  if (summary.status === "waiting" || (summary.kind !== "computer" && summary.opponent === "waiting" && !summary.passAlong)) {
    return { text: "Waiting", tone: "waiting" };
  }
  if (summary.yourTurn) return { text: "Your move", tone: "your-move" };
  return { text: "Their move", tone: "their-move" };
}

function meta(summary, now) {
  if (summary.status === "finished") {
    const when = relativeTime(secondsToMs(summary.endedAt), now);
    const reason = END_REASONS[summary.endReason];
    return ["Ended" + (when ? ` ${when}` : ""), reason].filter(Boolean).join(" · ");
  }
  const when = relativeTime(secondsToMs(summary.lastActivityAt), now);
  return `You play ${capitalise(summary.colour)}` + (when ? ` · last move ${when}` : "");
}

/** 64 cells for the thumbnail, rank 8 first from White's side, or rank 1 first from Black's. */
export function thumbnailSquares(fen, colour = "white") {
  const placement = typeof fen === "string" ? fen.split(" ")[0] : "";
  const ranks = placement.split("/");
  const cells = [];
  for (let rank = 0; rank < 8; rank += 1) {
    const row = [];
    for (const char of ranks.length === 8 ? ranks[rank] : "8") {
      if (/[1-8]/.test(char)) for (let n = 0; n < Number(char); n += 1) row.push(null);
      else if (/[pnbrqkPNBRQK]/.test(char)) row.push(char);
    }
    while (row.length < 8) row.push(null);
    row.slice(0, 8).forEach((piece, file) => cells.push({ dark: (rank + file) % 2 === 1, piece }));
  }
  return colour === "black" ? cells.reverse() : cells;
}

/** BR3.2: the label, meta line, pill and thumbnail of one found summary. */
export function rowModel(summary, now) {
  const model = {
    code: summary.code,
    href: `/r/${summary.code}`,
    label: label(summary),
    meta: meta(summary, now),
    pill: pill(summary),
    finished: summary.status === "finished",
    squares: thumbnailSquares(summary.fen, summary.colour),
  };
  model.ariaLabel = `${model.label}. ${model.meta}. ${model.pill.text}`;
  return model;
}

/** A stored seat shown without live data after a failed refresh (BR3.3, functional-spec edge cases). */
export function staleRowModel(seat) {
  const name = seat.kind === "computer" ? `Computer, ${LEVEL_NAMES[seat.computerLevel] || "unknown level"}` : `Room ${seat.code}`;
  const model = {
    code: seat.code,
    href: `/r/${seat.code}`,
    label: name,
    meta: "No live details right now",
    pill: { text: "Couldn't refresh", tone: "stale" },
    finished: false,
    squares: thumbnailSquares(null),
  };
  model.ariaLabel = `${model.label}. ${model.pill.text}`;
  return model;
}
