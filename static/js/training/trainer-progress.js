/**
 * Per-device trainer progress store (P2 U5, BR3.2). Pure apart from the
 * injected storage, so it runs in Node tests and in the browser.
 *
 *   const progress = createTrainerProgress(storage = safeLocalStorage(), { clock })
 *   progress.markDone(group, itemId)   -> true when it was kept
 *   progress.isDone(group, itemId)     -> boolean
 *   progress.countDone(group, prefix?) -> how many items of a group are done
 *                                         (prefix narrows, e.g. countDone("tactics", "fork"))
 *   progress.persistent                -> false when storage is missing or failing
 *
 * Keys are "<group>:<itemId>", e.g. "openings:italian" or "tactics:fork:00008",
 * with the time solved as the value, all in ONE JSON object under STORAGE_KEY.
 * At most MAX_ENTRIES are kept (the oldest go first). Storage errors are
 * logged and ignored: without storage there is simply no progress, and a
 * failed write keeps nothing (BR3.2, "storage blocked" edge case).
 */

import { safeLocalStorage } from "../settings.js";

export const STORAGE_KEY = "justchess.trainer.v1";
export const MAX_ENTRIES = 5000;
export const GROUPS = Object.freeze(["openings", "traps", "endgames", "tactics", "defence"]);
const ITEM_ID = /^[A-Za-z0-9][A-Za-z0-9:_-]{0,80}$/;

/** The progress group of a lesson kind (opening -> openings, trap -> traps, defence -> defence). */
export function groupOfKind(kind) {
  return { opening: "openings", trap: "traps", defence: "defence" }[kind] || null;
}

function sanitize(raw) {
  const clean = {};
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return clean;
  for (const [key, value] of Object.entries(raw)) {
    const group = key.split(":", 1)[0];
    if (GROUPS.includes(group) && Number.isFinite(value)) clean[key] = value;
  }
  return clean;
}

function readAll(storage) {
  if (!storage) return { entries: {}, persistent: false };
  try {
    const text = storage.getItem(STORAGE_KEY);
    return { entries: text == null ? {} : sanitize(JSON.parse(text)), persistent: true };
  } catch (error) {
    console.error(`JustChess: trainer progress could not be read, none is shown (${error.message})`);
    return { entries: {}, persistent: false };
  }
}

function trimmed(entries) {
  const keys = Object.keys(entries);
  if (keys.length <= MAX_ENTRIES) return entries;
  const keep = keys.sort((a, b) => entries[b] - entries[a]).slice(0, MAX_ENTRIES);
  return Object.fromEntries(keep.map((key) => [key, entries[key]]));
}

export function createTrainerProgress(storage = safeLocalStorage(), { clock = () => Date.now() } = {}) {
  const initial = readAll(storage);
  let entries = initial.entries;
  let persistent = initial.persistent;

  function keyOf(group, itemId) {
    if (!GROUPS.includes(group)) throw new TypeError(`unknown progress group ${JSON.stringify(group)}`);
    if (typeof itemId !== "string" || !ITEM_ID.test(itemId)) throw new TypeError(`bad progress item ${JSON.stringify(itemId)}`);
    return `${group}:${itemId}`;
  }

  return {
    get persistent() {
      return persistent;
    },
    markDone(group, itemId) {
      const key = keyOf(group, itemId);
      if (!persistent) return false;
      const next = trimmed({ ...entries, [key]: clock() });
      try {
        storage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch (error) {
        console.error(`JustChess: trainer progress could not be saved (${error.message})`);
        persistent = false;
        return false;
      }
      entries = next;
      return true;
    },
    isDone(group, itemId) {
      return Object.hasOwn(entries, keyOf(group, itemId));
    },
    countDone(group, prefix = null) {
      if (!GROUPS.includes(group)) throw new TypeError(`unknown progress group ${JSON.stringify(group)}`);
      const start = prefix ? `${group}:${prefix}:` : `${group}:`;
      return Object.keys(entries).filter((key) => key.startsWith(start)).length;
    },
  };
}
