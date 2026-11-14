// Tests for the captured row's helpers, static/js/captures.js (P2 U1, BR1.6).
import { test } from "node:test";
import assert from "node:assert/strict";

import { SanError, captureLabel, capturedPieces } from "../../static/js/captures.js";

// The snapshot's moveList shape: [{ number, white, black }].
function rows(...sans) {
  const list = [];
  sans.forEach((san, i) => {
    if (i % 2 === 0) list.push({ number: i / 2 + 1, white: san, black: null });
    else list[list.length - 1].black = san;
  });
  return list;
}

test("a normal capture by each side is listed for the side that took it", () => {
  assert.deepEqual(capturedPieces(rows("e4", "d5", "exd5")), { byWhite: ["p"], byBlack: [] });
  assert.deepEqual(capturedPieces(rows("e4", "d5", "exd5", "Qxd5")), { byWhite: ["p"], byBlack: ["P"] });
  // a flat SAN list works too
  assert.deepEqual(capturedPieces(["e4", "d5", "exd5", "Qxd5"]), { byWhite: ["p"], byBlack: ["P"] });
});

test("en passant takes the pawn beside the arrival square", () => {
  assert.deepEqual(capturedPieces(rows("e4", "a6", "e5", "d5", "exd6")), { byWhite: ["p"], byBlack: [] });
  // and the board after it is right: d5 is empty, so Qxd6 takes the white pawn on d6
  assert.deepEqual(capturedPieces(rows("e4", "a6", "e5", "d5", "exd6", "Qxd6")), { byWhite: ["p"], byBlack: ["P"] });
});

test("promotion with capture: the taken rook is listed and the promoted queen can itself be taken", () => {
  const line = ["a4", "b5", "axb5", "a6", "bxa6", "Bb7", "axb7", "Nc6", "bxa8=Q"];
  assert.deepEqual(capturedPieces(rows(...line)), { byWhite: ["r", "b", "p", "p"], byBlack: [] }, "ordered Q R B N P");
  assert.deepEqual(capturedPieces(rows(...line, "Qxa8")), { byWhite: ["r", "b", "p", "p"], byBlack: ["Q"] });
});

test("no captures: an empty list and a quiet opening give two empty rows", () => {
  assert.deepEqual(capturedPieces([]), { byWhite: [], byBlack: [] });
  assert.deepEqual(capturedPieces(rows("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "O-O")), { byWhite: [], byBlack: [] });
  assert.throws(() => capturedPieces(null), TypeError);
});

test("the player's own pending move is applied after the list (UCI or object)", () => {
  const list = rows("e4", "d5");
  assert.deepEqual(capturedPieces(list, "e4d5"), { byWhite: ["p"], byBlack: [] });
  assert.deepEqual(capturedPieces(list, { from: "e4", to: "d5", promotion: null }), { byWhite: ["p"], byBlack: [] });
  assert.deepEqual(capturedPieces(list, "g1f3"), { byWhite: [], byBlack: [] }, "a quiet pending move adds nothing");
  assert.throws(() => capturedPieces(list, "zz"), TypeError);
});

test("a pinned piece is not a SAN candidate, so the replay follows the right knight", () => {
  // 3.Nc3 is pinned by Bb4, so 4.Ne2 is the g1 knight; Bxc3+ then takes the c3 knight
  const line = ["e4", "e5", "d4", "Bb4+", "Nc3", "Nf6", "Ne2", "Bxc3+", "Nxc3"];
  assert.deepEqual(capturedPieces(rows(...line)), { byWhite: ["b"], byBlack: ["N"] });
});

test("a move that cannot be resolved throws SanError instead of guessing", () => {
  assert.throws(() => capturedPieces(rows("e5")), SanError, "no white pawn reaches e5");
  assert.throws(() => capturedPieces(rows("Nf3", "Nf6", "Nc4")), SanError, "neither white knight reaches c4");
  assert.throws(() => capturedPieces(rows("hello")), SanError);
});

test("the row's accessible label names the pieces for the viewer", () => {
  assert.equal(captureLabel(["p", "n"], "you"), "Pieces you captured: black pawn, black knight");
  assert.equal(captureLabel(["Q"], "opponent"), "Pieces your opponent captured: white queen");
  assert.equal(captureLabel([], "white"), "Pieces White captured: none");
  assert.equal(captureLabel(["R"], "black"), "Pieces Black captured: white rook");
  assert.throws(() => captureLabel([], "someone"), TypeError);
});
