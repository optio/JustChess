// Tests for the endgame trainer's pure texts and attempt storage, static/js/training/endgame-state.js (P2 U6, BR4.2).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ATTEMPT_KEY, TOO_FAST, UNAVAILABLE, clearAttempt, errorText, freshAttempt, loadAttempt, moveCounter, nextAttempt,
  saveAttempt, statusText, verdictMessage,
} from "../../static/js/training/endgame-state.js";

const ROOK = { id: "rook-cut-off", category: "rook-mate", title: "Cut the king off", goal: "mate", index: 1, count: 3,
  fen: "8/8/8/4k3/8/8/8/R3K3 w - - 0 1", legalMoves: ["a1a2", "e1e2"], side: "white", check: false };
const HOLD = { id: "opp-hold-the-opposition", category: "opposition", title: "Hold the opposition", goal: "draw",
  holdMoves: 30, index: 3, count: 3, fen: "8/8/3k4/8/4K3/4P3/8/8 b - - 0 1", legalMoves: ["d6e6"], side: "black" };

function memoryStorage() {
  const items = new Map();
  return {
    getItem: (key) => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: (key) => items.delete(key),
    items,
  };
}

function silenced(fn) {
  const original = console.error;
  const logged = [];
  console.error = (...args) => logged.push(args.join(" "));
  try {
    return { result: fn(), logged };
  } finally {
    console.error = original;
  }
}

test("the status names the goal and the place for mate, promote and draw positions", () => {
  assert.equal(statusText(ROOK), "Mate with the rook. Goal: checkmate. Position 1 of 3.");
  assert.equal(statusText({ ...ROOK, category: "queen-mate" }), "Mate with the queen. Goal: checkmate. Position 1 of 3.");
  assert.equal(statusText({ category: "king-pawn", goal: "promote", index: 2, count: 3 }),
    "King and pawn. Goal: promote the pawn. Position 2 of 3.");
  assert.equal(statusText(HOLD),
    "Use the opposition. Goal: hold the draw (30 moves, repetition or 50-move rule). Position 3 of 3.");
  assert.equal(statusText(null), "");
});

test("the move counter reads Move n of 30 and never passes the target", () => {
  assert.equal(moveCounter(0, 30), "Move 1 of 30");
  assert.equal(moveCounter(11, 30), "Move 12 of 30");
  assert.equal(moveCounter(30, 30), "Move 30 of 30");
  assert.equal(moveCounter(undefined, 10), "Move 1 of 10");
  assert.equal(moveCounter(3, null), "Move 4 of 30", "the default target");
});

test("passed verdicts say what was done, in how many moves", () => {
  assert.deepEqual(verdictMessage("mate", { status: "passed", reason: "checkmate", playerMoves: 14 }),
    { text: "Done! Mate in 14 moves.", tone: "success" });
  assert.deepEqual(verdictMessage("mate", { status: "passed", reason: "checkmate", playerMoves: 1 }),
    { text: "Done! Mate in 1 move.", tone: "success" });
  assert.equal(verdictMessage("promote", { status: "passed", reason: "promoted", playerMoves: 6 }).text,
    "Done! Pawn promoted in 6 moves.");
  for (const reason of ["held_moves", "threefold_repetition", "fifty_moves", "stalemate", "insufficient_material"]) {
    assert.equal(verdictMessage("draw", { status: "passed", reason, playerMoves: 30 }).text, "Done! Draw held.", reason);
  }
  assert.equal(verdictMessage("mate", { status: "playing", reason: null, playerMoves: 3 }), null, "nothing while playing");
});

test("failed verdicts say the computer escaped, or won when the player is mated", () => {
  for (const reason of ["stalemate", "threefold_repetition", "pawns_lost", "too_long", "insufficient_material"]) {
    assert.deepEqual(verdictMessage("mate", { status: "failed", reason, playerMoves: 9 }),
      { text: "The computer escaped. Start again.", tone: "warn" }, reason);
  }
  assert.equal(verdictMessage("draw", { status: "failed", reason: "player_mated", playerMoves: 9 }).text,
    "The computer won. Start again.");
});

test("an attempt survives a reload through session storage, for its own position only", () => {
  const storage = memoryStorage();
  const start = freshAttempt(ROOK);
  assert.deepEqual([start.moves, start.status, start.playerMoves, start.movesLeft], [[], "playing", 0, null]);
  const after = nextAttempt(start, "e1e2", { status: "playing", reason: null, reply: { uci: "e5d5", san: "Kd5" },
    playerMoves: 1, movesLeft: null, fen: "8/8/8/3k4/8/8/4K3/R7 w - - 2 2", legalMoves: ["a1a5"], check: false });
  assert.deepEqual(after.moves, ["e1e2", "e5d5"]);
  assert.equal(after.lastMove, "e5d5");
  assert.equal(saveAttempt(storage, after), true);
  assert.deepEqual(loadAttempt(storage, ROOK.id), after);
  assert.equal(loadAttempt(storage, "queen-first-steps"), null, "another position starts fresh");
  clearAttempt(storage);
  assert.equal(loadAttempt(storage, ROOK.id), null);
  assert.equal(freshAttempt(HOLD).movesLeft, 30, "a draw goal starts with the full count");
});

test("a storage error or a tampered attempt is logged and ignored, never thrown", () => {
  const broken = {
    getItem() { throw new Error("SecurityError"); },
    setItem() { throw new Error("QuotaExceededError"); },
    removeItem() { throw new Error("SecurityError"); },
  };
  const attempt = freshAttempt(ROOK);
  const saved = silenced(() => saveAttempt(broken, attempt));
  assert.equal(saved.result, false);
  assert.match(saved.logged[0], /could not be saved/);
  assert.equal(silenced(() => loadAttempt(broken, ROOK.id)).result, null);
  assert.doesNotThrow(() => silenced(() => clearAttempt(broken)));
  assert.equal(loadAttempt(null, ROOK.id), null, "no storage at all: no attempt");
  const storage = memoryStorage();
  storage.setItem(ATTEMPT_KEY, JSON.stringify({ ...attempt, moves: ["e1e2", "<script>"] }));
  assert.equal(loadAttempt(storage, ROOK.id), null, "a stored move that is not UCI is refused");
  storage.setItem(ATTEMPT_KEY, "{not json");
  assert.equal(silenced(() => loadAttempt(storage, ROOK.id)).result, null);
});

test("a 503 shows the server's unavailable or busy text, with a fallback", () => {
  assert.equal(errorText(503, "The computer is busy, try again in a moment"), "The computer is busy, try again in a moment");
  assert.equal(errorText(503, "No chess engine is installed"), "No chess engine is installed");
  assert.equal(errorText(503, ""), UNAVAILABLE);
  assert.equal(errorText(503, undefined), "The computer is not available right now");
});

test("a 429 asks the player to slow down; other failures keep their message", () => {
  assert.equal(errorText(429, "Too many requests. Try again shortly."), TOO_FAST);
  assert.equal(TOO_FAST, "Too many moves too fast. Wait a moment.");
  assert.equal(errorText(400, "Illegal move (move 3)"), "Illegal move (move 3)");
  assert.equal(errorText(0, ""), "Couldn't reach the server. Try again.");
  assert.equal(errorText(500, ""), "Something went wrong. Try again.");
});
