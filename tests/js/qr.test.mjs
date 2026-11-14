// Tests for the QR code: static/js/qr-canvas.js and the vendored encoder static/js/vendor/qrcode.js
// (P2 U1, BR3.4, ADR-008). The last test reads the symbol back with an independent reader
// (function-pattern map, mask, zigzag, de-interleave, Reed-Solomon syndromes, byte segment),
// so a code that a phone could not scan fails here.
import { test } from "node:test";
import assert from "node:assert/strict";

import { QrTooLongError, drawQr, qrMatrix } from "../../static/js/qr-canvas.js";
import { encodeQr, formatBits, rsDivisor, rsRemainder, versionBits } from "../../static/js/vendor/qrcode.js";

const INVITE = "https://chess.example/r/ABC123"; // 30 bytes: version 3 at level M

test("the matrix size follows the version the text needs", () => {
  assert.equal(qrMatrix("HI").length, 21, "version 1");
  const invite = qrMatrix(INVITE);
  assert.equal(invite.length, 29, "a 30-byte invite link is version 3 (29 x 29)");
  assert.ok(invite.every((row) => row.length === 29 && row.every((m) => typeof m === "boolean")));
  assert.equal(qrMatrix("x".repeat(213)).length, 57, "213 bytes is the version 10 limit at level M");
});

test("finder patterns sit in three corners, with the timing lines and the dark module", () => {
  const m = qrMatrix(INVITE);
  const size = m.length;
  const isFinder = (ox, oy) => {
    for (let y = 0; y < 7; y += 1) {
      for (let x = 0; x < 7; x += 1) {
        const ring = Math.max(Math.abs(x - 3), Math.abs(y - 3));
        if (m[oy + y][ox + x] !== (ring !== 2)) return false;
      }
    }
    return true;
  };
  assert.ok(isFinder(0, 0), "top left");
  assert.ok(isFinder(size - 7, 0), "top right");
  assert.ok(isFinder(0, size - 7), "bottom left");
  assert.ok(!isFinder(size - 7, size - 7), "no finder in the fourth corner");
  for (let i = 0; i < 8; i += 1) {
    assert.equal(m[7][i], false, `separator under the top-left finder at ${i}`);
    assert.equal(m[i][7], false, `separator beside the top-left finder at ${i}`);
  }
  for (let i = 8; i < size - 8; i += 1) {
    assert.equal(m[6][i], i % 2 === 0, `timing row at ${i}`);
    assert.equal(m[i][6], i % 2 === 0, `timing column at ${i}`);
  }
  assert.equal(m[size - 8][8], true, "the dark module");
});

test("the same input always gives the same code; a different input a different one", () => {
  assert.deepEqual(qrMatrix(INVITE), qrMatrix(INVITE));
  assert.notDeepEqual(qrMatrix(INVITE), qrMatrix("https://chess.example/r/ABC124"));
});

test("text longer than version 10 allows is refused with an error, as are empty and missing input", () => {
  assert.throws(() => qrMatrix("x".repeat(214)), (error) => error instanceof QrTooLongError && error.capacity === 213);
  assert.throws(() => qrMatrix(""), TypeError);
  assert.throws(() => qrMatrix(null), TypeError);
  assert.throws(() => drawQr(null, INVITE), TypeError);
});

test("Reed-Solomon matches the published 1-M example (HELLO WORLD)", () => {
  const data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17];
  assert.deepEqual(rsRemainder(data, rsDivisor(10)), [196, 35, 39, 119, 235, 215, 231, 226, 93, 23]);
});

test("format and version information match the standard's tables", () => {
  const levelM = ["101010000010010", "101000100100101", "101111001111100", "101101101001011",
    "100010111111001", "100000011001110", "100111110010111", "100101010100000"];
  levelM.forEach((bits, mask) => assert.equal(formatBits("M", mask), parseInt(bits, 2), `M mask ${mask}`));
  assert.equal(versionBits(7), 0x07c94);
  assert.equal(versionBits(10), 0x0a4d3);
});

// ---- an independent reader ------------------------------------------------------

