// Tests for the HTTP client static/js/api.js (BR1.3, BR3.3; U1 routes).
import { test } from "node:test";
import assert from "node:assert/strict";

import { NETWORK_MESSAGE, createApi, normalizeCode } from "../../static/js/api.js";

const TOKEN = "seat-token-abcdefghijklmnop";

function response(status, body, contentType = "application/json") {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => (name.toLowerCase() === "content-type" ? contentType : null) },
    json: async () => body,
  };
}

/** A fetch fake that records every call and answers from a queue (or a function). */
function fakeFetch(answer) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init, body: init.body === undefined ? undefined : JSON.parse(init.body) });
    return typeof answer === "function" ? answer(url, init) : answer;
  };
  return { fetchImpl, calls };
}

function quietly(fn) {
  const original = console.error;
  console.error = () => {};
  return Promise.resolve(fn()).finally(() => {
    console.error = original;
  });
}

test("200: create, join and move map to { ok, data } with the right routes and bodies", async () => {
  const { fetchImpl, calls } = fakeFetch(response(200, { code: "ABC123", token: TOKEN, slot: "A", colour: "white" }));
  const api = createApi(fetchImpl);
  const created = await api.createRoom();
  assert.deepEqual(created, { ok: true, status: 200, data: { code: "ABC123", token: TOKEN, slot: "A", colour: "white" } });
  await api.join("abc123", TOKEN);
  await api.join("ABC123");
  await api.move("ABC123", TOKEN, "e2e4", 1);
  await api.claimDraw("ABC123", TOKEN);
  await api.rematch("ABC123", TOKEN);
  assert.deepEqual(calls.map((c) => `${c.init.method} ${c.url}`), [
    "POST /api/rooms",
    "POST /api/rooms/ABC123/join",
    "POST /api/rooms/ABC123/join",
    "POST /api/rooms/ABC123/moves",
    "POST /api/rooms/ABC123/claim-draw",
    "POST /api/rooms/ABC123/rematch",
  ]);
  assert.deepEqual(calls[1].body, { token: TOKEN });
  assert.deepEqual(calls[2].body, {}, "a join with no stored seat sends an empty body");
  assert.deepEqual(calls[3].body, { token: TOKEN, uci: "e2e4", version: 1 });
});

test("409 carries the attached snapshot and the server's message", async () => {
  const snapshot = { game: 1, version: 7, status: "playing" };
  const { fetchImpl } = fakeFetch(response(409, { detail: "The board changed, here is the latest position", snapshot }));
  const result = await createApi(fetchImpl).move("ABC123", TOKEN, "e2e4", 6);
  assert.deepEqual(result, { ok: false, status: 409, message: "The board changed, here is the latest position", snapshot });
  const full = await createApi(fakeFetch(response(409, { detail: "This game already has two players" })).fetchImpl).join("ABC123");
  assert.deepEqual([full.status, full.snapshot], [409, undefined]);
});

test("400 and 403 give the server's message; validation errors and 500s get plain sentences", async () => {
  const illegal = await createApi(fakeFetch(response(400, { detail: "Illegal move" })).fetchImpl).move("ABC123", TOKEN, "e2e5", 1);
  assert.deepEqual(illegal, { ok: false, status: 400, message: "Illegal move" });
  const notYours = await createApi(fakeFetch(response(403, { detail: "This isn't your seat" })).fetchImpl).claimWin("ABC123", TOKEN);
  assert.equal(notYours.message, "This isn't your seat");
  const invalid = await createApi(fakeFetch(response(422, { detail: [{ loc: ["body"], msg: "x" }] })).fetchImpl).rematch("ABC123", TOKEN);
  assert.equal(invalid.message, "That request wasn't valid.");
  const broken = await createApi(fakeFetch(response(500, "oops", "text/plain")).fetchImpl).createRoom();
  assert.deepEqual(broken, { ok: false, status: 500, message: "Something went wrong. Try again." });
});

