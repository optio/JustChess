// Tests for the pure trainer reducer static/js/training/trainer-state.js (BR3.1, BR4.1-BR4.5).
// The lesson fixture has the shape GET /api/lessons/{id} returns: 1.e4 e5 2.Nf3, learner White.
import { test } from "node:test";
import assert from "node:assert/strict";

import { initialState, isLesson, moveLabel, reduce, TEXT } from "../../static/js/training/trainer-state.js";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
const AFTER_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2";
const AFTER_NF3 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2";
const AFTER_D4 = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1";

function lesson() {
  return {
    id: "mini",
    name: "Mini Opening",
    aliases: [],
    eco: null,
    side: "white",
    start: "startpos",
    objectives: ["Take the centre."],
    steps: [
      { ply: 0, side: "white", san: "e4", uci: "e2e4", note: "Take the centre.", fenBefore: START, fenAfter: AFTER_E4,
        legalBefore: ["b1c3", "d2d4", "e2e3", "e2e4", "g1f3"], alternatives: [] },
      { ply: 1, side: "black", san: "e5", uci: "e7e5", note: "Black answers.", fenBefore: AFTER_E4, fenAfter: AFTER_E5,
        legalBefore: ["c7c5", "d7d5", "e7e5", "e7e6", "g8f6"], alternatives: [] },
      { ply: 2, side: "white", san: "Nf3", uci: "g1f3", note: "Attack e5.", fenBefore: AFTER_E5, fenAfter: AFTER_NF3,
        legalBefore: ["b1c3", "d2d4", "f1c4", "g1f3"], alternatives: [] },
    ],
  };
}

/** Run events from state; returns the final state, the last event's effects, and every effect. */
function run(events, state = initialState()) {
  let current = state;
  let effects = [];
  const all = [];
  for (const event of events) {
    ({ state: current, effects } = reduce(current, event));
    all.push(...effects);
  }
  return { state: current, effects, all };
}

const loaded = () => run([{ type: "lessonLoaded", lesson: lesson() }]).state;
const practising = (side = "white") => run([{ type: "startPractice", side }], loaded()).state;
const boardOf = (effects) => effects.find((effect) => effect.type === "setBoard")?.options;
const types = (effects) => effects.map((effect) => effect.type);

test("a loaded lesson opens the walkthrough at move 0 from the lesson side; a broken one is refused", () => {
  const { state, effects } = run([{ type: "lessonLoaded", lesson: lesson() }]);
  assert.equal(state.phase, "walkthrough");
  assert.equal(state.index, 0);
  assert.equal(state.side, "white");
  assert.deepEqual(boardOf(effects), {
    fen: START, lastMove: null, check: false, orientation: "white", interactive: false, legalMoves: [], hintSquare: null,
  });
  assert.equal(state.message.text, TEXT.walkStart);
  const broken = run([{ type: "lessonLoaded", lesson: { ...lesson(), steps: [] } }]);
  assert.equal(broken.state.phase, "choosing");
  assert.equal(broken.state.message.text, TEXT.unreadable);
  assert.equal(isLesson(lesson()), true);
  assert.equal(moveLabel(lesson().steps[1]), "1… e5");
});

test("walkthrough: Next plays each step with its note, Back and Restart go back, both ends are limits", () => {
  const start = loaded();
  assert.deepEqual(run([{ type: "back" }], start).effects, [], "Back is disabled at the start");
  const first = run([{ type: "next" }], start);
  assert.equal(first.state.index, 1);
  assert.deepEqual([boardOf(first.effects).fen, boardOf(first.effects).lastMove], [AFTER_E4, "e2e4"]);
  assert.equal(first.state.message.text, "1. e4: Take the centre.");
  const end = run([{ type: "next" }, { type: "next" }], first.state).state;
  assert.equal(end.index, 3);
  assert.deepEqual(run([{ type: "next" }], end).effects, [], "Next is disabled at the end");
  const back = run([{ type: "back" }], end);
  assert.deepEqual([back.state.index, boardOf(back.effects).fen, boardOf(back.effects).lastMove], [2, AFTER_E5, "e7e5"]);
  const restarted = run([{ type: "restart" }], end);
  assert.deepEqual([restarted.state.index, boardOf(restarted.effects).fen], [0, START]);
  assert.equal(boardOf(restarted.effects).interactive, false, "the walkthrough board is never interactive");
});

