// Tests for static/js/notify-core.js (U5: BR1.1 keys on the client, BR3.2 decision table, BR3.3 worker logic).
// The expected keys are the ones tests/test_notifications.py and tests/test_push_api.py pin on the server.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

import {
  decide,
  endText,
  eventFor,
  notificationFromPush,
  plyCount,
  swDecision,
} from "../../static/js/notify-core.js";

const CODE = "ROOM01";
const ORIGIN = "https://chess.example";

/** A snapshot shaped like U1's (games.GameView.snapshot), with only the fields the logic reads. */
function snap({ game = 1, status = "playing", sans = [], endReason = null, result = null, bPresence = "connected",
  slot = "A", aColour = "white", code = CODE } = {}) {
  const moveList = [];
  sans.forEach((san, i) => {
    if (i % 2 === 0) moveList.push({ number: i / 2 + 1, white: san, black: null });
    else moveList[moveList.length - 1].black = san;
  });
  const bColour = aColour === "white" ? "black" : "white";
  return {
    code, game, status, endReason, result, moveList,
    turn: sans.length % 2 === 0 ? "white" : "black",
    seats: { A: { presence: "connected", colour: aColour }, B: { presence: bPresence, colour: bColour } },
    slot,
  };
}

test("join: seat A gets 'joined' when seat B leaves empty in game 1; seat B and watchers get nothing", () => {
  const before = snap({ status: "waiting", bPresence: "empty" });
  const after = snap({ status: "playing", bPresence: "away" });
  const event = eventFor(before, after, "A");
  assert.equal(event.key, "joined");
  assert.equal(event.tag, `${CODE}:joined`);
  assert.equal(event.banner, "Your opponent has joined");
  assert.equal(eventFor(before, after, "B"), null);
  assert.equal(eventFor(before, after, null), null, "a watcher is never alerted");
  assert.equal(eventFor(null, after, "A"), null, "the first snapshot of a room is not an event");
});

test("join: the stand-in computer taking seat B is no join; a friend taking over from it is", () => {
  const waiting = snap({ status: "waiting", bPresence: "empty" });
  const computer = { ...snap({ status: "playing", bPresence: "computer" }), mode: "computer", standIn: true };
  assert.equal(eventFor(waiting, computer, "A"), null, "the computer is not the opponent the creator waits for");
  const friend = { ...snap({ status: "playing", bPresence: "connected", sans: ["e4", "a5"] }), mode: "online" };
  const event = eventFor({ ...computer, moveList: friend.moveList, turn: friend.turn }, friend, "A");
  assert.equal(event.key, "joined");
  assert.equal(event.body, "Your friend took over from the computer.");
  assert.equal(eventFor(computer, friend, "B"), null);
});

test("move keys use the game number and the half-move count, for the side to move only", () => {
  const e4 = snap({ sans: ["e4"] });
  const event = eventFor(snap(), e4, "B");
  assert.deepEqual([event.kind, event.key, event.tag, event.title, event.body],
    ["move", "move:1:1", `${CODE}:move:1:1`, "Your move", "Your opponent played e4."]);
  assert.equal(eventFor(snap(), e4, "A"), null, "my own move does not alert me");
  assert.equal(eventFor(e4, snap({ sans: ["e4", "e5"] }), "A").key, "move:1:2");
  assert.equal(plyCount(snap({ sans: ["e4", "e5", "Nf3"] })), 3);

  // game 2, colours swapped: A plays black
  const g2 = snap({ game: 2, aColour: "black", sans: ["d4"] });
  assert.equal(eventFor(snap({ game: 2, aColour: "black" }), g2, "A").key, "move:2:1");
  assert.equal(eventFor(e4, e4, "B"), null, "the same snapshot again is not a new event");
});

test("a final move gives only 'ended', to the seat that did not cause it", () => {
  const before = snap({ sans: ["f3", "e5", "g4"] });
  const mate = snap({ sans: ["f3", "e5", "g4", "Qh4#"], status: "finished", endReason: "checkmate", result: "0-1" });
  const event = eventFor(before, mate, "A");
  assert.deepEqual([event.kind, event.key, event.body, event.banner],
    ["ended", "ended:1", "Game over — Checkmate", "Game over — Checkmate"]);
  assert.equal(eventFor(before, mate, "B"), null, "the mover caused the end");
  assert.equal(eventFor(mate, mate, "A"), null, "an already finished game is not a new event");
});

