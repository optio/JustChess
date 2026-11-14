/**
 * JustChess lobby view (U3, BR1.1, BR1.2, W1, W2; P2 U2 BR3.1-BR3.6, W5, W6).
 *
 *   const lobby = renderLobby(container, { onStart, onJoin, onLearn?, onOpenGame?, games?, labels })
 *   (onLearn, added in U6, shows the secondary "Train" button that goes to
 *   /learn; without it the button is not drawn. Its test id stays
 *   "learn-opening".)
 *   lobby.update({ error, code })   inline error under the code field, code kept
 *   lobby.setBusy(boolean)          disable "Start a game" while a room is created
 *   lobby.showStartError(message)   error under "Start a game"
 *   lobby.refreshGames()            refresh the "Your games" list now (Retry does this)
 *   lobby.destroy()
 *
 * One primary action ("Start a game") and a labelled code field ("Have a room
 * code?"). The field uppercases as you type, keeps at most 6 letters or
 * digits, and is checked against ^[A-Z0-9]{6}$ on submit; its error is linked
 * with aria-describedby.
 *
 * P2 U2: the headline is "Play a friend. Play the computer. Get better." and,
 * with ``games = { api, seats, now?, win?, doc? }``, the "Your games" panel
 * replaces the starting-position hero (mockups Screen 1). It lists this
 * browser's stored seats through one POST /api/rooms/summaries (tokens in the
 * body only) and moves between Loading, Listed, Stale and Empty (W5):
 *
 *   - refresh on load, when the tab becomes visible and every 60 s while it is
 *     visible; at most one request in flight and at most one every 30 s for
 *     the same seats, except Retry, an empty panel or a newly saved seat
 *     (BR3.4, functional-spec edge cases);
 *   - a seat is dropped only when its summary says found:false (BR3.3); a
 *     failed request keeps every seat and shows the known rows with
 *     "Couldn't refresh your games. Retry";
 *   - a refresh rebuilds the list in place and keeps focus on the same row;
 *   - each row is one link to /r/<code>; ``onOpenGame(code)`` handles a plain
 *     click in the page (modified clicks keep the browser's default).
 *
 * ``labels`` is accepted for the settings sheet; with the hero board gone,
 * ``setLabels`` has nothing to update.
 *
 * P2 U4 (BR8.1, W1): with ``computer = { storage, loadEngine, onPlay }`` the
 * lobby shows the "Play the computer" panel: a Colour radio group (White,
 * Black, Random) and a Level radio group (Beginner … Maximum), defaulting to
 * Random and Casual and remembered in storage (computer.js readChoice /
 * writeChoice, both in try/catch). ``loadEngine()`` resolves GET /api/engine's
 * answer; while it is unavailable the panel reads "Play the computer is
 * unavailable" with the reason and Play is disabled. Play calls
 * ``onPlay({ colour, level })``.
 *   lobby.setComputerBusy(boolean)     "Starting…" on Play while the room opens
 *   lobby.showComputerError(message)   an error under Play
 */

import { INVALID_CODE_MESSAGE, normalizeCode } from "../api.js";
import { clientGameplay } from "../gameplay.js";
import { COLOURS, COLOUR_NAMES, LEVELS, LEVEL_NAMES, panelModel, readChoice, writeChoice } from "../computer.js";
import { filterAndSort, reconcile, rowModel, seatsToSend, staleRowModel } from "../your-games.js";

export const HEADLINE = "Play a friend. Play the computer. Get better.";
export const LOADING_TEXT = "Loading your games…";
export const EMPTY_TEXT = "No games yet. Start one above or play the computer.";
export const STALE_TEXT = "Couldn't refresh your games.";
export const REFRESH_EVERY_MS = 60_000; // built-in value; gameplay.yaml's client.your_games_refresh_seconds wins
export const MIN_GAP_MS = 30_000;
const PIECE_PATH = "/static/pieces/cburnett/";

function make(tag, attributes = {}, text) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "className") node.className = value;
    else node.setAttribute(name, value);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

function thumbnail(squares) {
  const grid = make("span", { className: "game-thumb", "aria-hidden": "true" });
  for (const cell of squares) {
    const square = make("span", { className: cell.dark ? "thumb-sq is-dark" : "thumb-sq" });
    if (cell.piece) {
      const white = cell.piece === cell.piece.toUpperCase();
      square.append(make("img", { src: `${PIECE_PATH}${white ? "w" : "b"}${cell.piece.toUpperCase()}.svg`, alt: "" }));
    }
    grid.append(square);
  }
  return grid;
}

