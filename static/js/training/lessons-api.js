/**
 * Lessons HTTP client (U6) for GET /api/lessons, GET /api/lessons/{id} and
 * POST /api/position/move.
 *
 *   const api = createLessonsApi(fetchImpl = globalThis.fetch)
 *   api.list({ signal })                 -> [{ id, name, aliases, eco, side, moves }]
 *   api.get(id, { signal })              -> { id, name, ..., steps: [...] }
 *   api.positionMove(fen, uci, { signal }) -> { fen, san, legalMoves, check, outcome }
 *
 * Every call resolves with the same shape as U3's api.js, never rejects:
 *   { ok: true, status, data }
 *   { ok: false, status, message, aborted? }    status 0 = not reached or aborted
 *
 * The lesson id is checked against ^[a-z0-9][a-z0-9-]{0,47}$ and the move
 * against the UCI pattern before any request, so a bad value never reaches the
 * network. Answers are checked for the promised shape; anything else is the
 * generic server message. An aborted request resolves with aborted: true and
 * is never logged as an error.
 *
 * P2 U5 (trainer hub and puzzles), same answer shape:
 *   api.list({ signal, kind })              kind "opening" | "trap" | "defence" adds ?kind=
 *   api.themes({ signal })                  -> [{ theme, label, count }]
 *   api.puzzles(theme, { signal })          -> [{ id, rating }]
 *   api.puzzle(theme, id, { signal })       -> detail (no solution)
 *   api.checkPuzzle(theme, id, ply, uci, { signal }) -> { result, ... }
 *   api.puzzleHint(theme, id, ply, level, { signal }) -> { from } | { uci } | { line, fens }
 * The theme and the puzzle id are checked before any request.
 */

import { NETWORK_MESSAGE, SERVER_MESSAGE } from "../api.js";

export const LESSON_ID = /^[a-z0-9][a-z0-9-]{0,47}$/;
export const UCI_PATTERN = /^[a-h][1-8][a-h][1-8][qrbn]?$/;
export const NOT_FOUND = "Lesson not found";
export const ILLEGAL_MOVE = "Illegal move";
export const KINDS = Object.freeze(["opening", "trap", "defence"]);
export const THEMES = Object.freeze(["fork", "pin", "skewer", "discoveredAttack", "mateIn1", "mateIn2"]);
export const PUZZLE_ID = /^[0-9A-Za-z]{5}$/;
export const PUZZLE_NOT_FOUND = "Puzzle not found";
const HINT_LEVELS = ["piece", "move", "solution"];

export function isLessonId(value) {
  return typeof value === "string" && LESSON_ID.test(value);
}

function messageFrom(status, body) {
  if (body && typeof body.detail === "string" && body.detail) return body.detail;
  if (status === 422) return "That request wasn't valid.";
  return status >= 500 ? SERVER_MESSAGE : `The server refused the request (${status}).`;
}

async function readJson(response) {
  const type = response.headers && typeof response.headers.get === "function" ? response.headers.get("content-type") || "" : "";
  if (!type.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

const isSummary = (item) => Boolean(item) && isLessonId(item.id) && typeof item.name === "string"
  && (item.kind === undefined || KINDS.includes(item.kind));
const isThemeEntry = (item) => Boolean(item) && THEMES.includes(item.theme) && typeof item.label === "string"
  && Number.isInteger(item.count);
const isPuzzleRow = (item) => Boolean(item) && typeof item.id === "string" && PUZZLE_ID.test(item.id) && Number.isInteger(item.rating);
const isPuzzleDetail = (body) => Boolean(body) && typeof body.id === "string" && typeof body.afterSetup === "string"
  && Array.isArray(body.legalMoves);
const isCheck = (body) => Boolean(body) && ["correct", "wrong", "solved"].includes(body.result);
const isObject = (body) => Boolean(body) && typeof body === "object" && !Array.isArray(body);
const validPuzzleRef = (theme, id) => THEMES.includes(theme) && typeof id === "string" && PUZZLE_ID.test(id);
const isStep = (step) => Boolean(step) && typeof step.uci === "string" && typeof step.fenBefore === "string"
  && typeof step.fenAfter === "string" && Array.isArray(step.legalBefore);
const isLessonBody = (body) => Boolean(body) && typeof body.name === "string" && Array.isArray(body.steps)
  && body.steps.length > 0 && body.steps.every(isStep);
const isPosition = (body) => Boolean(body) && typeof body.fen === "string" && Array.isArray(body.legalMoves);

export function createLessonsApi(fetchImpl = (...args) => globalThis.fetch(...args)) {
  if (typeof fetchImpl !== "function") throw new TypeError("createLessonsApi needs a fetch function");

  async function request(method, path, { body, signal, accept } = {}) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let response;
    try {
      response = await fetchImpl(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: "same-origin",
        signal,
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
    return { ok: false, status: response.status, message: messageFrom(response.status, data) };
  }

  return {
    list({ signal, kind } = {}) {
      const path = KINDS.includes(kind) ? `/api/lessons?kind=${kind}` : "/api/lessons";
      return request("GET", path, { signal, accept: (data) => Array.isArray(data) && data.every(isSummary) });
    },
    themes({ signal } = {}) {
      return request("GET", "/api/puzzles", { signal, accept: (data) => Array.isArray(data) && data.every(isThemeEntry) });
    },
    puzzles(theme, { signal } = {}) {
      if (!THEMES.includes(theme)) return Promise.resolve({ ok: false, status: 404, message: PUZZLE_NOT_FOUND });
      return request("GET", `/api/puzzles/${theme}`, { signal, accept: (data) => Array.isArray(data) && data.every(isPuzzleRow) });
    },
    puzzle(theme, id, { signal } = {}) {
      if (!validPuzzleRef(theme, id)) return Promise.resolve({ ok: false, status: 404, message: PUZZLE_NOT_FOUND });
      return request("GET", `/api/puzzles/${theme}/${id}`, { signal, accept: isPuzzleDetail });
    },
    checkPuzzle(theme, id, ply, uci, { signal } = {}) {
      if (!validPuzzleRef(theme, id)) return Promise.resolve({ ok: false, status: 404, message: PUZZLE_NOT_FOUND });
      if (typeof uci !== "string" || !UCI_PATTERN.test(uci)) return Promise.resolve({ ok: false, status: 400, message: ILLEGAL_MOVE });
      return request("POST", `/api/puzzles/${theme}/${id}/check`, { body: { ply, uci }, signal, accept: isCheck });
    },
    puzzleHint(theme, id, ply, level, { signal } = {}) {
      if (!validPuzzleRef(theme, id)) return Promise.resolve({ ok: false, status: 404, message: PUZZLE_NOT_FOUND });
      if (!HINT_LEVELS.includes(level)) return Promise.resolve({ ok: false, status: 400, message: "Invalid hint level" });
      return request("POST", `/api/puzzles/${theme}/${id}/hint`, { body: { ply, level }, signal, accept: isObject });
    },
    get(id, { signal } = {}) {
      if (!isLessonId(id)) return Promise.resolve({ ok: false, status: 404, message: NOT_FOUND });
      return request("GET", `/api/lessons/${id}`, { signal, accept: isLessonBody });
    },
    positionMove(fen, uci, { signal } = {}) {
      if (typeof uci !== "string" || !UCI_PATTERN.test(uci) || typeof fen !== "string" || !fen) {
        return Promise.resolve({ ok: false, status: 400, message: ILLEGAL_MOVE });
      }
      return request("POST", "/api/position/move", { body: { fen, uci }, signal, accept: isPosition });
    },
  };
}
