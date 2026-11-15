// Tests for the game screen view model static/js/view-model.js (BR3.4-BR3.7, BR4.2, BR4.3).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  CLAIM_DRAW_LABELS,
  END_TITLES,
  NOTICES,
  STATUS_TEXT,
  announcement,
  endTitle,
  lastSeenPhrase,
  resultText,
  viewModel,
} from "../../static/js/view-model.js";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/** A small snapshot as U1 sends it; seat A plays white unless overridden. */
function snap(overrides = {}) {
  return {
    code: "ABC123",
    game: 1,
    fen: START,
    turn: "white",
    status: "playing",
    endReason: null,
    result: null,
    check: false,
    moveList: [],
    lastMove: null,
    version: 1,
    claimableDraw: false,
    claimableDrawReason: null,
    seats: { A: { presence: "connected", colour: "white" }, B: { presence: "connected", colour: "black" } },
    score: { A: 0, B: 0, draws: 0 },
    rematch: { state: "none", requestedBy: null },
    slot: "A",
    colour: "white",
    legalMoves: ["e2e4", "d2d4"],
    ...overrides,
  };
}

const AFTER_D4 = { turn: "black", moveList: [{ number: 1, white: "d4", black: null }], lastMove: "d2d4", version: 2 };

test("the status line follows the BR3.4 order: game over, reconnecting, waiting, check, your move, their move", () => {
  const over = snap({ status: "finished", endReason: "checkmate", result: "0-1", legalMoves: [] });
  assert.equal(viewModel(over, { connection: "reconnecting" }).status.text, "Game over — Checkmate", "game over beats reconnecting");
  assert.equal(viewModel(snap(), { connection: "reconnecting" }).status.text, STATUS_TEXT.reconnecting);
  assert.equal(viewModel(snap({ status: "waiting" }), { connection: "reconnecting" }).status.text, STATUS_TEXT.reconnecting,
    "reconnecting beats waiting");
  assert.equal(viewModel(snap({ status: "waiting" })).status.text, "Waiting for your opponent. Send them the link.");

  const yourMove = viewModel(snap({ ...AFTER_D4, slot: "B", colour: "black" }));
  assert.deepEqual(yourMove.status, { text: "Your move", sub: "White played d4", tone: "baize", dot: "solid" });
  assert.equal(yourMove.board.interactive, true);

  const check = viewModel(snap({ ...AFTER_D4, slot: "B", colour: "black", check: true }));
  assert.deepEqual([check.status.text, check.status.tone, check.status.dot], ["Check — your move", "baize", "red"]);

  const theirs = viewModel(snap(AFTER_D4));
  assert.deepEqual([theirs.status.text, theirs.status.tone, theirs.status.sub], ["Waiting for Black to move", "surface", null]);
  assert.equal(theirs.status.dot, "hourglass", "an hourglass while the opponent has to answer");
  const named = viewModel(snap({ ...AFTER_D4, seats: { A: { presence: "connected", colour: "white" }, B: { presence: "connected", colour: "black", nickname: "Bob" } } }));
  assert.equal(named.status.text, "Waiting for Bob (Black) to move", "the opponent's nickname when known");
  assert.equal(theirs.board.interactive, false);
  assert.deepEqual(theirs.board.legalMoves, []);

  const away = viewModel(snap({ ...AFTER_D4, seats: { A: { presence: "connected", colour: "white" }, B: { presence: "away", colour: "black" } } }));
  assert.deepEqual([away.status.text, away.status.sub, away.status.dot], ["Waiting for Black to move", "Black is away", "hollow"]);

  const unknownEnd = viewModel(snap({ status: "finished", endReason: "meteor", result: "1-0" }));
  assert.equal(unknownEnd.status.text, "Game over");
});

