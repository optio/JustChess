// Tests for static/js/board/geometry.js (BR1.1-BR1.3, BR2.1, BR2.2, BR2.4, BR3.2, BR4.1).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  FenError,
  START_FEN,
  applyMove,
  checkSquare,
  diffMove,
  frameLabels,
  isDarkSquare,
  isPromotionTarget,
  moveFocus,
  parseFen,
  squareLabels,
  squareName,
  squaresInOrder,
  targetsFrom,
} from "../../static/js/board/geometry.js";

const pieces = (fen) => parseFen(fen).pieces;

test("square colour: a1 is dark, h1 is light, and colours alternate (BR1.1)", () => {
  assert.equal(isDarkSquare("a1"), true);
  assert.equal(isDarkSquare("h1"), false);
  assert.equal(isDarkSquare("a8"), false);
  assert.equal(isDarkSquare("h8"), true);
  assert.equal(isDarkSquare("e4"), false);
  assert.equal(isDarkSquare("d4"), true);
});

test("orientation: white has a8 top left; black has h1 top left (BR1.2)", () => {
  const white = squaresInOrder("white");
  assert.equal(white[0][0], "a8");
  assert.equal(white[7][7], "h1");
  const black = squaresInOrder("black");
  assert.equal(black[0][0], "h1");
  assert.equal(black[0][7], "a1");
  assert.equal(black[7][0], "h8");
  assert.equal(new Set(black.flat()).size, 64);
  assert.throws(() => squaresInOrder("red"), TypeError);
});

test("labels follow the orientation in both modes (BR1.3)", () => {
  assert.deepEqual(squareLabels("a1", "white"), { file: "a", rank: "1" });
  assert.deepEqual(squareLabels("h1", "white"), { file: "h", rank: null });
  assert.deepEqual(squareLabels("a8", "white"), { file: null, rank: "8" });
  assert.deepEqual(squareLabels("h8", "black"), { file: "h", rank: "8" });
  assert.deepEqual(squareLabels("a1", "black"), { file: null, rank: null });
  assert.deepEqual(squareLabels("h1", "black"), { file: null, rank: "1" });
  assert.deepEqual(frameLabels("white"), { files: [..."abcdefgh"], ranks: [..."87654321"] });
  assert.deepEqual(frameLabels("black"), { files: [..."hgfedcba"], ranks: [..."12345678"] });
});

test("FEN parsing reads pieces and turn, and refuses bad FENs", () => {
  const start = parseFen(START_FEN);
  assert.equal(start.turn, "white");
  assert.equal(Object.keys(start.pieces).length, 32);
  assert.equal(start.pieces.e1, "K");
  assert.equal(start.pieces.d8, "q");
  assert.equal(start.pieces.e4, undefined);
  assert.equal(parseFen("4k3/8/8/8/8/8/8/4K3 b - - 0 1").turn, "black");
  for (const bad of [
    "",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w",            // 7 ranks
    "rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w",   // 9 squares in a rank
    "rnbqkbnr/ppppxppp/8/8/8/8/PPPPPPPP/RNBQKBNR w",   // bad letter
    "rnbq1bnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w",   // no black king
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x",   // bad side to move
  ]) {
    assert.throws(() => parseFen(bad), FenError, bad);
  }
});

test("targets match the legal moves exactly and promotion is detected (BR2.1, BR2.2)", () => {
  const legal = ["e2e3", "e2e4", "g1f3", "g1h3", "b7b8q", "b7b8r", "b7b8b", "b7b8n", "b7a8q", "b7a8r", "b7a8b", "b7a8n"];
  assert.deepEqual([...targetsFrom("e2", legal)].sort(), ["e3", "e4"]);
  assert.deepEqual([...targetsFrom("g1", legal)].sort(), ["f3", "h3"]);
  assert.equal(targetsFrom("d2", legal).size, 0);
  assert.deepEqual([...targetsFrom("b7", legal)].sort(), ["a8", "b8"]);
  assert.equal(isPromotionTarget("b7", "b8", legal), true);
  assert.equal(isPromotionTarget("b7", "a8", legal), true);
  assert.equal(isPromotionTarget("e2", "e4", legal), false);
  assert.equal(isPromotionTarget("e2", "e5", legal), false);
});

