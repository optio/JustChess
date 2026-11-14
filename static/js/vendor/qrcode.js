/*!
 * qrcode.js — a small QR Code Model 2 encoder (byte mode, versions 1-10).
 *
 * Written for JustChess in 2026 (it is not a copy of another library). The
 * algorithm follows ISO/IEC 18004:2015: byte-mode segment, Reed-Solomon error
 * correction over GF(256) with the 0x11D polynomial, block interleaving,
 * finder / timing / alignment patterns, BCH-coded format and version
 * information, and the eight data masks chosen by the standard penalty rules.
 *
 * MIT License
 *
 * Copyright (c) 2026 the JustChess authors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 * API:
 *   encodeQr(text, { ecl = "M" }) -> { version, size, mask, modules: boolean[][] }
 *     modules[y][x] is true for a dark module. Throws QrTooLongError when the
 *     UTF-8 text does not fit version 10 at the chosen level.
 *   QrTooLongError
 * Internals exported for tests: rsRemainder, rsDivisor, formatBits, versionBits.
 */

export const MAX_VERSION = 10;

/** Thrown when the text does not fit the largest supported version. */
export class QrTooLongError extends Error {
  constructor(byteLength, capacity) {
    super(`QR text is ${byteLength} bytes; at most ${capacity} bytes fit (version ${MAX_VERSION})`);
    this.name = "QrTooLongError";
    this.byteLength = byteLength;
    this.capacity = capacity;
  }
}

// Error correction level: format-bit value and, per version 1-10, the EC
// codewords per block and the block layout [[count, dataCodewords], ...].
const LEVELS = {
  L: {
    bits: 1,
    ec: [7, 10, 15, 20, 26, 18, 20, 24, 30, 18],
    blocks: [[[1, 19]], [[1, 34]], [[1, 55]], [[1, 80]], [[1, 108]], [[2, 68]], [[2, 78]], [[2, 97]], [[2, 116]], [[2, 68], [2, 69]]],
  },
  M: {
    bits: 0,
    ec: [10, 16, 26, 18, 24, 16, 18, 22, 22, 26],
    blocks: [[[1, 16]], [[1, 28]], [[1, 44]], [[2, 32]], [[2, 43]], [[4, 27]], [[4, 31]], [[2, 38], [2, 39]], [[3, 36], [2, 37]], [[4, 43], [1, 44]]],
  },
};

// ---- Reed-Solomon over GF(256), primitive polynomial x^8+x^4+x^3+x^2+1 ----

function gfMultiply(x, y) {
  let z = 0;
  for (let i = 7; i >= 0; i -= 1) {
    z = (z << 1) ^ ((z >>> 7) * 0x11d);
    z ^= ((y >>> i) & 1) * x;
  }
  return z & 0xff;
}

/** Generator polynomial coefficients (leading 1 dropped) for `degree` EC codewords. */
export function rsDivisor(degree) {
  const result = new Array(degree).fill(0);
  result[degree - 1] = 1;
  let root = 1;
  for (let i = 0; i < degree; i += 1) {
    for (let j = 0; j < degree; j += 1) {
      result[j] = gfMultiply(result[j], root);
      if (j + 1 < degree) result[j] ^= result[j + 1];
    }
    root = gfMultiply(root, 0x02);
  }
  return result;
}

/** The EC codewords of `data` for the given divisor. */
export function rsRemainder(data, divisor) {
  const result = new Array(divisor.length).fill(0);
  for (const byte of data) {
    const factor = byte ^ result.shift();
    result.push(0);
    divisor.forEach((coefficient, i) => {
      result[i] ^= gfMultiply(coefficient, factor);
    });
  }
  return result;
}

// ---- BCH-coded format and version information ----

/** The 15 format bits for a level letter and mask 0-7. */
export function formatBits(ecl, mask) {
  const data = (LEVELS[ecl].bits << 3) | mask;
  let rem = data;
  for (let i = 0; i < 10; i += 1) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
  return ((data << 10) | rem) ^ 0x5412;
}

/** The 18 version bits (versions 7 and up). */
export function versionBits(version) {
  let rem = version;
  for (let i = 0; i < 12; i += 1) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
  return (version << 12) | rem;
}

function bit(value, index) {
  return ((value >>> index) & 1) !== 0;
}

// ---- capacity ----

function rawDataModules(version) {
  let result = (16 * version + 128) * version + 64;
  if (version >= 2) {
    const align = Math.floor(version / 7) + 2;
    result -= (25 * align - 10) * align - 55;
    if (version >= 7) result -= 36;
  }
  return result;
}

function dataCodewords(level, version) {
  return level.blocks[version - 1].reduce((sum, [count, size]) => sum + count * size, 0);
}

