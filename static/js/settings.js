/**
 * JustChess settings store (U2). Pure apart from the injected storage and
 * event target, so it runs in Node tests and in the browser.
 *
 *   createSettings(storage = safeLocalStorage(), { events } = {}) -> store
 *
 * Five per-device settings (BR6.1) under the storage key
 * "justchess.settings.v1" as one JSON object. Unknown or corrupt values fall
 * back to the default for that key only. When storage cannot be read or
 * written the store keeps working in memory and reports persistent = false
 * (BR6.2). Other tabs stay in sync through the window "storage" event.
 *
 * static/js/boot.js applies the theme and board before first paint with the
 * same key and allow-lists (tests/js/settings.test.mjs checks they agree).
 */

export const STORAGE_KEY = "justchess.settings.v1";

export const ALLOWED = Object.freeze({
  theme: Object.freeze(["device", "light", "dark"]),
  board: Object.freeze(["walnut-maple", "tournament", "rosewood"]),
  labels: Object.freeze(["inside", "frame"]),
  blunderWarnings: Object.freeze([true, false]),
  notifications: Object.freeze([true, false]),
});

export const DEFAULTS = Object.freeze({
  theme: "device",
  board: "walnut-maple",
  labels: "inside",
  blunderWarnings: true,
  notifications: false,
});

export const NOT_PERSISTENT_NOTICE = "Settings won't be kept after you close this tab.";
export const NOTIFICATIONS_BLOCKED = "Notifications are blocked in this browser";

/** Keep each allowed value of raw; every other key gets its default. */
export function sanitizeSettings(raw) {
  const source = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  const clean = {};
  for (const key of Object.keys(DEFAULTS)) {
    clean[key] = ALLOWED[key].includes(source[key]) ? source[key] : DEFAULTS[key];
  }
  return clean;
}

function parseStored(text) {
  if (text == null) return {};
  try {
    return JSON.parse(text);
  } catch (error) {
    console.error(`JustChess: stored settings are not valid JSON, using defaults (${error.message})`);
    return {};
  }
}

/** localStorage when it can be used, else null (private mode, blocked site data). */
export function safeLocalStorage() {
  try {
    const storage = globalThis.localStorage;
    if (!storage) return null;
    const probe = `${STORAGE_KEY}.probe`;
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    return storage;
  } catch {
    return null;
  }
}

function readInitial(storage) {
  if (!storage) return { values: { ...DEFAULTS }, persistent: false };
  try {
    return { values: sanitizeSettings(parseStored(storage.getItem(STORAGE_KEY))), persistent: true };
  } catch (error) {
    console.error(`JustChess: settings storage could not be read, keeping settings for this tab only (${error.message})`);
    return { values: { ...DEFAULTS }, persistent: false };
  }
}

function defaultEvents() {
  return typeof globalThis.addEventListener === "function" ? globalThis : null;
}

export function createSettings(storage = safeLocalStorage(), { events = defaultEvents() } = {}) {
  const initial = readInitial(storage);
  let values = initial.values;
  let persistent = initial.persistent;
  const subscribers = new Set();

  function notify(key, value) {
    for (const fn of [...subscribers]) {
      try {
        fn(key, value, { ...values });
      } catch (error) {
        console.error("JustChess: a settings subscriber threw", error);
      }
    }
  }

  function save() {
    if (!persistent) return;
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(values));
    } catch (error) {
      persistent = false;
      console.error(`JustChess: settings could not be saved, keeping them for this tab only (${error.message})`);
    }
  }

  function set(key, value) {
    if (!Object.hasOwn(DEFAULTS, key)) throw new TypeError(`unknown setting ${JSON.stringify(key)}`);
    if (!ALLOWED[key].includes(value)) {
      throw new RangeError(`setting ${key} cannot be ${JSON.stringify(value)}; allowed: ${ALLOWED[key].join(", ")}`);
    }
    if (values[key] === value) return;
    values = { ...values, [key]: value };
    save();
    notify(key, value);
  }

  function onStorage(event) {
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    const incoming = event.key === null ? { ...DEFAULTS } : sanitizeSettings(parseStored(event.newValue));
    for (const key of Object.keys(DEFAULTS)) {
      if (incoming[key] === values[key]) continue;
      values = { ...values, [key]: incoming[key] };
      notify(key, incoming[key]);
    }
  }

  if (events) events.addEventListener("storage", onStorage);

  return {
    get(key) {
      if (!Object.hasOwn(DEFAULTS, key)) throw new TypeError(`unknown setting ${JSON.stringify(key)}`);
      return values[key];
    },
    all: () => ({ ...values }),
    set,
    subscribe(fn) {
      if (typeof fn !== "function") throw new TypeError("subscribe needs a function");
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
    get persistent() {
      return persistent;
    },
    destroy() {
      subscribers.clear();
      if (events) events.removeEventListener("storage", onStorage);
    },
  };
}

/**
 * Notifications hook contract: hook(requested) -> Promise<boolean>.
 * Returns { value, notice }: value is what to store; notice is the message to
 * show, or null. Turning on stores true only when the hook resolves true; a
 * false result or a rejection stores false with a notice. With no hook the
 * requested value is stored directly.
 */
export async function decideNotifications(requested, hook) {
  if (typeof hook !== "function") return { value: Boolean(requested), notice: null };
  let granted;
  try {
    granted = await hook(Boolean(requested));
  } catch (error) {
    const message = error && error.message ? error.message : NOTIFICATIONS_BLOCKED;
    return { value: false, notice: requested ? message : null };
  }
  if (!requested) return { value: false, notice: null };
  return granted === true ? { value: true, notice: null } : { value: false, notice: NOTIFICATIONS_BLOCKED };
}

/**
 * Set data-theme (omitted for "device") and data-board on root, and keep them
 * in sync with the store. Returns an unsubscribe function.
 */
export function applyToDocument(store, root = globalThis.document && globalThis.document.documentElement) {
  if (!root) throw new TypeError("applyToDocument needs a root element");
  const apply = () => {
    const theme = store.get("theme");
    if (theme === "device") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    root.setAttribute("data-board", store.get("board"));
  };
  apply();
  return store.subscribe((key) => {
    if (key === "theme" || key === "board") apply();
  });
}