test("claim draw shows only on your move while claimable, with the reason; claim win only when the opponent is abandoned", () => {
  const claimable = { claimableDraw: true, claimableDrawReason: "threefold" };
  const mine = viewModel(snap(claimable)).claims;
  assert.deepEqual([mine.draw, mine.drawLabel], ["threefold", "Claim draw (threefold repetition)"]);
  assert.equal(viewModel(snap({ ...claimable, claimableDrawReason: "fifty_moves" })).claims.drawLabel, CLAIM_DRAW_LABELS.fifty_moves);

  assert.equal(viewModel(snap({ ...claimable, turn: "black" })).claims.draw, null, "not on the opponent's move");
  assert.equal(viewModel(snap({ ...claimable, slot: null, colour: null })).claims.draw, null, "never for a watcher");
  assert.equal(viewModel(snap({ claimableDraw: false })).claims.draw, null);

  const abandoned = { seats: { A: { presence: "connected", colour: "white" }, B: { presence: "abandoned", colour: "black" } } };
  assert.equal(viewModel(snap(abandoned)).claims.win, true);
  assert.equal(viewModel(snap({ ...abandoned, turn: "black" })).claims.win, true, "the win claim does not need your move");
  assert.equal(viewModel(snap({ ...abandoned, slot: "B", colour: "black" })).claims.win, false, "only against the other seat");
  assert.equal(viewModel(snap({ ...abandoned, status: "finished", result: "1-0", endReason: "abandoned" })).claims.win, false);
  const awayOnly = { seats: { A: { presence: "connected", colour: "white" }, B: { presence: "away", colour: "black" } } };
  assert.equal(viewModel(snap(awayOnly)).claims.win, false, "away is not abandoned");
});

test("scoresheet rows come from moveList and the newest move is marked", () => {
  const moveList = [{ number: 1, white: "e4", black: "e5" }, { number: 2, white: "Nf3", black: null }];
  const sheet = viewModel(snap({ moveList, turn: "black" })).scoresheet;
  assert.deepEqual(sheet.rows, [{ number: 1, white: "e4", black: "e5" }, { number: 2, white: "Nf3", black: "" }]);
  assert.deepEqual(sheet.latest, { row: 1, side: "white" });
  assert.equal(sheet.result, null);

  const full = viewModel(snap({ moveList: [{ number: 1, white: "e4", black: "e5" }] })).scoresheet;
  assert.deepEqual(full.latest, { row: 0, side: "black" });
  assert.equal(viewModel(snap()).scoresheet.latest, null, "no moves, no newest move");
});

test("result glyphs: 1-0, 0-1 and the draw half", () => {
  assert.equal(resultText("1-0"), "1–0");
  assert.equal(resultText("0-1"), "0–1");
  assert.equal(resultText("1/2-1/2"), "½–½");
  assert.equal(resultText(null), null);
  assert.equal(resultText("*"), null);
  const over = viewModel(snap({ status: "finished", result: "1/2-1/2", endReason: "stalemate" }));
  assert.equal(over.scoresheet.result, "½–½");
});

test("the room score follows the player across a colour swap; a watcher sees Player A and B", () => {
  const score = { A: 2, B: 1, draws: 3 };
  const game1 = viewModel(snap({ score })).score;
  assert.equal(game1.text, "You 2 · Opponent 1 · Draws 3");
  // game 2: colours swapped, A now plays black; the score stays with the player
  const swapped = { score, game: 2, slot: "A", colour: "black",
    seats: { A: { presence: "connected", colour: "black" }, B: { presence: "connected", colour: "white" } } };
  const game2 = viewModel(snap(swapped));
  assert.equal(game2.score.text, "You 2 · Opponent 1 · Draws 3");
  assert.equal(game2.board.orientation, "black");
  assert.deepEqual(game2.players, { white: "Opponent", black: "You" });
  assert.equal(viewModel(snap({ score, slot: "B", colour: "black" })).score.text, "You 1 · Opponent 2 · Draws 3");
  const watcher = viewModel(snap({ score, slot: null, colour: null }));
  assert.equal(watcher.score.text, "Player A 2 · Player B 1 · Draws 3");
  assert.equal(watcher.board.orientation, "white");
});

