/**
 * The hint arrow over the game board (P2 U4, BR8.2, W6).
 *
 *   const arrow = createHintArrow(boardRoot)
 *   arrow.show({ from, to }, orientation)   draw it (the same look as the trainer's arrow)
 *   arrow.clear()
 *   arrow.destroy()
 *
 * An <svg viewBox="0 0 100 100"> laid over U2's .board-grid with
 * pointer-events: none and aria-hidden="true" (training.css .trainer-arrow);
 * the game's status line names the hinted move in words. The geometry comes
 * from computer.js hintArrow (square centres for the orientation).
 */

import { hintArrow } from "../computer.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function svgNode(doc, tag, attributes) {
  const node = doc.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  return node;
}

export function createHintArrow(boardRoot) {
  if (!(boardRoot instanceof Element)) throw new TypeError("createHintArrow needs the board element");
  const doc = boardRoot.ownerDocument;
  const svg = svgNode(doc, "svg", {
    class: "trainer-arrow hint-arrow", viewBox: "0 0 100 100", preserveAspectRatio: "none",
    "aria-hidden": "true", focusable: "false", "data-testid": "hint-arrow",
  });
  (boardRoot.querySelector(".board-grid") || boardRoot).append(svg);
  let drawn = null;

  function clear() {
    svg.replaceChildren();
    drawn = null;
  }

  function show(hint, orientation) {
    const key = hint ? `${hint.from}${hint.to}:${orientation}` : null;
    if (key === drawn) return;
    if (!hint) return clear();
    let shape;
    try {
      shape = hintArrow(hint, orientation);
    } catch (error) {
      console.error("JustChess: the hint arrow could not be drawn", error);
      return clear();
    }
    if (!shape) return clear();
    const { shaft, head } = shape;
    const points = head.map((point) => point.join(",")).join(" ");
    const line = { x1: shaft.x1, y1: shaft.y1, x2: shaft.x2, y2: shaft.y2 };
    const group = svgNode(doc, "g", { class: "trainer-arrow-shape", "data-uci": `${hint.from}${hint.to}` });
    group.append(
      svgNode(doc, "line", { ...line, class: "arrow-edge" }),
      svgNode(doc, "polygon", { points, class: "arrow-edge" }),
      svgNode(doc, "line", { ...line, class: "arrow-line" }),
      svgNode(doc, "polygon", { points, class: "arrow-head" }),
    );
    svg.replaceChildren(group);
    drawn = key;
  }

  return {
    show,
    clear,
    destroy() {
      svg.remove();
    },
  };
}
