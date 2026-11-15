/**
 * JustChess notification logic (U5), pure: no DOM, no browser APIs, so Node
 * tests run it as is.
 *
 *   eventFor(prev, next, slot) -> { kind, key, tag, title, body, banner } | null
 *       The alert a new snapshot means for this seat, keyed exactly like the
 *       server (justchess/notifications.py, BR1.1):
 *         joined           seat B's presence leaves "empty" while game 1 is playing (seat A only), or a
 *                          friend takes over the stand-in computer's seat; the computer itself is no join
 *         move:<game>:<ply> a new half-move by the opponent; ply = half-moves in moveList
 *         ended:<game>     status becomes "finished"; only for the seat that did not cause it,
 *                          and instead of the move alert for a final move
 *       The tag is "<code>:<key>", the same as the push the server sends.
 *       null for a watcher, the first snapshot of a room, or an event that
 *       targets the other seat. P2 U3: null while either snapshot is in
 *       pass-along mode (the player at the device made every change).
 *
 *   decide({ visible, permission, enabled, shownKeys, key }) -> "banner" | "local" | "none"
 *       A visible page shows its banner, whatever the setting. A hidden page
 *       asks the service worker for a local notification when the setting is
 *       on and permission is granted, with or without a push subscription:
 *       push and local share the tag with renotify false, so the second one
 *       silently replaces the first. A key already shown gives "none".
 *
 *   swDecision, notificationFromPush: the service worker's logic. static/sw.js
 *   is a classic worker and cannot import this module, so it carries a copy of
 *   the block between the "shared with sw.js" markers;
 *   tests/js/notify-core.test.mjs pins both copies equal.
 */

export const TITLE_JOINED = "Your opponent has joined";
export const TITLE_MOVE = "Your move";
export const TITLE_ENDED = "Game over";

// Same wording as view-model.js END_TITLES and the server's END_TITLES.
export const END_TEXT = Object.freeze({
  checkmate: "Checkmate",
  stalemate: "Stalemate",
  insufficient_material: "Draw — not enough pieces to mate",
  fivefold_repetition: "Draw by fivefold repetition",
  seventyfive_moves: "Draw by the 75-move rule",
  threefold_claimed: "Draw claimed (threefold repetition)",
  fifty_moves_claimed: "Draw claimed (50-move rule)",
  abandoned: "Opponent left",
});

// End reasons caused by the move just played (the mover caused the end).
const MOVE_ENDS = new Set(["checkmate", "stalemate", "insufficient_material", "fivefold_repetition", "seventyfive_moves"]);
// Draw claims are made by the side to move; the turn does not change.
const CLAIMED_DRAWS = new Set(["threefold_claimed", "fifty_moves_claimed"]);

/** Number of half-moves in a snapshot's moveList ([{ number, white, black }]). */
export function plyCount(snapshot) {
  const rows = snapshot && Array.isArray(snapshot.moveList) ? snapshot.moveList : [];
  return rows.reduce((total, row) => total + (row && row.white ? 1 : 0) + (row && row.black ? 1 : 0), 0);
}

/** The SAN of the latest half-move, or null. */
export function lastSan(snapshot) {
  const rows = snapshot && Array.isArray(snapshot.moveList) ? snapshot.moveList : [];
  const last = rows[rows.length - 1];
  if (!last) return null;
  return last.black || last.white || null;
}

export function endText(endReason) {
  return `Game over — ${Object.hasOwn(END_TEXT, endReason) ? END_TEXT[endReason] : "Game over"}`;
}

function other(colour) {
  return colour === "white" ? "black" : "white";
}

function slotOfColour(snapshot, colour) {
  const seats = snapshot.seats || {};
  for (const slot of ["A", "B"]) if (seats[slot] && seats[slot].colour === colour) return slot;
  return null;
}

