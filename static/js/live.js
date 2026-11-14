/**
 * JustChess live connection (U3) to U1's /ws/{code} socket (BR3.2, W4).
 *
 *   const live = createLive({ url, token, WebSocketImpl, onState, onSeatMoved,
 *                             onConnection, onNotFound, timers, visibility })
 *   live.setToken(token)   use another seat token (or null) from now on; reconnects
 *   live.close()           stop for good (leaving the room)
 *
 * - On open it sends { type: "hello", token?, visible }. A watcher sends no
 *   token. The token goes only in this message, never in the URL.
 * - Each { type: "state" } message is passed to onState without its "type",
 *   unless it is older than the last one by (game, version) (BR3.1).
 * - It pings every 5 s while open and sends { type: "visibility" } on change,
 *   and { type: "visibility", visible: false } on pagehide (U5: the server only
 *   trusts a visible page it heard from in the last 6 s).
 * - When the socket closes and we did not close it, onConnection("reconnecting")
 *   fires and a retry is scheduled after 1, 2, 4 and 8 s, then every 10 s
 *   (backoffDelay). onConnection("open") fires on the first state after a
 *   (re)connect, because only then is the server's snapshot in hand.
 * - Close code 1008 means the room does not exist: onNotFound fires, no retry.
 * - { type: "seat-moved" }: the token is forgotten and onSeatMoved fires; the
 *   server has already made this socket a watcher (BR1.7).
 *
 * - P2 U4 (BR7.2): { type: "computer", state, queuePosition } goes to
 *   onComputer({ state, queuePosition }) (the reply moved up the queue or its
 *   search started) and { type: "takeback" } to onTakeback(); the state that
 *   follows a takeback arrives as a normal "state" message.
 *
 * Everything the browser provides is injectable (WebSocketImpl, timers,
 * visibility) so tests/js/live.test.mjs drives it with fakes.
 */

export const BACKOFF = Object.freeze([1000, 2000, 4000, 8000]);
export const BACKOFF_STEADY = 10000;
export const PING_INTERVAL = 5000;
export const CLOSE_POLICY = 1008;

/** Delay before retry number `attempt` (0-based): 1, 2, 4, 8 s, then 10 s forever. */
export function backoffDelay(attempt) {
  if (!Number.isInteger(attempt) || attempt < 0) throw new RangeError(`attempt must be a non-negative integer, got ${attempt}`);
  return attempt < BACKOFF.length ? BACKOFF[attempt] : BACKOFF_STEADY;
}

