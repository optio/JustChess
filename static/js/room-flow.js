/**
 * Room flow helpers (U3, extracted in U6 for the U3 review finding "failure
 * paths untested"). app.js calls these and dispatches what they return; they
 * take the api, the seat store and the live client as arguments, so
 * tests/js/room-flow.test.mjs drives every failure path with fakes.
 *
 *   enterRoom({ api, seats, code, created?, continueToken?, isCurrent?, notify? })
 *     W3, BR1.4, BR1.5: redeem a "#continue=" token, then take the seat (the one
 *     just created, or join with the stored token). Resolves with one of:
 *       { kind: "stale" }                       the room was left meanwhile
 *       { kind: "notFound", message? }          404 (or 400 for a malformed code)
 *       { kind: "failed", message }             network or server error
 *       { kind: "full", snapshot }              409: the stored seat is removed; watch
 *       { kind: "joined", seat, notices }       notices: staleSeat, storageBlocked
 *     A refused continue token (403 or any status but 404 and 0) calls
 *     notify({ key: "continueExpired" }) at once and the join goes on.
 *
 *     P2 U3 (W2): with `requests` (the session request store), a visitor with no
 *     stored seat but a stored request token goes straight to
 *       { kind: "request", requestToken }      the joiner's waiting screen (no new request)
 *     and a join to a pass-along room resolves with that same kind after the
 *     202 (the token is stored in session storage first; the 202 also adds
 *     `colour`, the side the joiner would take over), or with
 *       { kind: "refused", reason }            "busy" | "declined_recently" | "too_many"
 *
 *   settleRequest({ seats, requests, code, requestToken, status }) -> seat | null
 *     W4: a final answer drops the session copy; "accepted" stores the request
 *     token as seat B and returns { token, slot: "B" } to open the game with.
 *
 *   actionAnswer(answer, { seats, live, code }) -> { snapshot, seatLost, notFound, flash }
 *     The answer to a seat action or a move (W5, BR3.3): apply an attached
 *     snapshot (409); a 403 "This isn't your seat" forgets the seat (storage
 *     and live token) and watches; a 404 means the room is gone; anything else
 *     is the server's message for the flash line.
 *
 *   submitMove({ api, code, token, uci, snapshot, check?, isCurrent? })
 *     The move check (hooks.beforeMove through runBeforeMove, which fails
 *     closed when the hook throws) and then POST /moves. Resolves with:
 *       { kind: "refused", message, snapshot? } not seated, or the check said no;
 *                                               snapshot only when the U4 check got a 409
 *       { kind: "stale" }
 *       { kind: "answer", answer }              hand it to actionAnswer
 *
 *   applyRefusal(result, { board, flash, applySnapshot })
 *     U4: what app.js does with a "refused" result: board.reject(), apply the
 *     snapshot when there is one, and flash the message when there is one.
 *
 *   playComputer({ api, seats, level, colour })   P2 U4 BR3.5, W1: "Play" in the lobby panel.
 *     The saved computer seat for the level is reopened: its game is resumed
 *     when unfinished (the colour choice is ignored), or a rematch in the chosen
 *     colour starts when it is finished. A saved seat the server answers 404 for
 *     is dropped. Without one, a computer room is created and its seat saved
 *     with kind "computer" and the level. Resolves with:
 *       { kind: "open", code, plan: "reopen" | "rematch" | "create", created? }   created: the create answer
 *       { kind: "failed", message }
 */

import { NETWORK_MESSAGE } from "./api.js";
import { findComputerSeat } from "./computer.js";
import { runBeforeMove } from "./hooks.js";
import { refusalKind } from "./pass-along.js";

export const SEAT_REFUSED = "This isn't your seat";

function storeSeat(seats, code, seat) {
  try {
    seats.set(code, seat);
  } catch (error) {
    console.error("JustChess: the seat answer was not valid", error);
  }
}

async function redeem({ api, seats, code, continueToken, isCurrent, notify }) {
  const redeemed = await api.redeemContinue(code, continueToken);
  if (!isCurrent()) return { kind: "stale" };
  if (redeemed.ok) {
    storeSeat(seats, code, { token: redeemed.data.token, slot: redeemed.data.slot });
    return null;
  }
  if (redeemed.status === 404) return { kind: "notFound" };
  if (redeemed.status === 0) return { kind: "failed", message: NETWORK_MESSAGE };
  notify({ key: "continueExpired" });
  return null;
}

