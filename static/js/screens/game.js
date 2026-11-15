/**
 * JustChess game view (U3): the board (U2), players line, status, claim
 * buttons, notices, Game settings sheet (U2 panel plus the continue-link row),
 * scoresheet, room score and the lessons drawer. Every value it shows comes
 * from a view model (view-model.js); it never reads a snapshot itself.
 *
 *   const game = createGameScreen(container, deps)
 *   game.render(view, { endPhase, reconnecting })
 *   game.renderJoining(code)
 *   game.flash(message)          the server's refusal under the status for 4 s (BR3.3)
 *   game.showBanner(show)        "Your move in the game. Back to the board" (BR3.8)
 *   game.drawerOpen              is the lessons drawer open
 *   game.board, game.boardRoot, game.resultCell, game.overlay, game.lessonsMount
 *   game.notifyBanner            U5's banner slot under the status (filled by notifications.js)
 *   game.destroy()
 *
 * deps: { settings, onMove(uci), onClaimDraw(), onClaimWin(), onStartNew(),
 *         onPlayAgain(), onShareResult(), onShareLink(),
 *         onContinueLink() -> Promise<{ ok, url?, message? }>,
 *         onCopy(text) -> Promise<"copied" | "field">, notificationsHook,
 *         lessonsMount(element) -> { destroy() } | void }
 *
 * Lessons drawer (U6 hook contract): deps.lessonsMount is called once, on the
 * first toggle that opens the drawer, with the drawer's mount element. Its
 * handle is kept, survives closing the drawer, and is destroyed by destroy().
 *
 * Board updates send only what changed. The fen is sent only when it differs
 * from the last one sent, so a snapshot that only changes presence never
 * answers (and so reverts) a move the board is still waiting on.
 * endPhase: null (no end shown), "sequence" (the win sequence owns the result
 * cell and the overlay stays closed) or "shown".
 *
 * P2 U1: the captured row (BR1.6) sits under the status line. It is derived
 * from the scoresheet's move list with captures.js, plus the player's own move
 * while the server has not answered: that pending capture joins the row when the
 * board's capture copy ends (onCaptureShown), and leaves it without a fade when
 * the move is refused (game.board.reject()).
 *
 * P2 U3 (BR4.1): pass-along controls from view.passAlong ("Play here while
 * waiting", "Wait for a friend instead" and the practice note), and seat A's
 * join-request banner from view.joinRequest above the status: role="alert",
 * "Someone wants to join as <colour> … Expires in m:ss", refreshed once a
 * minute and hidden at zero, with Accept and Decline. Extra deps:
 * onEnterPassAlong(), onLeavePassAlong(), onAnswerRequest(accept).
 *   game.renderJoiner(text)      the joiner's waiting or answer text, with
 *                                "Back to your games" (deps.onBackToGames) unless waiting
 *
 * P2 U4 (BR8.2): from view.computer, a row with Take back, Hint and Resign
 * (each shown and enabled as computer.js controlsFor says), "The computer
 * didn't answer." with Try again (view.computer.noAnswer), and the hint arrow
 * over the board (view.computer.hint, cleared by the next move, a takeback or
 * a new version). Resign opens an in-page confirm (role="alertdialog") with
 * "Resign" and "Keep playing"; Escape or "Keep playing" closes it and focus
 * goes back to the Resign button. The score line is view.score.line. Extra
 * deps: onTakeback(), onHint(), onResign() (after the confirm), onComputerRetry().
 */

import { createBoard } from "../board/board.js";
import { busyClick, isBusy, runBusy } from "../busy.js";
import { parseUci } from "../board/geometry.js";
import { createHintArrow } from "../board/hint-arrow.js";
import { captureLabel, capturedPieces } from "../captures.js";
import { NO_ANSWER_TEXT, RESIGN_QUESTION } from "../computer.js";
import { BANNER_REFRESH_MS, PRACTICE_NOTE, bannerText, requestDeadline } from "../pass-along.js";
import { renderSettingsPanel } from "../settings-panel.js";
import { STATUS_TEXT } from "../view-model.js";
import { createOverlay } from "./overlay.js";

