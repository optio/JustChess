/**
 * JustChess board component (U2). DOM shell around the pure modules:
 * geometry.js (squares, FEN, targets, move diff, focus, names) and
 * interaction.js (the selection / promotion / pending state machine).
 *
 *   const board = createBoard(element, options)
 *   board.set(partialOptions)   update any option; animates per W4
 *   board.reject()              the caller refused the pending move: slide back, unlock
 *   board.focus()               focus the roving square
 *   board.destroy()             remove listeners and DOM
 *   board.liveRegion            aria-live=polite element the caller fills
 *
 * Options: fen, orientation ("white"|"black"), legalMoves (UCI[]), lastMove
 * ({from,to} or UCI), check, interactive, labels ("inside"|"frame"),
 * piecePath, onMove(uci). See functional-design/frontend-components.md.
 * Added in U6 (both optional; without them the board behaves as before):
 *   onRejectedTap(from, to)  a piece was selected and the person chose an empty
 *                            square or an opponent's piece that is not one of
 *                            its targets (see interaction.js for when it never fires)
 *   hintSquare               a square drawn with a dashed accent ring, or null
 * Added in P2 U1 (optional):
 *   onCaptureShown({ piece, square })  a capture's shrink-and-fade copy has ended
 *                            (or, with no animation, right after the update). Captures
 *                            animate for received moves and for the player's own
 *                            optimistic move, once (BR1.1-BR1.5).
 *
 * CALLER'S DUTY: after onMove(uci) the board is pending and ignores input
 * until the caller answers. Answer every move either with set({ fen, ... })
 * (the new position) or with reject() on ANY failure: a refusal, a network
 * error, a timeout. A board never answered stays locked. A synchronous throw
 * from onMove is logged and treated as a refusal.
 *
 * - The 64 squares are buttons with role="gridcell", created once and kept,
 *   so focus survives set(). One square holds tabindex 0 (roving tabindex).
 * - Locked or pending squares stay focusable with aria-disabled="true".
 * - Motion uses the Web Animations API; completion is the animation's
 *   finished promise and "finish at once" calls finish(). Under reduced
 *   motion no animation is created and the end state is drawn at once.
 * - Castling is played by the king's two-square move (e1g1); the rook is not
 *   a target. A malformed FEN is logged with console.error and ignored.
 */

import {
  START_FEN,
  applyMove,
  checkSquare,
  diffMove,
  frameLabels,
  isDarkSquare,
  isSquare,
  kingSquare,
  moveFocus,
  normaliseLastMove,
  parseFen,
  pieceColour,
  samePieces,
  squareLabels,
  squareName,
  squaresInOrder,
  targetsFrom,
} from "./geometry.js";
import { clientGameplay } from "../gameplay.js";
import { initialState, reduce } from "./interaction.js";
import { openPromotion } from "./promotion.js";

const DEFAULTS = Object.freeze({
  fen: START_FEN,
  orientation: "white",
  legalMoves: [],
  lastMove: null,
  check: false,
  interactive: false,
  labels: "inside",
  piecePath: "/static/pieces/cburnett/",
  onMove: null,
  onRejectedTap: null,
  hintSquare: null,
  onCaptureShown: null,
});

const MOTION_FALLBACK = { slide: 200, capture: 260, pulse: 300, ease: "cubic-bezier(.2,.7,.2,1)" };
/** P2 U1, BR1.3: the taken piece shrinks to this scale while it fades out. */
export const CAPTURE_SCALE = 0.35;
const ARROW_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]);

