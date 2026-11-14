// Tests for the screen state reducer static/js/screen-state.js (functional-spec.md state machine, BR3.1, BR1.7, BR5.2).
import { test } from "node:test";
import assert from "node:assert/strict";

import { initialState, isCurrent, notFoundMessage, reduce } from "../../static/js/screen-state.js";

function snap(overrides = {}) {
  return { code: "ABC123", game: 1, version: 1, status: "playing", fen: "8/8/8/8/8/8/8/8 w - - 0 1", turn: "white", ...overrides };
}

function run(events, state = initialState()) {
  return events.reduce(reduce, state);
}

const seated = [{ type: "route", code: "ABC123" }, { type: "joined", slot: "A" }];

test("lobby and joining: a room path joins, and the join results lead to waiting, playing or game over", () => {
  assert.equal(initialState().view, "lobby");
  const joining = run([{ type: "route", code: "ABC123" }]);
  assert.deepEqual([joining.view, joining.code, joining.connection], ["joining", "ABC123", "open"]);
  assert.equal(run([{ type: "route" }], joining).view, "lobby", "the root path is the lobby");

  const stillJoining = run([{ type: "joined", slot: "A" }], joining);
  assert.equal(stillJoining.view, "joining", "a seat alone does not pick the view: the snapshot does");
  assert.equal(run([{ type: "snapshot", snapshot: snap({ status: "waiting", version: 0 }) }], stillJoining).view, "waiting");
  assert.equal(run([{ type: "snapshot", snapshot: snap() }], stillJoining).view, "playing");
  const over = run([{ type: "snapshot", snapshot: snap({ status: "finished" }) }], stillJoining);
  assert.deepEqual([over.view, over.transition, over.opened], ["gameOver", null, true], "opened on a finished game: no sequence");
  assert.throws(() => reduce(joining, { type: "joined", slot: "C" }), TypeError);
});

test("room full means watching with the seats-taken notice; not found and join failures go back to the lobby", () => {
  const full = run([{ type: "route", code: "ABC123" }, { type: "roomFull", snapshot: snap() }]);
  assert.deepEqual([full.view, full.slot, full.watching], ["watching", null, true]);
  assert.deepEqual(full.notices, [{ key: "seatsTaken" }]);
  assert.equal(full.snapshot.version, 1, "the attached snapshot is drawn as the watcher view");
  assert.equal(run([{ type: "snapshot", snapshot: snap({ status: "finished", version: 2 }) }], full).view, "watching",
    "a watcher stays watching whatever the game status");

  const missing = run([{ type: "route", code: "K7Q2PX" }, { type: "notFound" }]);
  assert.equal(missing.view, "notFound");
  assert.equal(missing.lobby.error, "No room with code K7Q2PX. Check the code or start a new game.");
  assert.equal(missing.lobby.code, "K7Q2PX", "the code stays in the field");
  assert.equal(notFoundMessage("K7Q2PX"), missing.lobby.error);
  const back = run([{ type: "route" }], missing);
  assert.deepEqual([back.view, back.lobby.error], ["lobby", null], "not found returns to the plain lobby");

  const failed = run([{ type: "route", code: "ABC123" }, { type: "joinFailed", message: "Couldn't reach the server. Try again." }]);
  assert.deepEqual([failed.view, failed.lobby.error, failed.lobby.code], ["lobby", "Couldn't reach the server. Try again.", "ABC123"]);
});

test("reconnecting is a flag on every room view, and a snapshot while reconnecting keeps the view right", () => {
  for (const status of ["waiting", "playing", "finished"]) {
    const state = run([...seated, { type: "snapshot", snapshot: snap({ status }) }, { type: "connection", value: "reconnecting" }]);
    assert.equal(state.connection, "reconnecting");
    assert.equal(state.view, { waiting: "waiting", playing: "playing", finished: "gameOver" }[status], `view kept for ${status}`);
  }
  const watcher = run([{ type: "route", code: "ABC123" }, { type: "roomFull" }, { type: "connection", value: "reconnecting" }]);
  assert.deepEqual([watcher.view, watcher.connection], ["watching", "reconnecting"]);
  const joining = run([{ type: "route", code: "ABC123" }, { type: "connection", value: "reconnecting" }]);
  assert.equal(joining.connection, "reconnecting");

  const lobby = run([{ type: "connection", value: "reconnecting" }]);
  assert.equal(lobby.connection, "open", "the lobby has no connection");
  const reconnected = run([...seated, { type: "snapshot", snapshot: snap() }, { type: "connection", value: "reconnecting" },
    { type: "snapshot", snapshot: snap({ version: 2 }) }, { type: "connection", value: "open" }]);
  assert.deepEqual([reconnected.view, reconnected.connection, reconnected.snapshot.version], ["playing", "open", 2]);
  assert.throws(() => reduce(lobby, { type: "connection", value: "maybe" }), TypeError);
});