async function join({ api, seats, code, isCurrent, requests }) {
  const stored = seats.get(code);
  const pendingToken = !stored && requests ? requests.get(code) : null;
  if (pendingToken) return { kind: "request", requestToken: pendingToken }; // a reload of the joiner's waiting screen
  const joined = await api.join(code, stored ? stored.token : null);
  if (!isCurrent()) return { kind: "stale" };
  if (joined.ok && joined.data && joined.data.requestPending) {
    const requestToken = joined.data.requestToken;
    if (requests) {
      try {
        requests.set(code, requestToken);
      } catch (error) {
        console.error("JustChess: the join request answer was not valid", error && error.name);
        return { kind: "failed", message: joined.message || "Something went wrong. Try again." };
      }
    }
    const colour = joined.data.colour === "white" || joined.data.colour === "black" ? joined.data.colour : null;
    return { kind: "request", requestToken, colour };
  }
  const refusal = refusalKind(joined);
  if (refusal) {
    if (stored) seats.remove(code);
    return { kind: "refused", reason: refusal };
  }
  if (joined.ok) {
    const seat = { token: joined.data.token, slot: joined.data.slot };
    const stale = Boolean(stored) && (stored.token !== seat.token || stored.slot !== seat.slot);
    return { kind: "seat", seat, notices: stale ? [{ key: "staleSeat", colour: joined.data.colour }] : [] };
  }
  if (joined.status === 409) {
    if (stored) seats.remove(code);
    return { kind: "full", snapshot: joined.snapshot || null };
  }
  if (joined.status === 404) {
    seats.remove(code);
    return { kind: "notFound" };
  }
  if (joined.status === 400) return { kind: "notFound", message: joined.message };
  return { kind: "failed", message: joined.message };
}

export async function enterRoom({ api, seats, code, created = null, continueToken = null, isCurrent = () => true, notify = () => {}, requests = null }) {
  if (continueToken) {
    const stop = await redeem({ api, seats, code, continueToken, isCurrent, notify });
    if (stop) return stop;
  }
  let seat = created ? { token: created.token, slot: created.slot } : null;
  let notices = [];
  if (!seat) {
    const joined = await join({ api, seats, code, isCurrent, requests });
    if (joined.kind !== "seat") return joined;
    ({ seat, notices } = joined);
  }
  storeSeat(seats, code, seat);
  if (!seats.persistent) notices = [...notices, { key: "storageBlocked" }];
  return { kind: "joined", seat, notices };
}

/**
 * P2 U3 W4: the joiner's request reached a final answer. Accepted: the request
 * token becomes this device's seat B token. Any answer drops the session copy.
 * Returns the seat to open the game with, or null.
 */
export function settleRequest({ seats, requests, code, requestToken, status }) {
  if (requests) requests.remove(code);
  if (status !== "accepted") return null;
  const seat = { token: requestToken, slot: "B" };
  storeSeat(seats, code, seat);
  return seat;
}

export function actionAnswer(answer, { seats, live = null, code = null } = {}) {
  const result = { snapshot: null, seatLost: false, notFound: false, flash: null };
  if (answer.ok) {
    result.snapshot = answer.data;
    return result;
  }
  if (answer.snapshot) result.snapshot = answer.snapshot;
  if (answer.status === 403 && answer.message === SEAT_REFUSED) {
    if (code) seats.remove(code);
    if (live) live.setToken(null);
    result.seatLost = true;
  } else if (answer.status === 404) {
    result.notFound = true;
  } else {
    result.flash = answer.message || null;
  }
  return result;
}

/**
 * A refused move (U4's widened hook result): tell the board to refuse (the
 * piece slides back), apply a newer snapshot through the caller's 409 path,
 * and show the message on the flash line.
 */
export function applyRefusal(result, { board, flash = () => {}, applySnapshot = () => {} }) {
  board.reject();
  if (result.snapshot) applySnapshot(result.snapshot);
  if (result.message) flash(result.message);
}

async function reopenComputerSeat({ api, seats, saved, colour }) {
  const read = await api.state(saved.code, saved.token);
  if (read.status === 404) {
    seats.remove(saved.code, saved.token);
    return null; // the room is gone (30 days idle): create a new one
  }
  if (!read.ok) return { kind: "failed", message: read.message || NETWORK_MESSAGE };
  if (read.data.status !== "finished" || read.data.slot !== "A") return { kind: "open", code: saved.code, plan: "reopen" };
  const again = await api.rematch(saved.code, saved.token, colour);
  if (!again.ok && again.status !== 409) return { kind: "failed", message: again.message || NETWORK_MESSAGE };
  return { kind: "open", code: saved.code, plan: "rematch" }; // 409: another tab already started it
}

export async function playComputer({ api, seats, level, colour }) {
  const saved = findComputerSeat(seats, level);
  if (saved) {
    const reopened = await reopenComputerSeat({ api, seats, saved, colour });
    if (reopened) return reopened;
  }
  const created = await api.createComputerRoom(level, colour);
  if (!created.ok) return { kind: "failed", message: created.message || NETWORK_MESSAGE };
  const { code, token, slot } = created.data;
  try {
    seats.set(code, { token, slot, kind: "computer", computerLevel: level });
  } catch (error) {
    console.error("JustChess: the computer room answer was not valid", error && error.name);
    return { kind: "failed", message: "Something went wrong. Try again." };
  }
  return { kind: "open", code, plan: "create", created: created.data };
}

export async function submitMove({ api, code, token, uci, snapshot, check = runBeforeMove, isCurrent = () => true }) {
  if (!code || !token || !snapshot) return { kind: "refused", message: null };
  const verdict = await check(uci, snapshot);
  if (!isCurrent()) return { kind: "stale" };
  if (!verdict.allowed) {
    const refused = { kind: "refused", message: verdict.message || null };
    if (verdict.snapshot) refused.snapshot = verdict.snapshot;
    return refused;
  }
  const answer = await api.move(code, token, uci, snapshot.version);
  if (!isCurrent()) return { kind: "stale" };
  return { kind: "answer", answer };
}
