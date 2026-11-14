/**
 * Arrow for the expected move after 3 misses (U6, BR4.3).
 *
 *   arrowGeometry(from, to, orientation) -> { x1, y1, x2, y2 }   PURE, board percent (0-100)
 *   arrowShape(geometry)                 -> { shaft, head }      PURE, shaft ends at the head's base
 *   renderArrow(svg, uci, orientation)                          draws into an <svg viewBox="0 0 100 100">,
 *                                                                or clears it when uci is null
 *
 * Coordinates are square centres: with White at the bottom, a1 is (6.25, 93.75)
 * and h8 is (93.75, 6.25); with Black at the bottom the board is turned.
 *
 * The SVG layer sits over U2's .board-grid with pointer-events: none and
 * aria-hidden="true"; the trainer's status line says the same move in words.
 * Colours come from tokens.css: a dashed --arrow stroke over a solid
 * --arrow-edge outline, checked at 3:1 against every square by
 * tests/js/contrast.test.mjs (the fill or the outline, like the pieces).
 */

import { fileIndex, isSquare, parseUci, rankIndex } from "../board/geometry.js";

const SQUARE = 12.5;
const HEAD_LENGTH = 5;
const HEAD_HALF_WIDTH = 3;
const SVG_NS = "http://www.w3.org/2000/svg";

function checkOrientation(orientation) {
  if (orientation !== "white" && orientation !== "black") {
    throw new TypeError(`orientation must be "white" or "black", got ${JSON.stringify(orientation)}`);
  }
}

/** The centre of a square in board percent for the given orientation. */
export function squareCentre(square, orientation) {
  if (!isSquare(square)) throw new TypeError(`not a square: ${JSON.stringify(square)}`);
  checkOrientation(orientation);
  const file = fileIndex(square);
  const rank = rankIndex(square);
  const column = orientation === "white" ? file : 7 - file;
  const row = orientation === "white" ? 7 - rank : rank;
  return { x: (column + 0.5) * SQUARE, y: (row + 0.5) * SQUARE };
}

export function arrowGeometry(from, to, orientation) {
  if (from === to) throw new TypeError("an arrow needs two different squares");
  const start = squareCentre(from, orientation);
  const end = squareCentre(to, orientation);
  return { x1: start.x, y1: start.y, x2: end.x, y2: end.y };
}

const round = (value) => Math.round(value * 100) / 100;

/** The shaft (centre to the head's base) and the head triangle (tip first). */
export function arrowShape({ x1, y1, x2, y2 }) {
  const length = Math.hypot(x2 - x1, y2 - y1);
  const ux = (x2 - x1) / length;
  const uy = (y2 - y1) / length;
  const baseX = x2 - ux * HEAD_LENGTH;
  const baseY = y2 - uy * HEAD_LENGTH;
  const nx = -uy * HEAD_HALF_WIDTH;
  const ny = ux * HEAD_HALF_WIDTH;
  return {
    shaft: { x1: round(x1), y1: round(y1), x2: round(baseX), y2: round(baseY) },
    head: [[x2, y2], [baseX + nx, baseY + ny], [baseX - nx, baseY - ny]].map(([x, y]) => [round(x), round(y)]),
  };
}

function svgNode(doc, tag, attributes) {
  const node = doc.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  return node;
}

/** Draw the arrow for uci (null clears it). Returns true when an arrow is drawn. */
export function renderArrow(svg, uci, orientation) {
  svg.replaceChildren();
  if (uci == null) return false;
  const move = parseUci(uci);
  if (!move) {
    console.error(`JustChess trainer: cannot draw an arrow for ${JSON.stringify(uci)}`);
    return false;
  }
  const { shaft, head } = arrowShape(arrowGeometry(move.from, move.to, orientation));
  const doc = svg.ownerDocument;
  const points = head.map((point) => point.join(",")).join(" ");
  const line = { x1: shaft.x1, y1: shaft.y1, x2: shaft.x2, y2: shaft.y2 };
  const group = svgNode(doc, "g", { class: "trainer-arrow-shape", "data-uci": uci });
  group.append(
    svgNode(doc, "line", { ...line, class: "arrow-edge" }),
    svgNode(doc, "polygon", { points, class: "arrow-edge" }),
    svgNode(doc, "line", { ...line, class: "arrow-line" }),
    svgNode(doc, "polygon", { points, class: "arrow-head" }),
  );
  svg.append(group);
  return true;
}
