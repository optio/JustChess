// Tests for the "Your games" list logic static/js/your-games.js (P2 U2, BR3.1-BR3.3).
import { test } from "node:test";
import assert from "node:assert/strict";

import { createSeatStore } from "../../static/js/seat-store.js";
import {
  DAY_MS,
  filterAndSort,
  reconcile,
  relativeTime,
  rowModel,
  seatsToSend,
  staleRowModel,
  thumbnailSquares,
} from "../../static/js/your-games.js";

const NOW = 1_800_000_000_000; // ms
const S = (msAgo) => (NOW - msAgo) / 1000; // server epoch seconds, msAgo before NOW
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const MIN = 60_000;
const HOUR = 60 * MIN;

/** A found RoomSummary shaped like justchess/summaries.py answers it; override only what a test is about. */
function summary(overrides = {}) {
  return {
    code: "ABC123", found: true, kind: "friend", computerLevel: null, opponent: "joined", colour: "white",
    status: "playing", yourTurn: true, result: null, endReason: null, lastActivityAt: S(4 * MIN), endedAt: null,
    fen: START_FEN, pendingJoinRequest: false, ...overrides,
  };
}

function memoryStorage() {
  const data = new Map();
  return {
    data,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
    key: (index) => [...data.keys()][index] ?? null,
    get length() {
      return data.size;
    },
  };
}

test("finished games older than 7 days are left out; unfinished games always stay", () => {
  const listed = filterAndSort([
    summary({ code: "OPEN01", lastActivityAt: S(40 * DAY_MS) }),
    summary({ code: "DONE01", status: "finished", result: "won", endedAt: S(7 * DAY_MS - MIN) }),
    summary({ code: "DONE02", status: "finished", result: "lost", endedAt: S(7 * DAY_MS + MIN) }),
    summary({ code: "DONE03", status: "finished", result: "drawn", endedAt: null }),
    { code: "GONE01", found: false },
  ], NOW);

  assert.deepEqual(listed.map((s) => s.code), ["OPEN01", "DONE01"]);
});

test("join requests sort first, then unfinished by newest activity, then finished by newest end", () => {
  const entries = [
    summary({ code: "FIN_OL", status: "finished", result: "won", endedAt: S(3 * DAY_MS) }),
    summary({ code: "OLDMOV", lastActivityAt: S(5 * HOUR) }),
    summary({ code: "FIN_NE", status: "finished", result: "lost", endedAt: S(HOUR) }),
    summary({ code: "NEWMOV", lastActivityAt: S(MIN) }),
    summary({ code: "REQST1", lastActivityAt: S(2 * DAY_MS), pendingJoinRequest: true }),
  ].map((s, index) => ({ seat: { code: s.code, slot: "A", token: `t${index}` }, summary: s }));

  const order = filterAndSort(entries, NOW).map((entry) => entry.summary.code);

  assert.deepEqual(order, ["REQST1", "NEWMOV", "OLDMOV", "FIN_NE", "FIN_OL"]);
});

test("labels and meta lines for a joined friend, a waiting friend, a computer room and a finished game", () => {
  assert.equal(rowModel(summary(), NOW).label, "Friend · ABC123");
  assert.equal(rowModel(summary(), NOW).meta, "You play White · last move 4 min ago");
  const waiting = rowModel(summary({ opponent: "waiting", status: "waiting", yourTurn: false }), NOW);
  assert.equal(waiting.label, "Waiting for a friend · ABC123");
  const computer = rowModel(summary({ kind: "computer", computerLevel: "club", opponent: "computer", colour: "black" }), NOW);
  assert.equal(computer.label, "Computer, Club");
  assert.match(computer.meta, /^You play Black/);
  const ended = rowModel(summary({ status: "finished", result: "won", endReason: "checkmate", endedAt: S(2 * DAY_MS) }), NOW);
  assert.equal(ended.meta, "Ended 2 days ago · checkmate");
  assert.equal(ended.href, "/r/ABC123");
  assert.ok(ended.finished);
  assert.equal(ended.ariaLabel, "Friend · ABC123. Ended 2 days ago · checkmate. You won");
});

