// P2 U3 pass-along and join-request logic (static/js/pass-along.js) and the view model's
// pass-along branch (static/js/view-model.js). Timers and the network call are fakes.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  JOINER_TEXT,
  POLL_MS,
  PRACTICE_NOTE,
  STAND_IN_NOTE,
  bannerText,
  controlsFor,
  countdownText,
  createJoinerPoller,
  initialJoinerState,
  joinerReduce,
  refusalKind,
  requestDeadline,
  shouldPoll,
  waitingText,
} from "../../static/js/pass-along.js";
import { viewModel } from "../../static/js/view-model.js";

const BASE = {
  code: "K7Q2PX", game: 1, version: 3, status: "playing", turn: "black", fen: "x", check: false,
  moveList: [{ number: 1, white: "e4", black: null }], slot: "A", colour: "white", mode: "pass_along",
  counted: false, legalMoves: ["e7e5", "d7d5"], joinRequest: null,
  seats: { A: { presence: "connected", colour: "white" }, B: { presence: "empty", colour: "black" } },
};

/** Fake timers: run() fires the pending callbacks in order. */
function fakeTimers() {
  const pending = new Map();
  let next = 1;
  return {
    pending,
    setTimer: (fn, delay) => { const id = next++; pending.set(id, { fn, delay }); return id; },
    clearTimer: (id) => pending.delete(id),
    async run() {
      const due = [...pending.entries()];
      pending.clear();
      for (const [, { fn }] of due) await fn();
    },
  };
}

test("controls: Play here for seat A while waiting alone; Wait for a friend and the note in pass-along; nothing otherwise", () => {
  const none = { playHere: false, playComputer: false, switchTo: null, waitForFriend: false, practiceNote: false, note: null };
  assert.deepEqual(controlsFor({ ...BASE, mode: "waiting" }), { ...none, playHere: true, playComputer: true });
  assert.deepEqual(controlsFor(BASE), { ...none, waitForFriend: true, practiceNote: true, note: PRACTICE_NOTE });
  const standIn = { ...BASE, mode: "computer", standIn: true, seats: { ...BASE.seats, B: { presence: "computer", colour: "black" } } };
  assert.deepEqual(controlsFor(standIn), { ...none, waitForFriend: true, practiceNote: true, note: STAND_IN_NOTE });
  assert.deepEqual(controlsFor({ ...standIn, standIn: false }), none, "a lobby computer room has no friend to wait for");
  const joined = { ...BASE, mode: "online", seats: { ...BASE.seats, B: { presence: "connected", colour: "black" } } };
  assert.deepEqual(controlsFor(joined), none);
  // Switching sides follows the server's canSwitchSides flag.
  assert.equal(controlsFor({ ...BASE, mode: "waiting", canSwitchSides: true }).switchTo, "black");
  assert.equal(controlsFor({ ...standIn, colour: "black", canSwitchSides: true }).switchTo, "white");
  assert.equal(controlsFor({ ...standIn, standIn: false, canSwitchSides: true }).switchTo, "black", "a lobby computer room too");
  assert.equal(controlsFor({ ...BASE, mode: "waiting", canSwitchSides: false }).switchTo, null);
  assert.equal(controlsFor({ ...BASE, slot: "B" }).waitForFriend, false, "only the creator");
  assert.equal(controlsFor({ ...BASE, mode: "waiting" }, { watching: true }).playHere, false, "never a watcher");
  assert.equal(controlsFor(null).playHere, false);
});

test("countdown and banner text, and the deadline from expiresIn against this device's clock", () => {
  assert.equal(countdownText(581), "9:41");
  assert.equal(countdownText(600), "10:00");
  assert.equal(countdownText(0.2), "0:01", "a part second still shows as a second left");
  assert.equal(countdownText(-5), "0:00");
  assert.equal(bannerText("black", 581),
    "Someone wants to join as Black. They will take over Black from this position. Expires in 9:41.");
  assert.equal(requestDeadline({ expiresAt: 9e9, expiresIn: 600 }, 1_000), 601_000);
  assert.equal(requestDeadline(null, 1_000), null);
});

