// Tests for the "Play the computer" panel logic (P2 U4, BR8.1, BR3.5): remembered choices, defaults,
// the unavailable state, and Play choosing reopen, rematch or create (room-flow.js playComputer).
import { test } from "node:test";
import assert from "node:assert/strict";

import { CHOICE_KEY, DEFAULT_CHOICE, readChoice, writeChoice } from "../../static/js/computer.js";
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
