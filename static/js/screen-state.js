/**
 * JustChess screen state machine (U3). A PURE reducer, no DOM:
 *
 *   reduce(state, event) -> state
 *
 * Base view (exactly one): "lobby" | "joining" | "notFound" | "waiting" |
 * "playing" | "gameOver" | "watching". The connection ("open" or
 * "reconnecting") is a separate flag on the room views, so reconnecting works
 * in every room view and the status line still puts "Game over" first (BR3.4).
 *
 * The state keeps the latest snapshot (BR3.1): a snapshot older than the one
 * held, by (game, version), is ignored. An equal pair is accepted, because
 * presence and rematch-lapse changes are broadcast without a version bump.
 * Every accepted snapshot re-derives the base view from its status, so a gap
 * that ends or restarts a game lands correctly.
 *
 * `transition` is set by the snapshot that caused it and cleared by the next
 * accepted snapshot: "ended" (playing -> finished in the same game, seen on
 * this screen: the win sequence plays) or "newGame" (a higher game number:
 * the sequence stops and the overlay closes). `opened` is true when the first
 * snapshot of a room arrives (a finished game then shows its end at once).
 *
 * Events:
 *   { type: "route", code? }                 "/" (no code) or "/r/{code}"
 *   { type: "joined", slot, notices? }       a seat from create, join or continue
 *   { type: "snapshot", snapshot }
 *   { type: "roomFull", snapshot? }          409 on join: watch, with the notice
 *   { type: "notFound", message? }           404 on join, or socket closed 1008
 *   { type: "joinFailed", message }          network or server error while joining
 *   { type: "connection", value }            "open" | "reconnecting"
 *   { type: "seatMoved" }                    socket seat-moved (BR1.7)
 *   { type: "seatLost" }                     403 "This isn't your seat" on an action
 *   { type: "notice", notice }               { key, colour? }
 *   { type: "dismissNotice", key }
 *   { type: "lobbyError", message, code? }   inline error on the lobby
 */

export const ROOM_VIEWS = Object.freeze(["joining", "waiting", "playing", "gameOver", "watching"]);
export const VIEWS = Object.freeze(["lobby", "notFound", ...ROOM_VIEWS]);

const SEAT_NOTICES = new Set(["storageBlocked", "staleSeat"]);

export function notFoundMessage(code) {
  return code ? `No room with code ${code}. Check the code or start a new game.` : "No room with that code. Check the code or start a new game.";
}

export function initialState() {
  return {
    view: "lobby",
    code: null,
    slot: null,
    watching: false,
    connection: "open",
    snapshot: null,
    notices: [],
    lobby: { error: null, code: "" },
    transition: null,
    opened: false,
  };
}

/** True unless `next` is older than `previous` by (game, version). */
export function isCurrent(previous, next) {
  if (!previous) return true;
  if (next.game !== previous.game) return next.game > previous.game;
  return next.version >= previous.version;
}

function isRoomView(view) {
  return ROOM_VIEWS.includes(view);
}

function addNotice(notices, notice) {
  if (!notice || typeof notice.key !== "string") return notices;
  return [...notices.filter((n) => n.key !== notice.key), { ...notice }];
}

function baseView(state, snapshot) {
  if (state.watching) return "watching";
  if (!state.slot) return "joining";
  if (snapshot.status === "waiting") return "waiting";
  if (snapshot.status === "finished") return "gameOver";
  return "playing";
}

function applySnapshot(state, snapshot) {
  if (!snapshot || typeof snapshot !== "object" || typeof snapshot.game !== "number" || typeof snapshot.version !== "number") {
    return state;
  }
  if (!isRoomView(state.view)) return state;
  if (state.code && snapshot.code && snapshot.code !== state.code) return state;
  const previous = state.snapshot;
  if (!isCurrent(previous, snapshot)) return { ...state, transition: null };
  let transition = null;
  if (previous && snapshot.game > previous.game) transition = "newGame";
  else if (previous && previous.game === snapshot.game && previous.status !== "finished" && snapshot.status === "finished") {
    transition = "ended";
  }
  return {
    ...state,
    snapshot,
    view: baseView(state, snapshot),
    transition,
    opened: !previous,
  };
}

function becomeWatcher(state, noticeKey) {
  if (!isRoomView(state.view)) return state;
  const notices = addNotice(state.notices.filter((n) => !SEAT_NOTICES.has(n.key)), { key: noticeKey });
  return { ...state, slot: null, watching: true, view: "watching", notices, transition: null };
}

function toLobby(state, error, code) {
  return { ...initialState(), view: "lobby", lobby: { error: error || null, code: code || "" } };
}

export function reduce(state, event) {
  if (!event || typeof event.type !== "string") throw new TypeError("screen event needs a type");
  switch (event.type) {
    case "route":
      if (!event.code) return toLobby(state, null, "");
      return { ...initialState(), view: "joining", code: event.code, lobby: { error: null, code: event.code } };
    case "joined":
      if (state.view !== "joining" && !isRoomView(state.view)) return state;
      if (event.slot !== "A" && event.slot !== "B") throw new TypeError(`joined needs slot A or B, got ${JSON.stringify(event.slot)}`);
      return {
        ...state,
        slot: event.slot,
        watching: false,
        notices: (event.notices || []).reduce(addNotice, state.notices.filter((n) => !SEAT_NOTICES.has(n.key))),
        view: state.snapshot ? baseView({ ...state, slot: event.slot, watching: false }, state.snapshot) : state.view,
      };
    case "snapshot":
      return applySnapshot(state, event.snapshot);
    case "roomFull": {
      if (!isRoomView(state.view)) return state;
      const watching = becomeWatcher(state, "seatsTaken");
      return event.snapshot ? applySnapshot(watching, event.snapshot) : watching;
    }
    case "notFound":
      if (state.view === "lobby") return state;
      return {
        ...initialState(),
        view: "notFound",
        lobby: { error: event.message || notFoundMessage(state.code), code: state.code || "" },
      };
    case "joinFailed":
      return toLobby(state, event.message || "Couldn't reach the server. Try again.", state.code);
    case "connection":
      if (event.value !== "open" && event.value !== "reconnecting") throw new TypeError(`connection must be open or reconnecting`);
      if (!isRoomView(state.view) || state.connection === event.value) return state;
      return { ...state, connection: event.value };
    case "seatMoved":
      return becomeWatcher(state, "seatMoved");
    case "seatLost":
      return becomeWatcher(state, "seatLost");
    case "notice":
      return { ...state, notices: addNotice(state.notices, event.notice) };
    case "dismissNotice":
      return { ...state, notices: state.notices.filter((n) => n.key !== event.key) };
    case "lobbyError":
      if (state.view !== "lobby" && state.view !== "notFound") return state;
      return { ...state, view: "lobby", lobby: { error: event.message || null, code: event.code ?? state.lobby.code } };
    default:
      throw new TypeError(`unknown screen event ${JSON.stringify(event.type)}`);
  }
}
