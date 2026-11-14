// Tests for the arrow geometry in static/js/training/arrow.js (BR4.3): board percent, both orientations.
import { test } from "node:test";
import assert from "node:assert/strict";

import { arrowGeometry, arrowShape, squareCentre } from "../../static/js/training/arrow.js";

test("with White at the bottom, e2-e4 runs up the e-file between the square centres", () => {
  assert.deepEqual(squareCentre("a1", "white"), { x: 6.25, y: 93.75 });
  assert.deepEqual(squareCentre("h8", "white"), { x: 93.75, y: 6.25 });
  assert.deepEqual(arrowGeometry("e2", "e4", "white"), { x1: 56.25, y1: 81.25, x2: 56.25, y2: 56.25 });
  const { shaft, head } = arrowShape(arrowGeometry("e2", "e4", "white"));
  assert.deepEqual(head[0], [56.25, 56.25], "the tip is on the target centre");
  assert.equal(shaft.y2, 61.25, "the shaft stops at the head's base, 5 units short");
  assert.deepEqual([head[1][1], head[2][1]], [61.25, 61.25]);
});

test("with Black at the bottom the board is turned: e2-e4 runs down the screen", () => {
  assert.deepEqual(squareCentre("a1", "black"), { x: 93.75, y: 6.25 });
  assert.deepEqual(arrowGeometry("e2", "e4", "black"), { x1: 43.75, y1: 18.75, x2: 43.75, y2: 43.75 });
  assert.equal(arrowShape(arrowGeometry("e2", "e4", "black")).shaft.y2, 38.75);
});

test("a knight move is drawn straight from centre to centre, and bad input is refused", () => {
  const knight = arrowGeometry("g1", "f3", "white");
  assert.deepEqual(knight, { x1: 81.25, y1: 93.75, x2: 68.75, y2: 68.75 });
  const { shaft, head } = arrowShape(knight);
  const length = Math.hypot(head[0][0] - shaft.x2, head[0][1] - shaft.y2);
  assert.ok(Math.abs(length - 5) < 0.02, `the head is 5 units long (${length})`);
  assert.throws(() => arrowGeometry("g1", "g1", "white"), TypeError);
  assert.throws(() => arrowGeometry("z9", "f3", "white"), TypeError);
  assert.throws(() => arrowGeometry("g1", "f3", "sideways"), TypeError);
});
