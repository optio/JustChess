/**
 * JustChess app entry (U3). Loaded by templates/index.html as a module.
 *
 * Routing: "/" is the lobby and "/r/{CODE}" a room, switched with
 * history.pushState and popstate, with no page reload (BR1.1, BR1.2).
 * "/learn" and "/learn/{id}" are the opening trainer on its own page (U6,
 * BR5.1), reached from the lobby's "Train" button. The trainer is
 * also mounted into the game's lessons drawer through hooks.lessonsMount,
 * which the game screen calls when the drawer first opens.
 *
 * The room flow's network steps and failure paths live in room-flow.js
 * (enterRoom, actionAnswer, submitMove), tested with fakes; this file
 * dispatches what they return.
 *
 * Opening a room (W3, BR1.4, BR1.5):
 *   1. A "#continue=<token>" fragment is removed from the address bar at once
 *      (replaceState) and redeemed; the new seat is stored.
 *   2. Join with the stored seat token (or none). A different token or slot in
 *      the answer means the stored seat was stale: the new seat replaces it and
 *      the screen says so. 409 room full: the stored seat is removed and the
 *      attached snapshot is drawn as the watcher view. 404: back to the lobby
 *      with "No room with code ...".
 *   3. Read the state with the X-Seat-Token header and draw it.
 *   4. Open the live socket (live.js); every newer snapshot redraws the screen.
 *
 * The screen state lives in screen-state.js (a pure reducer) and every pixel
 * of the game screen is drawn from view-model.js. This file only wires them to
 * the network, the DOM screens and the browser.
 *
 * Moves (W5, BR3.3): the board's move goes through hooks.beforeMove (U4), then
 * POST /moves with the snapshot's version. 200 or 409 apply the returned
 * snapshot; 400/403 slide the piece back and show the server's message for
 * 4 s; a 403 "This isn't your seat" also forgets the seat and switches to
 * watching. Whatever happens, a board still waiting after the answer is
 * rejected, so it can never stay locked.
 *
 * Blunder warnings (U4): at start-up the beforeMove hook is set to
 * createBlunderHook (blunder.js) with the blunder dialog
 * (screens/blunder-dialog.js). A refused check is applied with
 * room-flow's applyRefusal: the board slides back, a 409 snapshot goes through
 * handleAnswer like a 409 move answer, and a message goes to the flash line.
 * Every newer snapshot is offered to the dialog (it closes when the position
 * changed), and leaving the room closes it.
 *
 * Notifications (U5): at start-up, before any game screen is built,
 * hooks.notifications is set to the notifications module's toggle (U2's panel
 * runs it inside the switch's click) and hooks.onSnapshot is wrapped so every
 * new snapshot reaches notify.onSnapshot (banner, local notification). The
 * current seat is passed with notify.setSeat when a room is entered (a new
 * seat re-subscribes when the setting is on) and cleared when it is left or the
 * seat is lost; the game screen's banner slot is attached when it is built.
 *
 * Sharing (P2 U1): the top bar's Share button (and the overlay's share-link
 * button) open the share dialog (share-dialog.js): copy, app links, the share
 * sheet and a QR code of the invite link. Its text follows the room state and
 * refreshes while it is open. A copied result line without a clipboard is shown
 * in the overlay to copy by hand.
 *
 * Your games (P2 U2, W5): the lobby gets the seat store and the API for its
 * "Your games" panel, plus one memory object that outlives lobby rebuilds (the
 * 30 s request cap and the last rows). A row opens its room in the page, like
 * joining by code. The "Learn an opening" button is now "Train".
 *
 * Trainer hub (P2 U5, W4, BR3.1-BR3.4): "/learn" is now the hub (hub.js) with
 * its tabs; "/learn/tactics" opens it on the Tactics tab. "/learn/{id}" is the
 * lesson trainer (its "Other lessons" goes back to the hub) and
 * "/learn/tactics/{theme}" the puzzle screen (puzzle.js). One per-device
 * progress store (trainer-progress.js) is shared by the hub, the trainers and
 * the puzzles. The game's lessons drawer lists openings only (listKind).
 *
 * Endgame trainer (P2 U6, W1-W3, BR4.1, BR4.2): the hub gets the Endgames tab
 * (endgame-state.js ENDGAMES_TAB, registered once in the shared registry), whose
 * Play opens "/learn/endgames/{id}", the endgame screen (endgame.js).
 * "/learn/endgames" opens the hub on the Endgames tab.
 *
 * Pass-along and join requests (P2 U3, W1-W4, BR4.1): the game screen's
 * "Play here while waiting" / "Wait for a friend instead" post /mode, and the
 * request banner's Accept / Decline post /join-request/answer, all as seat
 * actions. A join answered 202 (room-flow "request") shows the joiner's waiting
 * text on the game screen and polls /join-request/status every 3 s while the
 * page is visible (pass-along.js createJoinerPoller); the request token waits in
 * session storage. Accepted: the token is stored as seat B and the room is
 * opened again, now seated. Declined, lapsed, busy, declined_recently and too
 * many requests show their text with "Back to your games".
 *
 * Play the computer (P2 U4, W1-W7, BR3.5, BR5.4, BR8.1-BR8.3): the lobby's
 * "Play the computer" panel reads GET /api/engine (again every 2 s while the
 * engine is starting) and its Play runs room-flow's playComputer (reopen,
 * rematch or create) and opens the room. In a computer room the top bar's
 * Share is hidden; Take back, Hint and Resign post their seat actions with the
 * snapshot's version; a hint is drawn as an arrow (and named on the flash line)
 * until the version changes. When the page shows the computer to move with
 * nothing asked (computer.js shouldResume), it calls computer-move: at once,
 * then at most 3 more times 5 s apart (nextRetry), then shows "The computer
 * didn't answer." with Try again. The socket's computer events update the
 * thinking / queued status, and a takeback event clears the arrow. The blunder
 * check runs unchanged before the player's moves.
 *
 * Gameplay settings: at start-up gameplay.js reads gameplay.yaml's page
 * settings from the shell (capture time, Your-games refresh, computer retries,
 * join poll), keeping the built-in values for anything missing.
 *
 * Seat tokens never appear in a URL or a log line.
 */

