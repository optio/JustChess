// Tests for the pure puzzle reducer static/js/training/puzzle-state.js (P2 U5, W5, BR2.3-BR2.5).
// The fixture has the shape GET /api/puzzles/{theme}/{id} returns: the back-rank mate in 2
// from tests/fixtures/puzzle_set.py (1...a6 2.Qd8+ Rxd8 3.Rxd8#), played as White.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  initialState, reduce, REPLY_DELAY_MS, REVEAL_MS, SETUP_DELAY_MS, statusText, TEXT, WRONG_MS,
} from "../../static/js/training/puzzle-state.js";

const START = "2r3k1/p4ppp/8/8/8/8/P2Q1PPP/3R2K1 b - - 0 1";
const AFTER_SETUP = "2r3k1/5ppp/p7/8/8/8/P2Q1PPP/3R2K1 w - - 0 2";
const AFTER_QD8 = "2rQ2k1/5ppp/p7/8/8/8/P4PPP/3R2K1 b - - 1 2";
const AFTER_RXD8 = "3r2k1/5ppp/p7/8/8/8/P4PPP/3R2K1 w - - 0 3";
const MATED = "3R2k1/5ppp/p7/8/8/8/P4PPP/6K1 b - - 0 3";

function puzzle() {
  return {
    id: "Bk001", theme: "mateIn2", label: "Mate in 2", fen: START, setup: "a7a6", playerMoves: 2, rating: 1200,
    side: "white", afterSetup: AFTER_SETUP, legalMoves: ["a2a3", "d2d7", "d2d8"], check: false,
  };
}

function run(events, state = initialState()) {
  let current = state;
  let effects = [];
  for (const event of events) ({ state: current, effects } = reduce(current, event));
  return { state: current, effects };
}

const types = (effects) => effects.map((effect) => effect.type);
const boardOf = (effects) => effects.find((effect) => effect.type === "setBoard")?.options;
const scheduled = (effects) => effects.find((effect) => effect.type === "schedule");

function yourMove() {
  const loaded = run([{ type: "loaded", puzzle: puzzle() }]);
  return run([scheduled(loaded.effects).event], loaded.state).state;
}

test("a loaded puzzle shows the start, then plays the set-up move and gives the player the board", () => {
  const loaded = run([{ type: "loaded", puzzle: puzzle() }]);
  assert.equal(loaded.state.phase, "settingUp");
  assert.deepEqual(boardOf(loaded.effects), {
    fen: START, lastMove: null, check: false, orientation: "white", interactive: false, legalMoves: [], hintSquare: null,
  });
  const timer = scheduled(loaded.effects);
  assert.equal(timer.delay, SETUP_DELAY_MS);
  const ready = run([timer.event], loaded.state);
  assert.equal(ready.state.phase, "yourMove");
  assert.deepEqual(boardOf(ready.effects), {
    fen: AFTER_SETUP, lastMove: "a7a6", check: false, orientation: "white", interactive: true,
    legalMoves: ["a2a3", "d2d7", "d2d8"], hintSquare: null,
  });
  assert.equal(statusText(puzzle()), "White to move: find mate in 2");
  const broken = run([{ type: "loaded", puzzle: { id: "x" } }]);
  assert.deepEqual([broken.state.phase, broken.state.message.text], ["loading", TEXT.unreadable]);
});

test("a correct move is checked, the reply plays after 300 ms, and the next ply is the player's", () => {
  const sent = run([{ type: "playerMove", uci: "d2d8" }], yourMove());
  assert.equal(sent.state.phase, "checking");
  assert.deepEqual(sent.effects, [{ type: "check", ply: 1, uci: "d2d8" }]);
  const data = { result: "correct", fen: AFTER_QD8, check: true, reply: "c8d8", replyFen: AFTER_RXD8, legalMoves: ["d1d8", "g1f1"], replyCheck: false };
  const reply = run([{ type: "checkResult", data }], sent.state);
  assert.equal(reply.state.phase, "reply");
  assert.deepEqual([boardOf(reply.effects).fen, boardOf(reply.effects).interactive, boardOf(reply.effects).lastMove], [AFTER_QD8, false, "d2d8"]);
  const timer = scheduled(reply.effects);
  assert.equal(timer.delay, REPLY_DELAY_MS);
  const back = run([timer.event], reply.state);
  assert.deepEqual([back.state.phase, back.state.ply], ["yourMove", 3]);
  assert.deepEqual(boardOf(back.effects), {
    fen: AFTER_RXD8, lastMove: "c8d8", check: false, orientation: "white", interactive: true, legalMoves: ["d1d8", "g1f1"], hintSquare: null,
  });
});

