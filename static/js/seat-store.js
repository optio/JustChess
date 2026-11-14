/**
 * JustChess seat store (U3, BR1.3): the seat token for each room, kept in
 * long-lived browser storage and nowhere else.
 *
 *   const seats = createSeatStore(storage = safeStorage(), { now = Date.now })
 *   seats.get(code)          -> { token, slot } | null
 *   seats.set(code, seat)    seat = { token, slot: "A" | "B", kind?, computerLevel? }
 *   seats.remove(code, token?)  with a token, only a seat holding that token is removed
 *   seats.validSeats()       -> [{ code, token, slot, kind, computerLevel, savedAt }]
 *                            every well-formed stored seat, most recently saved
 *                            first; malformed entries are skipped and removed
 *   seats.persistent         false when storage is missing or throws: the seat
 *                            is then kept in memory for this tab only and the
 *                            screen shows the storage-blocked notice
 *
 * Keys are "justchess.seat.<CODE>" with a JSON value
 * { token, slot, kind, computerLevel?, savedAt }. A corrupt value reads as no
 * seat. Tokens are never logged.
 *
 * P2 U2 (SavedSeat, BR2.1, BR3.3): ``kind`` is "friend" (the default) or
 * "computer", and ``computerLevel`` is set only for a computer seat, so U4 can
 * find a level's room. A set without a kind keeps the kind already stored for
 * that room. ``savedAt`` (ms) orders the seats for the "Your games" request.
 *
 *   parseContinueFragment(hash) -> continue token | null   for "#continue=<token>" (BR1.5)
 *
 * P2 U3 (W2, W4): a pending join request's token is kept per room in session
 * storage (this tab only), so a reload of the joiner's waiting screen polls the
 * same request instead of asking again. Once accepted it moves to the seat
 * store as seat B's token; on any other answer it is removed.
 *
 *   const requests = createRequestStore(storage = safeSessionStorage())
 *   requests.get(code) -> token | null    requests.set(code, token)    requests.remove(code)
 *   Keys are "justchess.request.<CODE>". Without storage the token is kept in
 *   memory for this page only.
 */

export const KEY_PREFIX = "justchess.seat.";
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{16,256}$/;
const CODE_PATTERN = /^[A-Z0-9]{6}$/;

export function seatKey(code) {
  const clean = String(code ?? "").toUpperCase();
  if (!CODE_PATTERN.test(clean)) throw new TypeError(`not a room code: ${JSON.stringify(code)}`);
  return KEY_PREFIX + clean;
}

export const KINDS = Object.freeze(["friend", "computer"]);
export const COMPUTER_LEVELS = Object.freeze(["beginner", "casual", "club", "strong", "maximum"]);

function validSeat(seat) {
  return Boolean(seat) && typeof seat.token === "string" && seat.token.length > 0 && seat.token.length <= 256 && (seat.slot === "A" || seat.slot === "B");
}

/** kind and computerLevel agree: a level exactly when the kind is computer (undefined kind = friend). */
function validKind(kind, level) {
  if (kind === undefined || kind === "friend") return level === undefined || level === null;
  return kind === "computer" && COMPUTER_LEVELS.includes(level);
}

/** A full stored record (P2 U2), or null when any field is malformed. Old records without kind read as friend. */
function readRecord(code, value) {
  if (!validSeat(value) || !validKind(value.kind, value.computerLevel)) return null;
  const savedAt = Number.isFinite(value.savedAt) ? value.savedAt : 0;
  const kind = value.kind === "computer" ? "computer" : "friend";
  return { code, token: value.token, slot: value.slot, kind, computerLevel: kind === "computer" ? value.computerLevel : null, savedAt };
}

function storedValue(record) {
  const value = { token: record.token, slot: record.slot, kind: record.kind, savedAt: record.savedAt };
  if (record.kind === "computer") value.computerLevel = record.computerLevel;
  return value;
}

/** localStorage when it can be written, else null (private mode, blocked site data). */
export function safeStorage() {
  try {
    const storage = globalThis.localStorage;
    if (!storage) return null;
    const probe = `${KEY_PREFIX}probe`;
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    return storage;
  } catch {
    return null;
  }
}

