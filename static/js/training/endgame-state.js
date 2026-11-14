/**
 * Endgame trainer texts, attempt storage, HTTP client and hub tab (P2 U6, BR4.1, BR4.2).
 * PURE apart from the injected fetch and storage: no DOM, so it runs in Node tests.
 *
 *   statusText(position)                -> "Mate with the rook. Goal: checkmate. Position 1 of 3."
 *   moveCounter(playerMoves, holdMoves) -> "Move 12 of 30" (draw goal; never above the target)
 *   verdictMessage(goal, verdict)       -> { text, tone } | null while playing
 *   errorText(status, detail)           -> the 503 (unavailable or busy) or 429 text
 *   saveAttempt(storage, attempt) / loadAttempt(storage, positionId) / clearAttempt(storage)
 *                                          the attempt in session storage, every access in try/catch
 *   createEndgamesApi(fetchImpl)        -> { list, get, play } resolving { ok, status, data | message }
 *   endgamesLoader(context)             -> the hub tab's rows (registered as ENDGAMES_TAB)
 *
 * The attempt is { positionId, moves, fen, legalMoves, check, lastMove, status,
 * reason, playerMoves, movesLeft }: the moves from the start position (the
 * player's at even indexes) and the board the page shows now. Nothing here is
 * trusted by the server, which replays the moves itself.
 */

import { NETWORK_MESSAGE, SERVER_MESSAGE } from "../api.js";

export const POSITION_ID = /^[a-z0-9-]{3,40}$/;
export const UCI_PATTERN = /^[a-h][1-8][a-h][1-8][qrbn]?$/;
export const ATTEMPT_KEY = "justchess.endgame.attempt.v1";
export const PROGRESS_GROUP = "endgames";
export const NOT_INSTALLED = "No endgame positions are installed";
export const NEEDS_STOCKFISH = "Needs Stockfish";
export const UNAVAILABLE = "The computer is not available right now";
export const TOO_FAST = "Too many moves too fast. Wait a moment.";
export const THINKING = "Computer is thinking…";
export const UNKNOWN_POSITION = "There is no such endgame position.";
export const MAX_PLIES = 1000; // the storage check's upper bound; the server enforces its own cap

const CATEGORY_LEADS = Object.freeze({
  "queen-mate": "Mate with the queen",
  "rook-mate": "Mate with the rook",
  "king-pawn": "King and pawn",
  opposition: "Use the opposition",
});
const GOAL_SHORT = Object.freeze({ mate: "checkmate", promote: "promote the pawn", draw: "hold the draw" });
const STATUSES = Object.freeze(["playing", "passed", "failed"]);

export function goalText(goal, holdMoves = 30) {
  if (goal === "draw") return `Goal: hold the draw (${holdMoves} moves, repetition or 50-move rule)`;
  return `Goal: ${GOAL_SHORT[goal] || "reach the goal"}`;
}

/** BR4.2: "<lead>. Goal: <goal>. Position <index> of <count>." */
export function statusText(position) {
  if (!position) return "";
  const lead = CATEGORY_LEADS[position.category] || position.title || "Endgame";
  const where = Number.isInteger(position.index) && Number.isInteger(position.count)
    ? ` Position ${position.index} of ${position.count}.` : "";
  return `${lead}. ${goalText(position.goal, position.holdMoves)}.${where}`;
}

/** BR4.2: "Move n of 30" for a draw goal; n is the move being played, capped at the target. */
export function moveCounter(playerMoves, holdMoves) {
  const target = Number.isInteger(holdMoves) && holdMoves > 0 ? holdMoves : 30;
  const done = Number.isInteger(playerMoves) && playerMoves > 0 ? playerMoves : 0;
  return `Move ${Math.min(done + 1, target)} of ${target}`;
}

function movesWord(count) {
  return `${count} ${count === 1 ? "move" : "moves"}`;
}

