/**
 * Endgame trainer screen at /learn/endgames/{id} (P2 U6, W2, W3, BR4.2).
 *
 *   const screen = mountEndgame(element, { api, positionId, progress?, settings?, win?, storage?, onBack?, onOpen? })
 *   screen.destroy()     clear the timer, abort requests, remove the board and the DOM
 *
 *   api        an endgame-state.js client (createEndgamesApi)
 *   progress   a trainer-progress.js store; a passed position is recorded as "endgames:<id>"
 *   storage    where the attempt is kept (default sessionStorage, every access in try/catch),
 *              so a reload continues it
 *   onBack     "All endgames" pressed (the app goes back to the hub's Endgames tab)
 *   onOpen(id) "Next position" pressed (the app opens /learn/endgames/<id>)
 *
 * The board is the U2 board, oriented to the player's side; it only offers the
 * legal moves the server sent. Each move is sent with the whole move list
 * (POST /api/endgames/{id}/play); while it waits the message reads "Computer
 * is thinking…" and the board takes no input. The answer's position after the
 * player's move is drawn first, then the defender's reply. On 503 or 429 (or
 * any failure) the move is taken back and the message says why. Hint shows the
 * position's text, with no request; Start again clears the attempt.
 */

import { createBoard } from "../board/board.js";
import {
  PROGRESS_GROUP, THINKING, UNKNOWN_POSITION, clearAttempt, createEndgamesApi, freshAttempt, loadAttempt,
  moveCounter, nextAttempt, saveAttempt, statusText, verdictMessage,
} from "./endgame-state.js";

export const REPLY_DELAY_MS = 300;

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

function defaultStorage(win) {
  try {
    return (win && win.sessionStorage) || null;
  } catch {
    return null;
  }
}

function buildView() {
  const root = make("section", { className: "puzzle endgame", "aria-labelledby": "endgame-status", "data-testid": "endgame" });
  const head = make("div", { className: "puzzle-head" });
  const titles = make("div", { className: "puzzle-titles" });
  const status = make("h1", { className: "puzzle-status", id: "endgame-status", "data-testid": "endgame-status" });
  const sub = make("p", { className: "puzzle-sub t-muted", "data-testid": "endgame-sub" });
  titles.append(status, sub);
  const back = button("All endgames", "endgame-back", "btn btn-quiet");
  head.append(titles, back);
  const boardHost = make("div", { className: "puzzle-board trainer-board", "data-testid": "endgame-board" });
  const panel = make("div", { className: "puzzle-panel" });
  const counter = make("p", { className: "endgame-counter", "data-testid": "endgame-counter" });
  const message = make("p", { className: "trainer-message", role: "status", "aria-live": "polite", "data-testid": "endgame-message" });
  const hint = make("p", { className: "endgame-hint", "data-testid": "endgame-hint" });
  hint.hidden = true;
  const controls = make("div", { className: "trainer-controls" });
  const b = {
    hint: button("Hint", "endgame-hint-button"),
    restart: button("Start again", "endgame-restart"),
    next: button("Next position", "endgame-next", "btn btn-primary"),
  };
  b.next.hidden = true;
  controls.append(b.hint, b.restart, b.next);
  panel.append(counter, message, hint, controls);
  root.append(head, boardHost, panel);
  return { root, status, sub, back, boardHost, counter, message, hint, b };
}