test("solving records progress once; after Show solution a solve records nothing", () => {
  const sent = run([{ type: "playerMove", uci: "d2d8" }], yourMove());
  const done = run([{ type: "checkResult", data: { result: "solved", fen: MATED, check: true } }], sent.state);
  assert.deepEqual([done.state.phase, done.state.message.text, done.state.message.tone], ["solved", "Solved", "success"]);
  assert.deepEqual(done.effects.filter((effect) => effect.type === "progress"), [{ type: "progress", theme: "mateIn2", id: "Bk001" }]);
  assert.equal(boardOf(done.effects).interactive, false);
  const revealedState = { ...sent.state, revealed: true };
  const quiet = run([{ type: "checkResult", data: { result: "solved", fen: MATED, check: true } }], revealedState);
  assert.ok(!types(quiet.effects).includes("progress"), "a seen puzzle is not counted as solved");
  assert.deepEqual(run([{ type: "next" }], done.state).effects.map((effect) => effect.type), ["arrow", "next"]);
});

test("a wrong move is shown, then taken back after 600 ms, and can be retried without limit", () => {
  let state = yourMove();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const sent = run([{ type: "playerMove", uci: "d2d7" }], state);
    const wrong = run([{ type: "checkResult", data: { result: "wrong" } }], sent.state);
    assert.deepEqual([wrong.state.phase, wrong.state.message.text], ["wrong", TEXT.wrong]);
    const timer = scheduled(wrong.effects);
    assert.equal(timer.delay, WRONG_MS);
    assert.ok(!types(wrong.effects).includes("rejectMove"), "the wrong move stays visible first");
    const back = run([timer.event], wrong.state);
    assert.equal(back.state.phase, "yourMove");
    assert.equal(back.effects[0].type, "rejectMove");
    assert.equal(boardOf(back.effects).fen, AFTER_SETUP);
    state = back.state;
  }
  assert.equal(state.ply, 1, "still the same step");
});

test("a failed check takes the move back with no verdict; moves outside the player's turn are refused", () => {
  const sent = run([{ type: "playerMove", uci: "d2d8" }], yourMove());
  const failed = run([{ type: "checkError" }], sent.state);
  assert.deepEqual([failed.state.phase, failed.state.message.text], ["yourMove", "Couldn't check that move. Try again."]);
  assert.equal(failed.effects[0].type, "rejectMove");
  assert.equal(boardOf(failed.effects).interactive, true);
  assert.deepEqual(run([{ type: "playerMove", uci: "d2d8" }], sent.state).effects, [{ type: "rejectMove" }]);
  assert.deepEqual(run([{ type: "playerMove", uci: "d2d8" }], initialState()).effects, [{ type: "rejectMove" }]);
});

test("Hint first highlights the piece, then draws the arrow; a third press does nothing", () => {
  const first = run([{ type: "hint" }], yourMove());
  assert.deepEqual(first.effects, [{ type: "hint", ply: 1, level: "piece" }]);
  const piece = run([{ type: "hintResult", level: "piece", data: { from: "d2" } }], first.state);
  assert.deepEqual(piece.effects, [{ type: "setBoard", options: { hintSquare: "d2" } }]);
  assert.equal(piece.state.message.text, "Move the piece on d2.");
  assert.deepEqual(run([{ type: "hint" }], piece.state).effects, [{ type: "hint", ply: 1, level: "move" }]);
  const shown = run([{ type: "hintResult", level: "move", data: { uci: "d2d8" } }], piece.state);
  assert.deepEqual(shown.effects, [{ type: "arrow", uci: "d2d8", orientation: "white" }]);
  assert.deepEqual(run([{ type: "hint" }], shown.state).effects, [], "two steps only");
});

test("Show solution plays the line at 800 ms per move, ends as seen, and stale timers are ignored", () => {
  const asked = run([{ type: "showSolution" }], yourMove());
  assert.equal(asked.state.phase, "revealing");
  assert.ok(asked.effects.some((effect) => effect.type === "hint" && effect.level === "solution"));
  const data = { line: ["d2d8", "c8d8", "d1d8"], fens: [AFTER_QD8, AFTER_RXD8, MATED] };
  let step = run([{ type: "hintResult", level: "solution", data }], asked.state);
  const fens = [];
  for (let i = 0; i < 3; i += 1) {
    const timer = scheduled(step.effects);
    assert.equal(timer.delay, REVEAL_MS);
    assert.deepEqual(run([{ ...timer.event, seq: timer.event.seq - 1 }], step.state).effects, [], "an old timer does nothing");
    step = run([timer.event], step.state);
    fens.push(boardOf(step.effects).fen);
    assert.equal(boardOf(step.effects).interactive, false);
  }
  assert.deepEqual(fens, [AFTER_QD8, AFTER_RXD8, MATED]);
  assert.deepEqual([step.state.phase, step.state.message.text], ["seen", TEXT.seen]);
  assert.ok(!types(step.effects).includes("progress"));
  assert.throws(() => reduce(initialState(), { type: "fly" }), TypeError);
});
