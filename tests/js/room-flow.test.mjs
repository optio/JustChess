// Failure-path tests for the room flow app.js runs (static/js/room-flow.js), carried over from the
// U3 review ("failure paths untested"). The api, the seat storage and the live client are fakes.
import { test } from "node:test";
import assert from "node:assert/strict";

import { CHECK_FAILED, resetHooks, setHook } from "../../static/js/hooks.js";
import { actionAnswer, applyRefusal, enterRoom, SEAT_REFUSED, settleRequest, submitMove } from "../../static/js/room-flow.js";
import { createRequestStore, createSeatStore } from "../../static/js/seat-store.js";

const CODE = "K7Q2PX";
const OLD = { token: "old-seat-token-aaaaaaaa", slot: "A" };
const NEW = { token: "new-seat-token-bbbbbbbb", slot: "B" };
const SNAPSHOT = { code: CODE, game: 1, version: 4, status: "playing", slot: null };

function memoryStorage() {
  const map = new Map();
  return {
    map,
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
}

/** A fake api: each method answers from `answers` and records its call. */
function fakeApi(answers) {
  const calls = [];
  const api = {};
  for (const name of ["join", "redeemContinue", "move", "state"]) {
    api[name] = async (...args) => {
      calls.push([name, ...args]);
      const answer = answers[name];
      if (answer === undefined) throw new Error(`unexpected ${name} call`);
      return typeof answer === "function" ? answer(...args) : answer;
    };
  }
  return { api, calls };
}

function seatsWith(seat) {
  const seats = createSeatStore(memoryStorage());
  if (seat) seats.set(CODE, seat);
  return seats;
}

test("a stored seat that the server replaces gives the stale-seat notice and stores the new seat", async () => {
  const seats = seatsWith(OLD);
  const { api, calls } = fakeApi({ join: { ok: true, status: 200, data: { ...NEW, colour: "black" } } });
  const result = await enterRoom({ api, seats, code: CODE });
  assert.deepEqual(result, { kind: "joined", seat: NEW, notices: [{ key: "staleSeat", colour: "black" }] });
  assert.deepEqual(calls, [["join", CODE, OLD.token]], "the join sends the stored token");
  assert.deepEqual(seats.get(CODE), NEW);
  const blocked = await enterRoom({ api, seats: createSeatStore(null), code: CODE });
  assert.deepEqual(blocked.notices, [{ key: "storageBlocked" }], "no storage: the seat is kept for this tab and said so");
});

test("409 room full removes the stored seat and hands back the watcher snapshot", async () => {
  const seats = seatsWith(OLD);
  const { api } = fakeApi({ join: { ok: false, status: 409, message: "This game already has two players.", snapshot: SNAPSHOT } });
  assert.deepEqual(await enterRoom({ api, seats, code: CODE }), { kind: "full", snapshot: SNAPSHOT });
  assert.equal(seats.get(CODE), null);
  const gone = fakeApi({ join: { ok: false, status: 404, message: "No such room" } });
  assert.deepEqual(await enterRoom({ api: gone.api, seats: seatsWith(OLD), code: CODE }), { kind: "notFound" });
});

test("a continue fragment is redeemed first and the join uses the new seat", async () => {
  const seats = seatsWith(OLD);
  const notices = [];
  const { api, calls } = fakeApi({
    redeemContinue: { ok: true, status: 200, data: { ...NEW, colour: "black", code: CODE } },
    join: (code, token) => ({ ok: true, status: 200, data: { token, slot: "B", colour: "black" } }),
  });
  const result = await enterRoom({ api, seats, code: CODE, continueToken: "continue-token-cccccccc", notify: (n) => notices.push(n) });
  assert.deepEqual(calls.map((call) => call[0]), ["redeemContinue", "join"]);
  assert.equal(calls[1][2], NEW.token, "the join sends the redeemed token");
  assert.deepEqual(result, { kind: "joined", seat: NEW, notices: [] });
  assert.deepEqual(notices, []);
});

test("a refused continue token (403) says so at once and the join goes on with the stored seat", async () => {
  const seats = seatsWith(OLD);
  const notices = [];
  const { api, calls } = fakeApi({
    redeemContinue: { ok: false, status: 403, message: "This continue link is no longer valid" },
    join: { ok: true, status: 200, data: { ...OLD, colour: "white" } },
  });
  const result = await enterRoom({ api, seats, code: CODE, continueToken: "continue-token-cccccccc", notify: (n) => notices.push(n) });
  assert.deepEqual(notices, [{ key: "continueExpired" }]);
  assert.deepEqual(calls[1], ["join", CODE, OLD.token]);
  assert.deepEqual(result, { kind: "joined", seat: OLD, notices: [] });
  const offline = fakeApi({ redeemContinue: { ok: false, status: 0, message: "Couldn't reach the server. Try again." } });
  assert.equal((await enterRoom({ api: offline.api, seats, code: CODE, continueToken: "continue-token-cccccccc" })).kind, "failed");
  const stale = await enterRoom({ api, seats, code: CODE, continueToken: "continue-token-cccccccc", isCurrent: () => false });
  assert.deepEqual(stale, { kind: "stale" }, "an answer for a room already left is dropped");
});

test("a 403 'This isn't your seat' on an action forgets the seat and the socket token, so the screen watches", () => {
  const seats = seatsWith(OLD);
  const tokens = [];
  const live = { setToken: (token) => tokens.push(token) };
  const result = actionAnswer({ ok: false, status: 403, message: SEAT_REFUSED }, { seats, live, code: CODE });
  assert.deepEqual(result, { snapshot: null, seatLost: true, notFound: false, flash: null });
  assert.equal(seats.get(CODE), null);
  assert.deepEqual(tokens, [null]);
  const other = actionAnswer({ ok: false, status: 403, message: "Not your turn" }, { seats: seatsWith(OLD), live, code: CODE });
  assert.deepEqual([other.seatLost, other.flash], [false, "Not your turn"], "any other 403 is only shown");
});

test("a move refused with 400 shows the message; 409 also applies the attached snapshot", () => {
  const seats = seatsWith(OLD);
  assert.deepEqual(actionAnswer({ ok: false, status: 400, message: "Illegal move" }, { seats, code: CODE }),
    { snapshot: null, seatLost: false, notFound: false, flash: "Illegal move" });
  assert.deepEqual(actionAnswer({ ok: false, status: 409, message: "The board changed. Try again.", snapshot: SNAPSHOT }, { seats, code: CODE }),
    { snapshot: SNAPSHOT, seatLost: false, notFound: false, flash: "The board changed. Try again." });
  assert.deepEqual(actionAnswer({ ok: true, status: 200, data: SNAPSHOT }, { seats, code: CODE }).snapshot, SNAPSHOT);
  assert.equal(actionAnswer({ ok: false, status: 404, message: "gone" }, { seats, code: CODE }).notFound, true);
  assert.deepEqual(seats.get(CODE), OLD, "none of these forget the seat");
});

test("a beforeMove hook that throws fails closed: the move is never posted", async (t) => {
  t.mock.method(console, "error", () => {});
  setHook("beforeMove", () => { throw new Error("the blunder check crashed"); });
  try {
    const { api, calls } = fakeApi({ move: { ok: true, status: 200, data: SNAPSHOT } });
    const result = await submitMove({ api, code: CODE, token: OLD.token, uci: "e2e4", snapshot: SNAPSHOT });
    assert.deepEqual(result, { kind: "refused", message: CHECK_FAILED });
    assert.deepEqual(calls, [], "nothing reaches the server");
    resetHooks();
    const posted = await submitMove({ api, code: CODE, token: OLD.token, uci: "e2e4", snapshot: SNAPSHOT });
    assert.equal(posted.kind, "answer");
    assert.deepEqual(calls, [["move", CODE, OLD.token, "e2e4", 4]], "with the default hook the move is posted with the version");
    assert.deepEqual(await submitMove({ api, code: CODE, token: null, uci: "e2e4", snapshot: SNAPSHOT }), { kind: "refused", message: null });
  } finally {
    resetHooks();
  }
});

// --- P2 U3: join requests ----------------------------------------------------------

const REQUEST_TOKEN = "request-token-dddddddddddd";

test("a 202 keeps the request token in session storage, a reload polls it without asking again, and accepted makes it seat B", async () => {
  const session = memoryStorage();
  const requests = createRequestStore(session);
  const seats = seatsWith(null);
  const { api, calls } = fakeApi({
    join: { ok: true, status: 202, data: { requestPending: true, requestToken: REQUEST_TOKEN, expiresAt: 1, expiresIn: 600, colour: "black" } },
  });
  assert.deepEqual(await enterRoom({ api, seats, code: CODE, requests }), { kind: "request", requestToken: REQUEST_TOKEN, colour: "black" });
  assert.equal(session.map.get(`justchess.request.${CODE}`), REQUEST_TOKEN);
  assert.equal(seats.get(CODE), null, "no seat until the creator accepts");

  const reloaded = await enterRoom({ api, seats, code: CODE, requests: createRequestStore(session) });
  assert.deepEqual(reloaded, { kind: "request", requestToken: REQUEST_TOKEN });
  assert.equal(calls.length, 1, "the reload sent no second join");

  assert.deepEqual(settleRequest({ seats, requests, code: CODE, requestToken: REQUEST_TOKEN, status: "accepted" }),
    { token: REQUEST_TOKEN, slot: "B" });
  assert.deepEqual(seats.get(CODE), { token: REQUEST_TOKEN, slot: "B" });
  assert.equal(requests.get(CODE), null, "the session copy is dropped");
});

test("busy, declined_recently and too many requests come back as refusals; a declined request leaves no seat", async () => {
  for (const [answer, reason] of [
    [{ ok: false, status: 409, error: "busy", message: "Someone else is already asking to join. Try again in a few minutes." }, "busy"],
    [{ ok: false, status: 409, error: "declined_recently", message: "The creator declined. You can ask again later." }, "declined_recently"],
    [{ ok: false, status: 429, error: "too_many", message: "Too many requests. Try again shortly." }, "too_many"],
  ]) {
    const requests = createRequestStore(memoryStorage());
    const { api } = fakeApi({ join: answer });
    assert.deepEqual(await enterRoom({ api, seats: seatsWith(null), code: CODE, requests }), { kind: "refused", reason });
    assert.equal(requests.get(CODE), null);
  }
  const seats = seatsWith(null);
  const requests = createRequestStore(memoryStorage());
  requests.set(CODE, REQUEST_TOKEN);
  assert.equal(settleRequest({ seats, requests, code: CODE, requestToken: REQUEST_TOKEN, status: "declined" }), null);
  assert.deepEqual([seats.get(CODE), requests.get(CODE)], [null, null]);
});

// --- U4: the widened beforeMove result --------------------------------------------

/** A board, flash line and snapshot sink that record what app.js would do. */
function fakeScreen() {
  const log = [];
  return {
    log,
    board: { reject: () => log.push(["reject"]) },
    flash: (message) => log.push(["flash", message]),
    applySnapshot: (snapshot) => log.push(["snapshot", snapshot.version]),
  };
}

test("an object result with a snapshot refuses the move, applies the snapshot and shows the message", async () => {
  const newer = { ...SNAPSHOT, version: 5 };
  setHook("beforeMove", async () => ({ allow: false, message: "The board changed, here is the latest position", snapshot: newer }));
  try {
    const { api, calls } = fakeApi({ move: { ok: true, status: 200, data: SNAPSHOT } });
    const result = await submitMove({ api, code: CODE, token: OLD.token, uci: "e2e4", snapshot: SNAPSHOT });
    assert.deepEqual(result, { kind: "refused", message: "The board changed, here is the latest position", snapshot: newer });
    assert.deepEqual(calls, [], "nothing is posted");
    const screen = fakeScreen();
    applyRefusal(result, screen);
    assert.deepEqual(screen.log, [["reject"], ["snapshot", 5], ["flash", "The board changed, here is the latest position"]]);
  } finally {
    resetHooks();
  }
});

test("an object result with only a message shows it; a plain false stays a silent refusal", async () => {
  setHook("beforeMove", async () => ({ allow: false, message: "Not your turn" }));
  try {
    const { api } = fakeApi({});
    const result = await submitMove({ api, code: CODE, token: OLD.token, uci: "e2e4", snapshot: SNAPSHOT });
    assert.deepEqual(result, { kind: "refused", message: "Not your turn" });
    const screen = fakeScreen();
    applyRefusal(result, screen);
    assert.deepEqual(screen.log, [["reject"], ["flash", "Not your turn"]]);

    setHook("beforeMove", async () => false);
    const silent = await submitMove({ api, code: CODE, token: OLD.token, uci: "e2e4", snapshot: SNAPSHOT });
    assert.deepEqual(silent, { kind: "refused", message: null });
    const quiet = fakeScreen();
    applyRefusal(silent, quiet);
    assert.deepEqual(quiet.log, [["reject"]], "the board slides back, nothing else");
  } finally {
    resetHooks();
  }
});

test("a superseded dialog ({ allow: false }) or any value but true refuses without posting", async () => {
  try {
    for (const verdict of [{ allow: false }, { allow: true }, "yes", 1, undefined]) {
      setHook("beforeMove", async () => verdict);
      const { api, calls } = fakeApi({});
      const result = await submitMove({ api, code: CODE, token: OLD.token, uci: "e2e4", snapshot: SNAPSHOT });
      assert.deepEqual(result, { kind: "refused", message: null }, `verdict ${JSON.stringify(verdict)}`);
      assert.deepEqual(calls, []);
    }
  } finally {
    resetHooks();
  }
});