test("every end reason has its title, an unknown reason falls back, and the subtitle names winner and move", () => {
  const expected = {
    checkmate: "Checkmate",
    stalemate: "Stalemate",
    insufficient_material: "Draw — not enough pieces to mate",
    fivefold_repetition: "Draw by fivefold repetition",
    seventyfive_moves: "Draw by the 75-move rule",
    threefold_claimed: "Draw claimed (threefold repetition)",
    fifty_moves_claimed: "Draw claimed (50-move rule)",
    abandoned: "Opponent left",
    // P2 U4: the automatic draws and resignation of computer games
    threefold_repetition: "Draw by threefold repetition",
    fifty_moves: "Draw by the 50-move rule",
    resigned: "Resigned",
  };
  assert.deepEqual({ ...END_TITLES }, expected);
  for (const [reason, title] of Object.entries(expected)) assert.equal(endTitle(reason), title);
  assert.equal(endTitle("timeout"), "Game over");
  assert.equal(endTitle(undefined), "Game over");

  const mate = viewModel(snap({ status: "finished", endReason: "checkmate", result: "0-1", turn: "white", legalMoves: [],
    moveList: [{ number: 1, white: "f3", black: "e5" }, { number: 2, white: "g4", black: "Qh4#" }] }));
  assert.deepEqual([mate.overlay.title, mate.overlay.subtitle], ["You lost", "Your opponent won. Black wins with Qh4#. Checkmate."]);
  assert.equal(mate.overlay.shareText, "I lost by checkmate on JustChess");
  assert.equal(viewModel(snap({ status: "finished", endReason: "stalemate", result: "1/2-1/2" })).overlay.subtitle, "Draw");
  assert.equal(viewModel(snap({ status: "finished", endReason: "abandoned", result: "1-0",
    moveList: [{ number: 1, white: "e4", black: null }] })).overlay.subtitle, "You beat Your opponent. White wins. Opponent left.");
  assert.equal(viewModel(snap()).overlay, null, "no overlay while playing");
});

test("the rematch button has four states, and none for a watcher", () => {
  const finished = { status: "finished", endReason: "checkmate", result: "1-0" };
  const rematch = (state, requestedBy, slot = "A") =>
    viewModel(snap({ ...finished, slot, colour: slot === "A" ? "white" : "black", rematch: { state, requestedBy } })).overlay.rematch;
  assert.equal(rematch("none", null), "offer");
  assert.equal(rematch("pending", "A"), "waiting");
  assert.equal(rematch("pending", "B"), "opponentReady");
  assert.equal(rematch("pending", "A", "B"), "opponentReady");
  assert.equal(rematch("lapsed", "A"), "lapsed");
  assert.equal(viewModel(snap({ ...finished, slot: null, colour: null })).overlay.rematch, "none");
  assert.equal(viewModel(snap({ ...finished }), { watching: true }).overlay.rematch, "none", "a watcher flag wins over a stale slot");
});

