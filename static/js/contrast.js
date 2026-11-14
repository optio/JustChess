/**
 * WCAG 2.1 contrast helpers and the token contrast audit (U2). Pure, no DOM.
 *
 * - parseColor / relativeLuminance / contrastRatio / composite: the WCAG
 *   relative-luminance formula, with alpha colours composited over the
 *   background first.
 * - parseTokenBlocks / buildPalette: read static/css/tokens.css text into the
 *   light and dark page palettes and the three board palettes.
 * - contrastReport: every pair the design must meet, with its threshold:
 *   pieces 3:1 against all six squares (fill or edge), labels 4.5:1 (also on
 *   squares under the last-move highlight, both page themes, added in U3),
 *   primary and quiet buttons 4.5:1, body and muted text 4.5:1, focus ring 3:1,
 *   and the training arrow 3:1 on every square in both page themes (U6).
 *
 * Used by tests/js/contrast.test.mjs and by the demo page's self-check, so
 * both judge the same CSS with the same thresholds.
 */

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;
const RGB = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i;

export const PIECE_MIN = 3;
export const TEXT_MIN = 4.5;
export const NON_TEXT_MIN = 3;

/** "#abc", "#aabbcc", "rgb(…)", "rgba(…)" -> { r, g, b, a }. Throws on anything else. */
export function parseColor(value) {
  const text = String(value).trim();
  const hex = HEX.exec(text);
  if (hex) {
    const digits = hex[1].length === 3 ? [...hex[1]].map((d) => d + d).join("") : hex[1];
    return { r: parseInt(digits.slice(0, 2), 16), g: parseInt(digits.slice(2, 4), 16), b: parseInt(digits.slice(4, 6), 16), a: 1 };
  }
  const rgb = RGB.exec(text);
  if (rgb) return { r: Number(rgb[1]), g: Number(rgb[2]), b: Number(rgb[3]), a: rgb[4] === undefined ? 1 : Number(rgb[4]) };
  throw new TypeError(`not a colour: ${JSON.stringify(value)}`);
}

function toColor(value) {
  return typeof value === "string" ? parseColor(value) : value;
}

/** Alpha-composite fg over an opaque bg. */
export function composite(fg, bg) {
  const top = toColor(fg);
  const base = toColor(bg);
  const mix = (channel) => top[channel] * top.a + base[channel] * (1 - top.a);
  return { r: mix("r"), g: mix("g"), b: mix("b"), a: 1 };
}