import { NETWORK_MESSAGE, createApi, normalizeCode, INVALID_CODE_MESSAGE } from "./api.js";
import { callSafely, hooks, setHook } from "./hooks.js";
import { createLive, socketUrl } from "./live.js";
import { createBlunderHook } from "./blunder.js";
import { createNotifications } from "./notifications.js";
import { actionAnswer, applyRefusal, enterRoom, playComputer, settleRequest, submitMove } from "./room-flow.js";
import { nextRetry, shouldResume } from "./computer.js";
import { clientGameplay, loadFromDocument } from "./gameplay.js";
import { JOINER_TEXT, createJoinerPoller, waitingText } from "./pass-along.js";
import { initialState, reduce } from "./screen-state.js";
import { createRequestStore, createSeatStore, parseContinueFragment, safeStorage } from "./seat-store.js";
import { createLessonsApi } from "./training/lessons-api.js";
import { mountTrainer } from "./training/trainer.js";
import { mountHub } from "./training/hub.js";
import { mountPuzzle } from "./training/puzzle.js";
import { mountEndgame } from "./training/endgame.js";
import { ENDGAMES_TAB, createEndgamesApi } from "./training/endgame-state.js";
import { registerTab, sharedRegistry } from "./training/hub-tabs.js";
import { createTrainerProgress } from "./training/trainer-progress.js";
import { applyToDocument, createSettings } from "./settings.js";
import { chooseShareMethod, continueUrl, copyText, inviteUrl, shareLink } from "./share.js";
import { createShareDialog } from "./share-dialog.js";
import { announcement, viewModel, winnerOf } from "./view-model.js";
import { createBlunderDialog } from "./screens/blunder-dialog.js";
import { createGameScreen } from "./screens/game.js";
import { renderLobby } from "./screens/lobby.js";
import { playWinSequence } from "./screens/win-sequence.js";

export const CREATE_FAILED = "Could not create a room. Try again.";
export const SEAT_REFUSED = "This isn't your seat"; // same text as room-flow.js and U1
const LOBBY_TITLE = "JustChess — Play a friend. Play the computer. Get better.";
const LEARN_TITLE = "Learn an opening — JustChess";
const HUB_TITLE = "Train — JustChess";
const TACTICS_TITLE = "Tactics — JustChess";
const ENDGAMES_TITLE = "Endgames — JustChess";
const LEARN_PATH = /^\/learn(?:\/([^/]*))?\/?$/;
const TACTICS_PATH = /^\/learn\/tactics\/([^/]+)\/?$/;
const ENDGAME_PATH = /^\/learn\/endgames\/([^/]+)\/?$/;
const ENGINE_STARTING = "The computer is starting";
const ENGINE_POLL_MS = 2000;
const ENGINE_POLL_LIMIT = 30;

