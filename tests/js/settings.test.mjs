// Tests for the settings store static/js/settings.js (BR6.1, BR6.2) and the notifications hook decision.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

import {
  ALLOWED,
  DEFAULTS,
  NOTIFICATIONS_BLOCKED,
  STORAGE_KEY,
  applyToDocument,
  createSettings,
  decideNotifications,
} from "../../static/js/settings.js";

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
  };
}

function fakeEvents() {
  const listeners = new Map();
  return {
    addEventListener: (type, fn) => listeners.set(type, fn),
    removeEventListener: (type) => listeners.delete(type),
    fire: (type, event) => listeners.get(type)?.(event),
    has: (type) => listeners.has(type),
  };
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

test("defaults apply when nothing is stored, and the store is persistent", () => {
  const store = createSettings(memoryStorage(), { events: null });
  assert.deepEqual(store.all(), { ...DEFAULTS });
  assert.equal(store.get("blunderWarnings"), true);
  assert.equal(store.get("notifications"), false);
  assert.equal(store.persistent, true);
});

test("a corrupt value for one key keeps the others; broken JSON falls back to defaults", () => {
  const stored = { theme: "dark", board: "marble", labels: "frame", blunderWarnings: "yes", notifications: true };
  const store = createSettings(memoryStorage({ [STORAGE_KEY]: JSON.stringify(stored) }), { events: null });
  assert.deepEqual(store.all(), { theme: "dark", board: "walnut-maple", labels: "frame", blunderWarnings: true, notifications: true });

  const { result, messages } = quietly(() => createSettings(memoryStorage({ [STORAGE_KEY]: "{not json" }), { events: null }));
  assert.deepEqual(result.all(), { ...DEFAULTS });
  assert.equal(messages.length, 1, "the corrupt value is reported, not swallowed");
});

test("storage that throws gives persistent false while values still work (BR6.2)", () => {
  const throwing = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() {} };
  const { result: blocked } = quietly(() => createSettings(throwing, { events: null }));
  assert.equal(blocked.persistent, false);
  blocked.set("board", "rosewood");
  assert.equal(blocked.get("board"), "rosewood");

  assert.equal(createSettings(null, { events: null }).persistent, false, "no storage at all");

  const writeFails = memoryStorage();
  writeFails.setItem = () => { throw new Error("quota"); };
  const store = createSettings(writeFails, { events: null });
  assert.equal(store.persistent, true);
  const { messages } = quietly(() => store.set("theme", "light"));
  assert.equal(store.persistent, false, "a failed write switches to memory-only");
  assert.equal(store.get("theme"), "light");
  assert.equal(messages.length, 1);
});

test("set saves the whole object and calls subscribers; unsubscribe stops calls", () => {
  const storage = memoryStorage();
  const store = createSettings(storage, { events: null });
  const calls = [];
  const unsubscribe = store.subscribe((key, value, all) => calls.push([key, value, all.labels]));
  store.set("labels", "frame");
  store.set("labels", "frame");
  assert.deepEqual(calls, [["labels", "frame", "frame"]], "an unchanged value does not notify");
  assert.deepEqual(JSON.parse(storage.getItem(STORAGE_KEY)), { ...DEFAULTS, labels: "frame" });
  unsubscribe();
  store.set("labels", "inside");
  assert.equal(calls.length, 1);

  const { messages } = quietly(() => {
    store.subscribe(() => { throw new Error("subscriber bug"); });
    store.set("theme", "dark");
  });
  assert.equal(store.get("theme"), "dark");
  assert.equal(messages.length, 1, "a throwing subscriber is reported and does not break the store");
});

test("an unknown key or value is refused with an error", () => {
  const store = createSettings(memoryStorage(), { events: null });
  assert.throws(() => store.set("board", "marble"), RangeError);
  assert.throws(() => store.set("blunderWarnings", "true"), RangeError);
  assert.throws(() => store.set("volume", 3), TypeError);
  assert.throws(() => store.get("volume"), TypeError);
  assert.deepEqual(store.all(), { ...DEFAULTS });
});