export function mountEndgame(element, {
  api = createEndgamesApi(),
  positionId,
  progress = null,
  settings = null,
  win = window,
  storage = defaultStorage(win),
  onBack = null,
  onOpen = null,
} = {}) {
  if (!(element instanceof Element)) throw new TypeError("mountEndgame needs a container element");
  const view = buildView();
  element.append(view.root);
  const labels = settings && typeof settings.get === "function" ? settings.get("labels") : "inside";
  const board = createBoard(view.boardHost, {
    interactive: false,
    labels: labels === "frame" ? "frame" : "inside",
    onMove: (uci) => queueMicrotask(() => sendMove(uci)),
  });

  let position = null;
  let attempt = null;
  let pending = false;
  let message = null;
  let destroyed = false;
  let timer = null;
  const controllers = new Set();

  async function call(fn) {
    const controller = new AbortController();
    controllers.add(controller);
    try {
      return await fn(controller.signal);
    } finally {
      controllers.delete(controller);
    }
  }

  function drawBoard(fen, lastMove, check, interactive, legalMoves = []) {
    board.set({ fen, lastMove: lastMove || null, check: Boolean(check), orientation: position.side, interactive,
      legalMoves: interactive ? [...legalMoves] : [] });
  }

  function drawAttempt() {
    const playing = attempt.status === "playing";
    drawBoard(attempt.fen, attempt.lastMove, attempt.check, playing && !pending, attempt.legalMoves);
  }

  function finishedMessage() {
    return verdictMessage(position.goal, attempt);
  }

  function render() {
    view.root.dataset.phase = !position ? "loading" : pending ? "waiting" : attempt.status;
    view.status.textContent = position ? statusText(position) : "Loading the position…";
    view.sub.textContent = position ? `${position.categoryLabel} · ${position.title}` : "";
    const showCounter = Boolean(position) && position.goal === "draw";
    view.counter.hidden = !showCounter;
    view.counter.textContent = showCounter ? moveCounter(attempt.playerMoves, position.holdMoves) : "";
    const shown = pending ? { text: THINKING, tone: "info" } : message || (attempt ? finishedMessage() : null);
    view.message.textContent = shown ? shown.text : "";
    view.message.dataset.tone = shown ? shown.tone : "info";
    view.b.hint.disabled = !position || !view.hint.hidden;
    view.b.restart.disabled = !position || pending;
    view.b.next.hidden = !(attempt && attempt.status === "passed" && position.next);
  }

  function showProblem(text) {
    view.status.textContent = "Endgames";
    view.message.textContent = text;
    view.message.dataset.tone = "error";
    for (const control of Object.values(view.b)) control.disabled = true;
  }

  async function start() {
    const answer = await call((signal) => api.get(positionId, { signal }));
    if (destroyed || answer.aborted) return;
    if (!answer.ok) return showProblem(answer.status === 404 ? UNKNOWN_POSITION : answer.message);
    position = answer.data;
    attempt = loadAttempt(storage, position.id) || freshAttempt(position);
    drawAttempt();
    render();
  }

  function refuse(text) {
    pending = false;
    message = { text, tone: "error" };
    board.reject();
    drawAttempt();
    render();
  }

  async function sendMove(uci) {
    if (destroyed) return;
    if (!position || pending || attempt.status !== "playing") {
      board.reject();
      return;
    }
    pending = true;
    message = null;
    render();
    const moves = [...attempt.moves, uci];
    const answer = await call((signal) => api.play(position.id, moves, { signal }));
    if (destroyed || answer.aborted) return;
    if (!answer.ok) return refuse(answer.message); // 503 / 429 / anything else: the move is taken back
    const data = answer.data;
    drawBoard(data.playerFen || data.fen, uci, data.playerCheck, false);
    attempt = nextAttempt(attempt, uci, data);
    saveAttempt(storage, attempt);
    if (attempt.status === "passed" && progress) {
      try {
        progress.markDone(PROGRESS_GROUP, position.id);
      } catch (error) {
        console.error("JustChess endgames: the solved position could not be recorded", error);
      }
    }
    const showReply = () => {
      timer = null;
      if (destroyed) return;
      pending = false;
      drawAttempt();
      render();
    };
    if (data.reply) timer = win.setTimeout(showReply, REPLY_DELAY_MS);
    else showReply();
  }

  function restart() {
    if (!position || pending) return;
    if (timer !== null) {
      win.clearTimeout(timer);
      timer = null;
    }
    clearAttempt(storage);
    attempt = freshAttempt(position);
    message = null;
    view.hint.hidden = true;
    drawAttempt();
    render();
  }

  view.b.hint.addEventListener("click", () => {
    if (!position) return;
    view.hint.textContent = position.hint;
    view.hint.hidden = false;
    render();
  });
  view.b.restart.addEventListener("click", restart);
  view.b.next.addEventListener("click", () => {
    if (position && position.next && typeof onOpen === "function") onOpen(position.next);
  });
  view.back.addEventListener("click", () => {
    if (typeof onBack === "function") onBack();
  });

  render();
  if (typeof positionId !== "string") showProblem(UNKNOWN_POSITION);
  else start();

  return {
    get attempt() {
      return attempt;
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      if (timer !== null) win.clearTimeout(timer);
      for (const controller of controllers) controller.abort();
      board.destroy();
      view.root.remove();
    },
  };
}
