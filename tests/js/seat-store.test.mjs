// Tests for the seat store static/js/seat-store.js (BR1.3, BR1.5).
import { test } from "node:test";
import assert from "node:assert/strict";

import { KEY_PREFIX, createSeatStore, parseContinueFragment, seatKey } from "../../static/js/seat-store.js";

const TOKEN = "seat-token-abcdefghijklmnop";

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
    key: (index) => [...data.keys()][index] ?? null,
    get length() {
      return data.size;
    },
  };
}

function steppingClock(start = 1_000) {
  let now = start;
  return () => (now += 1000);
}

function throwingStorage() {
  const fail = () => {
    throw Object.assign(new Error("blocked"), { name: "SecurityError" });
  };
  return { getItem: fail, setItem: fail, removeItem: fail };
}

function quietly(fn) {
  const original = console.error;
  const messages = [];
  console.error = (...args) => messages.push(args.join(" "));
  try {
    return { result: fn(), messages };
  } finally {
    console.error = original;
  }
}

test("storage that throws keeps the seat in memory for this tab and reports not persistent", () => {
  const seats = createSeatStore(throwingStorage());
  assert.equal(seats.persistent, true, "persistence is assumed until storage fails");
  const { messages } = quietly(() => seats.set("ABC123", { token: TOKEN, slot: "A" }));
  assert.equal(seats.persistent, false);
  assert.deepEqual(seats.get("ABC123"), { token: TOKEN, slot: "A" });
  assert.ok(messages.length === 1 && !messages[0].includes(TOKEN), "the failure is logged once, without the token");
  seats.remove("ABC123");
  assert.equal(seats.get("ABC123"), null);

  const none = createSeatStore(null);
  assert.equal(none.persistent, false, "no storage at all is not persistent");
  none.set("ABC123", { token: TOKEN, slot: "B" });
  assert.deepEqual(none.get("abc123"), { token: TOKEN, slot: "B" });
});

test("set, get and remove round-trip through storage", () => {
  const storage = memoryStorage();
  const seats = createSeatStore(storage, { now: () => 5000 });
  assert.equal(seats.get("ABC123"), null);
  seats.set("ABC123", { token: TOKEN, slot: "B", extra: "dropped" });
  assert.deepEqual(JSON.parse(storage.data.get("justchess.seat.ABC123")), { token: TOKEN, slot: "B", kind: "friend", savedAt: 5000 });
  assert.deepEqual(createSeatStore(storage).get("ABC123"), { token: TOKEN, slot: "B" }, "a reload reads the same seat");
  seats.remove("ABC123");
  assert.equal(storage.data.has("justchess.seat.ABC123"), false);
  assert.throws(() => seats.set("ABC123", { token: "", slot: "A" }), TypeError);
  assert.throws(() => seats.set("ABC123", { token: TOKEN, slot: "C" }), TypeError);
});

test("keys are justchess.seat.<CODE>; corrupt values read as no seat", () => {
  assert.equal(KEY_PREFIX, "justchess.seat.");
  assert.equal(seatKey("k7q2px"), "justchess.seat.K7Q2PX");
  assert.throws(() => seatKey("BAD!"), TypeError);
  const storage = memoryStorage({
    "justchess.seat.AAAAAA": "{not json",
    "justchess.seat.BBBBBB": JSON.stringify({ token: TOKEN, slot: "Z" }),
    "justchess.seat.CCCCCC": JSON.stringify({ token: TOKEN, slot: "A" }),
  });
  const seats = createSeatStore(storage);
  assert.equal(seats.get("AAAAAA"), null);
  assert.equal(seats.get("BBBBBB"), null);
  assert.deepEqual(seats.get("CCCCCC"), { token: TOKEN, slot: "A" });
});

// --- P2 U2: kind, computer level, validSeats and remove(code, token) ---------------