test("diffMove: normal move, capture, both castlings, en passant, promotion, null (BR4.1)", () => {
  const start = pieces(START_FEN);
  const afterE4 = pieces("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1");
  assert.deepEqual(diffMove(start, afterE4, { from: "e2", to: "e4" }), {
    moves: [{ piece: "P", from: "e2", to: "e4", becomes: "P" }],
    captured: [],
  });
  assert.deepEqual(diffMove(start, afterE4, "e2e4").moves[0].to, "e4", "UCI lastMove is accepted");

  const beforeCapture = pieces("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2");
  const afterCapture = pieces("rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2");
  assert.deepEqual(diffMove(beforeCapture, afterCapture, { from: "e4", to: "d5" }).captured, [{ piece: "p", square: "d5" }]);

  const castleReady = pieces("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
  const shortCastle = diffMove(castleReady, pieces("r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1"), { from: "e1", to: "g1" });
  assert.deepEqual(shortCastle.moves.map((m) => m.from + m.to), ["e1g1", "h1f1"]);
  const longCastle = diffMove(castleReady, pieces("2kr3r/8/8/8/8/8/8/R3K2R w KQ - 1 2"), { from: "e8", to: "c8" });
  assert.deepEqual(longCastle.moves.map((m) => m.from + m.to), ["e8c8", "a8d8"]);

  const epBefore = pieces("4k3/8/8/3Pp3/8/8/8/4K3 w - e6 0 1");
  const epAfter = pieces("4k3/8/4P3/8/8/8/8/4K3 b - - 0 1");
  assert.deepEqual(diffMove(epBefore, epAfter, { from: "d5", to: "e6" }).captured, [{ piece: "p", square: "e5" }]);

  const promoBefore = pieces("1n2k3/P7/8/8/8/8/8/4K3 w - - 0 1");
  const promoAfter = pieces("1Q2k3/8/8/8/8/8/8/4K3 b - - 0 1");
  const promo = diffMove(promoBefore, promoAfter, { from: "a7", to: "b8" });
  assert.deepEqual(promo.moves, [{ piece: "P", from: "a7", to: "b8", becomes: "Q" }]);
  assert.deepEqual(promo.captured, [{ piece: "n", square: "b8" }]);

  assert.equal(diffMove(start, afterCapture, { from: "e4", to: "d5" }), null, "unrelated positions");
  assert.equal(diffMove(start, afterE4, { from: "d2", to: "d4" }), null, "lastMove does not match");
  assert.equal(diffMove(start, afterE4, null), null, "no lastMove");
  assert.deepEqual(applyMove(castleReady, "e1", "c1"), pieces("r3k2r/8/8/8/8/8/8/2KR3R b kq - 1 1"));
});

test("focus moves stop at the edges and are mirrored for black (BR2.4)", () => {
  assert.equal(moveFocus("e4", "ArrowUp", "white"), "e5");
  assert.equal(moveFocus("e4", "ArrowRight", "white"), "f4");
  assert.equal(moveFocus("e4", "ArrowUp", "black"), "e3");
  assert.equal(moveFocus("e4", "ArrowRight", "black"), "d4");
  assert.equal(moveFocus("a8", "ArrowUp", "white"), "a8");
  assert.equal(moveFocus("a8", "ArrowLeft", "white"), "a8");
  assert.equal(moveFocus("h1", "ArrowUp", "black"), "h1");
  assert.equal(moveFocus("h1", "ArrowLeft", "black"), "h1");
  assert.equal(moveFocus("h1", "ArrowDown", "black"), "h2");
  assert.equal(moveFocus("e4", "Tab", "white"), "e4");
});

test("accessible names and the king in check (BR3.2, BR3.1)", () => {
  assert.equal(squareName("e4", "P"), "e4, white pawn");
  assert.equal(squareName("e4", null), "e4, empty");
  assert.equal(squareName("g8", "n", { selected: true }), "g8, black knight, selected");
  assert.equal(squareName("f6", null, { target: true }), "f6, empty, legal move");
  assert.equal(squareName("d5", "p", { target: true }), "d5, black pawn, legal move");
  const position = parseFen("4k3/8/8/8/8/8/8/R3K3 b - - 0 1");
  assert.equal(checkSquare(position.pieces, position.turn, true), "e8");
  assert.equal(checkSquare(position.pieces, position.turn, false), null);
});