function countBits(version) {
  return version < 10 ? 8 : 16;
}

function byteCapacity(level, version) {
  return Math.floor((dataCodewords(level, version) * 8 - 4 - countBits(version)) / 8);
}

// ---- data codewords ----

function utf8(text) {
  return Array.from(new TextEncoder().encode(text));
}

function dataStream(bytes, level, version) {
  const bits = [];
  const push = (value, length) => {
    for (let i = length - 1; i >= 0; i -= 1) bits.push((value >>> i) & 1);
  };
  push(0b0100, 4);
  push(bytes.length, countBits(version));
  bytes.forEach((byte) => push(byte, 8));
  const capacityBits = dataCodewords(level, version) * 8;
  push(0, Math.min(4, capacityBits - bits.length));
  push(0, (8 - (bits.length % 8)) % 8);
  const codewords = [];
  for (let i = 0; i < bits.length; i += 8) codewords.push(bits.slice(i, i + 8).reduce((acc, b) => (acc << 1) | b, 0));
  for (let pad = 0xec; codewords.length < capacityBits / 8; pad ^= 0xec ^ 0x11) codewords.push(pad);
  return codewords;
}

function interleave(codewords, level, version) {
  const ecLength = level.ec[version - 1];
  const divisor = rsDivisor(ecLength);
  const blocks = [];
  let offset = 0;
  for (const [count, size] of level.blocks[version - 1]) {
    for (let i = 0; i < count; i += 1) {
      const data = codewords.slice(offset, offset + size);
      offset += size;
      blocks.push({ data, ec: rsRemainder(data, divisor) });
    }
  }
  const result = [];
  const longest = Math.max(...blocks.map((block) => block.data.length));
  for (let i = 0; i < longest; i += 1) {
    for (const block of blocks) if (i < block.data.length) result.push(block.data[i]);
  }
  for (let i = 0; i < ecLength; i += 1) {
    for (const block of blocks) result.push(block.ec[i]);
  }
  return result;
}

// ---- the symbol ----

function alignmentPositions(version) {
  if (version === 1) return [];
  const count = Math.floor(version / 7) + 2;
  const size = version * 4 + 17;
  const step = Math.ceil((version * 4 + 4) / (count * 2 - 2)) * 2;
  const result = [6];
  for (let pos = size - 7; result.length < count; pos -= step) result.splice(1, 0, pos);
  return result;
}

class Symbol {
  constructor(version, ecl) {
    this.version = version;
    this.ecl = ecl;
    this.size = version * 4 + 17;
    this.modules = Array.from({ length: this.size }, () => new Array(this.size).fill(false));
    this.isFunction = Array.from({ length: this.size }, () => new Array(this.size).fill(false));
    this.drawFunctionPatterns();
  }

  setFunction(x, y, dark) {
    this.modules[y][x] = dark;
    this.isFunction[y][x] = true;
  }

  drawFunctionPatterns() {
    const { size } = this;
    for (let i = 0; i < size; i += 1) {
      this.setFunction(6, i, i % 2 === 0);
      this.setFunction(i, 6, i % 2 === 0);
    }
    this.drawFinder(3, 3);
    this.drawFinder(size - 4, 3);
    this.drawFinder(3, size - 4);
    const positions = alignmentPositions(this.version);
    const last = positions.length - 1;
    positions.forEach((x, i) => positions.forEach((y, j) => {
      const corner = (i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0);
      if (!corner) this.drawAlignment(x, y);
    }));
    this.drawFormat(0); // reserved now, redrawn with the chosen mask
    this.drawVersion();
  }

  drawFinder(cx, cy) {
    for (let dy = -4; dy <= 4; dy += 1) {
      for (let dx = -4; dx <= 4; dx += 1) {
        const x = cx + dx;
        const y = cy + dy;
        if (x < 0 || y < 0 || x >= this.size || y >= this.size) continue;
        const distance = Math.max(Math.abs(dx), Math.abs(dy));
        this.setFunction(x, y, distance !== 2 && distance !== 4);
      }
    }
  }