test("pills for every case, including Waiting and Ended", () => {
  const pill = (overrides) => rowModel(summary(overrides), NOW).pill;
  assert.deepEqual(pill({}), { text: "Your move", tone: "your-move" });
  assert.deepEqual(pill({ yourTurn: false }), { text: "Their move", tone: "their-move" });
  assert.deepEqual(pill({ status: "waiting", opponent: "waiting", yourTurn: false }), { text: "Waiting", tone: "waiting" });
  assert.deepEqual(pill({ pendingJoinRequest: true }), { text: "Join request", tone: "request" });
  assert.deepEqual(pill({ status: "finished", result: "won", endedAt: S(HOUR) }), { text: "You won", tone: "won" });
  assert.deepEqual(pill({ status: "finished", result: "lost", endedAt: S(HOUR) }), { text: "You lost", tone: "lost" });
  assert.deepEqual(pill({ status: "finished", result: "drawn", endedAt: S(HOUR) }), { text: "Draw", tone: "drawn" });
  assert.deepEqual(pill({ status: "finished", result: null, endedAt: S(HOUR) }), { text: "Ended", tone: "ended" });
  assert.deepEqual(staleRowModel({ code: "ABC123", kind: "friend", slot: "A" }).pill, { text: "Couldn't refresh", tone: "stale" });
  assert.equal(staleRowModel({ code: "CMP001", kind: "computer", computerLevel: "strong", slot: "A" }).label, "Computer, Strong");
});

test("reconcile drops a stored seat only when its summary says found:false", () => {
  const seats = createSeatStore(memoryStorage(), { now: () => 1 });
  seats.set("KEEP01", { token: "token-keep-0123456789", slot: "A" });
  seats.set("GONE01", { token: "token-gone-0123456789", slot: "B" });
  const sent = seatsToSend(seats.validSeats());

  const result = reconcile(seats, sent, sent.map((seat) => (seat.code === "GONE01"
    ? { code: "GONE01", found: false }
    : summary({ code: "KEEP01" }))));

  assert.equal(result.ok, true);
  assert.deepEqual(result.kept.map((entry) => entry.seat.code), ["KEEP01"]);
  assert.equal(seats.get("GONE01"), null);
  assert.notEqual(seats.get("KEEP01"), null);
});

test("a failed or mismatched answer keeps every seat", () => {
  const seats = createSeatStore(memoryStorage(), { now: () => 1 });
  seats.set("KEEP01", { token: "token-keep-0123456789", slot: "A" });
  seats.set("KEEP02", { token: "token-keep-9876543210", slot: "A" });
  const sent = seatsToSend(seats.validSeats());

  for (const answer of [undefined, null, [], [{ code: "KEEP01", found: false }], sent.map(() => ({ code: "OTHER1", found: false }))]) {
    assert.equal(reconcile(seats, sent, answer).ok, false, JSON.stringify(answer));
  }
  assert.equal(seats.validSeats().length, 2, "nothing was dropped");
});

test("malformed stored seats are skipped before sending, duplicates collapse and at most 50 are sent", () => {
  const storage = memoryStorage();
  storage.setItem("justchess.seat.BROKEN", "{not json");
  const seats = createSeatStore(storage, { now: () => 1 });
  seats.set("GOOD01", { token: "token-good-0123456789", slot: "A" });

  const sent = seatsToSend(seats.validSeats());
  assert.deepEqual(sent.map((seat) => seat.code), ["GOOD01"]);
  assert.equal(storage.data.has("justchess.seat.BROKEN"), false, "the bad entry was removed, not sent");

  const many = Array.from({ length: 60 }, (_, i) => ({ code: `R${String(i).padStart(5, "0")}`, token: `token-${i}`, slot: "A" }));
  const chosen = seatsToSend([many[0], ...many, { code: "bad", token: "x", slot: "A" }, { code: "TOOLNG", token: "t".repeat(129), slot: "A" }]);
  assert.equal(chosen.length, 50);
  assert.equal(chosen[0].code, "R00000", "duplicates collapse, order is kept");
});

test("relative times and the thumbnail orientation", () => {
  assert.equal(relativeTime(NOW - 20_000, NOW), "just now");
  assert.equal(relativeTime(NOW + 90_000, NOW), "just now", "a server clock ahead of the browser reads as just now");
  assert.equal(relativeTime(NOW - 4 * MIN, NOW), "4 min ago");
  assert.equal(relativeTime(NOW - 2 * HOUR - MIN, NOW), "2 h ago");
  assert.equal(relativeTime(NOW - 30 * HOUR, NOW), "yesterday");
  assert.equal(relativeTime(NOW - 3 * DAY_MS, NOW), "3 days ago");

  const white = thumbnailSquares(START_FEN, "white");
  assert.equal(white.length, 64);
  assert.equal(white[0].piece, "r", "a8 is top left from White's side");
  assert.equal(white[0].dark, false);
  assert.equal(white[63].piece, "R");
  const black = thumbnailSquares(START_FEN, "black");
  assert.equal(black[0].piece, "R", "h1 is top left from Black's side");
  assert.ok(thumbnailSquares("not a fen").every((cell) => cell.piece === null));
});