export const FLASH_MS = 4000;
export const PHONE_ROWS = 6;
export const BANNER_TEXT = "Your move in the game. Back to the board";
export const CONTINUE_WARNING = "Anyone with this link can play your side. Don't share it.";
export const CONTINUE_FAILED = "Couldn't make a link. Try again.";
export const SAVING_STATUS = Object.freeze({ text: "Saving your move…", sub: null, tone: "surface", dot: "saving" });

function make(tag, attributes = {}, text) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "className") node.className = value;
    else node.setAttribute(name, value);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

function sameList(a, b) {
  return a.length === b.length && a.every((value, i) => value === b[i]);
}

function playsLine(name, colour) {
  return `${name} ${name === "You" ? "play" : "plays"} ${colour}`;
}

const PIECE_PATH = "/static/pieces/cburnett/";

function prefersReducedMotion() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function plyCount(rows) {
  return rows.reduce((n, row) => n + (row.white ? 1 : 0) + (row.black ? 1 : 0), 0);
}

/** Indexes in `next` holding a piece that `previous` did not have (a multiset difference). */
function addedIndexes(previous, next) {
  const left = {};
  for (const letter of previous) left[letter] = (left[letter] || 0) + 1;
  const added = new Set();
  next.forEach((letter, index) => {
    if (left[letter]) left[letter] -= 1;
    else added.add(index);
  });
  return added;
}

/**
 * P2 U1, BR1.6: the captured row under the status line. Two lines ("you" and
 * "your opponent" for a seat, White and Black for a watcher), each a list of
 * piece glyphs with an accessible label. paint() redraws from the move list
 * (plus the player's pending move); fade is "none", "settle" (the 200 ms
 * fade-in at once) or "after-capture" (the same fade, waiting for the board's
 * 260 ms capture copy first). Under reduced motion nothing fades.
 */
function buildCapturedRow() {
  const root = make("div", { className: "captured", "data-testid": "captured" });
  const lines = ["top", "bottom"].map((which) => {
    const line = make("div", { className: "captured-line", role: "img", "data-testid": `captured-${which}` });
    const title = make("span", { className: "captured-title", "aria-hidden": "true" }, "Captured");
    const pieces = make("span", { className: "captured-pieces", "aria-hidden": "true" });
    line.append(title, pieces);
    root.append(line);
    return { line, pieces };
  });
  root.hidden = true;
  let last = null; // { top: letters[], bottom: letters[] }

  function fill({ line, pieces }, letters, owner, newIndexes, fade) {
    line.setAttribute("aria-label", captureLabel(letters, owner));
    pieces.replaceChildren(...letters.map((letter, index) => {
      const colour = letter === letter.toUpperCase() ? "w" : "b";
      const img = make("img", {
        className: `captured-piece${colour === "b" ? " is-black" : ""}`, src: `${PIECE_PATH}${colour}${letter.toUpperCase()}.svg`, alt: "",
      });
      if (newIndexes.has(index)) img.classList.add("is-new", ...(fade === "after-capture" ? ["is-waiting"] : []));
      return img;
    }));
  }

  return {
    root,
    paint({ rows, pending, seat, colour }, fade) {
      let lists;
      try {
        lists = capturedPieces(rows, pending ? parseUci(pending) : null);
      } catch (error) {
        console.error("JustChess: the captured pieces could not be worked out from the move list", error);
        root.hidden = true;
        last = null;
        return;
      }
      const mine = colour === "black" ? lists.byBlack : lists.byWhite;
      const theirs = colour === "black" ? lists.byWhite : lists.byBlack;
      const next = seat ? { top: mine, bottom: theirs } : { top: lists.byWhite, bottom: lists.byBlack };
      const owners = seat ? ["you", "opponent"] : ["white", "black"];
      const animate = fade !== "none" && last !== null && !prefersReducedMotion();
      fill(lines[0], next.top, owners[0], animate ? addedIndexes(last.top, next.top) : new Set(), fade);
      fill(lines[1], next.bottom, owners[1], animate ? addedIndexes(last.bottom, next.bottom) : new Set(), fade);
      root.hidden = next.top.length === 0 && next.bottom.length === 0; // nothing taken yet: no empty row
      last = next;
    },
    reset() {
      root.hidden = true;
      last = null;
      lines.forEach(({ pieces }) => pieces.replaceChildren());
    },
  };
}

