/**
 * Opening trainer view (U6, FR7.1-FR7.5, BR3.1, BR4.x, BR5.1).
 *
 *   const trainer = mountTrainer(element, { api?, initialLessonId?, variant?, settings?, onRoute?, win? })
 *   trainer.open(id | null)     load one lesson, or show the list
 *   trainer.destroy()           clear the reply timer, abort any request, remove the board and the DOM
 *
 *   api        a lessons-api.js client (default: createLessonsApi())
 *   variant    "page" for /learn (the list title is the page's h1) or "drawer" for
 *              the game's "Learn openings" drawer (stacked, its own board)
 *   settings   U2's settings store; the trainer's board follows the labels setting
 *   onRoute    called with an id or null when the person picks a lesson or
 *              "Other lessons", so /learn can update the address bar
 *
 * P2 U5 options (both optional):
 *   progress   a trainer-progress.js store; a completed practice run is recorded
 *              as "<group>:<lessonId>" (openings, traps or defence by the lesson's kind)
 *   listKind   "opening" | "trap" | "defence": the list shows that kind only
 *              (the game's drawer passes "opening")
 *
 * The state lives in trainer-state.js (a pure reducer). This file builds the
 * DOM once, sends every click, board callback, timer and network answer to the
 * reducer, runs the effects it returns, and redraws from the state. It owns a
 * U2 board of its own and never touches a game board or a game socket.
 *
 * The arrow layer is an SVG over the board grid with pointer-events: none and
 * aria-hidden; the role="status" message says the same move in words.
 */

import { createBoard } from "../board/board.js";
import { renderArrow } from "./arrow.js";
import { createLessonsApi, isLessonId, NOT_FOUND } from "./lessons-api.js";
import { groupOfKind } from "./trainer-progress.js";
import {
  currentStep,
  initialState,
  isLearnerPly,
  moveLabel,
  otherSide,
  reduce,
  sideName,
  TRAINER_DELAY_MS,
  TEXT,
} from "./trainer-state.js";

export const LIST_TITLE = "Learn an opening";
export const EMPTY_TEXT = "No lessons yet. Add a file to the lessons folder.";
export const LOADING_TEXT = "Loading lessons…";
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

function buildList(variant) {
  const list = make("div", { className: "trainer-list", "data-testid": "trainer-list" });
  const title = make(variant === "page" ? "h1" : "h2", { className: "trainer-list-title" }, LIST_TITLE);
  const lede = make("p", { className: "trainer-lede" },
    "Pick an opening. Watch the moves with a note for each, then practise them against the trainer.");
  const status = make("p", { className: "trainer-list-status", role: "status", "data-testid": "trainer-list-status" });
  const options = make("ul", { className: "trainer-options", "data-testid": "trainer-lessons" });
  list.append(title, lede, status, options);
  return { list, status, options };
}

function buildControls() {
  const controls = make("div", { className: "trainer-controls", "data-testid": "trainer-controls" });
  const b = {
    back: button("Back", "trainer-back"),
    next: button("Next", "trainer-next", "btn btn-primary"),
    restart: button("Restart", "trainer-restart", "btn btn-quiet"),
    practise: button("Practise", "trainer-practise", "btn btn-primary"),
    hint: button("Hint", "trainer-hint"),
    keepPlaying: button("Keep playing freely", "trainer-keep-playing"),
    backToLine: button("Back to the line", "trainer-back-to-line", "btn btn-primary"),
    again: button("Practise again", "trainer-practise-again", "btn btn-primary"),
    other: button("Practise as Black", "trainer-practise-other"),
  };
  controls.append(...Object.values(b));
  return { controls, b };
}

function buildSideSwitch() {
  const group = make("div", { className: "trainer-side", role: "radiogroup", "aria-label": "Practise as", "data-testid": "trainer-side" });
  const radios = {};
  for (const side of ["white", "black"]) {
    radios[side] = make("button", {
      className: "trainer-side-option", type: "button", role: "radio", "aria-checked": "false", "data-side": side,
      "data-testid": `trainer-side-${side}`,
    }, `Practise as ${sideName(side)}`);
    group.append(radios[side]);
  }
  return { group, radios };
}

function buildSheet() {
  const sheet = make("section", { className: "sheet trainer-sheet", "aria-labelledby": "trainer-sheet-title", "data-testid": "trainer-sheet" });
  const title = make("h3", { className: "sheet-title", id: "trainer-sheet-title" }, "Moves and notes");
  const table = make("table");
  const head = make("thead");
  const row = make("tr");
  row.append(make("th", { scope: "col" }, "Move"), make("th", { scope: "col" }, "Note"));
  head.append(row);
  const body = make("tbody", { "data-testid": "trainer-sheet-rows" });
  table.append(make("caption", { className: "visually-hidden" }, "Moves of the lesson with their notes"), head, body);
  sheet.append(title, table);
  return { sheet, body };
}

