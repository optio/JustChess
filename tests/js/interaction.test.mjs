// Tests for the pure board interaction reducer static/js/board/interaction.js (BR2.1-BR2.4).
import { test } from "node:test";
import assert from "node:assert/strict";

import { parseFen, START_FEN } from "../../static/js/board/geometry.js";
import { initialState, reduce } from "../../static/js/board/interaction.js";

const START = parseFen(START_FEN).pieces;
const START_LEGAL = ["a2a3", "a2a4", "b1a3", "b1c3", "e2e3", "e2e4", "g1f3", "g1h3"];
const PROMO = parseFen("4k3/1P6/8/8/8/8/8/4K3 w - - 0 1").pieces;
const PROMO_LEGAL = ["b7b8q", "b7b8r", "b7b8b", "b7b8n", "e1d1", "e1d2", "e1e2", "e1f1", "e1f2"];

const ctx = (overrides = {}) => ({ legalMoves: START_LEGAL, interactive: true, shown: START, ...overrides });

function run(events, context = ctx(), state = initialState(true)) {
  let current = state;
  let effects = [];
  for (const event of events) {
    ({ state: current, effects } = reduce(current, event, context));
  }
  return { state: current, effects };
}

test("selecting a piece that cannot move, or an empty square, does nothing", () => {
  assert.deepEqual(run([{ type: "tap", square: "d1" }]).state, initialState(true));
  assert.deepEqual(run([{ type: "tap", square: "e4" }]).state, initialState(true));
  const empty = run([{ type: "tap", square: "e2" }], ctx({ legalMoves: [] }));
  assert.equal(empty.state.mode, "idle", "an empty legal list selects nothing");
});

test("tapping a movable piece selects it; retapping or tapping elsewhere clears it", () => {
  const selected = run([{ type: "tap", square: "e2" }]);
  assert.equal(selected.state.mode, "selected");
  assert.equal(selected.state.selected, "e2");
  assert.equal(run([{ type: "tap", square: "e2" }, { type: "tap", square: "g1" }]).state.selected, "g1");
  assert.equal(run([{ type: "tap", square: "e2" }, { type: "tap", square: "e2" }]).state.mode, "idle");
  assert.equal(run([{ type: "tap", square: "e2" }, { type: "tap", square: "h6" }]).state.selected, null);
  assert.equal(run([{ type: "tap", square: "e2" }, { type: "escape" }]).state.mode, "idle");
});

test("tapping a target emits the move once, shows it optimistically and enters pending", () => {
  const { state, effects } = run([{ type: "tap", square: "e2" }, { type: "tap", square: "e4" }]);
  assert.equal(state.mode, "pending");
  assert.deepEqual(state.pending, { uci: "e2e4", from: "e2", to: "e4", promotion: null });
  assert.equal(state.selected, null);
  assert.deepEqual(effects, [
    { type: "applyOptimistic", from: "e2", to: "e4", promotion: null },
    { type: "emitMove", uci: "e2e4" },
    { type: "focus", square: "e4" },
  ]);
  const ignored = reduce(state, { type: "tap", square: "g1" }, ctx());
  assert.deepEqual(ignored, { state, effects: [] }, "input is ignored while pending");
});

test("a promotion target opens the picker; picking emits with the suffix, cancel returns to idle", () => {
  const context = ctx({ legalMoves: PROMO_LEGAL, shown: PROMO });
  const open = run([{ type: "tap", square: "b7" }, { type: "tap", square: "b8" }], context);
  assert.equal(open.state.mode, "promoting");
  assert.deepEqual(open.effects, [{ type: "openPromotion", from: "b7", to: "b8" }]);

  const picked = reduce(open.state, { type: "promotionChosen", piece: "n" }, context);
  assert.equal(picked.state.mode, "pending");
  assert.deepEqual(picked.effects.find((e) => e.type === "emitMove"), { type: "emitMove", uci: "b7b8n" });

  const cancelled = reduce(open.state, { type: "promotionChosen", piece: null }, context);
  assert.equal(cancelled.state.mode, "idle");
  assert.equal(cancelled.state.selected, null);
  assert.equal(cancelled.effects.some((e) => e.type === "emitMove"), false);

  const escaped = reduce(open.state, { type: "escape" }, context);
  assert.equal(escaped.state.mode, "idle");
  assert.deepEqual(escaped.effects, [{ type: "closePromotion" }]);
});

