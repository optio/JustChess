// Tests for the trainer hub tab registry static/js/training/hub-tabs.js (P2 U5, BR3.1).
import { test } from "node:test";
import assert from "node:assert/strict";

import { countLabel, createTabRegistry, DEFAULT_TABS, listTabs, nextTabIndex } from "../../static/js/training/hub-tabs.js";

test("the default tabs are Openings, Traps, Tactics and Defence, in that order", () => {
  assert.deepEqual(createTabRegistry().tabs().map((tab) => tab.id), ["openings", "traps", "tactics", "defence"]);
  assert.deepEqual(listTabs().map((tab) => tab.label), ["Openings", "Traps", "Tactics", "Defence"]);
  assert.equal(DEFAULT_TABS[0].id, "openings", "Train opens on Openings first (BR3.4)");
});

test("registerTab adds a tab in order position, e.g. U6's Endgames between Traps and Tactics", () => {
  const registry = createTabRegistry();
  const load = async () => ({ rows: [], solved: 0, total: 0 });
  registry.registerTab({ id: "endgames", label: "Endgames", order: 30, load });
  const tabs = registry.tabs();
  assert.deepEqual(tabs.map((tab) => tab.id), ["openings", "traps", "endgames", "tactics", "defence"]);
  assert.equal(tabs[2].load, load);
  assert.ok(registry.has("endgames"));
  assert.ok(Object.isFrozen(tabs[2]), "a registered tab cannot be changed afterwards");
});

test("registerTab refuses duplicates, unknown ids and malformed tabs", () => {
  const registry = createTabRegistry();
  assert.throws(() => registry.registerTab({ id: "openings", label: "Again", order: 1 }), /already registered/);
  assert.throws(() => registry.registerTab({ id: "chess960", label: "960", order: 60 }), /unknown tab id/);
  assert.throws(() => registry.registerTab({ id: "endgames", label: "", order: 30 }), /label/);
  assert.throws(() => registry.registerTab({ id: "endgames", label: "Endgames", order: "x" }), /order/);
  assert.throws(() => registry.registerTab({ id: "endgames", label: "Endgames", order: 30, load: "no" }), /load/);
  assert.equal(registry.tabs().length, 4, "nothing was added by the refused calls");
});

test("Left and Right move between tabs and wrap at both ends", () => {
  assert.equal(nextTabIndex(0, "ArrowRight", 4), 1);
  assert.equal(nextTabIndex(3, "ArrowRight", 4), 0);
  assert.equal(nextTabIndex(0, "ArrowLeft", 4), 3);
  assert.equal(nextTabIndex(2, "ArrowLeft", 4), 1);
  assert.equal(nextTabIndex(7, "ArrowRight", 4), 1, "an out-of-range index starts from the first tab");
});

test("Home and End jump; other keys do nothing; counts read solved/total", () => {
  assert.equal(nextTabIndex(2, "Home", 4), 0);
  assert.equal(nextTabIndex(1, "End", 4), 3);
  for (const key of ["Enter", "ArrowUp", "ArrowDown", "Tab", "a"]) assert.equal(nextTabIndex(1, key, 4), null, key);
  assert.equal(nextTabIndex(0, "End", 0), null, "no tabs, no move");
  assert.equal(countLabel(2, 10), "2/10");
  assert.equal(countLabel(12, 10), "10/10", "never more solved than there are");
  assert.equal(countLabel(undefined, null), "0/0");
});