function validateOptions(partial) {
  if (!partial || typeof partial !== "object") throw new TypeError("board options must be an object");
  for (const key of Object.keys(partial)) {
    if (!Object.hasOwn(DEFAULTS, key)) throw new TypeError(`unknown board option ${JSON.stringify(key)}`);
  }
  const { orientation, labels, legalMoves, onMove, onRejectedTap, hintSquare, onCaptureShown } = partial;
  if (onCaptureShown !== undefined && onCaptureShown !== null && typeof onCaptureShown !== "function") {
    throw new TypeError("onCaptureShown must be a function");
  }
  if (orientation !== undefined && orientation !== "white" && orientation !== "black") {
    throw new TypeError(`orientation must be "white" or "black", got ${JSON.stringify(orientation)}`);
  }
  if (labels !== undefined && labels !== "inside" && labels !== "frame") {
    throw new TypeError(`labels must be "inside" or "frame", got ${JSON.stringify(labels)}`);
  }
  if (legalMoves !== undefined && (!Array.isArray(legalMoves) || legalMoves.some((m) => typeof m !== "string"))) {
    throw new TypeError("legalMoves must be an array of UCI strings");
  }
  if (onMove !== undefined && onMove !== null && typeof onMove !== "function") {
    throw new TypeError("onMove must be a function");
  }
  if (onRejectedTap !== undefined && onRejectedTap !== null && typeof onRejectedTap !== "function") {
    throw new TypeError("onRejectedTap must be a function");
  }
  if (hintSquare !== undefined && hintSquare !== null && !isSquare(hintSquare)) {
    throw new TypeError(`hintSquare must be a square or null, got ${JSON.stringify(hintSquare)}`);
  }
}

function el(tag, className, attributes = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
}

function buildSquare(square) {
  const button = el("button", `sq${isDarkSquare(square) ? " is-dark" : ""}`, {
    type: "button",
    role: "gridcell",
    tabindex: "-1",
    "data-square": square,
    "data-testid": `board-square-${square}`,
  });
  button.append(el("span", "sq-label rank", { "aria-hidden": "true" }), el("span", "sq-label file", { "aria-hidden": "true" }));
  return button;
}

function buildDom(element) {
  const frame = el("div", "board-frame", { "data-testid": "board" });
  const inlay = el("div", "board-inlay");
  const grid = el("div", "board-grid", { role: "grid", "aria-label": "Chessboard" });
  const rows = Array.from({ length: 8 }, () => el("div", "board-row", { role: "row" }));
  grid.append(...rows);
  const files = el("div", "frame-files", { "aria-hidden": "true" });
  const ranks = el("div", "frame-ranks", { "aria-hidden": "true" });
  for (let i = 0; i < 8; i += 1) {
    files.append(el("span"));
    ranks.append(el("span"));
  }
  inlay.append(grid);
  frame.append(inlay, files, ranks);
  const live = el("div", "board-live", { "aria-live": "polite", "data-testid": "board-live" });
  const squares = new Map();
  for (const square of squaresInOrder("white").flat()) squares.set(square, buildSquare(square));
  element.append(frame, live);
  return { frame, grid, rows, files, ranks, live, squares };
}