function gameRow(model, key) {
  const item = make("li", { className: "your-games-item" });
  const link = make("a", {
    className: model.finished ? "game-row is-finished" : "game-row",
    href: model.href,
    "aria-label": model.ariaLabel,
    "data-testid": "your-games-row",
    "data-code": model.code,
    "data-key": key,
  });
  const text = make("span", { className: "game-row-text" });
  text.append(make("span", { className: "game-row-label" }, model.label), make("span", { className: "game-row-meta" }, model.meta));
  link.append(thumbnail(model.squares), text, make("span", { className: `pill pill-${model.pill.tone}`, "data-testid": "your-games-pill" }, model.pill.text));
  item.append(link);
  return item;
}

/**
 * The "Your games" panel (W5). Returns { element, refresh, destroy }.
 * ``memory`` (an object the page keeps across lobby rebuilds) holds the last
 * request time and rows, so the 30 s cap holds for the page and a returning
 * lobby shows the known rows at once instead of a blank panel.
 */
function createYourGames({ api, seats, now = Date.now, win = window, doc = document, memory = {} }, onOpenGame) {
  const panel = make("section", { className: "your-games sheet", "aria-labelledby": "your-games-title", "data-testid": "your-games" });
  const title = make("h2", { className: "sheet-title your-games-title", id: "your-games-title" }, "Your games");
  const status = make("p", { className: "your-games-status", "aria-live": "polite", "data-testid": "your-games-status" });
  const stale = make("p", { className: "your-games-stale", hidden: "", "data-testid": "your-games-stale" });
  const retry = make("button", { className: "btn btn-quiet", type: "button", "data-testid": "your-games-retry" }, "Retry");
  stale.append(make("span", {}, `${STALE_TEXT} `), retry);
  const list = make("ul", { className: "your-games-list", "data-testid": "your-games-list" });
  panel.append(title, status, stale, list);

  let rows = Array.isArray(memory.rows) ? memory.rows : []; // [{ model, key }] currently shown
  let inFlight = false;
  let destroyed = false;
  if (!Number.isFinite(memory.lastRequestAt)) memory.lastRequestAt = -Infinity;
  let timer = null;

  function render(phase) {
    const focusedKey = panel.contains(doc.activeElement) ? doc.activeElement.getAttribute("data-key") : null;
    status.textContent = phase === "loading" ? LOADING_TEXT : phase === "empty" ? EMPTY_TEXT : "";
    status.hidden = !status.textContent;
    stale.hidden = phase !== "stale";
    panel.dataset.state = phase;
    memory.rows = rows;
    list.replaceChildren(...rows.map(({ model, key }) => gameRow(model, key)));
    if (focusedKey) {
      const again = list.querySelector(`[data-key="${focusedKey}"]`);
      if (again) again.focus({ preventScroll: true });
    }
  }

  function showSummaries(kept) {
    rows = filterAndSort(kept, now()).map(({ seat, summary }) => ({ model: rowModel(summary, now()), key: `${seat.code}-${seat.slot}` }));
    render(rows.length ? "listed" : "empty");
  }

  function showFailure(sent) {
    if (!rows.length) rows = sent.map((seat) => ({ model: staleRowModel(seat), key: `${seat.code}-${seat.slot}` }));
    render(rows.length ? "stale" : "empty");
  }

  async function refresh({ force = false } = {}) {
    if (destroyed || inFlight || (doc.hidden && !force)) return;
    const sent = seatsToSend(seats.validSeats());
    if (!sent.length) {
      rows = [];
      render("empty");
      return;
    }
    // The cap applies once rows are on screen for the same seats; a panel with
    // nothing to show, or a seat saved since the last request, always asks.
    const seatSet = sent.map((seat) => `${seat.code}-${seat.slot}`).sort().join(" ");
    if (!force && rows.length && seatSet === memory.seatSet && now() - memory.lastRequestAt < MIN_GAP_MS) return;
    if (!rows.length) render("loading");
    inFlight = true;
    memory.lastRequestAt = now();
    memory.seatSet = seatSet;
    let answer;
    try {
      answer = await api.fetchSummaries(sent);
    } finally {
      inFlight = false;
    }
    if (destroyed) return;
    const reconciled = answer.ok ? reconcile(seats, sent, answer.data && answer.data.rooms) : { ok: false };
    if (reconciled.ok) showSummaries(reconciled.kept);
    else {
      if (answer.ok) console.error("JustChess: the games summary did not match the seats sent; keeping every seat");
      showFailure(sent);
    }
  }

  function onVisibility() {
    if (!doc.hidden) refresh();
  }

  function onRetry() {
    refresh({ force: true });
  }

  function onListClick(event) {
    const link = event.target.closest("a.game-row");
    if (!link || typeof onOpenGame !== "function") return;
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onOpenGame(link.getAttribute("data-code"));
  }

  retry.addEventListener("click", onRetry);
  list.addEventListener("click", onListClick);
  doc.addEventListener("visibilitychange", onVisibility);
  timer = win.setInterval(() => refresh(), clientGameplay().yourGamesRefreshMs); // gameplay.yaml, 60 s built in
  if (rows.length) render("listed");
  refresh();

  return {
    element: panel,
    refresh,
    destroy() {
      destroyed = true;
      win.clearInterval(timer);
      retry.removeEventListener("click", onRetry);
      list.removeEventListener("click", onListClick);
      doc.removeEventListener("visibilitychange", onVisibility);
    },
  };
}