test("the announcement names the move and whose turn it is; notices map to their sentences", () => {
  const before = snap();
  const afterD4 = snap(AFTER_D4);
  assert.equal(announcement(before, afterD4, "black"), "White played d4. Your move.");
  assert.equal(announcement(before, afterD4, "white"), "You played d4.");
  assert.equal(announcement(before, afterD4, null), "White played d4.");
  assert.equal(announcement(afterD4, { ...afterD4, seats: { ...afterD4.seats } }, "black"), null, "nothing new, nothing said");
  const mated = snap({ status: "finished", endReason: "checkmate", result: "0-1", turn: "white", version: 5,
    moveList: [{ number: 1, white: "f3", black: "e5" }, { number: 2, white: "g4", black: "Qh4#" }] });
  const beforeMate = snap({ turn: "black", version: 4, moveList: [{ number: 1, white: "f3", black: "e5" }, { number: 2, white: "g4", black: null }] });
  assert.equal(announcement(beforeMate, mated, "white"), "Black played Qh4#. Game over — Checkmate. Black wins.");
  assert.equal(announcement(mated, snap({ game: 2, colour: "black" }), "black"), "New game. You play black.");
  assert.equal(announcement(null, afterD4, "black"), null, "the first snapshot is not announced");

  const vm = viewModel(snap(), { notices: [{ key: "storageBlocked" }, { key: "staleSeat", colour: "black" }, { key: "seatsTaken" }, { key: "nope" }] });
  assert.deepEqual(vm.notices.map((n) => n.text), [
    NOTICES.storageBlocked,
    "Your old seat had expired, so you joined as black.",
    "This game already has two players.",
  ]);
  assert.equal(vm.notices[2].action, "startNew");
  assert.throws(() => viewModel(null), TypeError);
  assert.throws(() => viewModel({ fen: START }), /missing/);
});

test("players line names both sides when known; a room left back to waiting says it waits; joins are announced only for people", () => {
  const named = viewModel(snap({ seats: { A: { presence: "connected", colour: "white", nickname: "Alice" }, B: { presence: "connected", colour: "black", nickname: "Bob" } } }));
  assert.deepEqual(named.players, { white: "You (Alice)", black: "Opponent (Bob)" });
  const plain = viewModel(snap());
  assert.deepEqual(plain.players, { white: "You", black: "Opponent" });

  const left = viewModel(snap({ ...AFTER_D4, mode: "waiting", status: "playing", seats: { A: { presence: "connected", colour: "white" }, B: { presence: "empty", colour: "black" } } }));
  assert.equal(left.status.text, STATUS_TEXT.waiting, "nobody joined: still waiting, even with a game under way");
  assert.equal(left.status.sub, "They continue from this position.");

  const waiting = snap({ status: "waiting", mode: "waiting", seats: { A: { presence: "connected", colour: "white" }, B: { presence: "empty", colour: "black" } } });
  const passAlong = { ...waiting, status: "playing", mode: "pass_along", version: 1 };
  assert.equal(announcement(waiting, passAlong, "white"), null, "pass-along is no opponent joining");
  const joined = { ...waiting, status: "playing", mode: "online", version: 1, seats: { ...waiting.seats, B: { presence: "connected", colour: "black" } } };
  assert.equal(announcement(waiting, joined, "white"), "Your opponent joined.");
});

test("last seen is relative and vague, shown while the opponent to move is away", () => {
  const cases = [[0, "a few minutes ago"], [14 * 60, "a few minutes ago"], [15 * 60, "more than 15 minutes ago"],
    [45 * 60, "more than 30 minutes ago"], [90 * 60, "about an hour ago"], [5 * 3600, "hours ago"],
    [30 * 3600, "a day ago"], [5 * 86400, "days ago"]];
  for (const [seconds, phrase] of cases) assert.equal(lastSeenPhrase(seconds), phrase, `${seconds} s`);
  assert.equal(lastSeenPhrase(null), null);
  assert.equal(lastSeenPhrase(undefined), null);
  const away = viewModel(snap({ ...AFTER_D4, seats: { A: { presence: "connected", colour: "white" },
    B: { presence: "away", colour: "black", nickname: "Bob", lastSeenSeconds: 3 * 3600 } } }));
  assert.equal(away.status.text, "Waiting for Bob (Black) to move");
  assert.equal(away.status.sub, "Bob was last seen hours ago");
  const awayNoName = viewModel(snap({ ...AFTER_D4, seats: { A: { presence: "connected", colour: "white" },
    B: { presence: "away", colour: "black", lastSeenSeconds: 20 * 60 } } }));
  assert.equal(awayNoName.status.sub, "Black was last seen more than 15 minutes ago");
});