test("a network failure resolves with status 0 and the reach-the-server message", async () => {
  const api = createApi(async () => {
    throw new TypeError("Failed to fetch");
  });
  const result = await quietly(() => api.state("ABC123", TOKEN));
  assert.deepEqual(result, { ok: false, status: 0, message: NETWORK_MESSAGE });
  assert.equal(NETWORK_MESSAGE, "Couldn't reach the server. Try again.");
});

test("state reads send the seat token in the X-Seat-Token header, and only when there is one", async () => {
  const { fetchImpl, calls } = fakeFetch(response(200, { game: 1, version: 1 }));
  const api = createApi(fetchImpl);
  await api.state("ABC123", TOKEN);
  await api.state("ABC123", null);
  assert.equal(calls[0].init.method, "GET");
  assert.equal(calls[0].url, "/api/rooms/ABC123");
  assert.equal(calls[0].init.headers["X-Seat-Token"], TOKEN);
  assert.equal(calls[0].init.body, undefined);
  assert.equal("X-Seat-Token" in calls[1].init.headers, false, "a watcher sends no header");
});

test("no token ever appears in a URL, and bad codes or moves never reach the network", async () => {
  const { fetchImpl, calls } = fakeFetch(response(200, { continueToken: "c".repeat(40) }));
  const api = createApi(fetchImpl, { base: "" });
  await api.join("ABC123", TOKEN);
  await api.state("ABC123", TOKEN);
  await api.move("ABC123", TOKEN, "e7e8q", 3);
  await api.continueLink("ABC123", TOKEN);
  await api.redeemContinue("ABC123", "c".repeat(40));
  for (const call of calls) {
    assert.doesNotMatch(call.url, new RegExp(TOKEN), `${call.url} carries the seat token`);
    assert.doesNotMatch(call.url, /c{40}|token=|\?/, `${call.url} carries a token or a query`);
  }
  assert.deepEqual(calls.at(-1).body, { continueToken: "c".repeat(40) });

  const before = calls.length;
  assert.deepEqual(await api.join("BAD!"), { ok: false, status: 400, message: "Room code must be 6 letters or digits" });
  assert.equal((await api.move("ABC123", TOKEN, "e2e4; DROP", 1)).status, 400);
  assert.equal((await api.rematch("ABC123", "")).status, 403, "an action without a token is refused locally");
  assert.equal(calls.length, before, "nothing invalid was sent");
  assert.equal(normalizeCode(" k7q2px "), "K7Q2PX");
  assert.equal(normalizeCode("K7Q2P"), null);
  assert.throws(() => api.move("ABC123", TOKEN, "e2e4", -1), TypeError);
});

test("U4 checkMove posts to /check-move with the move body and passes the abort signal; an abort is a warning", async () => {
  const { fetchImpl, calls } = fakeFetch(response(200, { warning: null, san: "e4", version: 3 }));
  const api = createApi(fetchImpl);
  const controller = new AbortController();
  const checked = await api.checkMove("abc123", TOKEN, "e2e4", 3, { signal: controller.signal });
  assert.deepEqual(checked, { ok: true, status: 200, data: { warning: null, san: "e4", version: 3 } });
  assert.equal(calls[0].url, "/api/rooms/ABC123/check-move");
  assert.deepEqual(calls[0].body, { token: TOKEN, uci: "e2e4", version: 3 });
  assert.equal(calls[0].init.signal, controller.signal);
  assert.equal((await api.checkMove("ABC123", TOKEN, "e2", 3)).status, 400, "a malformed move is refused locally");
  assert.equal(calls.length, 1);

  const warned = [];
  const original = console.warn;
  console.warn = (message) => warned.push(message);
  try {
    const aborted = createApi(async () => { throw Object.assign(new Error("aborted"), { name: "AbortError" }); });
    assert.deepEqual(await aborted.checkMove("ABC123", TOKEN, "e2e4", 3), { ok: false, status: 0, message: NETWORK_MESSAGE });
  } finally {
    console.warn = original;
  }
  assert.match(warned[0], /check-move was aborted/);
});
