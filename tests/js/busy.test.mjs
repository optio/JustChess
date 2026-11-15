// Tests for static/js/busy.js: progress and repeat-click protection for slow actions.
import { test } from "node:test";
import assert from "node:assert/strict";

import { busyClick, isBusy, runBusy } from "../../static/js/busy.js";

/** The few button parts busy.js touches. */
function fakeButton() {
  const classes = new Set();
  const attributes = new Map();
  const listeners = [];
  return {
    classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name), contains: (name) => classes.has(name) },
    setAttribute: (name, value) => attributes.set(name, String(value)),
    removeAttribute: (name) => attributes.delete(name),
    getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
    addEventListener: (type, handler) => listeners.push([type, handler]),
    click() { return listeners.filter(([type]) => type === "click").map(([, handler]) => handler({})); },
  };
}

test("a running action shows progress and ignores repeat clicks until it settles", async () => {
  const button = fakeButton();
  let calls = 0;
  let finish;
  busyClick(button, () => { calls += 1; return new Promise((resolve) => { finish = resolve; }); });
  const first = button.click()[0];
  button.click();
  button.click();
  assert.equal(calls, 1);
  assert.ok(isBusy(button));
  assert.ok(button.classList.contains("is-busy"));
  assert.equal(button.getAttribute("aria-busy"), "true");
  finish("done");
  assert.equal(await first, "done");
  assert.equal(isBusy(button), false);
  assert.equal(button.classList.contains("is-busy"), false);
  assert.equal(button.getAttribute("aria-busy"), null);
  button.click();
  assert.equal(calls, 2, "a settled action can run again");
});

test("a failing action still clears the busy state and passes the error on", async () => {
  const button = fakeButton();
  await assert.rejects(runBusy(button, async () => { throw new Error("network"); }), /network/);
  assert.equal(isBusy(button), false);
  assert.equal(button.classList.contains("is-busy"), false);
});

test("a missing button or a second concurrent run returns null without calling", async () => {
  assert.equal(await runBusy(null, () => 1), null);
  const button = fakeButton();
  let release;
  const running = runBusy(button, () => new Promise((resolve) => { release = resolve; }));
  let second = 0;
  assert.equal(await runBusy(button, () => { second += 1; }), null);
  assert.equal(second, 0);
  release();
  await running;
});
