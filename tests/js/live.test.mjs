// Tests for the live connection static/js/live.js (BR3.1, BR3.2, BR1.7).
import { test } from "node:test";
import assert from "node:assert/strict";

import { BACKOFF, PING_INTERVAL, backoffDelay, createLive, socketUrl } from "../../static/js/live.js";

const TOKEN = "seat-token-abcdefghijklmnop";

/** A WebSocket fake: tests open, message and close it by hand. */
function socketFactory() {
  const sockets = [];
  class FakeSocket {
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      this.sent = [];
      this.closedWith = null;
      sockets.push(this);
    }
    send(text) {
      this.sent.push(JSON.parse(text));
    }
    close(code) {
      this.closedWith = code;
      this.readyState = 3;
    }
    // test helpers
    open() {
      this.readyState = 1;
      this.onopen?.();
    }
    receive(message) {
      this.onmessage?.({ data: JSON.stringify(message) });
    }
    drop(code = 1006) {
      this.readyState = 3;
      this.onclose?.({ code });
    }
  }
  return { FakeSocket, sockets };
}

/** Fake timers: nothing runs until the test calls run(). */
function fakeTimers() {
  const timeouts = new Map();
  const intervals = new Map();
  let next = 1;
  return {
    timeouts,
    intervals,
    setTimeout: (fn, ms) => (timeouts.set(next, { fn, ms }), next++),
    clearTimeout: (id) => timeouts.delete(id),
    setInterval: (fn, ms) => (intervals.set(next, { fn, ms }), next++),
    clearInterval: (id) => intervals.delete(id),
    runTimeouts() {
      const due = [...timeouts.entries()];
      timeouts.clear();
      due.forEach(([, t]) => t.fn());
      return due.map(([, t]) => t.ms);
    },
    tickIntervals() {
      [...intervals.values()].forEach((t) => t.fn());
    },
  };
}

function fakeVisibility(initial = true) {
  let visible = initial;
  let listener = null;
  return {
    isVisible: () => visible,
    subscribe(fn) {
      listener = fn;
      return () => {
        listener = null;
      };
    },
    set(value) {
      visible = value;
      listener?.(value);
    },
    get subscribed() {
      return listener !== null;
    },
  };
}

function setup(options = {}) {
  const { FakeSocket, sockets } = socketFactory();
  const timers = fakeTimers();
  const visibility = fakeVisibility(options.visible ?? true);
  const events = [];
  const live = createLive({
    url: "ws://localhost/ws/ABC123",
    token: options.token ?? null,
    WebSocketImpl: FakeSocket,
    timers,
    visibility,
    onState: (s) => events.push(["state", s.game, s.version]),
    onSeatMoved: () => events.push(["seatMoved"]),
    onConnection: (value) => events.push(["connection", value]),
    onNotFound: () => events.push(["notFound"]),
  });
  return { live, sockets, timers, visibility, events };
}

const state = (game, version, extra = {}) => ({ type: "state", code: "ABC123", game, version, ...extra });

test("the backoff schedule is 1, 2, 4 and 8 s, then 10 s forever, and drives the retries", () => {
  assert.deepEqual(BACKOFF, [1000, 2000, 4000, 8000]);
  assert.deepEqual([0, 1, 2, 3, 4, 5, 50].map(backoffDelay), [1000, 2000, 4000, 8000, 10000, 10000, 10000]);
  assert.throws(() => backoffDelay(-1), RangeError);

  const { sockets, timers, events } = setup({ token: TOKEN });
  sockets[0].open();
  sockets[0].receive(state(1, 1));
  sockets[0].drop();
  assert.deepEqual(events.at(-1), ["connection", "reconnecting"]);
  const delays = [];
  for (let i = 0; i < 6; i += 1) {
    delays.push(...timers.runTimeouts());
    sockets.at(-1).drop(); // every retry fails at once
  }
  assert.deepEqual(delays, [1000, 2000, 4000, 8000, 10000, 10000]);
  assert.equal(events.filter((e) => e[1] === "reconnecting").length, 1, "reconnecting is reported once, not per retry");

  timers.runTimeouts();
  sockets.at(-1).open();
  sockets.at(-1).receive(state(1, 2));
  assert.deepEqual(events.at(-2), ["connection", "open"], "a successful hello clears reconnecting");
  sockets.at(-1).drop();
  assert.deepEqual(timers.runTimeouts(), [1000], "the schedule restarts after a success");
  assert.equal(socketUrl({ protocol: "https:", host: "chess.example" }, "ABC123"), "wss://chess.example/ws/ABC123");
  assert.equal(socketUrl({ protocol: "http:", host: "localhost:8000" }, "ABC123"), "ws://localhost:8000/ws/ABC123");
});

