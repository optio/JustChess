// Tests for the "Play the computer" panel logic (P2 U4, BR8.1, BR3.5): remembered choices, defaults,
// the unavailable state, and Play choosing reopen, rematch or create (room-flow.js playComputer).
import { test } from "node:test";
import assert from "node:assert/strict";

import { CHOICE_KEY, DEFAULT_CHOICE, UNAVAILABLE_PANEL_TEXT, panelModel, readChoice, writeChoice } from "../../static/js/computer.js";
import { playComputer } from "../../static/js/room-flow.js";
import { createSeatStore } from "../../static/js/seat-store.js";

const TOKEN_A = "seat-token-aaaaaaaaaaaaaaaa";
const TOKEN_B = "seat-token-bbbbbbbbbbbbbbbb";
const TOKEN_NEW = "seat-token-nnnnnnnnnnnnnnnn";

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
    key: (index) => [...data.keys()][index] ?? null,
    get length() {
      return data.size;
    },
    data,
  };
}

const throwingStorage = {
  getItem() {
    throw new Error("SecurityError");
  },
  setItem() {
    throw new Error("QuotaExceededError");
  },
};

/** A fake api that records calls and answers from a table. */
function fakeApi({ states = {}, rematch = { ok: true, status: 200, data: {} }, created = null } = {}) {
  const calls = [];
  return {
    calls,
    state: async (code, token) => {
      calls.push(["state", code, token]);
      return states[code] || { ok: false, status: 404, message: "Room not found" };
    },
    rematch: async (code, token, colour) => {
      calls.push(["rematch", code, token, colour]);
      return rematch;
    },
    createComputerRoom: async (level, colour) => {
      calls.push(["create", level, colour]);
      return created || { ok: true, status: 201, data: { code: "NEW123", token: TOKEN_NEW, slot: "A", colour: "white" } };
    },
  };
}

test("choices are remembered and restored", () => {
  const storage = memoryStorage();
  assert.equal(writeChoice(storage, { colour: "black", level: "strong" }), true);
  assert.deepEqual(JSON.parse(storage.getItem(CHOICE_KEY)), { colour: "black", level: "strong" });
  assert.deepEqual(readChoice(storage), { colour: "black", level: "strong" });
  writeChoice(storage, { colour: "white", level: "maximum" });
  assert.deepEqual(readChoice(storage), { colour: "white", level: "maximum" });
  storage.setItem(CHOICE_KEY, JSON.stringify({ colour: "purple", level: "club" }));
  assert.deepEqual(readChoice(storage), { colour: "random", level: "club" }, "a bad field falls back alone");
});

test("the defaults are Random and Casual, also when storage is blocked or corrupt", () => {
  assert.deepEqual(DEFAULT_CHOICE, { colour: "random", level: "casual" });
  assert.deepEqual(readChoice(memoryStorage()), { colour: "random", level: "casual" });
  assert.deepEqual(readChoice(null), { colour: "random", level: "casual" });
  assert.deepEqual(readChoice(throwingStorage), { colour: "random", level: "casual" });
  assert.deepEqual(readChoice(memoryStorage({ [CHOICE_KEY]: "{not json" })), { colour: "random", level: "casual" });
  assert.equal(writeChoice(throwingStorage, { colour: "white", level: "club" }), false);
});

test("an unavailable engine disables Play and shows the reason", () => {
  assert.deepEqual(panelModel({ available: true, reason: null }), { playEnabled: true, message: null, reason: null });
  assert.deepEqual(panelModel({ available: false, reason: "No chess engine is installed" }),
    { playEnabled: false, message: UNAVAILABLE_PANEL_TEXT, reason: "No chess engine is installed" });
  assert.deepEqual(panelModel(null), { playEnabled: false, message: UNAVAILABLE_PANEL_TEXT, reason: null });
});

test("Play reopens, rematches or creates from the saved seats", async () => {
  let now = 1000;
  const seats = createSeatStore(memoryStorage(), { now: () => now++ });
  seats.set("CLUB01", { token: TOKEN_A, slot: "A", kind: "computer", computerLevel: "club" });
  seats.set("BEGN01", { token: TOKEN_B, slot: "A", kind: "computer", computerLevel: "beginner" });
  seats.set("FRND01", { token: TOKEN_B, slot: "A" });

  const playing = fakeApi({ states: { CLUB01: { ok: true, status: 200, data: { status: "playing", slot: "A" } } } });
  const reopened = await playComputer({ api: playing, seats, level: "club", colour: "black" });
  assert.deepEqual(reopened, { kind: "open", code: "CLUB01", plan: "reopen" });
  assert.deepEqual(playing.calls, [["state", "CLUB01", TOKEN_A]], "an unfinished game is resumed; the colour is ignored");

  const finished = fakeApi({ states: { CLUB01: { ok: true, status: 200, data: { status: "finished", slot: "A" } } } });
  const rematched = await playComputer({ api: finished, seats, level: "club", colour: "black" });
  assert.deepEqual(rematched, { kind: "open", code: "CLUB01", plan: "rematch" });
  assert.deepEqual(finished.calls[1], ["rematch", "CLUB01", TOKEN_A, "black"]);

  const gone = fakeApi(); // BEGN01 answers 404: dropped, then a new room is created and saved
  const created = await playComputer({ api: gone, seats, level: "beginner", colour: "white" });
  assert.equal(created.kind, "open");
  assert.equal(created.plan, "create");
  assert.equal(created.code, "NEW123");
  assert.deepEqual(gone.calls.map((call) => call[0]), ["state", "create"]);
  assert.equal(seats.get("BEGN01"), null);
  const saved = seats.validSeats().find((seat) => seat.code === "NEW123");
  assert.deepEqual([saved.kind, saved.computerLevel, saved.token], ["computer", "beginner", TOKEN_NEW]);

  const fresh = fakeApi();
  await playComputer({ api: fresh, seats, level: "maximum", colour: "random" });
  assert.deepEqual(fresh.calls, [["create", "maximum", "random"]], "no saved seat for the level: create at once");

  const refused = fakeApi({ created: { ok: false, status: 503, message: "No chess engine is installed" } });
  assert.deepEqual(await playComputer({ api: refused, seats, level: "strong", colour: "white" }),
    { kind: "failed", message: "No chess engine is installed" });
});