test("interactive false from selected, promoting or pending gives locked with the right effects", () => {
  const off = { type: "setInteractive", value: false };
  const fromSelected = run([{ type: "tap", square: "e2" }, off]);
  assert.equal(fromSelected.state.mode, "locked");
  assert.equal(fromSelected.state.selected, null);
  assert.deepEqual(fromSelected.effects, []);

  const promoCtx = ctx({ legalMoves: PROMO_LEGAL, shown: PROMO });
  const fromPromoting = run([{ type: "tap", square: "b7" }, { type: "tap", square: "b8" }, off], promoCtx);
  assert.equal(fromPromoting.state.mode, "locked");
  assert.equal(fromPromoting.state.promoting, null);
  assert.deepEqual(fromPromoting.effects, [{ type: "closePromotion" }]);

  const fromPending = run([{ type: "tap", square: "e2" }, { type: "tap", square: "e4" }, off]);
  assert.equal(fromPending.state.pending.uci, "e2e4", "the pending move stays pending");
  assert.deepEqual(fromPending.effects, []);
  const lockedCtx = ctx({ interactive: false });
  assert.deepEqual(reduce(fromPending.state, { type: "tap", square: "g1" }, lockedCtx).effects, []);
  const answered = reduce(fromPending.state, { type: "position", next: START, lastMove: null }, lockedCtx);
  assert.equal(answered.state.mode, "locked");
  assert.equal(answered.state.pending, null);

  const backOn = reduce(initialState(false), { type: "setInteractive", value: true }, ctx());
  assert.equal(backOn.state.mode, "idle");
});

test("reject clears pending and slides the piece back to its origin", () => {
  const pending = run([{ type: "tap", square: "g1" }, { type: "tap", square: "f3" }]);
  const { state, effects } = reduce(pending.state, { type: "reject" }, ctx());
  assert.equal(state.mode, "idle");
  assert.equal(state.pending, null);
  assert.deepEqual(effects, [{ type: "slideBack", from: "g1", to: "f3" }, { type: "focus", square: "g1" }]);
  assert.deepEqual(reduce(initialState(true), { type: "reject" }, ctx()).effects, [], "reject without pending is a no-op");
});

test("a position equal to the optimistic one gives no animation; a new one animates", () => {
  const optimistic = parseFen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1").pieces;
  const pending = run([{ type: "tap", square: "e2" }, { type: "tap", square: "e4" }]);
  const sameCtx = ctx({ shown: optimistic, legalMoves: [] });
  const same = reduce(pending.state, { type: "position", next: optimistic, lastMove: { from: "e2", to: "e4" } }, sameCtx);
  assert.deepEqual(same.effects, [{ type: "render", animation: null }]);
  assert.equal(same.state.pending, null);

  const reply = parseFen("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2").pieces;
  const moved = reduce(same.state, { type: "position", next: reply, lastMove: { from: "e7", to: "e5" } }, sameCtx);
  assert.deepEqual(moved.effects[0].animation.moves, [{ piece: "p", from: "e7", to: "e5", becomes: "p" }]);
});

test("a position update keeps a still-movable selection and closes an open picker", () => {
  const selected = run([{ type: "tap", square: "e2" }]);
  const kept = reduce(selected.state, { type: "position", next: START, lastMove: null }, ctx());
  assert.equal(kept.state.selected, "e2");
  const dropped = reduce(selected.state, { type: "position", next: START, lastMove: null }, ctx({ legalMoves: ["g1f3"] }));
  assert.equal(dropped.state.selected, null);
  assert.equal(dropped.state.mode, "idle");

  const promoCtx = ctx({ legalMoves: PROMO_LEGAL, shown: PROMO });
  const open = run([{ type: "tap", square: "b7" }, { type: "tap", square: "b8" }], promoCtx);
  const closed = reduce(open.state, { type: "position", next: PROMO, lastMove: null }, promoCtx);
  assert.equal(closed.effects[0].type, "closePromotion");
  assert.equal(closed.state.mode, "idle");
  assert.throws(() => reduce(initialState(true), { type: "dance" }, ctx()), TypeError);
});