test("a snapshot after a gap lands on the right view: a finished game, then a new game", () => {
  const playing = run([...seated, { type: "snapshot", snapshot: snap({ version: 3 }) }]);
  const ended = reduce(playing, { type: "snapshot", snapshot: snap({ version: 9, status: "finished" }) });
  assert.deepEqual([ended.view, ended.transition], ["gameOver", "ended"]);
  const newGame = reduce(ended, { type: "snapshot", snapshot: snap({ game: 2, version: 0 }) });
  assert.deepEqual([newGame.view, newGame.transition], ["playing", "newGame"], "game 2 version 0 is newer than game 1 version 9");
  const skipped = reduce(playing, { type: "snapshot", snapshot: snap({ game: 3, version: 4, status: "finished" }) });
  assert.deepEqual([skipped.view, skipped.transition], ["gameOver", "newGame"], "a gap across games is a new game, not an ending seen here");
  const quiet = reduce(newGame, { type: "snapshot", snapshot: snap({ game: 2, version: 0 }) });
  assert.equal(quiet.transition, null, "the next snapshot clears the transition");
});

test("older snapshots are ignored and equal ones are accepted (presence changes keep the version)", () => {
  assert.equal(isCurrent(null, snap()), true);
  assert.equal(isCurrent(snap({ version: 5 }), snap({ version: 4 })), false);
  assert.equal(isCurrent(snap({ version: 5 }), snap({ version: 5 })), true);
  assert.equal(isCurrent(snap({ game: 2, version: 0 }), snap({ game: 1, version: 30 })), false);
  const state = run([...seated, { type: "snapshot", snapshot: snap({ version: 5 }) }]);
  const stale = reduce(state, { type: "snapshot", snapshot: snap({ version: 4, status: "finished" }) });
  assert.deepEqual([stale.view, stale.snapshot.version], ["playing", 5]);
  const presence = reduce(state, { type: "snapshot", snapshot: snap({ version: 5, seats: { B: { presence: "away" } } }) });
  assert.equal(presence.snapshot.seats.B.presence, "away");
  assert.equal(reduce(state, { type: "snapshot", snapshot: snap({ code: "ZZZ999", version: 9 }) }).snapshot.version, 5,
    "a snapshot of another room is ignored");
});

test("seat-moved turns every room view into watching, joining included, and forgets seat notices", () => {
  const views = {
    joining: run([{ type: "route", code: "ABC123" }]),
    waiting: run([...seated, { type: "snapshot", snapshot: snap({ status: "waiting" }) }]),
    playing: run([...seated, { type: "snapshot", snapshot: snap() }]),
    gameOver: run([...seated, { type: "snapshot", snapshot: snap({ status: "finished" }) }]),
  };
  for (const [name, state] of Object.entries(views)) {
    const withNotice = reduce(state, { type: "notice", notice: { key: "storageBlocked" } });
    const moved = reduce(withNotice, { type: "seatMoved" });
    assert.deepEqual([moved.view, moved.slot, moved.watching], ["watching", null, true], `seat-moved from ${name}`);
    assert.deepEqual(moved.notices, [{ key: "seatMoved" }], `notices after seat-moved from ${name}`);
  }
  assert.equal(reduce(initialState(), { type: "seatMoved" }).view, "lobby", "the lobby ignores seat-moved");
});

test("a seat 403 leads to watching with its own notice; notices can be added and dismissed", () => {
  const playing = run([...seated, { type: "snapshot", snapshot: snap() }]);
  const lost = reduce(playing, { type: "seatLost" });
  assert.deepEqual([lost.view, lost.slot], ["watching", null]);
  assert.deepEqual(lost.notices, [{ key: "seatLost" }]);
  const joinedNotices = run([{ type: "route", code: "ABC123" },
    { type: "joined", slot: "B", notices: [{ key: "staleSeat", colour: "black" }, { key: "storageBlocked" }] }]);
  assert.deepEqual(joinedNotices.notices.map((n) => n.key), ["staleSeat", "storageBlocked"]);
  const twice = reduce(joinedNotices, { type: "notice", notice: { key: "storageBlocked" } });
  assert.equal(twice.notices.length, 2, "a notice is shown once");
  assert.deepEqual(reduce(twice, { type: "dismissNotice", key: "staleSeat" }).notices, [{ key: "storageBlocked" }]);
  assert.throws(() => reduce(playing, { type: "teleport" }), TypeError);
});

test("a new game during the win sequence restarts cleanly, and not found from a live room goes to the lobby", () => {
  const ended = run([...seated, { type: "snapshot", snapshot: snap({ version: 3 }) },
    { type: "snapshot", snapshot: snap({ version: 4, status: "finished" }) }]);
  assert.equal(ended.transition, "ended");
  const sameGame = reduce(ended, { type: "snapshot", snapshot: snap({ version: 5, status: "finished", rematch: { state: "pending" } }) });
  assert.deepEqual([sameGame.transition, sameGame.view], [null, "gameOver"], "a rematch request does not restart the sequence");
  const next = reduce(sameGame, { type: "snapshot", snapshot: snap({ game: 2, version: 0 }) });
  assert.deepEqual([next.transition, next.view], ["newGame", "playing"]);

  const socketGone = reduce(next, { type: "notFound" });
  assert.deepEqual([socketGone.view, socketGone.snapshot, socketGone.lobby.code], ["notFound", null, "ABC123"]);
  const typed = reduce(reduce(socketGone, { type: "lobbyError", message: "Room code must be 6 letters or digits", code: "AB" }), { type: "route" });
  assert.equal(typed.view, "lobby");
});