test("practice on the learner's ply makes the board interactive with that step's legal moves", () => {
  const { state, effects } = run([{ type: "startPractice" }], loaded());
  assert.deepEqual([state.phase, state.index, state.side, state.trainerPending], ["practice", 0, "white", null]);
  const board = boardOf(effects);
  assert.equal(board.interactive, true);
  assert.deepEqual(board.legalMoves, lesson().steps[0].legalBefore);
  assert.ok(!types(effects).includes("scheduleTrainer"));
});

test("a correct move is played with its note, then the trainer replies on its timer; a stale timer is ignored", () => {
  const correct = run([{ type: "learnerMove", uci: "e2e4" }], practising());
  assert.equal(correct.state.index, 1);
  assert.equal(correct.state.message.text, "Correct. 1. e4: Take the centre.");
  assert.deepEqual([boardOf(correct.effects).fen, boardOf(correct.effects).interactive], [AFTER_E4, false]);
  const schedule = correct.effects.find((effect) => effect.type === "scheduleTrainer");
  assert.ok(schedule, "the trainer's reply is scheduled");
  assert.equal(correct.state.trainerPending, schedule.seq);

  assert.deepEqual(run([{ type: "trainerMove", seq: schedule.seq + 5 }], correct.state).effects, [], "a stale timer does nothing");
  const reply = run([{ type: "trainerMove", seq: schedule.seq }], correct.state);
  assert.deepEqual([reply.state.index, reply.state.trainerPending], [2, null]);
  assert.equal(reply.state.message.text, "Black plays 1… e5: Black answers.");
  const board = boardOf(reply.effects);
  assert.deepEqual([board.fen, board.lastMove, board.interactive], [AFTER_E5, "e7e5", true]);
  assert.deepEqual(board.legalMoves, lesson().steps[2].legalBefore);
  assert.ok(!types(reply.effects).includes("cancelTrainer"), "a timer that fired is not cancelled");
});

test("illegal taps count misses; the third miss draws the arrow with the SAN and note; the step resets them", () => {
  const once = run([{ type: "rejectedTap", from: "e2", to: "e5" }], practising());
  assert.deepEqual([once.state.misses, once.state.message.text, once.state.arrow], [1, "That move isn't legal.", null]);
  assert.deepEqual(once.effects, [{ type: "arrow", uci: null, orientation: "white" }]);
  const thrice = run([{ type: "rejectedTap" }, { type: "rejectedTap" }], once.state);
  assert.deepEqual([thrice.state.misses, thrice.state.arrow], [3, "e2e4"]);
  assert.equal(thrice.state.message.text, "The move is e4. Take the centre.");
  assert.deepEqual(thrice.effects, [{ type: "arrow", uci: "e2e4", orientation: "white" }]);
  const played = run([{ type: "learnerMove", uci: "e2e4" }], thrice.state);
  assert.deepEqual([played.state.misses, played.state.arrow], [0, null]);
  assert.ok(played.effects.some((effect) => effect.type === "arrow" && effect.uci === null), "the arrow is removed");
  assert.deepEqual(run([{ type: "rejectedTap" }], loaded()).effects, [], "taps outside practice are ignored");
});

test("Hint highlights the from-square on a learner ply, and says it in words", () => {
  const { state, effects } = run([{ type: "hint" }], practising());
  assert.equal(state.hintShown, true);
  assert.equal(state.message.text, "Move the piece on e2.");
  assert.deepEqual(effects, [{ type: "setBoard", options: { hintSquare: "e2" } }]);
  assert.deepEqual(run([{ type: "hint" }], loaded()).effects, [], "no hint in the walkthrough");
});

