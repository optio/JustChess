/**
 * Tactics puzzle screen at /learn/tactics/{theme} (P2 U5, W5, BR2.3-BR2.5, BR3.3).
 *
 *   const screen = mountPuzzle(element, { api, theme, progress?, settings?, win?, onBack? })
 *   screen.destroy()     clear every timer, abort requests, remove the board and the DOM
 *
 *   api        a lessons-api.js client (themes/puzzles/puzzle/checkPuzzle/puzzleHint)
 *   progress   a trainer-progress.js store; a puzzle solved without "Show solution"
 *              is recorded as "tactics:<theme>:<id>"
 *   onBack     "All tactics" pressed (the app goes back to the hub's Tactics tab)
 *
 * The screen opens the first unsolved puzzle of the theme (rating order, so
 * easier first); Next puzzle goes to the next unsolved one, wrapping round.
 * The state lives in puzzle-state.js (a pure reducer); this file builds the
 * DOM once, runs the reducer's effects (board, arrow, timers, network) and
 * redraws. The status reads "White to move: find the fork" with
 * "Forks · puzzle 12 of 300" under it, and the Lichess credit (BR3.3) is
 * always shown. The board is the U2 board (U1's capture animation included).
 */

import { createBoard } from "../board/board.js";
import { renderArrow } from "./arrow.js";
import { createLessonsApi, THEMES } from "./lessons-api.js";
import { initialState, reduce, statusText } from "./puzzle-state.js";

export const CREDIT = "Puzzles from the Lichess puzzle database, released under CC0.";
export const NOT_INSTALLED = "Puzzles are not installed";
export const UNKNOWN_THEME = "There is no such puzzle theme.";
export const ALL_SOLVED = "You have solved every puzzle in this theme. Here they are again.";
const SVG_NS = "http://www.w3.org/2000/svg";

function make(tag, attributes = {}, text) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "className") node.className = value;
    else node.setAttribute(name, value);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(label, testid, className = "btn btn-secondary") {
  return make("button", { className, type: "button", "data-testid": testid }, label);
}

function buildView() {
  const root = make("section", { className: "puzzle", "aria-labelledby": "puzzle-status", "data-testid": "puzzle" });
  const head = make("div", { className: "puzzle-head" });
  const back = button("All tactics", "puzzle-back", "btn btn-quiet");
  const titles = make("div", { className: "puzzle-titles" });
  const status = make("h1", { className: "puzzle-status", id: "puzzle-status", "data-testid": "puzzle-status" });
  const sub = make("p", { className: "puzzle-sub t-muted", "data-testid": "puzzle-sub" });
  titles.append(status, sub);
  head.append(titles, back);
  const boardHost = make("div", { className: "puzzle-board trainer-board", "data-testid": "puzzle-board" });
  const panel = make("div", { className: "puzzle-panel" });
  const message = make("p", { className: "trainer-message puzzle-message", role: "status", "aria-live": "polite", "data-testid": "puzzle-message" });
  const controls = make("div", { className: "trainer-controls" });
  const b = {
    hint: button("Hint", "puzzle-hint"),
    solution: button("Show solution", "puzzle-solution"),
    next: button("Next puzzle", "puzzle-next", "btn btn-primary"),
  };
  controls.append(b.hint, b.solution, b.next);
  const credit = make("p", { className: "puzzle-credit t-muted", "data-testid": "puzzle-credit" }, CREDIT);
  panel.append(message, controls, credit);
  root.append(head, boardHost, panel);
  return { root, back, status, sub, boardHost, message, b };
}

