// Tests for static/js/computer.js (P2 U4, BR5.4, BR8.2): names, status text, controls, retries, arrow, score;
// plus the computer parts of view-model.js and the live socket's computer and takeback events.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  RETRY_DELAY_MS,
  controlsFor,
  hintArrow,
  levelName,
  nextRetry,
  opponentLabel,
  scoreLine,
  shouldResume,
  statusText,
} from "../../static/js/computer.js";
import { createLive } from "../../static/js/live.js";
import { viewModel } from "../../static/js/view-model.js";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4_E5 = [{ number: 1, white: "e4", black: "e5" }];

/** A computer-room snapshot for seat A, as the server sends it (BR7.1). */
function snap(overrides = {}, computer = {}) {
  return {
    code: "ABC123",
    game: 1,
    fen: START,
    turn: "white",
    status: "playing",
    endReason: null,
    result: null,
    check: false,
    moveList: AFTER_E4_E5,
    lastMove: "e7e5",
    version: 2,
    claimableDraw: false,
    claimableDrawReason: null,
    seats: { A: { presence: "connected", colour: "white" }, B: { presence: "computer", colour: "black" } },
    score: { A: 2, B: 3, draws: 1 },
    rematch: { state: "none", requestedBy: null },
    slot: "A",
    colour: "white",
    legalMoves: ["d2d4"],
    mode: "computer",
    computerLevel: "club",
    computer: { state: "idle", queuePosition: null, reason: null, level: "club", available: true, message: null, ...computer },
    ...overrides,
  };
}

test("level names and the opponent label", () => {
  assert.deepEqual(["beginner", "casual", "club", "strong", "maximum"].map(levelName), ["Beginner", "Casual", "Club", "Strong", "Maximum"]);
  assert.equal(levelName("grandmaster"), "Unknown level");
  assert.equal(opponentLabel("strong"), "Computer · Strong");
});

test("status text for queued, thinking and unavailable; none when idle", () => {
  assert.equal(statusText({ state: "queued", queuePosition: 3 }), "Waiting for the computer… (3 ahead)");
  assert.equal(statusText({ state: "thinking" }), "Computer is thinking…");
  assert.equal(statusText({ state: "unavailable", reason: "The computer stopped working" }),
    "The computer can't move right now: The computer stopped working. You can still look through the game.");
  assert.equal(statusText({ state: "idle" }), null);
  assert.equal(statusText(null), null);
});

test("takeback needs the player's turn, a player move, an idle computer and a playing game", () => {
  assert.equal(controlsFor(snap()).takeback.enabled, true);
  assert.equal(controlsFor(snap({ moveList: [] })).takeback.enabled, false, "nothing played yet");
  assert.equal(controlsFor(snap({ turn: "black" }, { state: "thinking" })).takeback.enabled, false, "a reply is in flight");
  assert.equal(controlsFor(snap({ status: "finished" })).takeback.enabled, false);
  const down = snap({ turn: "black", moveList: [{ number: 1, white: "e4", black: null }] }, { state: "unavailable", available: false });
  assert.equal(controlsFor(down).takeback.enabled, true, "the computer can't answer: the player's move can go back");
  const blackPlayer = snap({ colour: "black", moveList: [{ number: 1, white: "e4", black: null }], turn: "black" });
  assert.equal(controlsFor(blackPlayer).takeback.enabled, false, "only the computer has moved");
});

test("hint is enabled on the player's turn while available and no hint is pending", () => {
  assert.equal(controlsFor(snap()).hint.enabled, true);
  assert.equal(controlsFor(snap(), { hintPending: true }).hint.enabled, false);
  assert.equal(controlsFor(snap({ turn: "black" }, { state: "thinking" })).hint.enabled, false);
  assert.equal(controlsFor(snap({}, { state: "unavailable", available: false })).hint.enabled, false);
  assert.equal(controlsFor(snap({ status: "finished" })).hint.enabled, false);
});

test("resign while playing; no controls for watchers or friend rooms", () => {
  assert.deepEqual(controlsFor(snap()).resign, { show: true, enabled: true });
  assert.deepEqual(controlsFor(snap({ status: "finished" })).resign, { show: true, enabled: false });
  const hidden = { show: false, enabled: false };
  assert.deepEqual(controlsFor(snap(), { watching: true }), { takeback: hidden, hint: hidden, resign: hidden });
  assert.deepEqual(controlsFor(snap({ mode: "online", computer: null })).resign, hidden);
  assert.deepEqual(controlsFor(snap({ slot: null })).hint, hidden);
});