test("claims: a draw claim alerts the other seat; a win claim alerts the abandoned seat", () => {
  const playing = snap({ sans: ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1", "Ng8"] });
  const drawn = { ...playing, status: "finished", endReason: "threefold_claimed", result: "1/2-1/2" };
  assert.equal(eventFor(playing, drawn, "B").key, "ended:1", "white (A) claimed on its move: B is told");
  assert.equal(eventFor(playing, drawn, "A"), null);
  assert.equal(eventFor(playing, drawn, "B").body, "Game over — Draw claimed (threefold repetition)");

  const won = { ...snap({ sans: ["e4"] }), status: "finished", endReason: "abandoned", result: "1-0" };
  assert.equal(eventFor(snap({ sans: ["e4"] }), won, "B").key, "ended:1");
  assert.equal(eventFor(snap({ sans: ["e4"] }), won, "A"), null);
  assert.equal(endText("not-a-reason"), "Game over — Game over");
});

test("decide: visible means a banner, hidden means local with or without push, shown keys and off give none", () => {
  const key = `${CODE}:move:1:1`;
  const base = { permission: "granted", enabled: true, shownKeys: new Set(), key };
  assert.equal(decide({ ...base, visible: true }), "banner");
  assert.equal(decide({ ...base, visible: false }), "local", "hidden: local notification (push or not)");
  assert.equal(decide({ ...base, visible: false, shownKeys: new Set([key]) }), "none");
  assert.equal(decide({ ...base, visible: true, shownKeys: new Set([key]) }), "none");
  assert.equal(decide({ ...base, visible: false, enabled: false }), "none", "turned off: no system notification");
  assert.equal(decide({ ...base, visible: true, enabled: false }), "banner", "turned off: the visible banner stays");
  assert.equal(decide({ ...base, visible: false, permission: "denied" }), "none");
  assert.equal(decide({ ...base, key: null, visible: true }), "none");
});

test("the tag carries the room, so two rooms never replace each other's notifications", () => {
  const one = eventFor(snap(), snap({ sans: ["e4"] }), "B");
  const two = eventFor(snap({ code: "ROOM02" }), snap({ code: "ROOM02", sans: ["e4"] }), "B");
  assert.equal(one.key, two.key);
  assert.notEqual(one.tag, two.tag);
  assert.equal(two.tag, "ROOM02:move:1:1");
  assert.equal(eventFor(snap(), snap({ code: "ROOM02", sans: ["e4"] }), "B"), null, "a different room is not compared");
});

test("service worker logic: always show, quietly when the room's page is visible; payloads are checked", () => {
  const clients = [{ url: `${ORIGIN}/r/${CODE}`, visibilityState: "visible" }];
  assert.deepEqual(swDecision({ clients, code: CODE, origin: ORIGIN }), { show: true, silent: true });
  assert.deepEqual(swDecision({ clients: [{ ...clients[0], visibilityState: "hidden" }], code: CODE, origin: ORIGIN }),
    { show: true, silent: false });
  assert.equal(swDecision({ clients, code: "ROOM02", origin: ORIGIN }).silent, false, "another room's page");
  assert.equal(swDecision({ clients, code: CODE, origin: "https://evil.example" }).silent, false);

  const note = notificationFromPush({ title: "Your move", body: "Your opponent played e4.", tag: `${CODE}:move:1:1`,
    url: "https://evil.example/phish", code: CODE });
  assert.equal(note.title, "Your move");
  assert.deepEqual(note.options, { body: "Your opponent played e4.", tag: `${CODE}:move:1:1`, renotify: false,
    data: { url: `/r/${CODE}`, code: CODE } }, "the url is always the room page, never the payload's");
  assert.equal(notificationFromPush({ title: "x", tag: "OTHER1:joined", code: CODE }), null);
  assert.equal(notificationFromPush({ title: "x", tag: "bad:joined", code: "bad" }), null);
  assert.equal(notificationFromPush(null), null);
});

function sharedBlock(source) {
  const start = source.indexOf("// --- shared with sw.js");
  const end = source.indexOf("// --- end shared with sw.js ---");
  assert.ok(start >= 0 && end > start, "the shared markers are present");
  return source.slice(source.indexOf("\n", start) + 1, end).replace(/^export /gm, "").trim();
}

test("static/sw.js carries an identical copy of the shared worker logic", () => {
  const core = readFileSync(new URL("../../static/js/notify-core.js", import.meta.url), "utf8");
  const worker = readFileSync(new URL("../../static/sw.js", import.meta.url), "utf8");
  assert.equal(sharedBlock(worker), sharedBlock(core));
});

/** Run static/sw.js in a sandbox with a fake ServiceWorkerGlobalScope. */
function loadWorker({ clients = [] } = {}) {
  const listeners = {};
  const shown = [];
  const opened = [];
  const focused = [];
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    skipWaiting: () => Promise.resolve(),
    registration: { showNotification: async (title, options) => { shown.push({ title, options }); } },
    clients: {
      claim: () => Promise.resolve(),
      matchAll: async () => clients.map((client) => ({ ...client, focus: async () => { focused.push(client.url); } })),
      openWindow: async (url) => { opened.push(url); },
    },
  };
  const source = readFileSync(new URL("../../static/sw.js", import.meta.url), "utf8");
  runInNewContext(source, { self, URL, console });
  async function fire(type, event) {
    let pending = Promise.resolve();
    listeners[type]({ ...event, waitUntil: (promise) => { pending = promise; } });
    await pending;
  }
  return { fire, shown, opened, focused };
}

test("the worker shows each push with its tag, and a tap focuses or opens the room", async () => {
  const worker = loadWorker({ clients: [{ url: `${ORIGIN}/r/${CODE}`, visibilityState: "hidden" }] });
  const payload = { title: "Your move", body: "Your opponent played e4.", tag: `${CODE}:move:1:1`, url: `/r/${CODE}`, code: CODE };
  await worker.fire("push", { data: { json: () => payload } });
  assert.equal(worker.shown.length, 1);
  assert.equal(worker.shown[0].options.tag, `${CODE}:move:1:1`);
  assert.equal(worker.shown[0].options.silent, false);

  await worker.fire("notificationclick", { notification: { data: { url: `/r/${CODE}` }, close() {} } });
  assert.deepEqual(worker.focused, [`${ORIGIN}/r/${CODE}`]);
  const empty = loadWorker();
  await empty.fire("notificationclick", { notification: { data: { url: `/r/${CODE}` }, close() {} } });
  assert.deepEqual(empty.opened, [`${ORIGIN}/r/${CODE}`]);

  const broken = loadWorker();
  await broken.fire("push", { data: { json: () => { throw new SyntaxError("not json"); } } });
  assert.equal(broken.shown.length, 1, "an unreadable push still shows a notification (never the generic notice)");
  assert.equal(broken.shown[0].options.tag, "justchess");
});