/** P2 U3: the pass-along buttons and practice note (BR4.1, Screen 5). */
function buildPassAlongRow(call) {
  const row = make("div", { className: "pass-along", "data-testid": "pass-along" });
  const start = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "pass-along-start" }, "Play here while waiting");
  const computer = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "stand-in-start" }, "Play the computer while waiting");
  const stop = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "pass-along-stop" }, "Wait for a friend instead");
  const note = make("p", { className: "t-small t-muted pass-along-note", "data-testid": "pass-along-note" }, PRACTICE_NOTE);
  row.append(start, computer, stop, note);
  busyClick(start, () => call("onEnterPassAlong"));
  busyClick(computer, () => call("onPlayComputerWhileWaiting"));
  busyClick(stop, () => call("onLeavePassAlong"));
  return {
    row,
    render(controls) {
      start.hidden = !controls.playHere;
      computer.hidden = !controls.playComputer;
      stop.hidden = !controls.waitForFriend;
      note.hidden = !controls.practiceNote;
      note.textContent = controls.note || PRACTICE_NOTE;
      row.hidden = start.hidden && computer.hidden && stop.hidden && note.hidden;
    },
  };
}

/**
 * P2 U3: seat A's join-request banner (BR2.5, BR4.1, Screen 6). The deadline is
 * taken from expiresIn when a new request (a new expiresAt) first arrives; the
 * text refreshes once a minute and the banner hides itself when time runs out.
 */
function buildRequestBanner(call) {
  const root = make("div", { className: "join-request", role: "alert", "data-testid": "join-request-banner" });
  const text = make("p", { className: "join-request-text", "data-testid": "join-request-text" });
  const accept = make("button", { className: "btn btn-primary", type: "button", "data-testid": "join-request-accept" }, "Accept");
  const decline = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "join-request-decline" }, "Decline");
  const buttons = make("div", { className: "join-request-actions" });
  buttons.append(accept, decline);
  root.append(text, buttons);
  root.hidden = true;
  let current = null; // { expiresAt, colour, deadline }
  let ranOut = null; // expiresAt of a request whose countdown reached zero here: never shown again
  let refreshTimer = null;
  let endTimer = null;

  function clearTimers() {
    if (refreshTimer !== null) clearInterval(refreshTimer);
    if (endTimer !== null) clearTimeout(endTimer);
    refreshTimer = endTimer = null;
  }

  function paint() {
    if (!current) return;
    const left = (current.deadline - Date.now()) / 1000;
    if (left <= 0) {
      runOut();
      return;
    }
    text.textContent = bannerText(current.colour, left);
  }

  function hide() {
    clearTimers();
    current = null;
    root.hidden = true;
  }

  function runOut() {
    if (current) ranOut = current.expiresAt;
    hide();
  }

  async function answer(button, acceptIt) {
    if (isBusy(accept) || isBusy(decline)) return;
    accept.disabled = decline.disabled = true;
    try {
      await runBusy(button, () => call("onAnswerRequest", acceptIt));
    } finally {
      accept.disabled = decline.disabled = false;
    }
  }

  accept.addEventListener("click", () => answer(accept, true));
  decline.addEventListener("click", () => answer(decline, false));

  return {
    root,
    render(request) {
      if (!request || request.expiresAt === ranOut) return hide();
      if (!current || current.expiresAt !== request.expiresAt) {
        clearTimers();
        const deadline = requestDeadline(request, Date.now());
        current = { expiresAt: request.expiresAt, colour: request.colour, deadline };
        refreshTimer = setInterval(paint, BANNER_REFRESH_MS);
        endTimer = setTimeout(runOut, Math.max(0, deadline - Date.now()));
      }
      current.colour = request.colour;
      root.hidden = false;
      paint();
    },
    destroy: clearTimers,
  };
}

/**
 * P2 U4: the computer's controls (Take back, Hint, Resign), the resign confirm and the
 * "didn't answer" line with Try again. render(view.computer) shows or hides each part.
 */