test("resume: computer to move and idle; at most 3 retries, 5 s apart", () => {
  assert.equal(shouldResume(snap({ turn: "black" })), true);
  assert.equal(shouldResume(snap({ turn: "black" }, { state: "thinking" })), false);
  assert.equal(shouldResume(snap()), false, "the player's turn");
  assert.equal(shouldResume(snap({ turn: "black" }, { state: "unavailable", available: false })), false);
  assert.deepEqual(nextRetry({ attempts: 0, lastAttemptAt: null, now: 1000 }), { action: "call", delayMs: 0 });
  assert.deepEqual(nextRetry({ attempts: 1, lastAttemptAt: 1000, now: 3000 }), { action: "wait", delayMs: 3000 });
  assert.deepEqual(nextRetry({ attempts: 1, lastAttemptAt: 1000, now: 1000 + RETRY_DELAY_MS }), { action: "call", delayMs: 0 });
  assert.equal(nextRetry({ attempts: 3, lastAttemptAt: 0, now: 99_999 }).action, "call", "the third retry");
  assert.deepEqual(nextRetry({ attempts: 4, lastAttemptAt: 0, now: 99_999 }), { action: "give-up", delayMs: 0 });
});

test("the hint arrow runs between square centres for either orientation", () => {
  const white = hintArrow({ from: "e2", to: "e4" }, "white");
  assert.deepEqual(white.shaft, { x1: 56.25, y1: 81.25, x2: 56.25, y2: 61.25 });
  assert.deepEqual(white.head[0], [56.25, 56.25], "the tip is on e4's centre");
  const black = hintArrow({ from: "e2", to: "e4" }, "black");
  assert.deepEqual(black.shaft, { x1: 43.75, y1: 18.75, x2: 43.75, y2: 38.75 });
  assert.deepEqual(black.head[0], [43.75, 43.75]);
  assert.equal(hintArrow(null, "white"), null);
  assert.throws(() => hintArrow({ from: "e2", to: "e4" }, "sideways"), TypeError);
});

test("the score line counts the player against the computer", () => {
  assert.equal(scoreLine({ A: 2, B: 3, draws: 1 }), "This level: You 2 · Computer 3 · Draws 1");
  assert.equal(scoreLine(null), "This level: You 0 · Computer 0 · Draws 0");
});

test("the view model of a computer room: label, statuses, no claims, no share, no moves while unavailable", () => {
  const view = viewModel(snap({ claimableDraw: true, claimableDrawReason: "threefold" }));
  assert.equal(view.players.black, "Computer · Club");
  assert.equal(view.score.line, "This level: You 2 · Computer 3 · Draws 1");
  assert.equal(view.claims.draw, null);
  assert.equal(view.computer.label, "Computer · Club");
  const thinking = viewModel(snap({ turn: "black" }, { state: "thinking" }));
  assert.equal(thinking.status.text, "Computer is thinking…");
  const down = viewModel(snap({}, { state: "unavailable", available: false, reason: "No chess engine is installed" }));
  assert.equal(down.board.interactive, false);
  assert.match(down.status.text, /^The computer can't move right now: No chess engine is installed\./);
  const over = viewModel(snap({ status: "finished", endReason: "resigned", result: "0-1" }));
  assert.equal(over.overlay.title, "You lost");
  assert.equal(over.overlay.share, false);
  assert.equal(over.overlay.rematch, "offer", "the result card offers Play again");
  const hinted = viewModel(snap(), { hint: { from: "d2", to: "d4", san: "d4", version: 2 } });
  assert.deepEqual(hinted.computer.hint, { from: "d2", to: "d4", san: "d4" });
  assert.equal(viewModel(snap({ version: 3 }), { hint: { from: "d2", to: "d4", version: 2 } }).computer.hint, null, "a new version clears it");
  assert.equal(viewModel(snap({ mode: "online", computer: null, computerLevel: null })).computer, null);
});

test("the live socket passes computer and takeback events on", () => {
  const sockets = [];
  class FakeSocket {
    constructor() {
      this.readyState = 0;
      sockets.push(this);
    }
    send() {}
    close() {}
  }
  const events = [];
  const timers = { setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {} };
  const live = createLive({
    url: "ws://localhost/ws/ABC123",
    WebSocketImpl: FakeSocket,
    timers,
    visibility: null,
    onComputer: (event) => events.push(["computer", event]),
    onTakeback: () => events.push(["takeback"]),
  });
  const socket = sockets[0];
  socket.readyState = 1;
  socket.onopen();
  socket.onmessage({ data: JSON.stringify({ type: "computer", state: "queued", queuePosition: 2 }) });
  socket.onmessage({ data: JSON.stringify({ type: "computer", state: "thinking", queuePosition: null }) });
  socket.onmessage({ data: JSON.stringify({ type: "computer", state: "nonsense" }) });
  socket.onmessage({ data: JSON.stringify({ type: "takeback" }) });
  live.close();
  assert.deepEqual(events, [
    ["computer", { state: "queued", queuePosition: 2 }],
    ["computer", { state: "thinking", queuePosition: null }],
    ["takeback"],
  ]);
});