/** BR4.2: the text for a finished attempt, or null while it is still playing. */
export function verdictMessage(goal, verdict) {
  if (!verdict || verdict.status === "playing") return null;
  const count = Number.isInteger(verdict.playerMoves) ? verdict.playerMoves : 0;
  if (verdict.status === "passed") {
    if (verdict.reason === "checkmate") return { text: `Done! Mate in ${movesWord(count)}.`, tone: "success" };
    if (verdict.reason === "promoted") return { text: `Done! Pawn promoted in ${movesWord(count)}.`, tone: "success" };
    return { text: "Done! Draw held.", tone: "success" };
  }
  if (verdict.reason === "player_mated") return { text: "The computer won. Start again.", tone: "warn" };
  return { text: "The computer escaped. Start again.", tone: "warn" };
}

/** BR3.3/BR4.2: what to show when a play request is refused. */
export function errorText(status, detail) {
  if (status === 429) return TOO_FAST;
  if (status === 503) return typeof detail === "string" && detail ? detail : UNAVAILABLE;
  if (typeof detail === "string" && detail) return detail;
  return status === 0 ? NETWORK_MESSAGE : SERVER_MESSAGE;
}

// --- attempt storage (session storage, BR4.2) ----------------------------------

function isUciList(list) {
  return Array.isArray(list) && list.length <= MAX_PLIES && list.every((uci) => typeof uci === "string" && UCI_PATTERN.test(uci));
}

export function isAttempt(value) {
  return Boolean(value) && typeof value === "object" && POSITION_ID.test(value.positionId || "")
    && isUciList(value.moves) && typeof value.fen === "string" && isUciList(value.legalMoves)
    && STATUSES.includes(value.status) && Number.isInteger(value.playerMoves);
}

export function saveAttempt(storage, attempt) {
  if (!storage || !isAttempt(attempt)) return false;
  try {
    storage.setItem(ATTEMPT_KEY, JSON.stringify(attempt));
    return true;
  } catch (error) {
    console.error(`JustChess: the endgame attempt could not be saved (${error && error.message})`);
    return false;
  }
}

/** The saved attempt for ``positionId``, or null (nothing saved, another position, unreadable). */
export function loadAttempt(storage, positionId) {
  if (!storage) return null;
  try {
    const text = storage.getItem(ATTEMPT_KEY);
    if (text == null) return null;
    const attempt = JSON.parse(text);
    return isAttempt(attempt) && attempt.positionId === positionId ? attempt : null;
  } catch (error) {
    console.error(`JustChess: the endgame attempt could not be read (${error && error.message})`);
    return null;
  }
}

export function clearAttempt(storage) {
  if (!storage) return;
  try {
    storage.removeItem(ATTEMPT_KEY);
  } catch (error) {
    console.error(`JustChess: the endgame attempt could not be cleared (${error && error.message})`);
  }
}

/** The attempt after a play answer: the player's move, the defender's reply (if any) and the verdict. */
export function nextAttempt(attempt, uci, answer) {
  const moves = [...attempt.moves, uci];
  if (answer.reply && typeof answer.reply.uci === "string") moves.push(answer.reply.uci);
  return {
    ...attempt,
    moves,
    fen: answer.fen,
    legalMoves: Array.isArray(answer.legalMoves) ? [...answer.legalMoves] : [],
    check: Boolean(answer.check),
    lastMove: answer.reply ? answer.reply.uci : uci,
    status: answer.status,
    reason: answer.reason || null,
    playerMoves: answer.playerMoves,
    movesLeft: Number.isInteger(answer.movesLeft) ? answer.movesLeft : null,
  };
}

/** A fresh attempt at the start position of a loaded position. */
export function freshAttempt(position) {
  return {
    positionId: position.id,
    moves: [],
    fen: position.fen,
    legalMoves: [...position.legalMoves],
    check: Boolean(position.check),
    lastMove: null,
    status: "playing",
    reason: null,
    playerMoves: 0,
    movesLeft: position.goal === "draw" ? position.holdMoves : null,
  };
}

// --- HTTP client -----------------------------------------------------------------