function readMotion(frame) {
  const style = getComputedStyle(frame);
  const ms = (name, fallback) => {
    const value = parseFloat(style.getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  };
  return {
    slide: ms("--t-slide", MOTION_FALLBACK.slide),
    // P2 U4 tuning: gameplay.yaml's capture time, unless the theme turned motion off (reduced motion: 0).
    capture: ms("--t-capture", MOTION_FALLBACK.capture) === 0 ? 0 : clientGameplay().captureAnimationMs,
    pulse: ms("--t-pulse", MOTION_FALLBACK.pulse),
    ease: style.getPropertyValue("--ease-out").trim() || MOTION_FALLBACK.ease,
  };
}

function prefersReducedMotion() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function parseOrNull(fen) {
  try {
    return parseFen(fen);
  } catch (error) {
    console.error(`JustChess board: ignoring malformed FEN ${JSON.stringify(fen)} (${error.message})`);
    return null;
  }
}

export function createBoard(element, options = {}) {
  if (!(element instanceof Element)) throw new TypeError("createBoard needs a container element");
  validateOptions(options);
  const opts = { ...DEFAULTS, ...options, legalMoves: [...(options.legalMoves || [])] };
  const firstPosition = parseOrNull(opts.fen) || parseFen(START_FEN);
  let shown = firstPosition.pieces;
  let turn = firstPosition.turn;
  let beforeOptimistic = null;
  let ix = initialState(opts.interactive);
  let inCheckBefore = Boolean(opts.check);
  let focusSquare = null;
  let picker = null;
  let destroyed = false;
  const running = new Map();
  const dom = buildDom(element);

  // ---- drawing ---------------------------------------------------------

  function pieceSrc(letter) {
    return `${opts.piecePath}${pieceColour(letter) === "white" ? "w" : "b"}${letter.toUpperCase()}.svg`;
  }

  function showPiece(button, letter) {
    let img = button.querySelector("img.piece:not(.piece-ghost)");
    if (!letter) {
      if (img) img.remove();
      return;
    }
    if (!img) {
      img = el("img", "piece", { alt: "", draggable: "false" });
      button.append(img);
    }
    if (img.dataset.shown !== letter) {
      img.src = pieceSrc(letter);
      img.dataset.shown = letter;
    }
    img.classList.toggle("is-black", pieceColour(letter) === "black");
  }

  function rovingSquare() {
    return focusSquare || kingSquare(shown, opts.orientation) || squaresInOrder(opts.orientation)[7][0];
  }

  function layout() {
    const hadFocus = dom.grid.contains(document.activeElement) ? document.activeElement : null;
    squaresInOrder(opts.orientation).forEach((row, index) => {
      dom.rows[index].append(...row.map((square) => dom.squares.get(square)));
    });
    for (const [square, button] of dom.squares) {
      const labels = squareLabels(square, opts.orientation);
      button.querySelector(".sq-label.rank").textContent = labels.rank || "";
      button.querySelector(".sq-label.file").textContent = labels.file || "";
    }
    const frame = frameLabels(opts.orientation);
    [...dom.files.children].forEach((span, i) => { span.textContent = frame.files[i]; });
    [...dom.ranks.children].forEach((span, i) => { span.textContent = frame.ranks[i]; });
    if (hadFocus && document.activeElement !== hadFocus) hadFocus.focus({ preventScroll: true });
  }

  function render() {
    const last = normaliseLastMove(opts.lastMove);
    const check = checkSquare(shown, turn, opts.check);
    const targets = ix.selected ? targetsFrom(ix.selected, opts.legalMoves) : new Set();
    const locked = !opts.interactive || ix.mode === "locked" || ix.mode === "pending";
    const roving = rovingSquare();
    dom.frame.dataset.labels = opts.labels;
    for (const [square, button] of dom.squares) {
      const piece = shown[square] || null;
      const selected = ix.selected === square;
      const target = targets.has(square);
      showPiece(button, piece);
      button.classList.toggle("is-last", Boolean(last) && (square === last.from || square === last.to));
      button.classList.toggle("is-selected", selected);
      button.classList.toggle("is-target", target);
      button.classList.toggle("has-piece", Boolean(piece));
      button.classList.toggle("is-check", square === check);
      button.classList.toggle("is-hint", square === opts.hintSquare);
      button.setAttribute("aria-label", squareName(square, piece, { selected, target }));
      if (locked) button.setAttribute("aria-disabled", "true");
      else button.removeAttribute("aria-disabled");
      button.tabIndex = square === roving ? 0 : -1;
    }
  }

  // ---- motion ----------------------------------------------------------

  function track(animation, cleanup) {
    let cleaned = false;
    const done = () => {
      if (cleaned) return;
      cleaned = true;
      running.delete(animation);
      cleanup();
    };
    running.set(animation, done);
    animation.finished.then(done, done);
  }

  /** Jump every running animation to its end and clean up synchronously. */
  function finishAnimations() {
    for (const [animation, done] of [...running]) {
      try {
        animation.finish();
      } catch (error) {
        console.error("JustChess board: could not finish an animation", error);
      }
      done();
    }
  }

  function canAnimate() {
    return typeof Element.prototype.animate === "function" && !prefersReducedMotion();
  }

  function slide(move, motion) {
    const button = dom.squares.get(move.to);
    const img = button.querySelector("img.piece:not(.piece-ghost)");
    if (!img) return;
    const from = dom.squares.get(move.from).getBoundingClientRect();
    const to = button.getBoundingClientRect();
    if (move.becomes !== move.piece) {
      img.src = pieceSrc(move.piece);
      img.dataset.shown = move.piece;
    }
    img.classList.add("is-moving");
    const animation = img.animate(
      [{ transform: `translate(${from.left - to.left}px, ${from.top - to.top}px)` }, { transform: "translate(0, 0)" }],
      { duration: motion.slide, easing: motion.ease },
    );
    track(animation, () => {
      img.classList.remove("is-moving");
      showPiece(button, shown[move.to] || null);
    });
  }

  function captureShown(capture) {
    if (!opts.onCaptureShown || destroyed) return;
    try {
      opts.onCaptureShown({ piece: capture.piece, square: capture.square });
    } catch (error) {
      console.error("JustChess board: onCaptureShown threw", error);
    }
  }

  /** P2 U1, BR1.3/BR1.5: the taken piece shrinks to 35 % and fades out on its own square; it never takes input. */
  function fadeCaptured(capture, motion) {
    const ghost = el("img", "piece piece-ghost", { alt: "", src: pieceSrc(capture.piece), "data-testid": "capture-ghost" });
    ghost.classList.toggle("is-black", pieceColour(capture.piece) === "black");
    dom.squares.get(capture.square).append(ghost);
    const animation = ghost.animate(
      [{ opacity: 1, transform: "scale(1)" }, { opacity: 0, transform: `scale(${CAPTURE_SCALE})` }],
      { duration: motion.capture, easing: motion.ease, fill: "forwards" },
    );
    track(animation, () => {
      ghost.remove();
      captureShown(capture);
    });
  }

  /** No animation (reduced motion, no Web Animations): report the captures once the caller's turn ends. */
  function reportCapturesLater(captured) {
    if (!captured.length || !opts.onCaptureShown) return;
    queueMicrotask(() => captured.forEach(captureShown));
  }

  function animate(diff, { capturesOnly = false } = {}) {
    if (!diff) return;
    const motion = canAnimate() ? readMotion(dom.frame) : null;
    if (!motion || (motion.slide <= 0 && motion.capture <= 0)) {
      reportCapturesLater(diff.captured);
      return;
    }
    if (motion.capture > 0) diff.captured.forEach((capture) => fadeCaptured(capture, motion));
    else reportCapturesLater(diff.captured);
    if (!capturesOnly && motion.slide > 0) diff.moves.forEach((move) => slide(move, motion));
  }

  function pulseCheck() {
    const square = checkSquare(shown, turn, true);
    if (!square || !canAnimate()) return;
    const motion = readMotion(dom.frame);
    if (motion.pulse <= 0) return;
    const wash = el("span", "sq-wash", { "aria-hidden": "true" });
    dom.squares.get(square).prepend(wash);
    const animation = wash.animate([{ opacity: 0 }, { opacity: 1 }, { opacity: 0 }], { duration: motion.pulse, iterations: 2 });
    track(animation, () => wash.remove());
  }

  // ---- effects ---------------------------------------------------------

  function callOnMove(uci) {
    if (!opts.onMove) return;
    try {
      opts.onMove(uci);
    } catch (error) {
      console.error(`JustChess board: onMove threw for ${uci}; treating the move as refused`, error);
      dispatch({ type: "reject" });
    }
  }

  function callOnRejectedTap(from, to) {
    if (!opts.onRejectedTap) return;
    try {
      opts.onRejectedTap(from, to);
    } catch (error) {
      console.error(`JustChess board: onRejectedTap threw for ${from}${to}`, error);
    }
  }

  function openPicker(from, to) {
    const promise = openPromotion(dom.squares.get(to), pieceColour(shown[from]), opts.piecePath);
    picker = promise;
    promise
      .then((piece) => {
        if (picker === promise) picker = null;
        if (!destroyed) dispatch({ type: "promotionChosen", piece });
      })
      .catch((error) => {
        if (picker === promise) picker = null;
        console.error("JustChess board: the promotion picker failed", error);
        if (!destroyed) dispatch({ type: "promotionChosen", piece: null });
      });
  }

  function closePicker() {
    if (!picker) return;
    const open = picker;
    picker = null;
    open.cancel();
  }

  function focusOn(square) {
    focusSquare = square;
    const active = document.activeElement;
    const boardHasFocus = dom.frame.contains(active) || active === document.body || active === null;
    if (boardHasFocus) dom.squares.get(square).focus({ preventScroll: true });
  }

  function runEffect(effect, event, after) {
    switch (effect.type) {
      case "applyOptimistic": {
        finishAnimations();
        beforeOptimistic = shown;
        shown = applyMove(shown, effect.from, effect.to, effect.promotion) || shown;
        // P2 U1, BR1.2: the player's own capture animates at once; the confirming
        // position equals what is shown, so it never animates a second time.
        const diff = diffMove(beforeOptimistic, shown, { from: effect.from, to: effect.to });
        if (diff && diff.captured.length) after.push(() => animate(diff, { capturesOnly: true }));
        break;
      }
      case "emitMove":
        after.push(() => callOnMove(effect.uci));
        break;
      case "openPromotion":
        after.push(() => openPicker(effect.from, effect.to));
        break;
      case "closePromotion":
        closePicker();
        break;
      case "render":
        // A confirmation equal to the shown (optimistic) position lets its capture finish (BR1.2).
        if (effect.animation || !samePieces(shown, event.next)) finishAnimations();
        shown = event.next;
        beforeOptimistic = null;
        after.push(() => animate(effect.animation));
        break;
      case "slideBack":
        finishAnimations();
        if (beforeOptimistic) shown = beforeOptimistic;
        beforeOptimistic = null;
        after.push(() => animate({ moves: [{ piece: shown[effect.from], becomes: shown[effect.from], from: effect.to, to: effect.from }], captured: [] }));
        break;
      case "focus":
        after.push(() => focusOn(effect.square));
        break;
      case "rejectedTap":
        after.push(() => callOnRejectedTap(effect.from, effect.to));
        break;
      default:
        console.error(`JustChess board: unknown effect ${effect.type}`);
    }
  }

  function dispatch(event) {
    const ctx = { legalMoves: opts.legalMoves, interactive: opts.interactive, shown };
    const result = reduce(ix, event, ctx);
    ix = result.state;
    const after = [];
    result.effects.forEach((effect) => runEffect(effect, event, after));
    render();
    after.forEach((task) => task());
  }

  // ---- input -----------------------------------------------------------

  function squareOf(target) {
    const button = target instanceof Element ? target.closest("button.sq") : null;
    return button && dom.grid.contains(button) ? button.dataset.square : null;
  }

  function onClick(event) {
    const square = squareOf(event.target);
    if (square) dispatch({ type: "tap", square });
  }

  function onKeydown(event) {
    const square = squareOf(event.target);
    if (!square) return;
    if (ARROW_KEYS.has(event.key)) {
      event.preventDefault();
      const next = moveFocus(square, event.key, opts.orientation);
      focusSquare = next;
      render();
      dom.squares.get(next).focus({ preventScroll: true });
    } else if (event.key === "Escape" && (ix.mode === "selected" || ix.mode === "promoting")) {
      event.preventDefault();
      dispatch({ type: "escape" });
    }
  }

  function onFocusIn(event) {
    const square = squareOf(event.target);
    if (!square || square === focusSquare) return;
    const previous = dom.squares.get(rovingSquare());
    focusSquare = square;
    if (previous) previous.tabIndex = -1;
    dom.squares.get(square).tabIndex = 0;
  }

  dom.grid.addEventListener("click", onClick);
  dom.grid.addEventListener("keydown", onKeydown);
  dom.grid.addEventListener("focusin", onFocusIn);

  layout();
  render();

  // ---- public API ------------------------------------------------------

  function set(partial) {
    if (destroyed) throw new Error("JustChess board: set() after destroy()");
    validateOptions(partial);
    const before = { orientation: opts.orientation, interactive: opts.interactive };
    Object.assign(opts, partial);
    if (partial.legalMoves) opts.legalMoves = [...partial.legalMoves];
    if (opts.orientation !== before.orientation) layout();
    let dispatched = false;
    if (Object.hasOwn(partial, "fen")) {
      const position = parseOrNull(partial.fen);
      if (position) {
        turn = position.turn;
        dispatch({ type: "position", next: position.pieces, lastMove: opts.lastMove });
        dispatched = true;
      }
    } else if (Object.hasOwn(partial, "legalMoves")) {
      dispatch({ type: "legalMoves" });
      dispatched = true;
    }
    if (opts.interactive !== before.interactive) {
      dispatch({ type: "setInteractive", value: opts.interactive });
      dispatched = true;
    }
    if (!dispatched) render();
    if (opts.check && !inCheckBefore) pulseCheck();
    inCheckBefore = Boolean(opts.check);
  }

  return {
    set,
    reject() {
      if (!destroyed) dispatch({ type: "reject" });
    },
    focus() {
      if (!destroyed) dom.squares.get(rovingSquare()).focus();
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      closePicker();
      finishAnimations();
      dom.grid.removeEventListener("click", onClick);
      dom.grid.removeEventListener("keydown", onKeydown);
      dom.grid.removeEventListener("focusin", onFocusIn);
      dom.frame.remove();
      dom.live.remove();
    },
    get liveRegion() {
      return dom.live;
    },
    get mode() {
      return ix.mode;
    },
  };
}