test("kind defaults to friend, a computer seat keeps its level, and a re-set without kind keeps both", () => {
  const storage = memoryStorage({ "justchess.seat.OLDOLD": JSON.stringify({ token: TOKEN, slot: "A" }) });
  const seats = createSeatStore(storage, { now: steppingClock() });

  seats.set("CMP001", { token: TOKEN, slot: "A", kind: "computer", computerLevel: "club" });
  assert.deepEqual(JSON.parse(storage.data.get("justchess.seat.CMP001")),
    { token: TOKEN, slot: "A", kind: "computer", computerLevel: "club", savedAt: 2000 });
  seats.set("CMP001", { token: TOKEN, slot: "A" }); // e.g. the join answer stores the seat again
  assert.equal(JSON.parse(storage.data.get("justchess.seat.CMP001")).computerLevel, "club");
  assert.deepEqual(seats.get("CMP001"), { token: TOKEN, slot: "A" }, "get keeps the room flow's shape");

  assert.throws(() => seats.set("CMP002", { token: TOKEN, slot: "A", kind: "computer" }), TypeError, "a level is required");
  assert.throws(() => seats.set("CMP002", { token: TOKEN, slot: "A", kind: "computer", computerLevel: "grandmaster" }), TypeError);
  assert.throws(() => seats.set("FRD001", { token: TOKEN, slot: "A", kind: "friend", computerLevel: "club" }), TypeError);
  assert.throws(() => seats.set("FRD001", { token: TOKEN, slot: "A", kind: "robot" }), TypeError);

  const old = seats.validSeats().find((seat) => seat.code === "OLDOLD");
  assert.deepEqual(old, { code: "OLDOLD", token: TOKEN, slot: "A", kind: "friend", computerLevel: null, savedAt: 0 },
    "a seat saved before kind existed reads as a friend seat");
});

test("validSeats lists newest first, skips and removes malformed entries; remove(code, token) checks the token", () => {
  const storage = memoryStorage({
    "justchess.seat.BADJSN": "{not json",
    "justchess.seat.BADSLT": JSON.stringify({ token: TOKEN, slot: "Z", kind: "friend", savedAt: 1 }),
    "justchess.seat.BADLVL": JSON.stringify({ token: TOKEN, slot: "A", kind: "computer", savedAt: 1 }),
    "justchess.seat.probe": "1",
    "other.app.key": "untouched",
  });
  const seats = createSeatStore(storage, { now: steppingClock() });
  seats.set("FIRST1", { token: TOKEN, slot: "A" });
  seats.set("SECND2", { token: "other-token-0123456789", slot: "B" });

  const listed = seats.validSeats();

  assert.deepEqual(listed.map((seat) => seat.code), ["SECND2", "FIRST1"]);
  for (const bad of ["BADJSN", "BADSLT", "BADLVL"]) assert.equal(storage.data.has(`justchess.seat.${bad}`), false, `${bad} removed`);
  assert.equal(storage.data.get("other.app.key"), "untouched");
  assert.equal(storage.data.get("justchess.seat.probe"), "1", "a key that is not a room code is left alone");

  seats.remove("FIRST1", "a-different-token-000");
  assert.deepEqual(seats.get("FIRST1"), { token: TOKEN, slot: "A" }, "a seat with another token is kept");
  seats.remove("FIRST1", TOKEN);
  assert.equal(seats.get("FIRST1"), null);

  const blocked = createSeatStore(null);
  blocked.set("MEMORY", { token: TOKEN, slot: "B" });
  assert.deepEqual(blocked.validSeats().map((seat) => seat.code), ["MEMORY"], "memory seats are listed too");
});

test("a valid continue fragment gives its token", () => {
  const token = "Abc_def-0123456789xyzXYZ";
  assert.equal(parseContinueFragment(`#continue=${token}`), token);
  assert.equal(parseContinueFragment(`continue=${token}`), token);
  assert.equal(parseContinueFragment(`#continue=${encodeURIComponent(token)}`), token);
});

test("invalid continue fragments give null", () => {
  for (const hash of ["", "#", "#continue=", "#continue=short", "#token=Abc_def-0123456789xyz", "#continue=bad token with spaces!!",
    "#continue=Abc_def-0123456789xyz&x=1", "#continue=%E0%A4%A", null, undefined, 42]) {
    assert.equal(parseContinueFragment(hash), null, `${JSON.stringify(hash)} is not a continue link`);
  }
});