/** The colour that did not cause the end of a finished game, or null when it cannot be told. */
function endTargetColour(snapshot) {
  const reason = snapshot.endReason;
  if (MOVE_ENDS.has(reason)) return snapshot.turn; // the mover caused it; the side to move is told
  if (CLAIMED_DRAWS.has(reason)) return other(snapshot.turn); // the side to move claimed
  if (reason === "abandoned") {
    if (snapshot.result === "1-0") return "black";
    if (snapshot.result === "0-1") return "white";
  }
  return null;
}

function make(kind, code, key, title, body, banner) {
  return { kind, key, tag: `${code}:${key}`, title, body, banner };
}

export function eventFor(prev, next, slot) {
  if (!prev || !next || (slot !== "A" && slot !== "B")) return null;
  if (prev.code !== next.code || typeof next.code !== "string") return null;
  // P2 U3: in pass-along one player moves both colours at one device, and accepting a join
  // request is the creator's own act: none of these is news to tell them.
  if (next.mode === "pass_along" || prev.mode === "pass_along") return null;
  const code = next.code;
  const sameGame = prev.game === next.game;

  if (next.status === "finished" && !(sameGame && prev.status === "finished")) {
    const target = slotOfColour(next, endTargetColour(next));
    if (target !== slot) return null;
    const text = endText(next.endReason);
    return make("ended", code, `ended:${next.game}`, TITLE_ENDED, text, text);
  }

  const before = prev.seats && prev.seats.B ? prev.seats.B.presence : null;
  const after = next.seats && next.seats.B ? next.seats.B.presence : null;
  // The computer standing in for the friend is not a join; a friend taking over from it is.
  if (slot === "A" && before === "computer" && after && after !== "empty" && after !== "computer" && next.mode !== "computer") {
    return make("joined", code, "joined", TITLE_JOINED, "Your friend took over from the computer.", TITLE_JOINED);
  }
  if (slot === "A" && before === "empty" && after && after !== "empty" && after !== "computer" && next.game === 1 && next.status === "playing") {
    return make("joined", code, "joined", TITLE_JOINED, "The game has started. You play White: your move.", TITLE_JOINED);
  }

  const ply = plyCount(next);
  if (next.status === "playing" && sameGame && ply > plyCount(prev)) {
    if (slotOfColour(next, next.turn) !== slot) return null; // the side to move is the opponent of the mover
    const san = lastSan(next);
    return make("move", code, `move:${next.game}:${ply}`, TITLE_MOVE, `Your opponent played ${san}.`, TITLE_MOVE);
  }
  return null;
}

export function decide({ visible, permission, enabled, shownKeys, key } = {}) {
  if (!key) return "none";
  if (shownKeys && typeof shownKeys.has === "function" && shownKeys.has(key)) return "none";
  if (visible) return "banner";
  return enabled === true && permission === "granted" ? "local" : "none";
}

// --- shared with sw.js (keep identical; tests/js/notify-core.test.mjs compares them) ---
export function roomPath(code) {
  return typeof code === "string" && /^[A-Z0-9]{6}$/.test(code) ? `/r/${code}` : null;
}

export function notificationFromPush(payload) {
  if (!payload || typeof payload !== "object") return null;
  const path = roomPath(payload.code);
  if (!path || typeof payload.title !== "string" || typeof payload.tag !== "string") return null;
  if (!payload.tag.startsWith(`${payload.code}:`)) return null;
  const url = path; // always the room page on this origin, never a URL taken from the payload
  return {
    code: payload.code,
    title: payload.title.slice(0, 60),
    options: {
      body: typeof payload.body === "string" ? payload.body.slice(0, 140) : "",
      tag: payload.tag,
      renotify: false,
      data: { url, code: payload.code },
    },
  };
}

export function swDecision({ clients, code, origin }) {
  const path = roomPath(code);
  const visiblePage = (clients || []).some((client) => {
    if (!client || client.visibilityState !== "visible" || typeof client.url !== "string") return false;
    try {
      const url = new URL(client.url);
      return url.origin === origin && url.pathname === path;
    } catch {
      return false;
    }
  });
  // Always show (never trigger the browser's generic "updated in the background" notice);
  // when the room's page is visible it is a rare race, so show it quietly.
  return { show: true, silent: visiblePage };
}
// --- end shared with sw.js ---
