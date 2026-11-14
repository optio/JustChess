// Tests for the hub's Endgames tab loader in static/js/training/endgame-state.js (P2 U6, BR4.1, W1).
import { test } from "node:test";
import assert from "node:assert/strict";

import { ENDGAMES_TAB, createEndgamesApi, endgamesLoader } from "../../static/js/training/endgame-state.js";
import { createTabRegistry } from "../../static/js/training/hub-tabs.js";
import { createTrainerProgress } from "../../static/js/training/trainer-progress.js";

const CATEGORIES = [
  { id: "queen-mate", label: "Queen mate", positions: [
    { id: "queen-first-steps", title: "First steps with the queen", goal: "mate", order: 1 },
    { id: "queen-mind-the-stalemate", title: "Mind the stalemate", goal: "mate", order: 2 },
  ] },
  { id: "opposition", label: "Opposition", positions: [
    { id: "opp-hold-the-opposition", title: "Hold the opposition", goal: "draw", order: 1 },
  ] },
];

/** A fetch that answers GET /api/endgames with ``body`` and records the paths asked for. */
function fakeFetch(body, status = 200) {
  const calls = [];
  const fetchImpl = async (path, options) => {
    calls.push([path, options.method]);
    return { ok: status < 400, status, headers: { get: () => "application/json" }, json: async () => body };
  };
  return { fetchImpl, calls };
}

function memoryStorage() {
  const items = new Map();
  return { getItem: (k) => (items.has(k) ? items.get(k) : null), setItem: (k, v) => items.set(k, String(v)), removeItem: (k) => items.delete(k) };
}

test("rows follow the categories with Done and the count, and Play opens the position", async () => {
  const { fetchImpl, calls } = fakeFetch({ installed: true, available: true, reason: null, categories: CATEGORIES });
  const progress = createTrainerProgress(memoryStorage());
  progress.markDone("endgames", "queen-mind-the-stalemate");
  const opened = [];
  const result = await endgamesLoader({ endgamesApi: createEndgamesApi(fetchImpl), progress, onOpenEndgame: (id) => opened.push(id) });
  assert.deepEqual(calls, [["/api/endgames", "GET"]]);
  assert.deepEqual(result.rows.map((row) => [row.id, row.done, row.disabled, row.action]), [
    ["queen-first-steps", false, false, "Play"],
    ["queen-mind-the-stalemate", true, false, "Play"],
    ["opp-hold-the-opposition", false, false, "Play"],
  ]);
  assert.equal(result.rows[0].subtitle, "Queen mate · checkmate");
  assert.equal(result.rows[2].subtitle, "Opposition · hold the draw");
  assert.deepEqual([result.solved, result.total, result.note], [1, 3, undefined]);
  result.rows[2].onAction();
  assert.deepEqual(opened, ["opp-hold-the-opposition"]);
  const registry = createTabRegistry();
  registry.registerTab(ENDGAMES_TAB);
  assert.deepEqual(registry.tabs().map((tab) => tab.id), ["openings", "traps", "endgames", "tactics", "defence"],
    "Endgames sits between Traps and Tactics");
});

test("without Stockfish the note gives the reason and every Play button is disabled", async () => {
  const { fetchImpl } = fakeFetch({ installed: true, available: false, reason: "No chess engine is installed", categories: CATEGORIES });
  const result = await endgamesLoader({ endgamesApi: createEndgamesApi(fetchImpl) });
  assert.equal(result.note, "Needs Stockfish: No chess engine is installed");
  assert.ok(result.rows.length === 3 && result.rows.every((row) => row.disabled), "Play is disabled on every row");
  assert.equal(result.rows[0].subtitle, "Queen mate · checkmate · Needs Stockfish");
  assert.equal(result.total, 3, "the count still shows");
});

test("when nothing is installed the tab says so; a failed list shows the error", async () => {
  const empty = await endgamesLoader({ endgamesApi: createEndgamesApi(fakeFetch({ installed: false, available: true, reason: null, categories: [] }).fetchImpl) });
  assert.deepEqual([empty.rows, empty.total, empty.note], [[], 0, "No endgame positions are installed"]);
  const failed = await endgamesLoader({ endgamesApi: createEndgamesApi(fakeFetch({ detail: "boom" }, 500).fetchImpl) });
  assert.equal(failed.error, "boom");
  assert.deepEqual(failed.rows, []);
});