function buildLesson() {
  const lesson = make("div", { className: "trainer-lesson", "data-testid": "trainer-lesson" });
  const head = make("div", { className: "trainer-head" });
  const titles = make("div", { className: "trainer-titles" });
  const name = make("h2", { className: "trainer-name", "data-testid": "trainer-name" });
  const meta = make("p", { className: "trainer-meta t-muted", "data-testid": "trainer-meta" });
  titles.append(name, meta);
  const otherLessons = button("Other lessons", "trainer-other-lessons", "btn btn-quiet");
  head.append(titles, otherLessons);
  const side = buildSideSwitch();
  const boardHost = make("div", { className: "trainer-board", "data-testid": "trainer-board" });
  const message = make("p", { className: "trainer-message", role: "status", "aria-live": "polite", "data-testid": "trainer-message" });
  const prompt = make("p", { className: "trainer-prompt t-muted", "data-testid": "trainer-prompt" });
  const { controls, b } = buildControls();
  const objectives = make("section", { className: "trainer-objectives", "data-testid": "trainer-objectives" });
  const objectivesTitle = make("h3", { className: "trainer-objectives-title" });
  const objectivesList = make("ul");
  objectives.append(objectivesTitle, objectivesList);
  const { sheet, body } = buildSheet();
  const play = make("div", { className: "trainer-play" });
  const side2 = make("div", { className: "trainer-panel" });
  play.append(side.group, boardHost);
  side2.append(message, prompt, controls, objectives, sheet);
  lesson.append(head, play, side2);
  return { lesson, name, meta, otherLessons, side, boardHost, message, prompt, b, objectives, objectivesTitle, objectivesList, sheetBody: body };
}

function alternativesText(step) {
  if (!step.alternatives || step.alternatives.length === 0) return "";
  return `Also good: ${step.alternatives.map((alt) => `${alt.san} (${alt.note})`).join("; ")}`;
}

function promptFor(state) {
  const step = currentStep(state);
  switch (state.phase) {
    case "walkthrough":
      return state.index >= state.lesson.steps.length ? "That is the whole line. Practise it, or step back through it." : "";
    case "practice":
      if (!step) return "";
      return step.side === state.side ? `Your move as ${sideName(state.side)}.` : "The trainer is moving…";
    case "offLine":
      return "Keep playing freely, or go back to the line.";
    case "freePlay":
      return "You move both sides. Go back to the line at any time.";
    default:
      return "";
  }
}