function buildComputerRow(call) {
  const root = make("div", { className: "computer-controls", "data-testid": "computer-controls" });
  const buttons = make("div", { className: "computer-buttons" });
  const takeback = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "computer-takeback" }, "Take back");
  const hint = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "computer-hint" }, "Hint");
  const resign = make("button", { className: "btn btn-quiet", type: "button", "data-testid": "computer-resign" }, "Resign");
  buttons.append(takeback, hint, resign);
  const confirm = make("div", {
    className: "computer-confirm", role: "alertdialog", "aria-labelledby": "computer-confirm-text", "data-testid": "resign-confirm",
  });
  const question = make("p", { className: "computer-confirm-text", id: "computer-confirm-text" }, RESIGN_QUESTION);
  const yes = make("button", { className: "btn btn-primary", type: "button", "data-testid": "resign-confirm-yes" }, "Resign");
  const no = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "resign-confirm-no" }, "Keep playing");
  const confirmButtons = make("div", { className: "computer-confirm-actions" });
  confirmButtons.append(yes, no);
  confirm.append(question, confirmButtons);
  confirm.hidden = true;
  const noAnswer = make("p", { className: "computer-no-answer", role: "alert", "data-testid": "computer-no-answer" });
  const retry = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "computer-retry" }, "Try again");
  noAnswer.append(make("span", {}, `${NO_ANSWER_TEXT} `), retry);
  noAnswer.hidden = true;
  root.append(buttons, confirm, noAnswer);
  root.hidden = true;

  function closeConfirm({ returnFocus = true } = {}) {
    if (confirm.hidden) return;
    confirm.hidden = true;
    if (returnFocus) resign.focus({ preventScroll: true });
  }

  busyClick(takeback, () => call("onTakeback"));
  busyClick(hint, () => call("onHint"));
  resign.addEventListener("click", () => {
    if (isBusy(resign)) return;
    confirm.hidden = false;
    no.focus({ preventScroll: true });
  });
  no.addEventListener("click", () => closeConfirm());
  yes.addEventListener("click", () => {
    closeConfirm({ returnFocus: false });
    runBusy(resign, () => call("onResign"));
  });
  confirm.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    closeConfirm();
  });
  busyClick(retry, () => call("onComputerRetry"));

  return {
    root,
    render(view) {
      root.hidden = !view;
      if (!view) {
        closeConfirm({ returnFocus: false });
        return;
      }
      const { controls } = view;
      for (const [button, control] of [[takeback, controls.takeback], [hint, controls.hint], [resign, controls.resign]]) {
        button.hidden = !control.show;
        button.disabled = !control.enabled;
      }
      buttons.hidden = !controls.resign.show;
      if (!controls.resign.enabled) closeConfirm({ returnFocus: false });
      noAnswer.hidden = !view.noAnswer;
    },
  };
}

function buildContinueRow(onContinueLink, onCopy) {
  const row = make("div", { className: "continue-row", "data-testid": "continue-row" });
  const heading = make("p", { className: "continue-title" }, "Continue on another device");
  const get = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "continue-link" }, "Get a private continue link");
  const result = make("div", { className: "continue-result" });
  result.hidden = true;
  const warning = make("p", { className: "continue-warning", "data-testid": "continue-warning" }, CONTINUE_WARNING);
  const label = make("label", { for: "continue-field" }, "Private link");
  const field = make("input", { id: "continue-field", className: "link-field", type: "text", readonly: "", "data-testid": "continue-field" });
  const copy = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "continue-copy" }, "Copy");
  const expiry = make("p", { className: "t-small t-muted" }, "It works once, for 10 minutes.");
  const fieldRow = make("div", { className: "link-row" });
  fieldRow.append(field, copy);
  result.append(warning, label, fieldRow, expiry);
  const error = make("p", { className: "field-error", role: "alert", "data-testid": "continue-error" });
  row.append(heading, get, result, error);

  get.addEventListener("click", () => runBusy(get, async () => {
    error.textContent = "";
    get.disabled = true;
    try {
      const answer = await onContinueLink();
      if (answer && answer.ok && answer.url) {
        field.value = answer.url;
        result.hidden = false;
        field.focus();
        field.select();
      } else {
        error.textContent = (answer && answer.message) || CONTINUE_FAILED;
      }
    } catch (failure) {
      console.error("JustChess: the continue link request failed", failure);
      error.textContent = CONTINUE_FAILED;
    } finally {
      get.disabled = false;
    }
  }));
  copy.addEventListener("click", async () => {
    const outcome = await onCopy(field.value);
    if (outcome === "copied") {
      copy.textContent = "Copied";
      setTimeout(() => { copy.textContent = "Copy"; }, 1600);
    } else {
      field.focus();
      field.select();
    }
  });
  return row;
}

