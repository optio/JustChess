// Tests for static/js/blunder.js (U4): the dialog text (BR3.2) and the move hook's decisions and
// failure mapping (BR3.1, BR3.4). The api, the settings, the dialog and the timers are fakes.
import { test } from "node:test";
import assert from "node:assert/strict";

import { CANCEL_LABEL, MATE_TITLE, createBlunderHook, dialogText, isCheckResult, moveWords } from "../../static/js/blunder.js";

const SNAPSHOT = Object.freeze({ code: "K7Q2PX", version: 4, turn: "white", colour: "white", status: "playing" });
const MATE = Object.freeze({ kind: "mate_in_one", move: "g4", mate: "Qh4#" });
const HANGING = Object.freeze({
  kind: "hanging_piece", move: "Ba3", piece: "bishop", square: "a3", capturer: { piece: "pawn", square: "b2" }, defended: false,
});
const DEFENDED = Object.freeze({
  kind: "hanging_piece", move: "Rd5", piece: "rook", square: "d5", capturer: { piece: "knight", square: "f6" }, defended: true,
});

function settingsWith(value) {
  return { get: (key) => (key === "blunderWarnings" ? value : undefined) };
}

/** A fake api answering checkMove from `answer` (a value or a function) and recording calls. */
function fakeApi(answer) {
  const calls = [];
  return {
    calls,
    checkMove: (...args) => {
      calls.push(args);
      return typeof answer === "function" ? answer(...args) : Promise.resolve(answer);
    },
  };
}

/** Timers fired by hand. */
function manualTimers() {
  const pending = new Map();
  let next = 1;
  return {
    pending,
    setTimeout: (fn, ms) => { pending.set(next, { fn, ms }); return next++; },
    clearTimeout: (id) => pending.delete(id),
    fireAll: () => { for (const [id, { fn }] of [...pending]) { pending.delete(id); fn(); } },
  };
}

function quietLogger() {
  const warnings = [];
  return { warnings, warn: (...args) => warnings.push(args.map(String).join(" ")) };
}

function makeHook({ answer, setting = true, choice = "confirm", timers = manualTimers(), settings } = {}) {
  const api = fakeApi(answer);
  const dialogs = [];
  const logger = quietLogger();
  const hook = createBlunderHook({
    api,
    settings: settings || settingsWith(setting),
    openDialog: async (text, context) => { dialogs.push({ text, context }); return choice; },
    timers,
    logger,
  });
  return { hook, api, dialogs, logger, timers };
}

const checked = (warning) => ({ ok: true, status: 200, data: { warning, san: warning ? warning.move : "e4", version: 4 } });

// --- dialog text ---------------------------------------------------------------

test("mate in one: the title names the consequence and the body names the mating move", () => {
  assert.deepEqual(dialogText(MATE, { opponent: "Black" }), {
    title: MATE_TITLE, body: "Black can play Qh4#.", confirmLabel: "Play g4 anyway", cancelLabel: CANCEL_LABEL,
  });
  assert.equal(CANCEL_LABEL, "Choose another move");
});

test("hanging piece: the body names the move in words, the capturer, the piece and its square", () => {
  assert.deepEqual(dialogText(HANGING, { opponent: "White" }), {
    title: "Your bishop can be taken for free",
    body: "After Bishop to a3, White's pawn on b2 takes your bishop on a3 and nothing takes back.",
    confirmLabel: "Play Ba3 anyway",
    cancelLabel: "Choose another move",
  });
  assert.equal(dialogText(DEFENDED, { opponent: "Black" }).body,
    "After Rook to d5, Black's knight on f6 takes your rook on d5 and you lose material.");
});

test("move words cover captures, pawns, promotion and castling; malformed warnings are refused", () => {
  assert.equal(moveWords("Nxe5+"), "Knight takes e5");
  assert.equal(moveWords("exd6"), "Pawn takes d6");
  assert.equal(moveWords("e8=Q"), "Pawn to e8, promoting to a queen");
  assert.equal(moveWords("O-O-O"), "Castling queenside");
  assert.throws(() => dialogText({ kind: "hanging_piece", move: "Ba3" }, { opponent: "White" }), TypeError);
  assert.throws(() => dialogText(MATE, { opponent: "Purple" }), TypeError);
  assert.equal(isCheckResult({ warning: null, san: "e4", version: 1 }), true);
  assert.equal(isCheckResult({ warning: { kind: "mate_in_one" }, san: "e4", version: 1 }), false);
});

// --- hook decisions --------------------------------------------------------------

test("setting off: the move goes ahead without asking the server", async () => {
  const { hook, api } = makeHook({ setting: false, answer: checked(MATE) });
  assert.equal(await hook("g2g4", SNAPSHOT), true);
  assert.deepEqual(api.calls, []);
});