export function mountPuzzle(element, {
  api = createLessonsApi(),
  theme,
  progress = null,
  settings = null,
  win = window,
  onBack = null,
} = {}) {
  if (!(element instanceof Element)) throw new TypeError("mountPuzzle needs a container element");
  const view = buildView();
  element.append(view.root);
  const labels = settings && typeof settings.get === "function" ? settings.get("labels") : "inside";
  const board = createBoard(view.boardHost, {
    interactive: false,
    labels: labels === "frame" ? "frame" : "inside",
    onMove: (uci) => queueMicrotask(() => dispatch({ type: "playerMove", uci })),
  });
  const arrowLayer = document.createElementNS(SVG_NS, "svg");
  for (const [name, value] of Object.entries({
    class: "trainer-arrow", viewBox: "0 0 100 100", preserveAspectRatio: "none", "aria-hidden": "true", focusable: "false", "data-testid": "puzzle-arrow",
  })) arrowLayer.setAttribute(name, value);
  (view.boardHost.querySelector(".board-grid") || view.boardHost).append(arrowLayer);

  let state = initialState();
  let destroyed = false;
  let rows = [];
  let index = -1;
  let label = "";
  let notice = null;
  const seen = new Set();
  const timers = new Set();
  const controllers = new Set();

  const doneKey = (id) => `${theme}:${id}`;
  const isSolved = (id) => {
    try {
      return Boolean(progress) && progress.isDone("tactics", doneKey(id));
    } catch {
      return false;
    }
  };

  // --- network ----------------------------------------------------------------

  async function call(fn) {
    const controller = new AbortController();
    controllers.add(controller);
    try {
      return await fn(controller.signal);
    } finally {
      controllers.delete(controller);
    }
  }

  function pickIndex(after) {
    const order = rows.map((_, i) => (after + 1 + i) % rows.length);
    const fresh = order.find((i) => i !== after && !isSolved(rows[i].id) && !seen.has(rows[i].id));
    if (fresh !== undefined) return fresh;
    const unsolved = order.find((i) => i !== after && !isSolved(rows[i].id));
    if (unsolved !== undefined) return unsolved;
    notice = ALL_SOLVED;
    return rows.length > 1 && after >= 0 ? (after + 1) % rows.length : 0;
  }

  async function openAt(position) {
    index = position;
    const row = rows[index];
    const answer = await call((signal) => api.puzzle(theme, row.id, { signal }));
    if (destroyed) return;
    if (!answer.ok) {
      if (!answer.aborted) showProblem(answer.message);
      return;
    }
    dispatch({ type: "loaded", puzzle: answer.data });
    if (notice) {
      state = { ...state, message: { text: notice, tone: "info" } };
      notice = null;
      render();
    }
  }

  async function start() {
    if (!THEMES.includes(theme)) return showProblem(UNKNOWN_THEME);
    const [list, themes] = await Promise.all([
      call((signal) => api.puzzles(theme, { signal })),
      call((signal) => api.themes({ signal })),
    ]);
    if (destroyed) return;
    if (themes.ok) label = (themes.data.find((entry) => entry.theme === theme) || {}).label || "";
    if (!list.ok) return list.aborted ? undefined : showProblem(list.status === 404 ? UNKNOWN_THEME : list.message);
    if (list.data.length === 0) return showProblem(NOT_INSTALLED);
    rows = list.data;
    await openAt(pickIndex(-1));
  }

  function showProblem(text) {
    view.message.textContent = text;
    view.message.dataset.tone = "error";
    view.status.textContent = text === NOT_INSTALLED ? NOT_INSTALLED : "Tactics";
    for (const control of Object.values(view.b)) control.disabled = true;
  }

  // --- effects ----------------------------------------------------------------

  function schedule(delay, event) {
    const timer = win.setTimeout(() => {
      timers.delete(timer);
      dispatch(event);
    }, delay);
    timers.add(timer);
  }

  async function check(ply, uci) {
    const puzzle = state.puzzle;
    const answer = await call((signal) => api.checkPuzzle(puzzle.theme, puzzle.id, ply, uci, { signal }));
    if (destroyed || answer.aborted) return;
    dispatch(answer.ok ? { type: "checkResult", data: answer.data } : { type: "checkError" });
  }

  async function hint(ply, level) {
    const puzzle = state.puzzle;
    const answer = await call((signal) => api.puzzleHint(puzzle.theme, puzzle.id, ply, level, { signal }));
    if (destroyed || answer.aborted) return;
    dispatch(answer.ok ? { type: "hintResult", level, data: answer.data } : { type: "hintError", message: answer.message });
  }

  function runEffect(effect) {
    switch (effect.type) {
      case "setBoard": board.set(effect.options); break;
      case "arrow": renderArrow(arrowLayer, effect.uci, effect.orientation); break;
      case "schedule": schedule(effect.delay, effect.event); break;
      case "check": check(effect.ply, effect.uci); break;
      case "hint": hint(effect.ply, effect.level); break;
      case "rejectMove": board.reject(); break;
      case "progress":
        if (progress) progress.markDone("tactics", doneKey(effect.id));
        break;
      case "next":
        if (rows.length) openAt(pickIndex(index));
        break;
      default:
        console.error(`JustChess puzzles: unknown effect ${effect.type}`);
    }
  }

  function dispatch(event) {
    if (destroyed) return;
    if (event.type === "loaded" && event.puzzle) seen.add(event.puzzle.id);
    const result = reduce(state, event);
    state = result.state;
    for (const effect of result.effects) {
      try {
        runEffect(effect);
      } catch (error) {
        console.error(`JustChess puzzles: the ${effect.type} effect failed`, error);
      }
    }
    render();
  }

  // --- drawing ----------------------------------------------------------------

  function render() {
    const { phase, puzzle } = state;
    view.root.dataset.phase = phase;
    view.status.textContent = puzzle ? statusText(puzzle) : "Loading the puzzle…";
    const name = label || (puzzle && puzzle.label) || "";
    view.sub.textContent = rows.length && index >= 0 ? `${name} · puzzle ${index + 1} of ${rows.length}` : name;
    view.message.textContent = state.message ? state.message.text : "";
    view.message.dataset.tone = state.message ? state.message.tone : "info";
    view.b.hint.disabled = phase !== "yourMove" || state.hintLevel >= 2;
    view.b.solution.disabled = phase !== "yourMove" && phase !== "wrong";
    view.b.next.disabled = phase === "loading";
  }

  // --- wiring -----------------------------------------------------------------

  view.b.hint.addEventListener("click", () => dispatch({ type: "hint" }));
  view.b.solution.addEventListener("click", () => dispatch({ type: "showSolution" }));
  view.b.next.addEventListener("click", () => dispatch({ type: "next" }));
  view.back.addEventListener("click", () => {
    if (typeof onBack === "function") onBack();
  });

  render();
  start();

  return {
    get state() {
      return state;
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      for (const timer of timers) win.clearTimeout(timer);
      timers.clear();
      for (const controller of controllers) controller.abort();
      board.destroy();
      view.root.remove();
    },
  };
}