export function createGameScreen(container, deps = {}) {
  if (!(container instanceof Element)) throw new TypeError("createGameScreen needs a container element");
  const { settings } = deps;
  if (!settings || typeof settings.get !== "function") throw new TypeError("createGameScreen needs the settings store");
  const call = (name, ...args) => (typeof deps[name] === "function" ? deps[name](...args) : undefined);

  const root = make("section", { className: "game", "aria-label": "Game", "data-testid": "game" });

  // --- board column -------------------------------------------------------
  const boardCol = make("div", { className: "game-board-col" });
  const boardRoot = make("div", { className: "game-board", "data-testid": "game-board" });
  const players = make("p", { className: "players", "data-testid": "players" });
  boardCol.append(boardRoot);

  // --- side column --------------------------------------------------------
  const side = make("div", { className: "game-side" });
  const status = make("div", { className: "status", role: "status", "aria-live": "polite", "data-testid": "status" });
  const dot = make("span", { className: "status-dot", "aria-hidden": "true" });
  const statusBody = make("p", { className: "status-body" });
  const statusText = make("strong", { className: "status-text", "data-testid": "status-text" });
  const statusSub = make("span", { className: "status-sub", "data-testid": "status-sub" });
  statusBody.append(statusText, statusSub);
  status.append(dot, statusBody);
  const flashLine = make("p", { className: "status-flash", role: "alert", "data-testid": "status-flash" });
  // U5: the notifications module fills this slot (notify.attachBanner); hidden until an alert.
  const notifyBanner = make("p", { className: "notify-banner", role: "status", "data-testid": "notify-banner" });
  notifyBanner.hidden = true;

  const claims = make("div", { className: "claims" });
  const claimDraw = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "claim-draw" });
  const claimWin = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "claim-win" });
  claims.append(claimDraw, claimWin);

  const notices = make("ul", { className: "notices", "data-testid": "notices" });

  const actions = make("div", { className: "game-actions" });
  const settingsToggle = make("button", {
    className: "btn btn-quiet", type: "button", "aria-expanded": "false", "aria-controls": "settings-sheet", "data-testid": "settings-toggle",
  }, "Game settings");
  actions.append(settingsToggle);

  const sheetPanel = make("div", { className: "settings-sheet", id: "settings-sheet", "data-testid": "settings-sheet" });
  sheetPanel.hidden = true;
  const sheetHead = make("div", { className: "settings-sheet-head" });
  const sheetTitle = make("h2", { className: "settings-sheet-title" }, "Game settings");
  const sheetClose = make("button", { className: "btn btn-quiet", type: "button", "data-testid": "settings-close" }, "Close");
  sheetHead.append(sheetTitle, sheetClose);
  const continueRow = buildContinueRow(() => call("onContinueLink"), (text) => call("onCopy", text));
  sheetPanel.append(sheetHead);
  const panel = renderSettingsPanel(sheetPanel, settings, {
    extraRows: continueRow,
    ...(typeof deps.notificationsHook === "function" ? { onNotificationsToggle: deps.notificationsHook } : {}),
  });

  const sheet = make("section", { className: "sheet", "aria-labelledby": "sheet-title", "data-testid": "scoresheet" });
  const sheetHeading = make("h2", { className: "sheet-title", id: "sheet-title" }, "Scoresheet");
  const table = make("table");
  const caption = make("caption", { className: "visually-hidden" }, "Moves of this game");
  const thead = make("thead");
  const headRow = make("tr");
  headRow.append(make("th", { scope: "col" }, "No."), make("th", { scope: "col" }, "White"), make("th", { scope: "col" }, "Black"));
  thead.append(headRow);
  const tbody = make("tbody", { "data-testid": "scoresheet-rows" });
  table.append(caption, thead, tbody);
  const sheetToggle = make("button", { className: "btn btn-quiet sheet-toggle", type: "button", "aria-expanded": "false", "data-testid": "scoresheet-toggle" });
  sheetToggle.hidden = true;
  const resultRow = make("div", { className: "sheet-result" });
  const resultCell = make("b", { "data-testid": "result" });
  resultRow.append(make("span", {}, "Result"), resultCell);
  sheet.append(sheetHeading, table, sheetToggle, resultRow);

  const score = make("p", { className: "score", "data-testid": "score" });

  const drawer = make("details", { className: "lessons", "data-testid": "lessons" });
  const summary = make("summary", {}, "Learn openings");
  summary.append(make("span", {}, " — your game keeps running"));
  const lessonsMount = make("div", { className: "lessons-mount", "data-testid": "lessons-mount" });
  drawer.append(summary, lessonsMount);

  const captured = buildCapturedRow();
  const passAlong = buildPassAlongRow(call); // P2 U3
  const requestBanner = buildRequestBanner(call); // P2 U3: above the status (Screen 6)
  const computerRow = buildComputerRow(call); // P2 U4
  const backToGames = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "joiner-back" }, "Back to your games");
  backToGames.hidden = true;
  backToGames.addEventListener("click", () => call("onBackToGames"));
  side.append(requestBanner.root, status, captured.root, flashLine, notifyBanner, claims, computerRow.root, passAlong.row, backToGames,
    notices, actions,
    sheetPanel, sheet, score, drawer);
  const banner = make("button", { className: "btn btn-primary lessons-banner", type: "button", "data-testid": "lessons-banner" }, BANNER_TEXT);
  banner.hidden = true;
  root.append(boardCol, side, banner);
  container.append(root);

  const overlay = createOverlay(boardCol, {
    onPlayAgain: () => call("onPlayAgain"),
    onShareResult: () => call("onShareResult"),
    onShareLink: () => call("onShareLink"),
  });
  boardCol.append(players);

  // P2 U1, BR1.6: what the captured row was last drawn from, and the player's move awaiting the server.
  const capturedInput = { rows: [], pending: null, seat: false, colour: "white" };
  let lastPlies = null;
  let lastStatus = null;
  const repaintPending = () => {
    if (capturedInput.pending) captured.paint(capturedInput, "settle");
  };

  const innerBoard = createBoard(boardRoot, {
    interactive: false,
    labels: settings.get("labels"),
    onMove: (uci) => {
      capturedInput.pending = uci;
      renderStatus(SAVING_STATUS, { keep: false }); // until the server answers
      call("onMove", uci);
    },
    onCaptureShown: repaintPending,
  });
  // The board as callers see it: a refused move also drops the pending capture from the row (no fade).
  const board = {
    set: (partial) => innerBoard.set(partial),
    reject() {
      const hadPending = capturedInput.pending !== null;
      capturedInput.pending = null;
      innerBoard.reject();
      if (hadPending && lastStatus) renderStatus(lastStatus);
      if (hadPending && lastPlies !== null) captured.paint(capturedInput, "none");
    },
    focus: () => innerBoard.focus(),
    destroy: () => innerBoard.destroy(),
    get liveRegion() {
      return innerBoard.liveRegion;
    },
    get mode() {
      return innerBoard.mode;
    },
  };
  const hintArrow = createHintArrow(boardRoot); // P2 U4
  const applied = { fen: null, orientation: "white", legalMoves: [], interactive: false, labels: settings.get("labels") };
  const unsubscribe = settings.subscribe((key, value) => {
    if (key === "labels" && value !== applied.labels) {
      applied.labels = value;
      board.set({ labels: value });
    }
  });

  let flashTimer = null;
  let sheetExpanded = false;
  let lessonsStarted = false;
  let lessonsHandle = null;

  // --- behaviour ------------------------------------------------------------

  function setSettingsOpen(open, { returnFocus = true } = {}) {
    sheetPanel.hidden = !open;
    settingsToggle.setAttribute("aria-expanded", String(open));
    if (open) sheetPanel.querySelector("input, button")?.focus({ preventScroll: true });
    else if (returnFocus) settingsToggle.focus({ preventScroll: true });
  }

  function onKeydown(event) {
    if (event.key === "Escape" && !sheetPanel.hidden) {
      event.preventDefault();
      setSettingsOpen(false);
    }
  }

  settingsToggle.addEventListener("click", () => setSettingsOpen(sheetPanel.hidden));
  sheetClose.addEventListener("click", () => setSettingsOpen(false));
  root.addEventListener("keydown", onKeydown);
  busyClick(claimDraw, () => call("onClaimDraw"));
  busyClick(claimWin, () => call("onClaimWin"));
  sheetToggle.addEventListener("click", () => {
    sheetExpanded = !sheetExpanded;
    applySheetCollapse();
  });
  function startLessons() {
    lessonsStarted = true;
    try {
      const handle = call("lessonsMount", lessonsMount);
      lessonsHandle = handle && typeof handle.destroy === "function" ? handle : null;
    } catch (error) {
      console.error("JustChess: the lessons drawer could not be filled", error);
    }
  }

  function stopLessons() {
    if (!lessonsHandle) return;
    const handle = lessonsHandle;
    lessonsHandle = null;
    try {
      handle.destroy();
    } catch (error) {
      console.error("JustChess: the lessons drawer could not be cleared", error);
    }
  }

  drawer.addEventListener("toggle", () => {
    if (drawer.open && !lessonsStarted) startLessons();
    if (!drawer.open) banner.hidden = true;
  });
  banner.addEventListener("click", () => {
    drawer.open = false;
    banner.hidden = true;
    boardRoot.scrollIntoView({ block: "start", behavior: "smooth" });
    board.focus();
  });

  function applySheetCollapse() {
    const rows = tbody.rows.length;
    const collapsible = rows > PHONE_ROWS;
    sheetToggle.hidden = !collapsible;
    sheet.classList.toggle("is-collapsed", collapsible && !sheetExpanded);
    sheetToggle.setAttribute("aria-expanded", String(sheetExpanded));
    sheetToggle.textContent = sheetExpanded ? `Show the last ${PHONE_ROWS} moves` : `Show all ${rows} moves`;
  }

  function renderBoard(view, reconnecting) {
    const next = view.board;
    const partial = {};
    if (next.orientation !== applied.orientation) partial.orientation = next.orientation;
    if (next.fen !== applied.fen) {
      partial.fen = next.fen;
      partial.lastMove = next.lastMove;
      partial.check = next.check;
    }
    if (!sameList(next.legalMoves, applied.legalMoves)) partial.legalMoves = next.legalMoves;
    if (next.interactive !== applied.interactive) partial.interactive = next.interactive;
    if (Object.keys(partial).length) {
      board.set(partial);
      Object.assign(applied, partial);
    }
    boardRoot.classList.toggle("is-reconnecting", reconnecting);
  }

  function renderStatus(statusView, { keep = true } = {}) {
    if (keep) lastStatus = statusView;
    status.setAttribute("aria-busy", String(statusView === SAVING_STATUS));
    statusText.textContent = statusView.text;
    statusSub.textContent = statusView.sub || "";
    statusSub.hidden = !statusView.sub;
    status.dataset.tone = statusView.tone;
    status.dataset.dot = statusView.dot || "none";
  }

  function renderClaims(view) {
    claimDraw.hidden = !view.claims.draw;
    claimDraw.textContent = view.claims.drawLabel || "";
    claimWin.hidden = !view.claims.win;
    claimWin.textContent = view.claims.winLabel;
    claims.hidden = claimDraw.hidden && claimWin.hidden;
  }

  function renderNotices(list) {
    notices.replaceChildren(...list.map((notice) => {
      const item = make("li", { className: "notice", "data-notice": notice.key });
      item.append(make("span", {}, notice.text));
      if (notice.action === "startNew") {
        const button = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "start-new-game" }, "Start a new game");
        busyClick(button, () => call("onStartNew"));
        item.append(button);
      }
      return item;
    }));
    notices.hidden = list.length === 0;
  }

  function renderSheet(sheetView, endPhase) {
    const rows = sheetView.rows.map((row, index) => {
      const tr = make("tr");
      if (index < sheetView.rows.length - PHONE_ROWS) tr.className = "is-older";
      const cells = [make("td", {}, String(row.number)), make("td", { className: "move" }, row.white), make("td", { className: "move" }, row.black)];
      if (sheetView.latest && sheetView.latest.row === index) {
        cells[sheetView.latest.side === "white" ? 1 : 2].classList.add("is-latest");
      }
      tr.append(...cells);
      return tr;
    });
    tbody.replaceChildren(...rows);
    applySheetCollapse();
    if (endPhase !== "sequence") resultCell.textContent = endPhase === "shown" ? sheetView.result || "" : "";
  }

  let capturedKey = null;

  /**
   * BR1.6: the row follows the server move list. A new position drops the pending
   * move. Only one new half-move fades in (after the board's capture copy); the
   * first render, a reconnect and a jump of several moves draw it at once.
   */
  function renderCaptured(view, reconnecting, fenChanged) {
    if (fenChanged) capturedInput.pending = null;
    const rows = view.scoresheet.rows;
    const plies = plyCount(rows);
    Object.assign(capturedInput, { rows, seat: Boolean(view.seat), colour: view.board.orientation });
    const key = JSON.stringify([rows, capturedInput.pending, capturedInput.seat, capturedInput.colour]);
    if (key === capturedKey) return; // a presence-only snapshot: leave a running fade alone
    const fade = lastPlies !== null && plies === lastPlies + 1 && !reconnecting ? "after-capture" : "none";
    capturedKey = key;
    lastPlies = plies;
    captured.paint(capturedInput, fade);
  }

  function render(view, { endPhase = null, reconnecting = false } = {}) {
    const fenChanged = view.board.fen !== applied.fen;
    renderBoard(view, reconnecting);
    const savingMove = capturedInput.pending !== null && !fenChanged && board.mode === "pending";
    renderCaptured(view, reconnecting, fenChanged);
    players.textContent = `${playsLine(view.players.white, "White")} · ${playsLine(view.players.black, "Black")}`;
    if (savingMove) lastStatus = view.status; // the move is still on its way: keep "Saving your move…"
    else renderStatus(view.status);
    renderClaims(view);
    passAlong.render(view.passAlong || { playHere: false, playComputer: false, waitForFriend: false, practiceNote: false });
    requestBanner.render(view.joinRequest || null);
    computerRow.render(view.computer || null);
    hintArrow.show(view.computer ? view.computer.hint : null, view.board.orientation);
    backToGames.hidden = true;
    renderNotices(view.notices);
    continueRow.hidden = !view.seat;
    renderSheet(view.scoresheet, endPhase);
    score.textContent = view.score.line || `Room score: ${view.score.text}`;
    overlay.render(view.overlay, { visible: endPhase === "shown" });
    root.dataset.state = view.overlay ? "over" : view.status.tone === "baize" ? "your-move" : "game";
  }

  function renderJoining(code) {
    renderStatus({ text: STATUS_TEXT.joining, sub: code ? `Room ${code}` : null, tone: "surface", dot: null });
    players.textContent = "";
    captured.reset();
    capturedInput.pending = null;
    capturedKey = null;
    lastPlies = null;
    renderClaims({ claims: { draw: null, win: false, winLabel: "" } });
    passAlong.render({ playHere: false, playComputer: false, waitForFriend: false, practiceNote: false });
    requestBanner.render(null);
    computerRow.render(null);
    hintArrow.clear();
    backToGames.hidden = true;
    renderNotices([]);
    continueRow.hidden = true;
    tbody.replaceChildren();
    applySheetCollapse();
    resultCell.textContent = "";
    score.textContent = "";
    overlay.render(null);
  }

  /** P2 U3 W4: the joiner's page: the waiting text, or a final answer with "Back to your games". */
  function renderJoiner(text, { waiting = false } = {}) {
    renderJoining(null);
    renderStatus({ text, sub: null, tone: "surface", dot: waiting ? "hollow" : null });
    backToGames.hidden = waiting;
  }

  return {
    render,
    renderJoining,
    renderJoiner,
    flash(message) {
      if (flashTimer !== null) clearTimeout(flashTimer);
      flashLine.textContent = message || "";
      flashTimer = message ? setTimeout(() => {
        flashLine.textContent = "";
        flashTimer = null;
      }, FLASH_MS) : null;
    },
    showBanner(show) {
      banner.hidden = !(show && drawer.open);
    },
    get drawerOpen() {
      return drawer.open;
    },
    board,
    boardRoot,
    resultCell,
    overlay,
    lessonsMount,
    notifyBanner,
    focusBoard() {
      board.focus();
    },
    destroy() {
      if (flashTimer !== null) clearTimeout(flashTimer);
      requestBanner.destroy();
      hintArrow.destroy();
      stopLessons();
      unsubscribe();
      root.removeEventListener("keydown", onKeydown);
      panel.destroy();
      overlay.destroy();
      board.destroy();
      root.remove();
    },
  };
}