export function createSeatStore(storage = safeStorage(), { now = Date.now } = {}) {
  const memory = new Map();
  let persistent = Boolean(storage);

  function fallBack(action, error) {
    if (persistent) console.error(`JustChess: seat storage could not ${action}, keeping the seat for this tab only (${error && error.name})`);
    persistent = false;
  }

  /** The parsed JSON value stored under key (memory first), undefined when absent, null when unreadable. */
  function readValue(key) {
    if (memory.has(key)) return memory.get(key);
    if (!persistent) return undefined;
    let raw;
    try {
      raw = storage.getItem(key);
    } catch (error) {
      fallBack("be read", error);
      return undefined;
    }
    if (raw == null) return undefined;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function removeKey(key) {
    memory.delete(key);
    if (!persistent) return;
    try {
      storage.removeItem(key);
    } catch (error) {
      fallBack("be cleared", error);
    }
  }

  /** Every seat key in storage and memory (collected first, so removing while reading is safe). */
  function seatKeys() {
    const keys = new Set(memory.keys());
    if (persistent && typeof storage.key === "function") {
      try {
        for (let index = 0; index < storage.length; index += 1) {
          const key = storage.key(index);
          if (typeof key === "string" && key.startsWith(KEY_PREFIX)) keys.add(key);
        }
      } catch (error) {
        fallBack("be listed", error);
      }
    }
    return [...keys];
  }

  return {
    get(code) {
      const key = seatKey(code);
      const value = readValue(key);
      const record = value ? readRecord(key.slice(KEY_PREFIX.length), value) : null;
      return record ? { token: record.token, slot: record.slot } : null;
    },
    set(code, seat) {
      const key = seatKey(code);
      if (!validSeat(seat)) throw new TypeError("a seat needs a token and slot A or B");
      let { kind, computerLevel } = seat;
      if (kind === undefined) {
        const previous = readValue(key);
        const kept = previous ? readRecord(key.slice(KEY_PREFIX.length), previous) : null;
        kind = kept ? kept.kind : "friend";
        computerLevel = kept ? kept.computerLevel : null;
      }
      if (!validKind(kind, computerLevel)) throw new TypeError("a computer seat needs a computer level, a friend seat none");
      const clean = storedValue({ token: seat.token, slot: seat.slot, kind, computerLevel, savedAt: now() });
      if (persistent) {
        try {
          storage.setItem(key, JSON.stringify(clean));
          memory.delete(key);
          return;
        } catch (error) {
          fallBack("be written", error);
        }
      }
      memory.set(key, clean);
    },
    remove(code, token) {
      const key = seatKey(code);
      if (token !== undefined) {
        const value = readValue(key);
        if (value && value.token !== token) return; // the room now holds another seat: keep it
      }
      removeKey(key);
    },
    /** Every well-formed seat, most recently saved first; malformed entries are skipped and removed (BR2.1). */
    validSeats() {
      const found = [];
      for (const key of seatKeys()) {
        const code = key.slice(KEY_PREFIX.length);
        if (!CODE_PATTERN.test(code)) continue; // not a seat key (e.g. the storage probe)
        const value = readValue(key);
        if (value === undefined) continue;
        const record = value ? readRecord(code, value) : null;
        if (record) found.push(record);
        else removeKey(key);
      }
      return found.sort((a, b) => b.savedAt - a.savedAt || a.code.localeCompare(b.code));
    },
    get persistent() {
      return persistent;
    },
  };
}

export const REQUEST_PREFIX = "justchess.request.";

/** sessionStorage when it can be written, else null. */
export function safeSessionStorage() {
  try {
    const storage = globalThis.sessionStorage;
    if (!storage) return null;
    const probe = `${REQUEST_PREFIX}probe`;
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    return storage;
  } catch {
    return null;
  }
}

export function createRequestStore(storage = safeSessionStorage()) {
  const memory = new Map();
  const keyFor = (code) => REQUEST_PREFIX + seatKey(code).slice(KEY_PREFIX.length);
  return {
    get(code) {
      const key = keyFor(code);
      if (memory.has(key)) return memory.get(key);
      let value = null;
      try {
        value = storage ? storage.getItem(key) : null;
      } catch {
        value = null;
      }
      return typeof value === "string" && TOKEN_PATTERN.test(value) ? value : null;
    },
    set(code, token) {
      const key = keyFor(code);
      if (typeof token !== "string" || !TOKEN_PATTERN.test(token)) throw new TypeError("not a request token");
      try {
        if (storage) {
          storage.setItem(key, token);
          memory.delete(key);
          return;
        }
      } catch {
        // storage refused: keep it for this page
      }
      memory.set(key, token);
    },
    remove(code) {
      const key = keyFor(code);
      memory.delete(key);
      try {
        if (storage) storage.removeItem(key);
      } catch {
        // nothing more to do: the memory copy is gone
      }
    },
  };
}

/** The continue token in "#continue=<token>", or null for any other or malformed fragment. */
export function parseContinueFragment(hash) {
  if (typeof hash !== "string") return null;
  const match = /^#?continue=([^&]*)$/.exec(hash.trim());
  if (!match) return null;
  let token;
  try {
    token = decodeURIComponent(match[1]);
  } catch {
    return null;
  }
  return TOKEN_PATTERN.test(token) ? token : null;
}