function radioGroup(name, legendText, values, names, selected) {
  const fieldset = make("fieldset", { className: "computer-group", "data-testid": `computer-${name}` });
  fieldset.append(make("legend", { className: "computer-legend" }, legendText));
  const options = make("div", { className: "computer-options" });
  for (const value of values) {
    const id = `computer-${name}-${value}`;
    const input = make("input", { type: "radio", name: `computer-${name}`, id, value, "data-testid": id });
    input.checked = value === selected;
    const label = make("label", { className: "computer-option", for: id });
    label.append(input, make("span", {}, names[value]));
    options.append(label);
  }
  fieldset.append(options);
  return fieldset;
}

/** P2 U4 BR8.1: the "Play the computer" panel. Returns { element, setBusy, showError, destroy }. */
function createComputerPanel({ storage = null, loadEngine = null, onPlay }) {
  let choice = readChoice(storage);
  const panel = make("section", { className: "computer-panel sheet", "aria-labelledby": "computer-title", "data-testid": "computer-panel" });
  const title = make("h2", { className: "sheet-title", id: "computer-title" }, "Play the computer");
  const colours = radioGroup("colour", "Your colour", COLOURS, COLOUR_NAMES, choice.colour);
  const levels = radioGroup("level", "Level", LEVELS, LEVEL_NAMES, choice.level);
  const unavailable = make("p", { className: "computer-unavailable", role: "status", "data-testid": "computer-unavailable" });
  unavailable.hidden = true;
  const play = make("button", { className: "btn btn-primary", type: "button", "data-testid": "computer-play" }, "Play");
  const error = make("p", { className: "field-error", role: "alert", "data-testid": "computer-error" });
  panel.append(title, colours, levels, unavailable, play, error);
  let engineOk = true;
  let busy = false;
  let destroyed = false;

  function applyEngine(status) {
    const model = panelModel(status);
    engineOk = model.playEnabled;
    unavailable.textContent = model.message ? `${model.message}${model.reason ? `: ${model.reason}` : ""}.` : "";
    unavailable.hidden = !model.message;
    play.disabled = busy || !engineOk;
  }

  function onChange(event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "radio") return;
    choice = { ...choice, [input.name === "computer-colour" ? "colour" : "level"]: input.value };
    writeChoice(storage, choice);
  }

  function onClick() {
    if (play.disabled) return;
    error.textContent = "";
    onPlay({ ...choice });
  }

  panel.addEventListener("change", onChange);
  play.addEventListener("click", onClick);
  if (typeof loadEngine === "function") {
    Promise.resolve()
      .then(loadEngine)
      .then((status) => { if (!destroyed) applyEngine(status); })
      .catch((failure) => {
        console.error("JustChess: could not read the engine status", failure && failure.name);
        if (!destroyed) applyEngine({ available: false, reason: null });
      });
  }

  return {
    element: panel,
    setBusy(value) {
      busy = Boolean(value);
      play.textContent = busy ? "Starting…" : "Play";
      play.disabled = busy || !engineOk;
    },
    showError(message) {
      error.textContent = message || "";
    },
    destroy() {
      destroyed = true;
      panel.removeEventListener("change", onChange);
      play.removeEventListener("click", onClick);
    },
  };
}