const BLOCKS_M = { 2: [[1, 28]], 3: [[1, 44]], 7: [[4, 31]], 10: [[4, 43], [1, 44]] };
const EC_M = { 2: 16, 3: 26, 7: 18, 10: 26 };
const ALIGN = { 2: [6, 18], 3: [6, 22], 7: [6, 22, 38], 10: [6, 28, 50] };
const MASK_TESTS = [
  (x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, (x) => x % 3 === 0, (x, y) => (x + y) % 3 === 0,
  (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0, (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0,
  (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0, (x, y) => (((x + y) % 2) + ((x * y) % 3)) % 2 === 0,
];

function functionMap(version) {
  const size = version * 4 + 17;
  const map = Array.from({ length: size }, () => new Array(size).fill(false));
  const area = (x0, y0, x1, y1) => {
    for (let y = y0; y <= y1; y += 1) for (let x = x0; x <= x1; x += 1) map[y][x] = true;
  };
  area(0, 0, 8, 8);
  area(size - 8, 0, size - 1, 8);
  area(0, size - 8, 8, size - 1);
  area(6, 0, 6, size - 1);
  area(0, 6, size - 1, 6);
  const pos = ALIGN[version];
  const last = pos.length - 1;
  pos.forEach((cx, i) => pos.forEach((cy, j) => {
    const finderCorner = (i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0);
    if (!finderCorner) area(cx - 2, cy - 2, cx + 2, cy + 2);
  }));
  if (version >= 7) {
    area(size - 11, 0, size - 9, 5);
    area(0, size - 11, 5, size - 9);
  }
  return map;
}

function readFormatMask(m) {
  let bits = 0;
  const at = (x, y) => (m[y][x] ? 1 : 0);
  const order = [];
  for (let i = 0; i <= 5; i += 1) order.push([8, i]);
  order.push([8, 7], [8, 8], [7, 8]);
  for (let i = 9; i < 15; i += 1) order.push([14 - i, 8]);
  order.forEach(([x, y], i) => { bits |= at(x, y) << i; });
  const mask = [0, 1, 2, 3, 4, 5, 6, 7].find((k) => formatBits("M", k) === bits);
  assert.notEqual(mask, undefined, `format bits ${bits.toString(2)} are a valid level-M code`);
  return mask;
}

function readCodewords(m, version) {
  const size = m.length;
  const fn = functionMap(version);
  const mask = MASK_TESTS[readFormatMask(m)];
  const bits = [];
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    const upward = ((right + 1) & 2) === 0;
    for (let vert = 0; vert < size; vert += 1) {
      const y = upward ? size - 1 - vert : vert;
      for (const x of [right, right - 1]) {
        if (!fn[y][x]) bits.push(m[y][x] !== mask(x, y) ? 1 : 0);
      }
    }
  }
  const codewords = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) codewords.push(bits.slice(i, i + 8).reduce((a, b) => (a << 1) | b, 0));
  return codewords;
}

const EXP = new Array(512);
const LOG = new Array(256);
for (let i = 0, x = 1; i < 255; i += 1) {
  EXP[i] = x;
  LOG[x] = i;
  x <<= 1;
  if (x & 0x100) x ^= 0x11d;
}
for (let i = 255; i < 512; i += 1) EXP[i] = EXP[i - 255];
const gfMul = (a, b) => (a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]);

function syndromesAreZero(block, ecLength) {
  for (let k = 0; k < ecLength; k += 1) {
    let s = 0;
    for (const c of block) s = gfMul(s, EXP[k]) ^ c; // Horner at alpha^k
    if (s !== 0) return false;
  }
  return true;
}

function decode(m) {
  const version = (m.length - 17) / 4;
  const all = readCodewords(m, version);
  const layout = BLOCKS_M[version].flatMap(([count, size]) => new Array(count).fill(size));
  const ecLength = EC_M[version];
  const blocks = layout.map(() => []);
  let i = 0;
  for (let k = 0; k < Math.max(...layout); k += 1) layout.forEach((size, b) => { if (k < size) blocks[b].push(all[i++]); });
  for (let k = 0; k < ecLength; k += 1) blocks.forEach((block) => block.push(all[i++]));
  blocks.forEach((block, b) => assert.ok(syndromesAreZero(block, ecLength), `version ${version} block ${b} has RS errors`));
  const data = blocks.flatMap((block, b) => block.slice(0, layout[b]));
  const bitstream = data.flatMap((byte) => [7, 6, 5, 4, 3, 2, 1, 0].map((s) => (byte >>> s) & 1));
  let p = 0;
  const take = (n) => { let v = 0; for (let k = 0; k < n; k += 1) v = (v << 1) | bitstream[p++]; return v; };
  assert.equal(take(4), 0b0100, "byte mode");
  const length = take(version < 10 ? 8 : 16);
  const bytes = Array.from({ length }, () => take(8));
  return { version, text: new TextDecoder().decode(new Uint8Array(bytes)) };
}

test("an independent reader decodes the codes back (versions 2, 3, 7 and 10, UTF-8 included)", () => {
  const cases = [
    ["https://chess.example/r/Q", 2],
    [INVITE, 3],
    [`https://justchess.example/r/ABC123?from=${"é".repeat(40)}`, 7],
    ["https://justchess.example/r/" + "Z".repeat(185), 10],
  ];
  for (const [text, version] of cases) {
    const symbol = encodeQr(text, { ecl: "M" });
    assert.equal(symbol.version, version, text);
    assert.deepEqual(decode(symbol.modules), { version, text });
  }
});