export function mountTrainer(element, {
  api = createLessonsApi(),
  initialLessonId = null,
  variant = "page",
  settings = null,
  onRoute = null,
  win = window,
  progress = null,
  listKind = null,
} = {}) {
  if (!(element instanceof Element)) throw new TypeError("mountTrainer needs a container element");
  if (variant !== "page" && variant !== "drawer") throw new TypeError(`variant must be "page" or "drawer", got ${JSON.stringify(variant)}`);

  const root = make("section", { className: "trainer", "data-variant": variant, "aria-label": "Opening trainer", "data-testid": "trainer" });
  const listView = buildList(variant);
  const view = buildLesson();
  root.append(listView.list, view.lesson);
  element.append(root);

  const labels = settings && typeof settings.get === "function" ? settings.get("labels") : "inside";
  const board = createBoard(view.boardHost, {
    interactive: false,
    labels: labels === "frame" ? "frame" : "inside",
    onMove: (uci) => queueMicrotask(() => dispatch({ type: "learnerMove", uci })),
    onRejectedTap: (from, to) => queueMicrotask(() => dispatch({ type: "rejectedTap", from, to })),
  });
  const arrowLayer = document.createElementNS(SVG_NS, "svg");
  for (const [name, value] of Object.entries({
    class: "trainer-arrow", viewBox: "0 0 100 100", preserveAspectRatio: "none", "aria-hidden": "true", focusable: "false", "data-testid": "trainer-arrow",
  })) arrowLayer.setAttribute(name, value);
  (view.boardHost.querySelector(".board-grid") || view.boardHost).append(arrowLayer);
  const unsubscribe = settings && typeof settings.subscribe === "function"
    ? settings.subscribe((key, value) => { if (key === "labels" && !destroyed) board.set({ labels: value }); })
    : () => {};

  let state = initialState();
  let destroyed = false;
  let trainerTimer = null;
  let requestController = null;
  let loadController = null;
  let listNotice = null;
  let renderedRows = null;

  // --- effects --------------------------------------------------------------

  function clearTrainerTimer() {
    if (trainerTimer !== null) win.clearTimeout(trainerTimer);
    trainerTimer = null;
  }

  function reducedMotion() {
    return typeof win.matchMedia === "function" && win.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function abortRequest() {
    if (requestController) requestController.abort();
    requestController = null;
  }

  async function positionMove(fen, uci) {
    abortRequest();
    const mine = new AbortController();
    requestController = mine;
    const answer = await api.positionMove(fen, uci, { signal: mine.signal });
    if (destroyed || requestController !== mine) return;
    requestController = null;
    if (answer.ok) dispatch({ type: "positionResult", data: answer.data });
    else if (!answer.aborted) dispatch({ type: "positionError", message: answer.message });
  }

  function runEffect(effect) {
    switch (effect.type) {
      case "setBoard":
        board.set(effect.options);
        break;
      case "arrow":
        renderArrow(arrowLayer, effect.uci, effect.orientation);
        break;
      case "scheduleTrainer":
        clearTrainerTimer();
        trainerTimer = win.setTimeout(() => {
          trainerTimer = null;
          dispatch({ type: "trainerMove", seq: effect.seq });
        }, reducedMotion() ? 0 : TRAINER_DELAY_MS);
        break;
      case "cancelTrainer":
        clearTrainerTimer();
        break;
      case "positionMove":
        positionMove(effect.fen, effect.uci);
        break;
      case "abortRequest":
        abortRequest();
        break;
      case "rejectMove":
        board.reject();
        break;
      case "showList":
        loadList();
        break;
      case "progress": {
        const group = groupOfKind(effect.kind);
        if (progress && group) progress.markDone(group, effect.lessonId);
        break;
      }
      default:
        console.error(`JustChess trainer: unknown effect ${effect.type}`);
    }
  }

  function dispatch(event) {
    if (destroyed) return;
    const result = reduce(state, event);
    state = result.state;
    for (const effect of result.effects) {
      try {
        runEffect(effect);
      } catch (error) {
        console.error(`JustChess trainer: the ${effect.type} effect failed`, error);
      }
    }
    render();
  }

  // --- list -----------------------------------------------------------------

  function abortLoad() {
    if (loadController) loadController.abort();
    loadController = null;
  }

  function renderOptions(lessons) {
    listView.options.replaceChildren(...lessons.map((lesson) => {
      const item = make("li");
      const choose = make("button", { className: "trainer-option", type: "button", "data-testid": `lesson-option-${lesson.id}` });
      const details = [lesson.eco, `${lesson.moves} ${lesson.moves === 1 ? "move" : "moves"}`, `as ${sideName(lesson.side)}`].filter(Boolean);
      choose.append(make("strong", { className: "trainer-option-name" }, lesson.name), make("span", { className: "trainer-option-meta" }, details.join(" · ")));
      if (lesson.aliases && lesson.aliases.length) {
        choose.append(make("span", { className: "trainer-option-alias" }, `Also called ${lesson.aliases.join(", ")}`));
      }
      choose.addEventListener("click", () => {
        if (typeof onRoute === "function") onRoute(lesson.id);
        open(lesson.id);
      });
      item.append(choose);
      return item;
    }));
  }

  async function loadList() {
    abortLoad();
    const mine = new AbortController();
    loadController = mine;
    const notice = listNotice;
    listNotice = null;
    listView.status.textContent = notice ? `${notice}. ${LOADING_TEXT}` : LOADING_TEXT;
    const answer = await api.list(listKind ? { signal: mine.signal, kind: listKind } : { signal: mine.signal });
    if (destroyed || loadController !== mine) return;
    loadController = null;
    if (!answer.ok) {
      if (!answer.aborted) listView.status.textContent = answer.message;
      return;
    }
    renderOptions(answer.data);
    const base = answer.data.length ? "" : EMPTY_TEXT;
    listView.status.textContent = notice ? `${notice}. ${answer.data.length ? "Choose another lesson." : EMPTY_TEXT}` : base;
  }

  function showList(notice = null) {
    listNotice = notice;
    if (state.phase !== "choosing") dispatch({ type: "otherLessons" });
    else loadList();
  }

  async function open(id) {
    if (destroyed) return;
    abortLoad();
    if (id == null) return showList();
    if (!isLessonId(id)) return showList(NOT_FOUND);
    const mine = new AbortController();
    loadController = mine;
    listView.status.textContent = "Loading the lesson…";
    const answer = await api.get(id, { signal: mine.signal });
    if (destroyed || loadController !== mine) return;
    loadController = null;
    if (answer.ok) {
      dispatch({ type: "lessonLoaded", lesson: answer.data });
      if (state.phase === "choosing") showList(TEXT.unreadable.replace(/\.$/, ""));
    } else if (!answer.aborted) {
      showList(answer.status === 404 ? NOT_FOUND : answer.message.replace(/\.$/, ""));
    }
  }

  // --- drawing --------------------------------------------------------------

  function renderSheet() {
    const lesson = state.lesson;
    if (!lesson) {
      view.sheetBody.replaceChildren();
      renderedRows = null;
      return;
    }
    const shown = state.phase === "complete" ? lesson.steps.length : state.index;
    const key = `${lesson.id}:${shown}`;
    if (renderedRows === key) return;
    renderedRows = key;
    view.sheetBody.replaceChildren(...lesson.steps.slice(0, shown).map((step, index) => {
      const row = make("tr", { "data-ply": String(step.ply) });
      const move = make("td", { className: index === shown - 1 ? "move is-latest" : "move" }, moveLabel(step));
      const note = make("td", { className: "trainer-note" });
      note.append(make("span", {}, step.note));
      const alternatives = alternativesText(step);
      if (alternatives) note.append(make("span", { className: "trainer-alternatives" }, alternatives));
      row.append(move, note);
      return row;
    }));
  }

  function renderControls() {
    const { b } = view;
    const phase = state.phase;
    const total = state.lesson ? state.lesson.steps.length : 0;
    for (const control of [b.back, b.next, b.restart, b.practise]) control.hidden = phase !== "walkthrough";
    b.back.disabled = state.index === 0;
    b.next.disabled = state.index >= total;
    b.hint.hidden = phase !== "practice";
    b.hint.disabled = !isLearnerPly(state);
    b.keepPlaying.hidden = phase !== "offLine";
    b.keepPlaying.disabled = !(state.offLine && state.offLine.fen);
    b.backToLine.hidden = phase !== "offLine" && phase !== "freePlay";
    b.again.hidden = phase !== "complete";
    b.other.hidden = phase !== "complete";
    b.other.textContent = `Practise as ${sideName(otherSide(state.side))}`;
  }

  function renderObjectives() {
    const lesson = state.lesson;
    const show = Boolean(lesson) && lesson.objectives && lesson.objectives.length > 0
      && (state.phase === "walkthrough" || state.phase === "complete");
    view.objectives.hidden = !show;
    if (!show) return;
    view.objectivesTitle.textContent = state.phase === "complete" ? TEXT.complete : "What you will learn";
    view.objectivesList.replaceChildren(...lesson.objectives.map((text) => make("li", {}, text)));
  }

  function render() {
    const choosing = state.phase === "choosing";
    root.dataset.phase = state.phase;
    listView.list.hidden = !choosing;
    view.lesson.hidden = choosing;
    if (!choosing) {
      view.name.textContent = state.lesson.name;
      view.meta.textContent = [state.lesson.eco, `${state.lesson.steps.length} moves`].filter(Boolean).join(" · ");
    }
    view.side.group.hidden = choosing || state.phase === "walkthrough";
    for (const [side, radio] of Object.entries(view.side.radios)) radio.setAttribute("aria-checked", String(state.side === side));
    view.message.textContent = state.message ? state.message.text : "";
    view.message.dataset.tone = state.message ? state.message.tone : "info";
    view.prompt.textContent = choosing ? "" : promptFor(state);
    renderControls();
    renderObjectives();
    renderSheet();
  }

  // --- wiring ---------------------------------------------------------------

  const { b } = view;
  b.back.addEventListener("click", () => dispatch({ type: "back" }));
  b.next.addEventListener("click", () => dispatch({ type: "next" }));
  b.restart.addEventListener("click", () => dispatch({ type: "restart" }));
  b.practise.addEventListener("click", () => dispatch({ type: "startPractice", side: state.lesson ? state.lesson.side : undefined }));
  b.hint.addEventListener("click", () => dispatch({ type: "hint" }));
  b.keepPlaying.addEventListener("click", () => dispatch({ type: "keepPlaying" }));
  b.backToLine.addEventListener("click", () => dispatch({ type: "backToLine" }));
  b.again.addEventListener("click", () => dispatch({ type: "startPractice" }));
  b.other.addEventListener("click", () => dispatch({ type: "switchSide", side: otherSide(state.side) }));
  view.otherLessons.addEventListener("click", () => {
    if (typeof onRoute === "function") onRoute(null);
    dispatch({ type: "otherLessons" });
  });
  for (const [side, radio] of Object.entries(view.side.radios)) {
    radio.addEventListener("click", () => {
      if (side !== state.side || state.phase === "complete") dispatch({ type: "switchSide", side });
    });
  }
  view.side.group.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    const side = otherSide(state.side);
    dispatch({ type: "switchSide", side });
    view.side.radios[side].focus();
  });

  render();
  open(initialLessonId);

  return {
    open,
    get state() {
      return state;
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      clearTrainerTimer();
      abortRequest();
      abortLoad();
      unsubscribe();
      board.destroy();
      root.remove();
    },
  };
}
