/**
 * JustChess HTTP client (U3) for U1's /api/rooms routes.
 *
 *   const api = createApi(fetchImpl = globalThis.fetch, { base = "" })
 *
 * Every call resolves, never rejects for HTTP or network errors:
 *   { ok: true, status, data }
 *   { ok: false, status, message, snapshot? }   status 0 = the server could not be reached
 *
 * Seat tokens travel only in request bodies (actions) and in the
 * X-Seat-Token header (state reads), never in a URL (BR1.3, U1 review). Room
 * codes are uppercased and validated before any request is made, so a bad
 * code never reaches the network. Tokens are never logged.
 *
 * U4 adds checkMove(code, token, uci, version, { signal }) for
 * POST /api/rooms/{code}/check-move. An aborted request (the caller's own
 * timeout) resolves as status 0 and is logged with console.warn, not as an error.
 *
 * P2 U2 adds fetchSummaries(seats) for POST /api/rooms/summaries: the seats'
 * codes and tokens go in the body only ({ seats: [{ code, token }] }) and the
 * answer is { ok, data: { rooms: [RoomSummary] } } or a failure. A list with a
 * malformed code or token is refused locally (status 400) and never sent; the
 * seat store's validSeats() and your-games.js seatsToSend() keep it clean.
 *
 * P2 U3 adds setMode(code, token, mode), answerRequest(code, token, accept) and
 * requestStatus(code, requestToken). A failure whose body names an ``error``
 * (busy, declined_recently, too_many) carries it as failure.error. A join to a
 * pass-along room answers 202 { requestPending, requestToken, expiresAt, expiresIn }.
 *
 * P2 U4 adds engine() (GET /api/engine), createComputerRoom(level, colour),
 * computerMove(code, token), takeback(code, token, version), hint(code, token,
 * version) and resign(code, token, version); rematch(code, token, colour?) sends
 * the colour only when one is given (computer rooms). A level or colour outside
 * the known lists is refused locally (status 400) and never sent.
 */

const COMPUTER_LEVELS = ["beginner", "casual", "club", "strong", "maximum"];
const COMPUTER_COLOURS = ["white", "black", "random"];

export const NETWORK_MESSAGE = "Couldn't reach the server. Try again.";
export const SERVER_MESSAGE = "Something went wrong. Try again.";
export const INVALID_CODE_MESSAGE = "Room code must be 6 letters or digits";
export const CODE_PATTERN = /^[A-Z0-9]{6}$/;
const UCI_PATTERN = /^[a-h][1-8][a-h][1-8][qrbn]?$/;
const TOKEN_MAX = 256;
const SUMMARY_TOKEN_MAX = 128; // the summaries route's token limit (BR2.1)

/** Uppercase and trim a typed code; returns the code or null when it is not 6 letters or digits. */
export function normalizeCode(raw) {
  const code = String(raw ?? "").trim().toUpperCase();
  return CODE_PATTERN.test(code) ? code : null;
}

function isToken(value) {
  return typeof value === "string" && value.length > 0 && value.length <= TOKEN_MAX;
}