test("a legal move off the line is shown and locks the board; Back to the line restores the step with the misses kept", () => {
  const off = run([{ type: "learnerMove", uci: "d2d4" }], practising());
  assert.deepEqual([off.state.phase, off.state.misses, off.state.message.text], ["offLine", 1, "Legal, but not this line"]);
  assert.deepEqual(off.effects[0], { type: "positionMove", fen: START, uci: "d2d4" });
  const shown = run([{ type: "positionResult", data: { fen: AFTER_D4, san: "d4", legalMoves: ["d7d5"], check: false, outcome: null } }], off.state);
  assert.deepEqual(boardOf(shown.effects), { fen: AFTER_D4, lastMove: "d2d4", check: false, interactive: false, legalMoves: [], hintSquare: null });
  const back = run([{ type: "backToLine" }], shown.state);
  assert.deepEqual([back.state.phase, back.state.index, back.state.misses], ["practice", 0, 1]);
  assert.deepEqual(boardOf(back.effects), {
    fen: START, lastMove: null, check: false, orientation: "white", interactive: true, legalMoves: lesson().steps[0].legalBefore, hintSquare: null,
  });
  const failed = run([{ type: "learnerMove", uci: "d2d4" }, { type: "positionError", message: "Couldn't reach the server. Try again." }], practising());
  assert.deepEqual([failed.state.phase, failed.state.message.text], ["practice", "Couldn't reach the server. Try again."]);
  assert.equal(boardOf(failed.effects).fen, START, "an error restores the lesson position");
});

test("free play: moves go to /api/position/move, an outcome locks the board, an error slides back, the way back aborts", () => {
  const offered = run([
    { type: "learnerMove", uci: "d2d4" },
    { type: "positionResult", data: { fen: AFTER_D4, san: "d4", legalMoves: ["d7d5", "g8f6"], check: false, outcome: null } },
    { type: "keepPlaying" },
  ], practising());
  assert.equal(offered.state.phase, "freePlay");
  assert.equal(offered.state.message.text, TEXT.free);
  assert.deepEqual([boardOf(offered.effects).interactive, boardOf(offered.effects).legalMoves], [true, ["d7d5", "g8f6"]]);

  const moved = run([{ type: "learnerMove", uci: "g8f6" }], offered.state);
  assert.deepEqual(moved.effects, [{ type: "positionMove", fen: AFTER_D4, uci: "g8f6" }]);
  const mate = run([{ type: "positionResult", data: { fen: "mated", san: "Nf6", legalMoves: [], check: true, outcome: "checkmate" } }], moved.state);
  assert.deepEqual([boardOf(mate.effects).interactive, mate.state.message.text], [false, "Checkmate."]);

  const refused = run([{ type: "positionError", message: "Illegal move" }], moved.state);
  assert.deepEqual(refused.effects, [{ type: "rejectMove" }]);
  assert.equal(refused.state.free.fen, AFTER_D4, "the last position is kept");

  const abandoned = run([{ type: "backToLine" }], moved.state);
  assert.equal(abandoned.effects[0].type, "abortRequest", "the request in flight is aborted");
  assert.deepEqual([abandoned.state.phase, abandoned.state.index, abandoned.state.misses], ["practice", 0, 1]);
});

test("switching to Black restarts practice with the board turned and the trainer's first ply scheduled", () => {
  const { state, effects } = run([{ type: "switchSide", side: "black" }], practising("white"));
  assert.deepEqual([state.side, state.index, state.misses], ["black", 0, 0]);
  const board = boardOf(effects);
  assert.deepEqual([board.orientation, board.interactive], ["black", false]);
  const schedule = effects.find((effect) => effect.type === "scheduleTrainer");
  assert.ok(schedule);
  const reply = run([{ type: "trainerMove", seq: schedule.seq }], state);
  assert.equal(reply.state.index, 1);
  assert.equal(reply.state.message.text, "White plays 1. e4: Take the centre.");
  assert.deepEqual([boardOf(reply.effects).interactive, boardOf(reply.effects).legalMoves], [true, lesson().steps[1].legalBefore]);
});