test("the joiner's state machine: pending keeps waiting, a final answer sticks, hidden pauses polling", () => {
  let state = initialJoinerState();
  assert.equal(shouldPoll(state), true);
  state = joinerReduce(state, { type: "status", status: "pending" });
  assert.equal(state.phase, "waiting");
  state = joinerReduce(state, { type: "hidden" });
  assert.equal(shouldPoll(state), false);
  state = joinerReduce(state, { type: "visible" });
  state = joinerReduce(state, { type: "status", status: "declined" });
  assert.equal(state.phase, "declined");
  assert.equal(joinerReduce(state, { type: "status", status: "accepted" }), state, "a final answer never changes");
  assert.equal(shouldPoll(state), false);
  assert.equal(joinerReduce(initialJoinerState(), { type: "status", status: "weird" }).phase, "waiting");
  assert.throws(() => joinerReduce(initialJoinerState(), { type: "nope" }), TypeError);
});

test("the poller asks every 3 s, keeps waiting through a network failure and stops on the answer", async () => {
  const timers = fakeTimers();
  const answers = [{ ok: true, data: { status: "pending" } }, { ok: false, status: 0 }, { ok: true, data: { status: "accepted" } }];
  const changes = [];
  let calls = 0;
  const poller = createJoinerPoller({ check: async () => answers[calls++], onChange: (s) => changes.push(s.phase), ...timers });
  poller.start();
  assert.equal([...timers.pending.values()][0].delay, 0, "the first poll is immediate");
  await timers.run();
  assert.equal([...timers.pending.values()][0].delay, POLL_MS);
  await timers.run();
  await timers.run();
  assert.equal(calls, 3);
  assert.deepEqual(changes, ["accepted"]);
  assert.equal(timers.pending.size, 0, "no more polling after the answer");
});

test("a hidden page stops polling and a visible one resumes at once", async () => {
  const timers = fakeTimers();
  let calls = 0;
  const poller = createJoinerPoller({ check: async () => { calls += 1; return { ok: true, data: { status: "pending" } }; }, ...timers });
  poller.start();
  poller.setHidden(true);
  assert.equal(timers.pending.size, 0, "nothing scheduled while hidden");
  await timers.run();
  assert.equal(calls, 0);
  poller.setHidden(false);
  assert.equal([...timers.pending.values()][0].delay, 0);
  await timers.run();
  assert.equal(calls, 1);
  poller.stop();
  assert.equal(timers.pending.size, 0);
  assert.throws(() => createJoinerPoller({}), TypeError);
});

test("refusals map to the joiner's messages", () => {
  assert.equal(refusalKind({ ok: false, status: 409, error: "busy" }), "busy");
  assert.equal(refusalKind({ ok: false, status: 409, error: "declined_recently" }), "declined_recently");
  assert.equal(refusalKind({ ok: false, status: 429, error: "too_many" }), "too_many");
  assert.equal(refusalKind({ ok: false, status: 409, message: "This game already has two players" }), null, "room full stays room full");
  assert.equal(refusalKind({ ok: true, status: 202 }), null);
  assert.equal(JOINER_TEXT.busy, "Someone else is already asking to join. Try again in a few minutes.");
  assert.equal(JOINER_TEXT.too_many, "Too many requests. Try again shortly.");
  assert.equal(JOINER_TEXT.lapsed, "Nobody answered. Try again later.");
  assert.equal(JOINER_TEXT.declined, "The creator declined. You can ask again later.");
  assert.equal(waitingText("white"), "Waiting for the creator to accept. You'll play White from the current position.");
  assert.equal(waitingText("black"), JOINER_TEXT.waiting);
  assert.equal(waitingText(null), "Waiting for the creator to accept. You'll play from the current position.", "after a reload");
});

test("view model: seat A in pass-along always has the move, in baize, with the banner facts; a practice game over says so", () => {
  const view = viewModel({ ...BASE, joinRequest: { expiresAt: 123, expiresIn: 581 } });
  assert.equal(view.yourMove, true);
  assert.deepEqual([view.board.interactive, view.board.legalMoves], [true, ["e7e5", "d7d5"]]);
  assert.deepEqual([view.status.text, view.status.tone], ["Pass-along: Black to move", "baize"]);
  assert.deepEqual(view.joinRequest, { colour: "black", expiresAt: 123, expiresIn: 581 });
  assert.equal(viewModel({ ...BASE, joinRequest: { expiresAt: 1, expiresIn: 5 } }, { watching: true }).joinRequest, null);

  const waiting = viewModel({ ...BASE, mode: "waiting" });
  assert.deepEqual([waiting.yourMove, waiting.board.interactive], [false, false], "back to waiting: Black's side locks");
  const over = viewModel({ ...BASE, status: "finished", result: "0-1", endReason: "checkmate", legalMoves: [] });
  assert.deepEqual([over.status.text, over.status.sub], ["Practice game over", "Checkmate. Black wins."]);
});