test("no warning: the move goes ahead; the check carries code, move and version", async () => {
  const { hook, api, dialogs, timers } = makeHook({ answer: checked(null) });
  assert.equal(await hook("e2e4", SNAPSHOT), true);
  assert.deepEqual(api.calls[0].slice(0, 3), ["K7Q2PX", "e2e4", 4]);
  assert.ok(api.calls[0][3].signal, "the request can be aborted");
  assert.deepEqual(dialogs, []);
  assert.equal(timers.pending.size, 0, "the timeout is cleared");
});

test("a warning opens the dialog: confirm plays the move, cancel refuses it, superseded refuses with no message", async () => {
  const confirmed = makeHook({ answer: checked(MATE), choice: "confirm" });
  assert.equal(await confirmed.hook("g2g4", SNAPSHOT), true);
  assert.equal(confirmed.dialogs[0].text.title, MATE_TITLE);
  assert.equal(confirmed.dialogs[0].text.body, "Black can play Qh4#.", "White to move: the opponent is Black");
  assert.equal(confirmed.dialogs[0].context.uci, "g2g4");
  const cancelled = makeHook({ answer: checked(HANGING), choice: "cancel" });
  assert.equal(await cancelled.hook("c1a3", SNAPSHOT), false);
  const superseded = makeHook({ answer: checked(MATE), choice: "superseded" });
  assert.deepEqual(await superseded.hook("g2g4", SNAPSHOT), { allow: false });
});

test("a timeout aborts the request and the move goes ahead with a console warning", async () => {
  let signal = null;
  const timers = manualTimers();
  const { hook, logger } = makeHook({ timers, answer: (_c, _u, _v, opts) => { signal = opts.signal; return new Promise(() => {}); } });
  const pending = hook("g2g4", SNAPSHOT);
  await Promise.resolve();
  assert.equal([...timers.pending.values()][0].ms, 2500);
  timers.fireAll();
  assert.equal(await pending, true);
  assert.equal(signal.aborted, true);
  assert.match(logger.warnings[0], /no answer within 2500 ms/);
});

test("network failure, 404, 413, 422, 429 and 5xx all go ahead", async () => {
  for (const status of [0, 404, 413, 422, 429, 500, 503]) {
    const { hook, logger } = makeHook({ answer: { ok: false, status, message: "nope" } });
    assert.equal(await hook("g2g4", SNAPSHOT), true, `status ${status}`);
    assert.equal(logger.warnings.length, 1, `status ${status} is logged`);
  }
});

test("409 refuses with the newer snapshot and the message", async () => {
  const newer = { ...SNAPSHOT, version: 5 };
  const { hook } = makeHook({ answer: { ok: false, status: 409, message: "The board changed, here is the latest position", snapshot: newer } });
  assert.deepEqual(await hook("g2g4", SNAPSHOT), {
    allow: false, message: "The board changed, here is the latest position", snapshot: newer,
  });
});

test("400 and 403 refuse with the server's message", async () => {
  const turn = makeHook({ answer: { ok: false, status: 403, message: "Not your turn" } });
  assert.deepEqual(await turn.hook("g2g4", SNAPSHOT), { allow: false, message: "Not your turn" });
  const illegal = makeHook({ answer: { ok: false, status: 400, message: "Illegal move" } });
  assert.deepEqual(await illegal.hook("g2g5", SNAPSHOT), { allow: false, message: "Illegal move" });
});

test("a malformed 200, a throwing settings read or a broken dialog all go ahead; the hook never throws", async () => {
  const malformed = makeHook({ answer: { ok: true, status: 200, data: { warning: "mate!", san: "g4" } } });
  assert.equal(await malformed.hook("g2g4", SNAPSHOT), true);
  const throwing = makeHook({ answer: checked(MATE), settings: { get: () => { throw new Error("storage exploded"); } } });
  assert.equal(await throwing.hook("g2g4", SNAPSHOT), true);
  assert.deepEqual(throwing.api.calls, []);
  const logger = quietLogger();
  const broken = createBlunderHook({
    api: fakeApi(checked(MATE)), settings: settingsWith(true), openDialog: () => { throw new Error("no DOM"); }, timers: manualTimers(), logger,
  });
  assert.equal(await broken("g2g4", SNAPSHOT), true);
  assert.equal(logger.warnings.length, 1);
  const rejecting = makeHook({ answer: () => Promise.reject(new Error("fetch blew up")) });
  assert.equal(await rejecting.hook("g2g4", SNAPSHOT), true);
  assert.equal(await rejecting.hook("g2g4", null), true, "no snapshot: go ahead");
});
