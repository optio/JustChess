// Tests for the board-fit mirror, static/js/layout.js (P2 U1, BR2.1-BR2.4; FR4.1, FR4.2).
import { test } from "node:test";
import assert from "node:assert/strict";

import { boardMode, boardSide } from "../../static/js/layout.js";

// functional-spec.md W2: the 7 FR4.1 sizes with their mode and board side.
const SIZES = [
  [360, 640, "portrait", 360],
  [390, 844, "portrait", 390],
  [768, 600, "portrait", 448],
  [768, 1024, "portrait", 736],
  [1280, 720, "desktop", 610],
  [640, 360, "landscape-phone", 336],
  [844, 390, "landscape-phone", 366],
];

test("portrait phones and tablets: edge to edge under 400 px, else limited by the height or the gutters", () => {
  for (const [w, h, mode, side] of SIZES.filter((s) => s[2] === "portrait")) {
    assert.equal(boardMode(w, h), mode, `${w} x ${h}`);
    assert.equal(boardSide(w, h), side, `${w} x ${h}`);
  }
});

test("desktop: the side is the height minus 110 px, capped at 640 px", () => {
  assert.equal(boardMode(1280, 720), "desktop");
  assert.equal(boardSide(1280, 720), 610);
  assert.equal(boardSide(1280, 900), 640, "capped");
  assert.equal(boardSide(1920, 1080), 640, "capped");
});

test("landscape phones: the side is the height minus 24 px", () => {
  for (const [w, h, mode, side] of SIZES.filter((s) => s[2] === "landscape-phone")) {
    assert.equal(boardMode(w, h), mode, `${w} x ${h}`);
    assert.equal(boardSide(w, h), side, `${w} x ${h}`);
  }
});

test("1024 x 500 is landscape-phone, not desktop (the landscape rule wins)", () => {
  assert.equal(boardMode(1024, 500), "landscape-phone");
  assert.equal(boardSide(1024, 500), 476);
  assert.equal(boardMode(1024, 501), "desktop", "one pixel taller is desktop");
  assert.equal(boardMode(500, 500), "portrait", "a square viewport is not landscape");
});

test("the floors: 352 px at 320 px wide (the page scrolls sideways), 288 px in a very short landscape", () => {
  assert.equal(boardMode(320, 568), "portrait");
  assert.equal(boardSide(320, 568), 352);
  assert.equal(boardSide(568, 300), 288, "8 x 36 px");
  assert.equal(boardMode(450, 460), "portrait");
  assert.equal(boardSide(450, 460), 352, "a short portrait window keeps the 352 px floor");
});

test("at every FR4.1 size the squares meet the floor, and bad sizes are refused", () => {
  for (const [w, h, mode] of SIZES) {
    const square = boardSide(w, h) / 8;
    assert.ok(square >= (mode === "landscape-phone" ? 36 : 44), `${w} x ${h}: ${square} px squares`);
  }
  assert.throws(() => boardMode(0, 600), TypeError);
  assert.throws(() => boardSide(Number.NaN, 600), TypeError);
});