test("hello carries the token for a seat and none for a watcher, never in the URL", () => {
  const seat = setup({ token: TOKEN });
  seat.sockets[0].open();
  assert.deepEqual(seat.sockets[0].sent[0], { type: "hello", visible: true, token: TOKEN });
  assert.doesNotMatch(seat.sockets[0].url, new RegExp(TOKEN));

  const watcher = setup({ token: null, visible: false });
  watcher.sockets[0].open();
  assert.deepEqual(watcher.sockets[0].sent[0], { type: "hello", visible: false });

  seat.live.setToken("new-token-abcdefghijklmnop");
  assert.equal(seat.sockets[0].closedWith, 1000, "a new token reconnects");
  seat.sockets[1].open();
  assert.equal(seat.sockets[1].sent[0].token, "new-token-abcdefghijklmnop");
  seat.sockets[0].drop(1000);
  assert.equal(seat.events.some((e) => e[1] === "reconnecting"), false, "closing the replaced socket is not a reconnect");
});

test("pings go out every 5 s while open and stop when the socket closes", () => {
  const { sockets, timers } = setup({ token: TOKEN });
  sockets[0].open();
  assert.deepEqual([...timers.intervals.values()].map((t) => t.ms), [PING_INTERVAL]);
  timers.tickIntervals();
  timers.tickIntervals();
  assert.deepEqual(sockets[0].sent.slice(1), [{ type: "ping" }, { type: "ping" }]);
  sockets[0].drop();
  assert.equal(timers.intervals.size, 0, "no ping timer after a close");
});

test("visibility changes are reported on the open socket; close() stops everything", () => {
  const { live, sockets, visibility, timers, events } = setup({ token: TOKEN });
  visibility.set(false); // not open yet: nothing to send, nothing thrown
  sockets[0].open();
  visibility.set(true);
  visibility.set(false);
  assert.deepEqual(sockets[0].sent.slice(1), [{ type: "visibility", visible: true }, { type: "visibility", visible: false }]);
  live.close();
  assert.equal(sockets[0].closedWith, 1000);
  assert.equal(visibility.subscribed, false);
  sockets[0].drop(1000);
  assert.equal(timers.timeouts.size, 0, "no retry after our own close");
  assert.equal(events.some((e) => e[1] === "reconnecting"), false);
});

test("seat-moved forgets the token and tells the screen; close code 1008 means not found, with no retry", () => {
  const { live, sockets, timers, events } = setup({ token: TOKEN });
  sockets[0].open();
  sockets[0].receive({ type: "seat-moved" });
  assert.deepEqual(events.at(-1), ["seatMoved"]);
  assert.equal(live.token, null);
  sockets[0].drop();
  timers.runTimeouts();
  sockets[1].open();
  assert.deepEqual(sockets[1].sent[0], { type: "hello", visible: true }, "the reconnect is a watcher hello");

  const gone = setup({ token: TOKEN });
  gone.sockets[0].open();
  gone.sockets[0].drop(1008);
  assert.deepEqual(gone.events, [["notFound"]]);
  assert.equal(gone.timers.timeouts.size, 0);
});

test("older snapshots are ignored, equal and newer ones pass, and a new game beats any version", () => {
  const { sockets, events } = setup({ token: TOKEN });
  sockets[0].open();
  sockets[0].receive(state(1, 5));
  sockets[0].receive(state(1, 4));
  sockets[0].receive(state(1, 5, { seats: {} }));
  sockets[0].receive(state(1, 6));
  sockets[0].receive(state(2, 0));
  sockets[0].receive(state(1, 9));
  sockets[0].receive({ type: "pong" });
  const original = console.error;
  console.error = () => {};
  try {
    sockets[0].onmessage({ data: "{broken" }); // not JSON: ignored, not thrown
  } finally {
    console.error = original;
  }
  assert.deepEqual(events.filter((e) => e[0] === "state"), [["state", 1, 5], ["state", 1, 5], ["state", 1, 6], ["state", 2, 0]]);
});