export function renderLobby(container, { onStart, onJoin, onLearn = null, onOpenGame = null, games = null, labels = "inside", computer = null } = {}) {
  if (!(container instanceof Element)) throw new TypeError("renderLobby needs a container element");
  if (typeof onStart !== "function" || typeof onJoin !== "function") throw new TypeError("renderLobby needs onStart and onJoin");
  void labels; // kept for the settings sheet; the lobby no longer draws a board

  const root = make("section", { className: "lobby", "aria-labelledby": "lobby-title", "data-testid": "lobby" });
  const text = make("div", { className: "lobby-text" });
  const title = make("h1", { className: "t-hero lobby-title", id: "lobby-title" }, HEADLINE);
  const lede = make("p", { className: "t-lede lobby-lede" },
    "No accounts. No subscriptions. Just chess. Start a game and send the link, or join with a room code.");
  const start = make("button", { className: "btn btn-primary", type: "button", "data-testid": "start-game" }, "Start a game");
  const startError = make("p", { className: "field-error", role: "alert", "data-testid": "start-error" });
  const actions = make("div", { className: "lobby-actions" });
  actions.append(start);
  let learn = null;
  if (typeof onLearn === "function") {
    learn = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "learn-opening" }, "Train");
    actions.append(learn);
  }

  const form = make("form", { className: "join-form", novalidate: "", "data-testid": "join-form" });
  const label = make("label", { for: "room-code-input" }, "Have a room code?");
  const row = make("div", { className: "join-row" });
  const input = make("input", {
    id: "room-code-input",
    className: "code-input",
    type: "text",
    maxlength: "6",
    autocomplete: "off",
    autocapitalize: "characters",
    spellcheck: "false",
    placeholder: "K7Q2PX",
    "aria-describedby": "room-code-error",
    "data-testid": "room-code-input",
  });
  const join = make("button", { className: "btn btn-secondary", type: "submit", "data-testid": "join-room" }, "Join");
  const codeError = make("p", { className: "field-error", id: "room-code-error", "aria-live": "polite", "data-testid": "room-code-error" });
  row.append(input, join);
  form.append(label, row, codeError);
  text.append(title, lede, actions, startError, form);
  const computerPanel = computer && typeof computer.onPlay === "function" ? createComputerPanel(computer) : null;
  if (computerPanel) text.append(computerPanel.element);
  root.append(text);
  container.append(root);
  const yourGames = games ? createYourGames(games, onOpenGame) : null;
  if (yourGames) root.append(yourGames.element);

  function showCodeError(message) {
    codeError.textContent = message || "";
    if (message) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
  }

  function onInput() {
    const cleaned = input.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
    if (cleaned !== input.value) input.value = cleaned;
    if (codeError.textContent) showCodeError("");
  }

  function onSubmit(event) {
    event.preventDefault();
    const code = normalizeCode(input.value);
    if (!code) {
      showCodeError(INVALID_CODE_MESSAGE);
      input.focus();
      return;
    }
    showCodeError("");
    onJoin(code);
  }

  function onStartClick() {
    startError.textContent = "";
    onStart();
  }

  function onLearnClick() {
    onLearn();
  }

  input.addEventListener("input", onInput);
  form.addEventListener("submit", onSubmit);
  start.addEventListener("click", onStartClick);
  if (learn) learn.addEventListener("click", onLearnClick);

  return {
    element: root,
    update({ error = null, code = "" } = {}) {
      if (code && !input.value) input.value = code;
      showCodeError(error);
    },
    setBusy(busy) {
      start.disabled = Boolean(busy);
      start.textContent = busy ? "Starting…" : "Start a game";
    },
    showStartError(message) {
      startError.textContent = message || "";
    },
    setComputerBusy(busy) {
      if (computerPanel) computerPanel.setBusy(busy);
    },
    showComputerError(message) {
      if (computerPanel) computerPanel.showError(message);
    },
    setLabels() {
      // The P2 U2 lobby has no board; the labels setting applies to the game screen.
    },
    refreshGames() {
      if (yourGames) yourGames.refresh({ force: true });
    },
    focusStart() {
      start.focus();
    },
    destroy() {
      input.removeEventListener("input", onInput);
      form.removeEventListener("submit", onSubmit);
      start.removeEventListener("click", onStartClick);
      if (learn) learn.removeEventListener("click", onLearnClick);
      if (yourGames) yourGames.destroy();
      if (computerPanel) computerPanel.destroy();
      root.remove();
    },
  };
}