export function startApp({
  doc = document,
  win = window,
  fetchImpl = (...args) => win.fetch(...args),
  WebSocketImpl = win.WebSocket,
} = {}) {
  const appRoot = doc.getElementById("app");
  const roomBar = doc.getElementById("room-bar");
  const roomCode = doc.getElementById("room-code");
  const shareButton = doc.getElementById("share");
  const shareDialogElement = doc.getElementById("share-dialog");
  const announcer = doc.getElementById("announcer");
  const homeLink = doc.getElementById("home-link");
  const topbar = doc.querySelector(".topbar");
  if (!appRoot || !roomBar || !shareButton || !announcer || !shareDialogElement) throw new Error("JustChess: the page shell is incomplete");

  loadFromDocument(doc); // gameplay.yaml's page settings, before anything that reads them is built
  const settings = createSettings();
  applyToDocument(settings, doc.documentElement);
  const seats = createSeatStore();
  const requests = createRequestStore(); // P2 U3: pending join-request tokens, this tab only
  const api = createApi(fetchImpl);
  const lessonsApi = createLessonsApi(fetchImpl);
  const progress = createTrainerProgress(); // P2 U5: per-device trainer progress
  const endgamesApi = createEndgamesApi(fetchImpl); // P2 U6
  if (!sharedRegistry.has(ENDGAMES_TAB.id)) registerTab(ENDGAMES_TAB);
  const origin = win.location.origin;
  // P2 U1: Share opens the share dialog (BR3.1-BR3.6); it replaced the inline link field.
  const shareDialog = createShareDialog(shareDialogElement, { trigger: shareButton, navigator: win.navigator });

  // U5: notifications. Registered before any game screen is built (it reads hooks.notifications).
  const notify = createNotifications({ win, doc, settings, fetchImpl });
  setHook("notifications", notify.toggle);
  const previousOnSnapshot = hooks.onSnapshot;
  setHook("onSnapshot", (snapshot, view) => {
    notify.onSnapshot(snapshot, view);
    previousOnSnapshot(snapshot, view);
  });
  notify.init();

  // U6: the lessons drawer holds a trainer with its own board (BR5.1).
  setHook("lessonsMount", (element) => mountTrainer(element, {
    api: lessonsApi, variant: "drawer", settings, win, progress, listKind: "opening",
  }));

  // U4: blunder warnings. The hook checks each move with POST /check-move
  // (the seat token is bound here) and asks through the dialog.
  const blunderDialog = createBlunderDialog(doc.body, { doc });
  setHook("beforeMove", createBlunderHook({
    api: { checkMove: (code, uci, version, options) => api.checkMove(code, roomToken, uci, version, options) },
    settings,
    openDialog: (text, { uci, snapshot }) => blunderDialog.open(text, {
      version: snapshot.version,
      game: snapshot.game,
      returnFocus: () => focusSquare(uci.slice(0, 2)),
    }),
  }));

  let state = initialState();
  let screen = null; // { kind: "lobby" | "game", ui }
  let live = null;
  let roomToken = null;
  let roomGeneration = 0;
  let endRun = null;
  let endPhase = null; // null | "sequence" | "shown"
  let wasYourMove = false;
  let joiner = null; // P2 U3: { text, waiting, poller } while this device asks to join
  const yourGamesMemory = {}; // P2 U2: the lobby panel's request cap and last rows, kept across lobby rebuilds
  // P2 U4: this page's computer-room state (reset when the room is left).
  let computerUi = freshComputerUi();
  const choiceStorage = safeStorage();

  function freshComputerUi() {
    return { hintPending: false, hint: null, noAnswer: false, attempts: 0, lastAttemptAt: null, timer: null, calling: false, position: null };
  }

  // --- screens ----------------------------------------------------------------

  function navigate(path) {
    if (win.location.pathname !== path) win.history.pushState(null, "", path);
  }

  function buildLearn(lessonId) {
    return mountTrainer(appRoot, {
      api: lessonsApi,
      variant: "page",
      settings,
      win,
      progress,
      initialLessonId: lessonId,
      onRoute: (id) => {
        if (id) return navigate(`/learn/${id}`);
        navigate("/learn");
        showHub(); // "Other lessons" goes back to the hub (P2 U5)
      },
    });
  }

  function buildHub(tab) {
    return mountHub(appRoot, {
      api: lessonsApi,
      progress,
      initialTab: tab,
      onOpenLesson: (id) => {
        navigate(`/learn/${id}`);
        showLesson(id);
      },
      onOpenTheme: (theme) => {
        navigate(`/learn/tactics/${theme}`);
        showPuzzle(theme);
      },
      context: { endgamesApi, onOpenEndgame: openEndgame },
    });
  }

  function openEndgame(id) {
    navigate(`/learn/endgames/${id}`);
    showEndgame(id);
  }

  function buildEndgame(id) {
    return mountEndgame(appRoot, {
      api: endgamesApi,
      positionId: id,
      progress,
      settings,
      win,
      onBack: () => {
        navigate("/learn/endgames");
        showHub("endgames");
      },
      onOpen: openEndgame,
    });
  }

  function buildPuzzle(theme) {
    return mountPuzzle(appRoot, {
      api: lessonsApi,
      theme,
      progress,
      settings,
      win,
      onBack: () => {
        navigate("/learn/tactics");
        showHub("tactics");
      },
    });
  }

  function showScreen(kind, arg = null, { force = false } = {}) {
    if (screen && screen.kind === kind && !force) return screen.ui;
    if (screen) screen.ui.destroy();
    appRoot.replaceChildren();
    let ui;
    if (kind === "learn") ui = buildLearn(arg);
    else if (kind === "hub") ui = buildHub(arg);
    else if (kind === "puzzle") ui = buildPuzzle(arg);
    else if (kind === "endgame") ui = buildEndgame(arg);
    else if (kind === "lobby") {
      ui = renderLobby(appRoot, {
        onStart: startGame,
        onJoin: joinByCode,
        onLearn: openLearn,
        onOpenGame: joinByCode,
        games: { api, seats, win, doc, memory: yourGamesMemory },
        labels: settings.get("labels"),
        computer: { storage: choiceStorage, loadEngine: loadEngineStatus, onPlay: playTheComputer },
      });
    } else ui = createGameScreen(appRoot, {
        settings,
        notificationsHook: hooks.notifications,
        onMove,
        onClaimDraw: () => seatAction((code, token) => api.claimDraw(code, token)),
        onClaimWin: () => seatAction((code, token) => api.claimWin(code, token)),
        onPlayAgain: () => seatAction((code, token) => api.rematch(code, token)),
        onEnterPassAlong: () => seatAction((code, token) => api.setMode(code, token, "pass_along")),
        onLeavePassAlong: () => seatAction((code, token) => api.setMode(code, token, "waiting")),
        onAnswerRequest: (accept) => seatAction((code, token) => api.answerRequest(code, token, accept)),
        onTakeback: () => versionedAction((code, token, version) => api.takeback(code, token, version)),
        onResign: () => versionedAction((code, token, version) => api.resign(code, token, version)),
        onHint: requestHint,
        onComputerRetry: retryComputer,
        onBackToGames: () => {
          if (win.location.pathname !== "/") win.history.pushState(null, "", "/");
          goLobby();
        },
        onShareResult: shareResult,
        onShareLink: shareInvite,
        onStartNew: startGame,
        onContinueLink: makeContinueLink,
        onCopy: (text) => copyText(text, { navigator: win.navigator }),
        lessonsMount: (element) => callSafely("lessonsMount", element, { getSnapshot: () => state.snapshot }),
      });
    if (kind === "game") notify.attachBanner(ui.notifyBanner);
    screen = { kind, ui };
    return ui;
  }

  /** Focus one board square (the blunder dialog returns focus to the move's from-square). */
  function focusSquare(square) {
    const game = screen && screen.kind === "game" ? screen.ui : null;
    const button = game ? game.boardRoot.querySelector(`button.sq[data-square="${square}"]`) : null;
    if (button) button.focus({ preventScroll: true });
    else if (game) game.focusBoard();
  }

  function currentView() {
    return viewModel(state.snapshot, {
      connection: state.connection,
      watching: state.watching,
      notices: state.notices,
      hintPending: computerUi.hintPending,
      hint: computerUi.hint,
      noAnswer: computerUi.noAnswer,
    });
  }

  function viewerColour() {
    return state.snapshot && !state.watching ? state.snapshot.colour || null : null;
  }

  function announce(text) {
    if (!text) return;
    announcer.textContent = "";
    win.setTimeout(() => { announcer.textContent = text; }, 30);
  }

  function clearEnd() {
    if (endRun) endRun.clear();
    endRun = null;
    endPhase = null;
  }

  function drawGame(game) {
    const view = currentView();
    game.render(view, { endPhase, reconnecting: state.connection === "reconnecting" });
    return view;
  }

  function startEnd(game, view, instant) {
    endPhase = "sequence";
    endRun = playWinSequence({
      boardRoot: game.boardRoot,
      resultCell: game.resultCell,
      resultText: view.scoresheet.result || "",
      winner: winnerOf(state.snapshot.result),
      instant,
      onReveal: () => {
        endPhase = "shown";
        if (screen && screen.kind === "game") drawGame(screen.ui);
      },
    });
  }

  function renderRoom(previous) {
    const game = showScreen("game");
    topbar?.classList.add("is-room");
    roomBar.hidden = false;
    roomCode.textContent = state.code;
    roomCode.setAttribute("aria-label", `Room code ${state.code}`);
    doc.title = `Room ${state.code} — JustChess`;
    shareButton.hidden = Boolean(state.snapshot && state.snapshot.mode === "computer"); // P2 U4: nobody to invite
    if (!state.snapshot) {
      if (joiner) game.renderJoiner(joiner.text, { waiting: joiner.waiting });
      else game.renderJoining(state.code);
      return;
    }
    const snapshotChanged = state.snapshot !== previous.snapshot;
    if (snapshotChanged && state.transition === "newGame") clearEnd();
    const finished = state.snapshot.status === "finished";
    let sequence = null;
    if (finished && endPhase === null) sequence = state.transition === "ended" ? "animate" : "instant";
    if (!finished && endPhase !== null) clearEnd();
    if (sequence) endPhase = "sequence";
    if (snapshotChanged) noteComputerSnapshot(state.snapshot);
    const view = drawGame(game);
    if (sequence) startEnd(game, view, sequence === "instant");
    if (snapshotChanged) {
      if (shareDialog.isOpen) shareDialog.open(shareDialogState()); // e.g. the opponent joined: refresh the text
      blunderDialog.supersede(state.snapshot);
      announce(announcement(previous.snapshot, state.snapshot, viewerColour()));
      if (view.yourMove && !wasYourMove) game.showBanner(true);
      if (state.transition === "newGame") game.focusBoard();
      callSafely("onSnapshot", state.snapshot, view);
      maybeResumeComputer();
    }
    wasYourMove = view.yourMove;
  }

  function renderLobbyView() {
    const lobby = showScreen("lobby");
    topbar?.classList.remove("is-room");
    roomBar.hidden = true;
    shareDialog.close();
    doc.title = LOBBY_TITLE;
    lobby.update({ error: state.lobby.error, code: state.lobby.code });
  }

  function dispatch(event) {
    const previous = state;
    state = reduce(state, event);
    if (state === previous) return;
    if (state.view === "lobby" || state.view === "notFound") {
      if (live) closeRoom();
      renderLobbyView();
    } else {
      renderRoom(previous);
    }
  }

  // --- rooms --------------------------------------------------------------------

  function stopJoiner() {
    if (joiner && joiner.poller) joiner.poller.stop();
    joiner = null;
  }

  /** P2 U3 W3/W4: show the joiner's text on the game screen (no snapshot: this device holds no seat). */
  function showJoiner(text, waiting) {
    joiner = { ...(joiner || {}), text, waiting };
    if (screen && screen.kind === "game" && !state.snapshot) screen.ui.renderJoiner(text, { waiting });
  }

  /** P2 U3 W4: poll the request every 3 s while visible; accepted opens the room again as seat B. */
  function startJoiner(code, requestToken, generation, colour = null) {
    showJoiner(waitingText(colour), true);
    const poller = createJoinerPoller({
      intervalMs: clientGameplay().joinPollMs, // gameplay.yaml, 3 s built in
      check: () => api.requestStatus(code, requestToken),
      onChange: ({ phase }) => {
        if (generation !== roomGeneration) return;
        const seat = settleRequest({ seats, requests, code, requestToken, status: phase });
        poller.stop();
        if (seat) {
          stopJoiner();
          openRoom(code);
          return;
        }
        showJoiner(JOINER_TEXT[phase] || JOINER_TEXT.unknown, false);
      },
    });
    joiner.poller = poller;
    poller.setHidden(Boolean(doc.hidden));
    poller.start();
  }

  doc.addEventListener("visibilitychange", () => {
    if (joiner && joiner.poller) joiner.poller.setHidden(Boolean(doc.hidden));
  });

  function closeRoom() {
    roomGeneration += 1;
    if (computerUi.timer !== null) win.clearTimeout(computerUi.timer);
    computerUi = freshComputerUi();
    shareButton.hidden = false;
    stopJoiner();
    blunderDialog.close();
    if (live) live.close();
    live = null;
    roomToken = null;
    notify.setSeat(null);
    wasYourMove = false;
    clearEnd();
  }

  function connectLive(code, token, generation) {
    if (generation !== roomGeneration) return;
    live = createLive({
      url: socketUrl(win.location, code),
      token,
      WebSocketImpl,
      onState: (snapshot) => dispatch({ type: "snapshot", snapshot }),
      onSeatMoved: () => {
        seats.remove(code);
        roomToken = null;
        notify.setSeat(null);
        dispatch({ type: "seatMoved" });
      },
      onConnection: (value) => dispatch({ type: "connection", value }),
      onNotFound: () => {
        seats.remove(code);
        dispatch({ type: "notFound" });
      },
      onComputer: ({ state: computerState, queuePosition }) => {
        const snapshot = state.snapshot;
        if (!snapshot || !snapshot.computer) return; // BR7.2: the status updates in place, same version
        dispatch({ type: "snapshot", snapshot: { ...snapshot, computer: { ...snapshot.computer, state: computerState, queuePosition } } });
      },
      onTakeback: () => {
        computerUi.hint = null;
      },
    });
  }

  function storeSeat(code, seat) {
    try {
      seats.set(code, seat);
    } catch (error) {
      console.error("JustChess: the seat answer was not valid", error);
    }
  }

  async function openRoom(code, created = null) {
    closeRoom();
    const generation = roomGeneration;
    const continueToken = parseContinueFragment(win.location.hash);
    if (win.location.hash) win.history.replaceState(null, "", `/r/${code}`);
    dispatch({ type: "route", code });

    const entered = await enterRoom({
      api,
      seats,
      code,
      created,
      continueToken,
      isCurrent: () => generation === roomGeneration,
      notify: (notice) => dispatch({ type: "notice", notice }),
      requests,
    });
    switch (entered.kind) {
      case "stale":
        return;
      case "request": // P2 U3 W2: a pass-along room; wait for the creator's answer
        startJoiner(code, entered.requestToken, generation, entered.colour);
        return;
      case "refused":
        showJoiner(JOINER_TEXT[entered.reason] || JOINER_TEXT.unknown, false);
        return;
      case "notFound":
        dispatch(entered.message ? { type: "notFound", message: entered.message } : { type: "notFound" });
        return;
      case "failed":
        dispatch({ type: "joinFailed", message: entered.message });
        return;
      case "full":
        dispatch({ type: "roomFull", snapshot: entered.snapshot });
        connectLive(code, null, generation);
        return;
      default:
        break;
    }
    const { seat, notices } = entered;
    roomToken = seat.token;
    notify.setSeat({ code, token: seat.token, slot: seat.slot });
    dispatch({ type: "joined", slot: seat.slot, notices });

    const read = await api.state(code, roomToken);
    if (generation !== roomGeneration) return;
    if (read.ok) dispatch({ type: "snapshot", snapshot: read.data });
    else if (read.status === 404) return dispatch({ type: "notFound" });
    // any other failure: the socket's first state message brings the snapshot
    connectLive(code, roomToken, generation);
  }

  function goLobby({ error = null, code = "" } = {}) {
    closeRoom();
    dispatch({ type: "route" });
    if (error) dispatch({ type: "lobbyError", message: error, code });
  }

  /** Leave any room and set the page up for one of the trainer screens. */
  function enterTrainer(title) {
    closeRoom();
    state = initialState();
    topbar?.classList.remove("is-room");
    roomBar.hidden = true;
    shareDialog.close();
    doc.title = title;
  }

  /** /learn (and /learn/tactics): the hub, optionally on one tab. */
  function showHub(tab = null) {
    enterTrainer(HUB_TITLE);
    if (screen && screen.kind === "hub") {
      if (tab) screen.ui.select(tab);
      return;
    }
    showScreen("hub", tab);
  }

  /** /learn/{id}: the lesson trainer on its own page (the id is checked by the trainer). */
  function showLesson(lessonId) {
    enterTrainer(LEARN_TITLE);
    if (screen && screen.kind === "learn") screen.ui.open(lessonId);
    else showScreen("learn", lessonId);
  }

  /** /learn/tactics/{theme}: the puzzle screen (the theme is checked by the screen). */
  function showPuzzle(theme) {
    enterTrainer(TACTICS_TITLE);
    showScreen("puzzle", theme, { force: true });
  }

  /** /learn/endgames/{id}: the endgame screen (the id is checked by the screen). */
  function showEndgame(id) {
    enterTrainer(ENDGAMES_TITLE);
    showScreen("endgame", id, { force: true });
  }

  function showLearn(lessonId) {
    if (lessonId === null) return showHub();
    if (lessonId === "tactics") return showHub("tactics");
    if (lessonId === "endgames") return showHub("endgames");
    return showLesson(lessonId);
  }

  function openLearn() {
    win.history.pushState(null, "", "/learn");
    showHub();
  }

  function learnId(raw) {
    if (!raw) return null;
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }

  function route() {
    const path = win.location.pathname;
    const tactics = TACTICS_PATH.exec(path);
    if (tactics) return showPuzzle(learnId(tactics[1]));
    const endgame = ENDGAME_PATH.exec(path);
    if (endgame) return showEndgame(learnId(endgame[1]));
    const learn = LEARN_PATH.exec(path);
    if (learn) return showLearn(learnId(learn[1]));
    const match = /^\/r\/([^/]+)\/?$/.exec(path);
    if (!match) return goLobby();
    let raw;
    try {
      raw = decodeURIComponent(match[1]);
    } catch {
      raw = match[1];
    }
    const code = normalizeCode(raw);
    if (!code) return goLobby({ error: INVALID_CODE_MESSAGE, code: raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6) });
    if (code !== raw) win.history.replaceState(null, "", `/r/${code}${win.location.hash}`);
    return openRoom(code);
  }

  async function startGame() {
    const lobby = screen && screen.kind === "lobby" ? screen.ui : null;
    if (lobby) lobby.setBusy(true);
    const created = await api.createRoom();
    if (lobby) lobby.setBusy(false);
    if (!created.ok) {
      if (lobby) lobby.showStartError(CREATE_FAILED);
      else if (screen && screen.kind === "game") screen.ui.flash(CREATE_FAILED);
      return;
    }
    const { code } = created.data;
    storeSeat(code, { token: created.data.token, slot: created.data.slot });
    win.history.pushState(null, "", `/r/${code}`);
    await openRoom(code, created.data);
  }

  function joinByCode(code) {
    win.history.pushState(null, "", `/r/${code}`);
    openRoom(code);
  }

  // --- play the computer (P2 U4) -------------------------------------------------

  const sleep = (ms) => new Promise((resolve) => win.setTimeout(resolve, ms));

  /** BR8.1: GET /api/engine for the panel; asks again every 2 s while the engine is still starting. */
  async function loadEngineStatus() {
    for (let attempt = 0; attempt < ENGINE_POLL_LIMIT; attempt += 1) {
      const answer = await api.engine();
      const status = answer.ok && answer.data ? answer.data : { available: false, reason: null };
      if (status.available || status.reason !== ENGINE_STARTING) return status;
      await sleep(ENGINE_POLL_MS);
    }
    return { available: false, reason: ENGINE_STARTING };
  }

  /** W1, BR3.5: reopen this level's room (rematch when finished) or create one, then open it. */
  async function playTheComputer({ colour, level }) {
    const lobby = screen && screen.kind === "lobby" ? screen.ui : null;
    if (lobby) lobby.setComputerBusy(true);
    let result;
    try {
      result = await playComputer({ api, seats, level, colour });
    } finally {
      if (lobby) lobby.setComputerBusy(false);
    }
    if (result.kind !== "open") {
      if (lobby) lobby.showComputerError(result.message);
      return;
    }
    win.history.pushState(null, "", `/r/${result.code}`);
    await openRoom(result.code, result.created || null);
  }

  /** New snapshot: drop a hint for an older version, and start counting resume calls afresh for a new position. */
  function noteComputerSnapshot(snapshot) {
    if (!snapshot || snapshot.mode !== "computer") return;
    if (computerUi.hint && computerUi.hint.version !== snapshot.version) computerUi.hint = null;
    const position = `${snapshot.game}:${snapshot.version}`;
    if (position !== computerUi.position) {
      computerUi.position = position;
      computerUi.attempts = 0;
      computerUi.lastAttemptAt = null;
      computerUi.noAnswer = false;
    }
  }

  function redrawGame() {
    if (screen && screen.kind === "game" && state.snapshot) drawGame(screen.ui);
  }

  /** BR5.4: call computer-move when the computer is to move and nothing was asked; 3 retries, 5 s apart. */
  function maybeResumeComputer() {
    if (!state.snapshot || state.watching || !roomToken || computerUi.calling || computerUi.timer !== null) return;
    if (computerUi.noAnswer || !shouldResume(state.snapshot)) return;
    const decision = nextRetry({ attempts: computerUi.attempts, lastAttemptAt: computerUi.lastAttemptAt, now: Date.now() });
    if (decision.action === "give-up") {
      computerUi.noAnswer = true;
      redrawGame();
    } else if (decision.action === "wait") {
      const generation = roomGeneration;
      computerUi.timer = win.setTimeout(() => {
        if (generation !== roomGeneration) return;
        computerUi.timer = null;
        maybeResumeComputer();
      }, decision.delayMs);
    } else {
      callComputerMove();
    }
  }

  async function callComputerMove() {
    const generation = roomGeneration;
    computerUi.calling = true;
    computerUi.attempts += 1;
    computerUi.lastAttemptAt = Date.now();
    let answer;
    try {
      answer = await api.computerMove(state.code, roomToken);
    } finally {
      if (generation === roomGeneration) computerUi.calling = false;
    }
    if (generation !== roomGeneration) return;
    if (answer.ok && answer.data && answer.data.computer && answer.data.computer.message && screen && screen.kind === "game") {
      screen.ui.flash(answer.data.computer.message); // busy: say so; the next try comes in 5 s
    }
    if (answer.ok || answer.status !== 0) handleAnswer(answer); // a network failure just counts as a try
    maybeResumeComputer(); // still idle on the computer's turn (busy, failed): the next try, or give up
  }

  /** "Try again" after "The computer didn't answer.": one more call, with a fresh count. */
  function retryComputer() {
    computerUi.noAnswer = false;
    computerUi.attempts = 0;
    computerUi.lastAttemptAt = null;
    redrawGame();
    maybeResumeComputer();
  }

  /** A seat action that needs the snapshot's version (takeback, resign). */
  async function versionedAction(request) {
    if (!state.snapshot) return;
    const version = state.snapshot.version;
    await seatAction((code, token) => request(code, token, version));
  }

  /** W6: ask for a hint; draw it as an arrow until the position changes. */
  async function requestHint() {
    if (!state.code || !roomToken || !state.snapshot || computerUi.hintPending) return;
    const generation = roomGeneration;
    const version = state.snapshot.version;
    computerUi.hintPending = true;
    redrawGame();
    let answer;
    try {
      answer = await api.hint(state.code, roomToken, version);
    } finally {
      if (generation === roomGeneration) computerUi.hintPending = false;
    }
    if (generation !== roomGeneration) return;
    if (answer.ok && answer.data && answer.data.version === version) {
      computerUi.hint = { from: answer.data.from, to: answer.data.to, san: answer.data.san, version };
      redrawGame();
      if (screen && screen.kind === "game") screen.ui.flash(`Hint: ${answer.data.san}`);
      return;
    }
    redrawGame();
    if (!answer.ok) handleAnswer(answer);
  }

  // --- actions ------------------------------------------------------------------

  function forgetSeat() {
    if (state.code) seats.remove(state.code);
    roomToken = null;
    notify.setSeat(null);
    if (live) live.setToken(null);
    dispatch({ type: "seatLost" });
  }

  /** Apply an action's answer (room-flow.js decides): a snapshot, the seat lost, the room gone, or the message. */
  function handleAnswer(answer) {
    const outcome = actionAnswer(answer, { seats, live, code: state.code });
    if (outcome.snapshot) dispatch({ type: "snapshot", snapshot: outcome.snapshot });
    if (outcome.seatLost) {
      roomToken = null;
      notify.setSeat(null);
      dispatch({ type: "seatLost" });
      return;
    }
    if (outcome.notFound) {
      dispatch({ type: "notFound" });
      return;
    }
    if (outcome.flash && screen && screen.kind === "game") screen.ui.flash(outcome.flash);
  }

  async function seatAction(request) {
    if (!state.code || !roomToken) return;
    const generation = roomGeneration;
    const answer = await request(state.code, roomToken);
    if (generation !== roomGeneration) return;
    handleAnswer(answer);
  }

  async function onMove(uci) {
    const game = screen && screen.kind === "game" ? screen.ui : null;
    const snapshot = state.snapshot;
    const generation = roomGeneration;
    if (!game || !snapshot || !roomToken) {
      if (game) game.board.reject();
      return;
    }
    try {
      const result = await submitMove({
        api, code: state.code, token: roomToken, uci, snapshot, isCurrent: () => generation === roomGeneration,
      });
      if (result.kind === "stale") return;
      if (result.kind === "refused") {
        applyRefusal(result, {
          board: game.board,
          flash: (message) => game.flash(message),
          // a newer snapshot from the check goes through the same path as a 409 move answer
          applySnapshot: (newer) => handleAnswer({ ok: false, status: 409, message: null, snapshot: newer }),
        });
        return;
      }
      handleAnswer(result.answer);
    } catch (error) {
      console.error(`JustChess: the move ${uci} could not be sent`, error);
      game.flash(NETWORK_MESSAGE);
    } finally {
      if (screen && screen.ui === game && game.board.mode === "pending") game.board.reject();
    }
  }

  async function makeContinueLink() {
    if (!state.code || !roomToken) return { ok: false, message: "Only a seated player can make a continue link." };
    const answer = await api.continueLink(state.code, roomToken);
    if (answer.ok && answer.data && typeof answer.data.continueToken === "string") {
      return { ok: true, url: continueUrl(origin, state.code, answer.data.continueToken) };
    }
    if (answer.status === 403 && answer.message === SEAT_REFUSED) forgetSeat();
    return { ok: false, message: answer.status === 0 ? NETWORK_MESSAGE : "Couldn't make a link. Try again." };
  }

  /** BR3.6: the colour whoever joins will play: the empty seat's colour, else the viewer's opposite. */
  function joinerColour(snapshot) {
    const seats = snapshot && snapshot.seats ? Object.values(snapshot.seats) : [];
    const empty = seats.find((seat) => seat && seat.presence === "empty" && (seat.colour === "white" || seat.colour === "black"));
    if (empty) return empty.colour;
    if (snapshot && snapshot.colour === "white") return "black";
    if (snapshot && snapshot.colour === "black") return "white";
    return "black";
  }

  function shareDialogState() {
    const snapshot = state.snapshot;
    return { url: inviteUrl(origin, state.code), waiting: Boolean(snapshot && snapshot.status === "waiting"), colour: joinerColour(snapshot) };
  }

  /** BR3.1: Share opens the dialog over an unchanged game screen. */
  function shareInvite() {
    if (!state.code) return;
    shareDialog.open(shareDialogState());
  }

  async function shareResult() {
    if (!state.snapshot || !state.code) return;
    const view = currentView();
    if (!view.overlay) return;
    const url = inviteUrl(origin, state.code);
    const game = screen && screen.kind === "game" ? screen.ui : null;
    if (chooseShareMethod(win.navigator) === "share") {
      await shareLink({ url, title: "JustChess", text: view.overlay.shareText }, { navigator: win.navigator });
      return;
    }
    const line = `${view.overlay.shareText}: ${url}`;
    const outcome = await copyText(line, { navigator: win.navigator });
    // No clipboard: the line is shown in the overlay to copy by hand (the old inline field is gone).
    game?.overlay.setMessage(outcome === "copied" ? "Result copied" : line);
  }

  // --- wiring -------------------------------------------------------------------

  shareButton.addEventListener("click", shareInvite);
  homeLink?.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    if (win.location.pathname !== "/") win.history.pushState(null, "", "/");
    goLobby();
  });
  win.addEventListener("popstate", () => route());
  settings.subscribe((key, value) => {
    if (key === "labels" && screen && screen.kind === "lobby") screen.ui.setLabels(value);
  });

  route();

  return {
    get state() {
      return state;
    },
  };
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  try {
    startApp();
  } catch (error) {
    console.error("JustChess could not start", error);
    const main = document.getElementById("app");
    if (main) main.textContent = "JustChess could not start. Reload the page to try again.";
  }
}