function messageFrom(status, body) {
  if (body && typeof body.detail === "string" && body.detail) return body.detail;
  if (status === 422 || (body && Array.isArray(body.detail))) return "That request wasn't valid.";
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

export function createApi(fetchImpl = globalThis.fetch, { base = "", player = null } = {}) {
  if (typeof fetchImpl !== "function") throw new TypeError("createApi needs a fetch function");

  async function request(method, path, { body, token, signal } = {}) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (token) headers["X-Seat-Token"] = token;
    const init = {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
      cache: "no-store",
    };
    if (signal) init.signal = signal;
    let response;
    try {
      response = await fetchImpl(base + path, init);
    } catch (error) {
      const name = error && error.name;
      // An abort is the caller's own timeout (U4 check-move), not a broken connection.
      if (name === "AbortError") console.warn(`JustChess: ${method} ${path} was aborted`);
      else console.error(`JustChess: ${method} ${path} could not reach the server (${name})`);
      return { ok: false, status: 0, message: NETWORK_MESSAGE };
    }
    const data = await readJson(response);
    if (response.ok) {
      if (data === null) return { ok: false, status: response.status, message: SERVER_MESSAGE };
      if (player && data.code && data.token) await player.attach(data.code, data.token);
      else if (player && body?.token && /^\/api\/rooms\/[A-Z0-9]{6}\//.test(path)) {
        await player.attach(path.split("/")[3], body.token);
      }
      return { ok: true, status: response.status, data };
    }
    const failure = { ok: false, status: response.status, message: messageFrom(response.status, data) };
    if (data && data.snapshot && typeof data.snapshot === "object") failure.snapshot = data.snapshot;
    if (data && typeof data.error === "string") failure.error = data.error; // P2 U3: busy, declined_recently, too_many
    return failure;
  }

  function invalidCode() {
    return Promise.resolve({ ok: false, status: 400, message: INVALID_CODE_MESSAGE });
  }

  function missingToken() {
    return Promise.resolve({ ok: false, status: 403, message: "This isn't your seat" });
  }

  function room(code) {
    const clean = normalizeCode(code);
    return clean ? `/api/rooms/${clean}` : null;
  }

  function seatAction(code, token, suffix, extra = {}, { signal } = {}) {
    const path = room(code);
    if (!path) return invalidCode();
    if (!isToken(token)) return missingToken();
    return request("POST", `${path}/${suffix}`, { body: { token, ...extra }, signal });
  }

  function moveBody(uci, version) {
    if (typeof uci !== "string" || !UCI_PATTERN.test(uci)) return null;
    if (!Number.isInteger(version) || version < 0) throw new TypeError("a move needs the snapshot's version");
    return { uci, version };
  }

  return {
    createRoom: () => request("POST", "/api/rooms"),
    join(code, token) {
      const path = room(code);
      if (!path) return invalidCode();
      return request("POST", `${path}/join`, { body: isToken(token) ? { token } : {} });
    },
    state(code, token) {
      const path = room(code);
      if (!path) return invalidCode();
      return request("GET", path, { token: isToken(token) ? token : undefined });
    },
    move(code, token, uci, version) {
      const body = moveBody(uci, version);
      if (!body) return Promise.resolve({ ok: false, status: 400, message: "Illegal move" });
      return seatAction(code, token, "moves", body);
    },
    /** U4: POST /api/rooms/{code}/check-move; resolves { ok, data: { warning, san, version } } or a failure. */
    checkMove(code, token, uci, version, { signal } = {}) {
      const body = moveBody(uci, version);
      if (!body) return Promise.resolve({ ok: false, status: 400, message: "Illegal move" });
      return seatAction(code, token, "check-move", body, { signal });
    },
    claimDraw: (code, token) => seatAction(code, token, "claim-draw"),
    claimWin: (code, token) => seatAction(code, token, "claim-win"),
    rematch: (code, token, colour) => seatAction(code, token, "rematch", COMPUTER_COLOURS.includes(colour) ? { colour } : {}),
    /** P2 U4: { available, path_source, version, reason }. */
    engine: () => request("GET", "/api/engine"),
    /** P2 U4: POST /api/rooms { kind: "computer", level, colour } -> { code, token, slot, colour, computer }. */
    createComputerRoom(level, colour) {
      if (!COMPUTER_LEVELS.includes(level) || !COMPUTER_COLOURS.includes(colour)) {
        return Promise.resolve({ ok: false, status: 400, message: "Choose a level and a colour" });
      }
      return request("POST", "/api/rooms", { body: { kind: "computer", level, colour } });
    },
    /** P2 U4 BR5.4: ask for the computer's reply when it is due; resolves with the snapshot. */
    computerMove: (code, token) => seatAction(code, token, "computer-move"),
    takeback(code, token, version) {
      if (!Number.isInteger(version) || version < 0) throw new TypeError("a takeback needs the snapshot's version");
      return seatAction(code, token, "takeback", { version });
    },
    /** P2 U4 BR6.1: resolves { ok, data: { uci, from, to, san, version } } or a failure. */
    hint(code, token, version) {
      if (!Number.isInteger(version) || version < 0) throw new TypeError("a hint needs the snapshot's version");
      return seatAction(code, token, "hint", { version });
    },
    resign(code, token, version) {
      if (!Number.isInteger(version) || version < 0) throw new TypeError("resigning needs the snapshot's version");
      return seatAction(code, token, "resign", { version });
    },
    continueLink: (code, token) => seatAction(code, token, "continue-link"),
    /** P2 U3: seat A switches the room to "pass_along" or back to "waiting"; resolves with seat A's snapshot. */
    setMode: (code, token, mode) => seatAction(code, token, "mode", { mode }),
    /** P2 U3: seat A accepts (true) or declines (false) the pending join request; resolves with the snapshot. */
    answerRequest: (code, token, accept) => seatAction(code, token, "join-request/answer", { accept: Boolean(accept) }),
    /** P2 U3: the joiner's poll; the request token travels in the body only. Resolves { status, expiresAt? }. */
    requestStatus(code, requestToken) {
      const path = room(code);
      if (!path) return invalidCode();
      if (!isToken(requestToken)) return Promise.resolve({ ok: true, status: 200, data: { status: "unknown" } });
      return request("POST", `${path}/join-request/status`, { body: { requestToken } });
    },
    /** P2 U2: one batch request for the "Your games" list; tokens travel in the body only. */
    fetchSummaries(seats) {
      const list = Array.isArray(seats) ? seats : [];
      if (list.length === 0) return Promise.resolve({ ok: true, status: 200, data: { rooms: [] } });
      const valid = list.every((seat) => seat && CODE_PATTERN.test(seat.code) && isToken(seat.token) && seat.token.length <= SUMMARY_TOKEN_MAX);
      if (!valid) return Promise.resolve({ ok: false, status: 400, message: "Invalid summary request" });
      return request("POST", "/api/rooms/summaries", { body: { seats: list.map(({ code, token }) => ({ code, token })) } });
    },
    redeemContinue(code, continueToken) {
      const path = room(code);
      if (!path) return invalidCode();
      if (!isToken(continueToken)) return Promise.resolve({ ok: false, status: 403, message: "This continue link is no longer valid" });
      return request("POST", `${path}/continue`, { body: { continueToken } });
    },
  };
}
