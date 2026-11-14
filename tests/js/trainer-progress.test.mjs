// Tests for the per-device progress store static/js/training/trainer-progress.js (P2 U5, BR3.2).
import { test } from "node:test";
import assert from "node:assert/strict";

import { createTrainerProgress, groupOfKind, MAX_ENTRIES, STORAGE_KEY } from "../../static/js/training/trainer-progress.js";

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => { data.set(key, String(value)); },
    removeItem: (key) => { data.delete(key); },
  };
}

function quietly(fn) {
  const original = console.error;
  console.error = () => {};
  try {
    return fn();
  } finally {
    console.error = original;
  }
}

test("a finished item is written under one key and read back by a new store", () => {
  const storage = memoryStorage();
  const progress = createTrainerProgress(storage, { clock: () => 1000 });
  assert.equal(progress.persistent, true);
  assert.equal(progress.markDone("openings", "italian"), true);
  assert.equal(progress.isDone("openings", "italian"), true);
  assert.deepEqual(JSON.parse(storage.getItem(STORAGE_KEY)), { "openings:italian": 1000 });
  const again = createTrainerProgress(storage);
  assert.equal(again.isDone("openings", "italian"), true, "kept on this device");
  assert.equal(again.isDone("traps", "italian"), false, "groups are separate");
});

test("counts are per group, and per theme for tactics", () => {
  const progress = createTrainerProgress(memoryStorage());
  progress.markDone("tactics", "fork:00008");
  progress.markDone("tactics", "fork:0000D");
  progress.markDone("tactics", "pin:000aY");
  progress.markDone("defence", "wayward-queen");
  progress.markDone("tactics", "fork:00008");
  assert.equal(progress.countDone("tactics"), 3, "marking twice counts once");
  assert.equal(progress.countDone("tactics", "fork"), 2);
  assert.equal(progress.countDone("tactics", "mateIn1"), 0);
  assert.equal(progress.countDone("defence"), 1);
  assert.deepEqual([groupOfKind("opening"), groupOfKind("trap"), groupOfKind("defence"), groupOfKind("x")],
    ["openings", "traps", "defence", null]);
});

test("without storage nothing is kept, nothing throws, and no progress is shown", () => {
  const progress = createTrainerProgress(null);
  assert.equal(progress.persistent, false);
  assert.equal(progress.markDone("openings", "italian"), false);
  assert.equal(progress.isDone("openings", "italian"), false);
  assert.equal(progress.countDone("openings"), 0);
});

test("unreadable or corrupt storage and a failing write are ignored", () => {
  const corrupt = quietly(() => createTrainerProgress(memoryStorage({ [STORAGE_KEY]: "{not json" })));
  assert.equal(corrupt.countDone("openings"), 0);
  const throwing = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  const blocked = quietly(() => createTrainerProgress(throwing));
  assert.equal(blocked.persistent, false);
  assert.equal(blocked.markDone("traps", "legals-mate"), false);
  const full = memoryStorage();
  full.setItem = () => { throw new Error("QuotaExceededError"); };
  const quota = createTrainerProgress(full);
  assert.equal(quietly(() => quota.markDone("traps", "legals-mate")), false, "a failed write keeps nothing");
  assert.equal(quota.isDone("traps", "legals-mate"), false);
  assert.equal(quota.persistent, false);
  const mixed = createTrainerProgress(memoryStorage({ [STORAGE_KEY]: JSON.stringify({ "openings:a": 1, "hacked:x": 2, "traps:b": "no" }) }));
  assert.equal(mixed.countDone("openings"), 1, "unknown groups and bad values are dropped");
});

test("at most 5000 entries are kept (the oldest go first) and bad keys are refused", () => {
  const seed = {};
  for (let i = 0; i < MAX_ENTRIES; i += 1) seed[`tactics:fork:${String(i).padStart(5, "0")}`] = i + 1;
  const storage = memoryStorage({ [STORAGE_KEY]: JSON.stringify(seed) });
  const progress = createTrainerProgress(storage, { clock: () => 1e12 });
  progress.markDone("openings", "italian");
  const stored = JSON.parse(storage.getItem(STORAGE_KEY));
  assert.equal(Object.keys(stored).length, MAX_ENTRIES);
  assert.ok(stored["openings:italian"], "the newest is kept");
  assert.equal(stored["tactics:fork:00000"], undefined, "the oldest went");
  assert.throws(() => progress.markDone("chess960", "x"), TypeError);
  assert.throws(() => progress.markDone("openings", "../etc"), TypeError);
  assert.throws(() => progress.countDone("nope"), TypeError);
});