  drawAlignment(cx, cy) {
    for (let dy = -2; dy <= 2; dy += 1) {
      for (let dx = -2; dx <= 2; dx += 1) this.setFunction(cx + dx, cy + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }
  }

  drawFormat(mask) {
    const bits = formatBits(this.ecl, mask);
    const { size } = this;
    for (let i = 0; i <= 5; i += 1) this.setFunction(8, i, bit(bits, i));
    this.setFunction(8, 7, bit(bits, 6));
    this.setFunction(8, 8, bit(bits, 7));
    this.setFunction(7, 8, bit(bits, 8));
    for (let i = 9; i < 15; i += 1) this.setFunction(14 - i, 8, bit(bits, i));
    for (let i = 0; i < 8; i += 1) this.setFunction(size - 1 - i, 8, bit(bits, i));
    for (let i = 8; i < 15; i += 1) this.setFunction(8, size - 15 + i, bit(bits, i));
    this.setFunction(8, size - 8, true); // the dark module
  }

  drawVersion() {
    if (this.version < 7) return;
    const bits = versionBits(this.version);
    for (let i = 0; i < 18; i += 1) {
      const a = this.size - 11 + (i % 3);
      const b = Math.floor(i / 3);
      this.setFunction(a, b, bit(bits, i));
      this.setFunction(b, a, bit(bits, i));
    }
  }

  drawCodewords(codewords) {
    const { size } = this;
    let i = 0;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      const upward = ((right + 1) & 2) === 0;
      for (let vert = 0; vert < size; vert += 1) {
        const y = upward ? size - 1 - vert : vert;
        for (let j = 0; j < 2; j += 1) {
          const x = right - j;
          if (this.isFunction[y][x] || i >= codewords.length * 8) continue;
          this.modules[y][x] = bit(codewords[i >>> 3], 7 - (i & 7));
          i += 1;
        }
      }
    }
  }

  applyMask(mask) {
    const test = MASKS[mask];
    for (let y = 0; y < this.size; y += 1) {
      for (let x = 0; x < this.size; x += 1) {
        if (!this.isFunction[y][x] && test(x, y)) this.modules[y][x] = !this.modules[y][x];
      }
    }
  }
}

const MASKS = [
  (x, y) => (x + y) % 2 === 0,
  (x, y) => y % 2 === 0,
  (x) => x % 3 === 0,
  (x, y) => (x + y) % 3 === 0,
  (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0,
  (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0,
  (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0,
  (x, y) => (((x + y) % 2) + ((x * y) % 3)) % 2 === 0,
];

// ---- mask penalty (ISO/IEC 18004 section 7.8.3) ----

const FINDER_LIKE = [
  [true, false, true, true, true, false, true, false, false, false, false],
  [false, false, false, false, true, false, true, true, true, false, true],
];

function linePenalty(line) {
  let penalty = 0;
  let run = 1;
  for (let i = 1; i <= line.length; i += 1) {
    if (i < line.length && line[i] === line[i - 1]) {
      run += 1;
      continue;
    }
    if (run >= 5) penalty += run - 2;
    run = 1;
  }
  for (let i = 0; i + 11 <= line.length; i += 1) {
    for (const pattern of FINDER_LIKE) {
      if (pattern.every((dark, k) => line[i + k] === dark)) penalty += 40;
    }
  }
  return penalty;
}

function penaltyScore(modules) {
  const size = modules.length;
  let penalty = 0;
  let dark = 0;
  for (let y = 0; y < size; y += 1) {
    penalty += linePenalty(modules[y]);
    penalty += linePenalty(modules.map((row) => row[y]));
  }
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      if (modules[y][x]) dark += 1;
      if (y + 1 < size && x + 1 < size) {
        const c = modules[y][x];
        if (c === modules[y][x + 1] && c === modules[y + 1][x] && c === modules[y + 1][x + 1]) penalty += 3;
      }
    }
  }
  const total = size * size;
  penalty += Math.floor(Math.abs(dark * 100 / total - 50) / 5) * 10;
  return penalty;
}

// ---- public API ----

export function encodeQr(text, { ecl = "M" } = {}) {
  if (typeof text !== "string") throw new TypeError("encodeQr needs a string");
  const level = LEVELS[ecl];
  if (!level) throw new TypeError(`unsupported error correction level ${JSON.stringify(ecl)}`);
  const bytes = utf8(text);
  let version = 1;
  while (version <= MAX_VERSION && bytes.length > byteCapacity(level, version)) version += 1;
  if (version > MAX_VERSION) throw new QrTooLongError(bytes.length, byteCapacity(level, MAX_VERSION));
  const codewords = interleave(dataStream(bytes, level, version), level, version);
  if (codewords.length !== Math.floor(rawDataModules(version) / 8)) {
    throw new Error(`QR internal error: ${codewords.length} codewords for version ${version}`);
  }
  const symbol = new Symbol(version, ecl);
  symbol.drawCodewords(codewords);
  let best = null;
  for (let mask = 0; mask < 8; mask += 1) {
    symbol.applyMask(mask);
    symbol.drawFormat(mask);
    const score = penaltyScore(symbol.modules);
    if (best === null || score < best.score) best = { mask, score };
    symbol.applyMask(mask); // XOR again to undo
  }
  symbol.applyMask(best.mask);
  symbol.drawFormat(best.mask);
  return { version, size: symbol.size, mask: best.mask, modules: symbol.modules.map((row) => [...row]) };
}
