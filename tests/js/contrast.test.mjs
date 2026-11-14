// Contrast tests for static/css/tokens.css through static/js/contrast.js (WCAG 2.1 AA, NFR6).
// Thresholds are fixed here: pieces 3:1, text 4.5:1. Never lower them to pass; adjust tokens instead.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  BOARD_THEMES,
  buildPalette,
  contrastRatio,
  contrastReport,
  parseColor,
  relativeLuminance,
  resolveColor,
} from "../../static/js/contrast.js";

const STATIC = fileURLToPath(new URL("../../static/", import.meta.url));
const report = contrastReport(buildPalette(readFileSync(`${STATIC}css/tokens.css`, "utf8")));

function assertAll(results, min, label) {
  assert.ok(results.length > 0, `${label}: no pairs were checked`);
  const failing = results.filter((r) => r.ratio < min).map((r) => `${r.name}: ${r.ratio.toFixed(2)} < ${min}`);
  assert.deepEqual(failing, [], `${label} below threshold`);
}

test("the luminance helper matches the WCAG reference values", () => {
  assert.equal(relativeLuminance("#000000"), 0);
  assert.equal(relativeLuminance("#FFFFFF"), 1);
  assert.equal(contrastRatio("#000", "#fff"), 21);
  assert.equal(contrastRatio("#777777", "#777777"), 1);
  assert.ok(Math.abs(contrastRatio("#767676", "#FFFFFF") - 4.54) < 0.01);
  assert.ok(Math.abs(contrastRatio("rgba(0, 0, 0, 0.5)", "#FFFFFF") - contrastRatio("#808080", "#FFFFFF")) < 0.05);
  assert.deepEqual(parseColor("#abc"), { r: 170, g: 187, b: 204, a: 1 });
  assert.throws(() => parseColor("brass"), TypeError);
});

test("pieces reach 3:1 against all six squares (fill or edge)", () => {
  assert.equal(report.pieces.length, 12, "3 themes x 2 squares x 2 colours");
  assertAll(report.pieces, 3, "pieces");
});

test("piece tokens match the colours inside the cburnett SVG files", () => {
  const dir = `${STATIC}pieces/cburnett/`;
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".svg"))) {
    const svg = readFileSync(dir + file, "utf8");
    if (file.startsWith("w")) {
      assert.match(svg, /fill="#fff"/, `${file} has a white fill`);
      assert.match(svg, /stroke="#000"/, `${file} has the dark outline`);
    } else {
      assert.match(svg, /stroke="#000"/, `${file} is drawn in black`);
      assert.doesNotMatch(svg, /fill="#fff"/, `${file} has no white body`);
    }
  }
});

test("coordinate labels reach 4.5:1 on the squares and in the frame", () => {
  assertAll(report.labels, 4.5, "labels");
});

test("coordinate labels stay at 4.5:1 under the last-move highlight on all three boards, in both themes (U2 review)", () => {
  assert.equal(report.lastMove.length, 12, "3 boards x 2 squares x 2 page themes");
  for (const board of BOARD_THEMES) {
    for (const theme of ["light", "dark"]) {
      for (const square of ["light", "dark"]) {
        const name = `${board} (${theme} theme): label on ${square} square under the last-move highlight`;
        assert.ok(report.lastMove.some((r) => r.name === name), `${name} is checked`);
      }
    }
  }
  assertAll(report.lastMove, 4.5, "labels under the last-move highlight");
});

test("the training arrow reaches 3:1 against all six squares in both themes, by its fill or its outline (U6)", () => {
  assert.equal(report.arrow.length, 12, "3 boards x 2 squares x 2 page themes");
  for (const board of BOARD_THEMES) {
    for (const theme of ["light", "dark"]) {
      for (const square of ["light", "dark"]) {
        assert.ok(report.arrow.some((r) => r.name.startsWith(`${board} (${theme} theme): arrow `) && r.name.endsWith(` on ${square} square`)),
          `${board} ${theme} ${square} is checked`);
      }
    }
  }
  assertAll(report.arrow, 3, "arrow");
});

test("the color-mix highlight token resolves to its colour at the stated alpha", () => {
  const t = (name) => ({ "--x": "#808080", "--hl": "color-mix(in srgb, var(--x) 38%, transparent)", "--plain": "#123456" })[name];
  assert.deepEqual(resolveColor(t, "--hl"), { r: 128, g: 128, b: 128, a: 0.38 });
  assert.deepEqual(resolveColor(t, "--plain"), { r: 18, g: 52, b: 86, a: 1 });
});

test("primary and quiet buttons, body, muted, link and baize text reach 4.5:1 in both themes", () => {
  const text = report.theme.filter((r) => r.min === 4.5);
  for (const theme of ["light", "dark"]) {
    for (const kind of ["primary button text", "body text on page", "muted text on paper", "your-move text on baize"]) {
      assert.ok(text.some((r) => r.name === `${theme}: ${kind}`), `${theme}: ${kind} is checked`);
    }
  }
  assertAll(text, 4.5, "text");
  assertAll(report.theme.filter((r) => r.min === 3), 3, "focus ring");
});