function linear(channel) {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(color) {
  const { r, g, b } = toColor(color);
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

/** WCAG contrast ratio of fg on bg (fg composited over bg when translucent). */
export function contrastRatio(fg, bg) {
  const base = toColor(bg);
  const top = composite(fg, base);
  const a = relativeLuminance(top);
  const b = relativeLuminance(base);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

/** { selector: { "--name": "value" } } for every innermost `selector { … }` block. */
export function parseTokenBlocks(css) {
  const blocks = {};
  const pattern = /([^{}]+)\{([^{}]*)\}/g;
  for (const match of stripComments(css).matchAll(pattern)) {
    const declarations = {};
    for (const line of match[2].split(";")) {
      const index = line.indexOf(":");
      if (index < 0) continue;
      const name = line.slice(0, index).trim();
      if (name.startsWith("--")) declarations[name] = line.slice(index + 1).trim();
    }
    for (const selector of match[1].split(",")) {
      const key = selector.trim();
      blocks[key] = { ...(blocks[key] || {}), ...declarations };
    }
  }
  return blocks;
}

function resolve(tokens, name, seen = new Set()) {
  const value = tokens[name];
  if (value === undefined) throw new Error(`token ${name} is not defined`);
  const reference = /^var\((--[\w-]+)\)$/.exec(value);
  if (!reference) return value;
  if (seen.has(name)) throw new Error(`token ${name} refers to itself`);
  seen.add(name);
  return resolve(tokens, reference[1], seen);
}

function resolver(...layers) {
  const tokens = Object.assign({}, ...layers);
  return (name) => resolve(tokens, name);
}

export const BOARD_THEMES = ["walnut-maple", "tournament", "rosewood"];

/** Build the light/dark page palettes and the board palettes from tokens.css text. */
export function buildPalette(css) {
  const blocks = parseTokenBlocks(css);
  const root = blocks[":root"];
  const dark = blocks[':root[data-theme="dark"]'];
  const darkMedia = blocks[':root:not([data-theme="light"])'];
  if (!root || !dark || !darkMedia) throw new Error("tokens.css must define :root and both dark theme blocks");
  const boards = {};
  for (const name of BOARD_THEMES) {
    const block = blocks[`:root[data-board="${name}"]`];
    if (!block) throw new Error(`tokens.css has no block for board theme ${name}`);
    boards[name] = { light: resolver(root, block), dark: resolver(root, dark, block) };
  }
  return {
    themes: { light: resolver(root), dark: resolver(root, dark), darkMedia: resolver(root, darkMedia) },
    boards,
  };
}

function pair(name, fg, bg, min) {
  const ratio = contrastRatio(fg, bg);
  return { name, fg, bg, ratio, min, pass: ratio >= min };
}

function pieceChecks(boards) {
  const results = [];
  for (const [board, themes] of Object.entries(boards)) {
    const t = themes.light;
    for (const square of ["--sq-light", "--sq-dark"]) {
      for (const colour of ["white", "black"]) {
        const fill = pair("fill", t(`--piece-${colour}-fill`), t(square), PIECE_MIN);
        const edge = pair("edge", t(`--piece-${colour}-edge`), t(square), PIECE_MIN);
        const best = fill.ratio >= edge.ratio ? fill : edge;
        results.push({ ...best, name: `${board}: ${colour} piece ${best.name} on ${square.slice(5)} square` });
      }
    }
  }
  return results;
}

function labelChecks(boards, themes) {
  const results = [];
  for (const [board, byTheme] of Object.entries(boards)) {
    const t = byTheme.light;
    results.push(pair(`${board}: label on light square`, t("--label-on-light"), t("--sq-light"), TEXT_MIN));
    results.push(pair(`${board}: label on dark square`, t("--label-on-dark"), t("--sq-dark"), TEXT_MIN));
  }
  for (const [theme, t] of Object.entries(themes)) {
    for (const wood of ["--walnut", "--walnut-hi"]) {
      results.push(pair(`${theme}: frame label on ${wood.slice(2)}`, t("--engrave"), t(wood), TEXT_MIN));
    }
  }
  return results;
}

const MIX = /^color-mix\(\s*in srgb\s*,\s*var\((--[\w-]+)\)\s+([\d.]+)%\s*,\s*transparent\s*\)$/;

/**
 * A token's colour as { r, g, b, a }. Besides plain colours it understands the
 * one color-mix form tokens.css uses for translucent highlights:
 * color-mix(in srgb, var(--x) N%, transparent) -> --x at alpha N/100.
 */
export function resolveColor(t, name) {
  const value = t(name);
  const mix = MIX.exec(value);
  if (!mix) return parseColor(value);
  return { ...parseColor(t(mix[1])), a: Number(mix[2]) / 100 };
}

/** U2 review carry-over (U3): square labels must stay 4.5:1 under the last-move highlight, in both page themes. */
function lastMoveChecks(boards) {
  const results = [];
  for (const [board, byTheme] of Object.entries(boards)) {
    for (const theme of ["light", "dark"]) {
      const t = byTheme[theme];
      const highlight = resolveColor(t, "--hl-last");
      for (const [square, label] of [["--sq-light", "--label-on-light"], ["--sq-dark", "--label-on-dark"]]) {
        const ground = composite(highlight, t(square));
        results.push(pair(`${board} (${theme} theme): label on ${square.slice(5)} square under the last-move highlight`, t(label), ground, TEXT_MIN));
      }
    }
  }
  return results;
}

/**
 * U6: the training arrow (a dashed --arrow fill over an --arrow-edge outline)
 * must reach 3:1 against every square, on all three boards and in both page
 * themes. Like a piece, it counts when its fill or its outline does.
 */
function arrowChecks(boards) {
  const results = [];
  for (const [board, byTheme] of Object.entries(boards)) {
    for (const theme of ["light", "dark"]) {
      const t = byTheme[theme];
      for (const square of ["--sq-light", "--sq-dark"]) {
        const fill = pair("fill", t("--arrow"), t(square), NON_TEXT_MIN);
        const edge = pair("outline", t("--arrow-edge"), t(square), NON_TEXT_MIN);
        const best = fill.ratio >= edge.ratio ? fill : edge;
        results.push({ ...best, name: `${board} (${theme} theme): arrow ${best.name} on ${square.slice(5)} square` });
      }
    }
  }
  return results;
}

function themeChecks(themes) {
  const results = [];
  for (const [theme, t] of Object.entries(themes)) {
    results.push(pair(`${theme}: primary button text`, t("--on-accent"), t("--accent-fill"), TEXT_MIN));
    results.push(pair(`${theme}: your-move text on baize`, t("--on-baize"), t("--baize"), TEXT_MIN));
    for (const ground of ["--page", "--surface", "--paper"]) {
      const where = ground.slice(2);
      results.push(pair(`${theme}: body text on ${where}`, t("--text"), t(ground), TEXT_MIN));
      results.push(pair(`${theme}: muted text on ${where}`, t("--muted"), t(ground), TEXT_MIN));
      results.push(pair(`${theme}: quiet button text on ${where}`, t("--accent-text"), t(ground), TEXT_MIN));
      results.push(pair(`${theme}: destructive text on ${where}`, t("--oxblood"), t(ground), TEXT_MIN));
      results.push(pair(`${theme}: link on ${where}`, t("--link"), t(ground), TEXT_MIN));
      results.push(pair(`${theme}: focus ring on ${where}`, t("--focus-ring"), t(ground), NON_TEXT_MIN));
    }
  }
  return results;
}

/** Every required pair, grouped: { pieces, labels, lastMove, arrow, theme } arrays of results. */
export function contrastReport(palette) {
  return {
    pieces: pieceChecks(palette.boards),
    labels: labelChecks(palette.boards, palette.themes),
    lastMove: lastMoveChecks(palette.boards),
    arrow: arrowChecks(palette.boards),
    theme: themeChecks(palette.themes),
  };
}

export function contrastFailures(report) {
  return [...report.pieces, ...report.labels, ...(report.lastMove || []), ...(report.arrow || []), ...report.theme]
    .filter((result) => !result.pass);
}