async function readJson(response) {
  const type = response.headers && typeof response.headers.get === "function" ? response.headers.get("content-type") || "" : "";
  if (!type.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

const isList = (body) => Boolean(body) && typeof body.installed === "boolean" && typeof body.available === "boolean"
  && Array.isArray(body.categories);
const isDetail = (body) => Boolean(body) && POSITION_ID.test(body.id || "") && typeof body.fen === "string"
  && Array.isArray(body.legalMoves) && ["white", "black"].includes(body.side);
const isVerdict = (body) => Boolean(body) && STATUSES.includes(body.status) && typeof body.fen === "string"
  && Array.isArray(body.legalMoves) && Number.isInteger(body.playerMoves);

export function createEndgamesApi(fetchImpl = (...args) => globalThis.fetch(...args)) {
  if (typeof fetchImpl !== "function") throw new TypeError("createEndgamesApi needs a fetch function");

  async function request(method, path, { body, signal, accept }) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let response;
    try {
      response = await fetchImpl(path, {
        method, headers, signal, credentials: "same-origin", body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (error) {
      if (error && error.name === "AbortError") return { ok: false, status: 0, aborted: true, message: "" };
      console.error(`JustChess: ${method} ${path} could not reach the server (${error && error.name})`);
      return { ok: false, status: 0, message: NETWORK_MESSAGE };
    }
    const data = await readJson(response);
    if (response.ok) {
      if (data === null || !accept(data)) {
        console.error(`JustChess: ${method} ${path} answered with an unexpected body`);
        return { ok: false, status: response.status, message: SERVER_MESSAGE };
      }
      return { ok: true, status: response.status, data };
    }
    const detail = data && typeof data.detail === "string" ? data.detail : "";
    return { ok: false, status: response.status, message: errorText(response.status, detail) };
  }

  const unknown = () => Promise.resolve({ ok: false, status: 404, message: UNKNOWN_POSITION });

  return {
    list({ signal } = {}) {
      return request("GET", "/api/endgames", { signal, accept: isList });
    },
    get(id, { signal } = {}) {
      if (typeof id !== "string" || !POSITION_ID.test(id)) return unknown();
      return request("GET", `/api/endgames/${id}`, { signal, accept: isDetail });
    },
    play(id, moves, { signal } = {}) {
      if (typeof id !== "string" || !POSITION_ID.test(id)) return unknown();
      if (!isUciList(moves) || moves.length % 2 === 0) return Promise.resolve({ ok: false, status: 400, message: "Illegal move" });
      return request("POST", `/api/endgames/${id}/play`, { body: { moves }, signal, accept: isVerdict });
    },
  };
}

// --- the hub's Endgames tab (BR4.1) ------------------------------------------------

function safeDone(progress, id) {
  try {
    return Boolean(progress) && progress.isDone(PROGRESS_GROUP, id);
  } catch {
    return false;
  }
}

/**
 * The tab loader: ``context`` is what the hub passes (``progress``, ``signal``)
 * plus its extra context (``endgamesApi``, ``onOpenEndgame``). Rows follow the
 * category order; each says its category and goal, and Play opens the position.
 */
export async function endgamesLoader({ endgamesApi = createEndgamesApi(), progress = null, signal, onOpenEndgame = () => {} } = {}) {
  const answer = await endgamesApi.list({ signal });
  if (!answer.ok) return { error: answer.message, aborted: answer.aborted, rows: [], solved: 0, total: 0 };
  const { installed, available, reason, categories } = answer.data;
  if (!installed || categories.length === 0) return { rows: [], solved: 0, total: 0, note: NOT_INSTALLED };
  const rows = [];
  for (const category of categories) {
    for (const position of category.positions || []) {
      const done = safeDone(progress, position.id);
      rows.push({
        id: position.id,
        title: position.title,
        subtitle: [category.label, GOAL_SHORT[position.goal], available ? null : NEEDS_STOCKFISH].filter(Boolean).join(" · "),
        done,
        action: "Play",
        disabled: !available,
        onAction: () => onOpenEndgame(position.id),
      });
    }
  }
  const solved = rows.filter((row) => row.done).length;
  const result = { rows, solved, total: rows.length };
  if (!available) result.note = `${NEEDS_STOCKFISH}: ${reason || UNAVAILABLE}`;
  return result;
}

export const ENDGAMES_TAB = Object.freeze({ id: "endgames", label: "Endgames", order: 30, load: endgamesLoader });
