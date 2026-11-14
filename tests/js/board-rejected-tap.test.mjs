// Tests for the U6 board addition in static/js/board/interaction.js: when the
// "rejectedTap" effect (board.js -> onRejectedTap(from, to)) fires, and every case where it must not.
import { test } from "node:test";
import assert from "node:assert/strict";

import { parseFen, START_FEN } from "../../static/js/board/geometry.js";
import { initialState, reduce } from "../../static/js/board/interaction.js";

const START = parseFen(START_FEN).pieces;
const LEGAL = ["a2a3", "a2a4", "b1a3", "b1c3", "e2e3", "e2e4", "g1f3", "g1h3"];
const PROMO = parseFen("4k3/1P6/8/8/8/8/8/4K3 w - - 0 1").pieces;
const PROMO_LEGAL = ["b7b8q", "b7b8r", "b7b8b", "b7b8n", "e1d1", "e1d2", "e1e2", "e1f1", "e1f2"];

const ctx = (overrides = {}) => ({ legalMoves: LEGAL, interactive: true, shown: START, ...overrides });

function run(events, context = ctx(), state = initialState(true)) {
  let current = state;
  const all = [];
  for (const event of events) {
    const result = reduce(current, event, context);
    current = result.state;
    all.push(...result.effects);
  }
  return { state: current, rejected: all.filter((effect) => effect.type === "rejectedTap") };
}

const tap = (square) => ({ type: "tap", square });

test("fires on an empty square that is not a target, and clears the selection", () => {
  const { state, rejected } = run([tap("e2"), tap("e5")]);
  assert.deepEqual(rejected, [{ type: "rejectedTap", from: "e2", to: "e5" }]);
  assert.deepEqual([state.mode, state.selected], ["idle", null]);
});

test("fires on an opponent's piece that is not a target", () => {
  assert.deepEqual(run([tap("g1"), tap("e7")]).rejected, [{ type: "rejectedTap", from: "g1", to: "e7" }]);
});

test("never fires on a deselect or on Escape", () => {
  assert.deepEqual(run([tap("e2"), tap("e2")]).rejected, []);
  assert.deepEqual(run([tap("e2"), { type: "escape" }]).rejected, []);
});

test("never fires when another own piece is chosen, movable (reselect) or not", () => {
  const reselect = run([tap("e2"), tap("g1")]);
  assert.deepEqual([reselect.rejected, reselect.state.selected], [[], "g1"]);
  const blocked = run([tap("e2"), tap("d1")]);
  assert.deepEqual([blocked.rejected, blocked.state.selected], [[], null]);
});

test("never fires while the board is not interactive", () => {
  const selected = run([tap("e2")]).state;
  const locked = reduce(selected, { type: "setInteractive", value: false }, ctx()).state;
  assert.deepEqual(run([tap("e5")], ctx({ interactive: false }), locked).rejected, []);
  assert.deepEqual(run([tap("e2"), tap("e5")], ctx({ interactive: false }), initialState(false)).rejected, []);
});

test("never fires while a move is pending or the promotion picker is open; a legal target never fires", () => {
  const pending = run([tap("e2"), tap("e4")]);
  assert.deepEqual(pending.rejected, [], "a legal move is a move, not a rejected tap");
  assert.deepEqual(run([tap("g1"), tap("e5")], ctx(), pending.state).rejected, []);
  const promoting = run([tap("b7"), tap("b8")], ctx({ legalMoves: PROMO_LEGAL, shown: PROMO }));
  assert.equal(promoting.state.mode, "promoting");
  assert.deepEqual(run([tap("a1")], ctx({ legalMoves: PROMO_LEGAL, shown: PROMO }), promoting.state).rejected, []);
});