test("the last step completes the line; Practise again and the other side restart practice", () => {
  let state = practising();
  state = run([{ type: "learnerMove", uci: "e2e4" }], state).state;
  state = run([{ type: "trainerMove", seq: state.trainerPending }], state).state;
  const done = run([{ type: "learnerMove", uci: "g1f3" }], state);
  assert.equal(done.state.phase, "complete");
  assert.equal(done.state.message.text, "Line complete. The last move was 2. Nf3.");
  assert.equal(boardOf(done.effects).interactive, false);
  assert.ok(!types(done.effects).includes("scheduleTrainer"));
  assert.deepEqual(run([{ type: "startPractice" }], done.state).state.phase, "practice");
  assert.equal(run([{ type: "startPractice", side: "black" }], done.state).state.side, "black");
});

test("P2 U5: completing practice emits one progress effect, and a run with the arrow still counts", () => {
  let state = practising();
  state = run([{ type: "rejectedTap" }, { type: "rejectedTap" }, { type: "rejectedTap" }], state).state;
  assert.equal(state.arrowShown, true, "the third miss drew the arrow");
  state = run([{ type: "learnerMove", uci: "e2e4" }], state).state;
  assert.equal(state.arrowShown, true, "the flag lasts for the whole run");
  state = run([{ type: "trainerMove", seq: state.trainerPending }], state).state;
  const done = run([{ type: "learnerMove", uci: "g1f3" }], state);
  assert.deepEqual(done.effects.filter((effect) => effect.type === "progress"),
    [{ type: "progress", lessonId: "mini", kind: "opening", arrowShown: true }]);
  const again = run([{ type: "startPractice" }], done.state).state;
  assert.equal(again.arrowShown, false, "Practise again starts a clean run");
  const walk = run([{ type: "next" }, { type: "next" }, { type: "next" }], loaded());
  assert.ok(!walk.effects.some((effect) => effect.type === "progress"), "the walkthrough alone records nothing");
});

test("Other lessons leaves every phase for the list", () => {
  const offLine = run([{ type: "learnerMove", uci: "d2d4" }], practising()).state;
  const free = run([
    { type: "positionResult", data: { fen: AFTER_D4, san: "d4", legalMoves: ["d7d5"], check: false, outcome: null } },
    { type: "keepPlaying" },
  ], offLine).state;
  const phases = { walkthrough: loaded(), practice: practising(), offLine, freePlay: free };
  for (const [name, state] of Object.entries(phases)) {
    assert.equal(state.phase, name);
    const { state: next, effects } = run([{ type: "otherLessons" }], state);
    assert.equal(next.phase, "choosing", `${name} -> choosing`);
    assert.equal(next.lesson, null);
    assert.ok(types(effects).includes("showList"), `${name} shows the list`);
  }
  assert.ok(types(run([{ type: "otherLessons" }], offLine).effects).includes("abortRequest"), "the off-line request is aborted");
});

test("leaving practice cancels the trainer's reply timer, and a cancelled timer firing late does nothing", () => {
  const waiting = run([{ type: "learnerMove", uci: "e2e4" }], practising()).state;
  const seq = waiting.trainerPending;
  for (const event of [{ type: "otherLessons" }, { type: "startPractice" }, { type: "switchSide", side: "black" }]) {
    const { effects } = run([event], waiting);
    assert.equal(effects[0].type, "cancelTrainer", `${event.type} cancels the timer first`);
  }
  const restarted = run([{ type: "startPractice" }], waiting).state;
  assert.deepEqual(run([{ type: "trainerMove", seq }], restarted).effects, [], "the old timer is ignored");
  assert.deepEqual(run([{ type: "learnerMove", uci: "e7e5" }], waiting).effects, [{ type: "rejectMove" }],
    "no learner move is accepted on the trainer's ply");
  assert.throws(() => reduce(initialState(), { type: "fly" }), TypeError);
});