/** ws(s)://host/ws/CODE for a page location. */
export function socketUrl(location, code) {
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${location.host}/ws/${encodeURIComponent(code)}`;
}

function defaultTimers() {
  return {
    setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
    clearTimeout: (id) => globalThis.clearTimeout(id),
    setInterval: (fn, ms) => globalThis.setInterval(fn, ms),
    clearInterval: (id) => globalThis.clearInterval(id),
  };
}

function defaultVisibility() {
  const doc = globalThis.document;
  if (!doc) return null;
  const win = typeof globalThis.addEventListener === "function" ? globalThis : null;
  return {
    isVisible: () => doc.visibilityState !== "hidden",
    subscribe(fn) {
      const handler = () => fn(doc.visibilityState !== "hidden");
      // U5: a page being hidden or unloaded says so at once, so the server never trusts a stale
      // "visible" (pagehide also fires on mobile tab switches and bfcache entry).
      const hidden = () => fn(false);
      doc.addEventListener("visibilitychange", handler);
      if (win) {
        win.addEventListener("pagehide", hidden);
        win.addEventListener("pageshow", handler);
      }
      return () => {
        doc.removeEventListener("visibilitychange", handler);
        if (win) {
          win.removeEventListener("pagehide", hidden);
          win.removeEventListener("pageshow", handler);
        }
      };
    },
  };
}

function noop() {}

export function createLive({
  url,
  token = null,
  WebSocketImpl = globalThis.WebSocket,
  onState = noop,
  onSeatMoved = noop,
  onConnection = noop,
  onNotFound = noop,
  onComputer = noop,
  onTakeback = noop,
  timers = defaultTimers(),
  visibility = defaultVisibility(),
} = {}) {
  if (typeof url !== "string" || !url) throw new TypeError("createLive needs the socket url");
  if (typeof WebSocketImpl !== "function") throw new TypeError("createLive needs a WebSocket implementation");
  let currentToken = token || null;
  let socket = null;
  let attempt = 0;
  let retryTimer = null;
  let pingTimer = null;
  let closed = false;
  let last = null; // { game, version } of the newest state passed on
  let connected = false;

  function send(message) {
    if (!socket || socket.readyState !== 1) return false;
    try {
      socket.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error("JustChess live: could not send on the socket", error && error.name);
      return false;
    }
  }

  function visibleNow() {
    return visibility ? visibility.isVisible() : true;
  }

  function stopPing() {
    if (pingTimer !== null) timers.clearInterval(pingTimer);
    pingTimer = null;
  }

  function isOlder(snapshot) {
    if (!last) return false;
    if (snapshot.game !== last.game) return snapshot.game < last.game;
    return snapshot.version < last.version;
  }

  function handleMessage(event) {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      console.error("JustChess live: ignoring a message that is not JSON");
      return;
    }
    if (!message || typeof message !== "object") return;
    if (message.type === "state") {
      const { type: _type, ...snapshot } = message;
      if (typeof snapshot.game !== "number" || typeof snapshot.version !== "number") return;
      if (!connected) {
        connected = true;
        attempt = 0;
        onConnection("open");
      }
      if (isOlder(snapshot)) return;
      last = { game: snapshot.game, version: snapshot.version };
      onState(snapshot);
    } else if (message.type === "seat-moved") {
      currentToken = null;
      onSeatMoved();
    } else if (message.type === "computer") {
      if (!["queued", "thinking", "idle", "unavailable"].includes(message.state)) return;
      const queuePosition = Number.isInteger(message.queuePosition) ? message.queuePosition : null;
      onComputer({ state: message.state, queuePosition });
    } else if (message.type === "takeback") {
      onTakeback();
    }
  }

  function scheduleRetry() {
    if (closed || retryTimer !== null) return;
    const delay = backoffDelay(attempt);
    attempt += 1;
    retryTimer = timers.setTimeout(() => {
      retryTimer = null;
      connect();
    }, delay);
  }

  function handleClose(event, own) {
    if (own !== socket) return; // a socket we already replaced
    socket = null;
    stopPing();
    const wasConnected = connected;
    connected = false;
    if (closed) return;
    if (event && event.code === CLOSE_POLICY) {
      closed = true;
      onNotFound();
      return;
    }
    if (wasConnected || attempt === 0) onConnection("reconnecting");
    scheduleRetry();
  }

  function connect() {
    if (closed) return;
    let ws;
    try {
      ws = new WebSocketImpl(url);
    } catch (error) {
      console.error("JustChess live: could not open the socket", error && error.name);
      onConnection("reconnecting");
      scheduleRetry();
      return;
    }
    socket = ws;
    ws.onopen = () => {
      if (ws !== socket) return;
      const hello = { type: "hello", visible: visibleNow() };
      if (currentToken) hello.token = currentToken;
      send(hello);
      stopPing();
      pingTimer = timers.setInterval(() => send({ type: "ping" }), PING_INTERVAL);
    };
    ws.onmessage = (event) => {
      if (ws === socket) handleMessage(event);
    };
    ws.onclose = (event) => handleClose(event, ws);
    ws.onerror = () => {
      /* the close event that follows drives the retry */
    };
  }

  const unsubscribeVisibility = visibility ? visibility.subscribe((visible) => send({ type: "visibility", visible })) : noop;

  connect();

  return {
    setToken(next) {
      currentToken = next || null;
      if (closed) return;
      const old = socket;
      socket = null;
      stopPing();
      connected = false;
      if (old) {
        try {
          old.close(1000);
        } catch {
          /* already closing */
        }
      }
      if (retryTimer !== null) {
        timers.clearTimeout(retryTimer);
        retryTimer = null;
      }
      attempt = 0;
      connect();
    },
    close() {
      if (closed) return;
      closed = true;
      stopPing();
      if (retryTimer !== null) timers.clearTimeout(retryTimer);
      retryTimer = null;
      unsubscribeVisibility();
      if (socket) {
        const old = socket;
        socket = null;
        try {
          old.close(1000);
        } catch {
          /* already closing */
        }
      }
    },
    get token() {
      return currentToken;
    },
  };
}