test("a storage event from another tab updates the values and notifies", () => {
  const events = fakeEvents();
  const store = createSettings(memoryStorage(), { events });
  const seen = [];
  store.subscribe((key, value) => seen.push(`${key}=${value}`));
  events.fire("storage", { key: STORAGE_KEY, newValue: JSON.stringify({ ...DEFAULTS, board: "tournament", theme: "bogus" }) });
  assert.equal(store.get("board"), "tournament");
  assert.equal(store.get("theme"), "device");
  assert.deepEqual(seen, ["board=tournament"]);
  events.fire("storage", { key: "someone.else", newValue: "{}" });
  assert.equal(store.get("board"), "tournament", "other keys are ignored");
  events.fire("storage", { key: null, newValue: null });
  assert.equal(store.get("board"), "walnut-maple", "storage.clear() resets to defaults");
  store.destroy();
  assert.equal(events.has("storage"), false);
});

test("applyToDocument sets data-theme (omitted for device) and data-board and follows changes", () => {
  const attributes = new Map();
  const root = {
    setAttribute: (name, value) => attributes.set(name, value),
    removeAttribute: (name) => attributes.delete(name),
  };
  const store = createSettings(memoryStorage(), { events: null });
  applyToDocument(store, root);
  assert.equal(attributes.has("data-theme"), false);
  assert.equal(attributes.get("data-board"), "walnut-maple");
  store.set("theme", "dark");
  store.set("board", "rosewood");
  assert.equal(attributes.get("data-theme"), "dark");
  assert.equal(attributes.get("data-board"), "rosewood");
  store.set("theme", "device");
  assert.equal(attributes.has("data-theme"), false);
});

const BOOT_SOURCE = readFileSync(new URL("../../static/js/boot.js", import.meta.url), "utf8");

function runBoot(getItem) {
  const attributes = new Map([["data-theme", "stale"]]);
  const documentElement = {
    setAttribute: (name, value) => attributes.set(name, value),
    removeAttribute: (name) => attributes.delete(name),
  };
  runInNewContext(BOOT_SOURCE, { window: { localStorage: { getItem } }, document: { documentElement }, JSON });
  return { theme: attributes.get("data-theme") ?? null, board: attributes.get("data-board") };
}

test("boot.js uses the store's key and allow-lists and falls back to the defaults", () => {
  for (const theme of [...ALLOWED.theme, "neon"]) {
    for (const board of [...ALLOWED.board, "marble"]) {
      const stored = JSON.stringify({ theme, board });
      const store = createSettings(memoryStorage({ [STORAGE_KEY]: stored }), { events: null });
      const expected = { theme: store.get("theme") === "device" ? null : store.get("theme"), board: store.get("board") };
      assert.deepEqual(runBoot((key) => (key === STORAGE_KEY ? stored : null)), expected, stored);
    }
  }
  assert.deepEqual(runBoot(() => { throw new Error("blocked"); }), { theme: null, board: "walnut-maple" });
  assert.deepEqual(runBoot(() => "{broken"), { theme: null, board: "walnut-maple" });
  assert.deepEqual(runBoot(() => null), { theme: null, board: "walnut-maple" });
});

test("notifications hook: granted, denied, throw and no hook", async () => {
  assert.deepEqual(await decideNotifications(true, async () => true), { value: true, notice: null });
  assert.deepEqual(await decideNotifications(true, async () => false), { value: false, notice: NOTIFICATIONS_BLOCKED });
  assert.deepEqual(await decideNotifications(true, async () => { throw new Error("Permission prompt dismissed"); }),
    { value: false, notice: "Permission prompt dismissed" });
  assert.deepEqual(await decideNotifications(true, async () => { throw new Error(""); }),
    { value: false, notice: NOTIFICATIONS_BLOCKED });
  assert.deepEqual(await decideNotifications(false, async () => true), { value: false, notice: null });
  assert.deepEqual(await decideNotifications(true, undefined), { value: true, notice: null });
  assert.deepEqual(await decideNotifications(false, undefined), { value: false, notice: null });
});
