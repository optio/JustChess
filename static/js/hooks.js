/**
 * JustChess extension points (U3). Later units replace these hooks; U3 ships
 * them as no-ops so the game screen works on its own.
 *
 *   hooks.beforeMove(uci, snapshot)
 *       -> Promise<true | false | { allow: false, message?: string, snapshot?: object }>
 *                                      U4: blunder check before posting (static/js/blunder.js).
 *                                      true posts the move; false makes the board slide back
 *                                      silently. The object form also refuses, and carries a
 *                                      message for the flash line and/or a newer snapshot that
 *                                      app.js applies through the same path as a 409 move answer.
 *                                      Anything else that is not exactly true refuses.
 *   hooks.notifications(requested)  -> Promise<boolean>   U5: notification permission
 *                                      (passed to U2's settings panel as onNotificationsToggle).
 *                                      null means "no hook": the setting is stored directly.
 *                                      app.js sets it at start-up to notifications.js's toggle.
 *   hooks.onSnapshot(snapshot, view) -> void              U5: notify on a join, a move or a game end.
 *                                      app.js wraps it at start-up: notifications.js sees each
 *                                      new snapshot first (banner or local notification), then
 *                                      the previous hook runs.
 *   hooks.lessonsMount(element, { getSnapshot }) -> { destroy() } | void
 *                                                         U6: fill the lessons drawer. The game
 *                                                         screen calls it once, when the drawer
 *                                                         first opens (not when the screen is
 *                                                         built), keeps what it returns, and calls
 *                                                         destroy() when the game screen is torn
 *                                                         down (leaving the room, a seat-moved
 *                                                         re-render, a route change).
 *                                                         getSnapshot() returns the latest game
 *                                                         snapshot; the trainer does not use it.
 *
 *   setHook(name, fn)   replace one hook (a later unit calls this at start-up)
 *   runBeforeMove(uci, snapshot) -> Promise<{ allowed, message, snapshot }>
 *       message and snapshot are null unless the hook's object form gave them.
 *       A hook that throws or rejects is logged and the move is refused with
 *       "Couldn't check that move. Try again." (fail closed, never post unchecked).
 */

export const CHECK_FAILED = "Couldn't check that move. Try again.";

const DEFAULT_HOOKS = Object.freeze({
  beforeMove: async () => true,
  notifications: null,
  onSnapshot: () => {},
  lessonsMount: () => {},
});

export const hooks = { ...DEFAULT_HOOKS };

export function setHook(name, fn) {
  if (!Object.hasOwn(DEFAULT_HOOKS, name)) throw new TypeError(`unknown hook ${JSON.stringify(name)}`);
  if (fn !== null && typeof fn !== "function") throw new TypeError(`hook ${name} must be a function`);
  if (fn === null && name !== "notifications") throw new TypeError(`hook ${name} cannot be removed`);
  hooks[name] = fn;
}

export function resetHooks() {
  Object.assign(hooks, DEFAULT_HOOKS);
}

export async function runBeforeMove(uci, snapshot) {
  let verdict;
  try {
    verdict = await hooks.beforeMove(uci, snapshot);
  } catch (error) {
    console.error(`JustChess: the move check failed for ${uci}`, error);
    return { allowed: false, message: CHECK_FAILED, snapshot: null };
  }
  if (verdict === true) return { allowed: true, message: null, snapshot: null };
  if (verdict && typeof verdict === "object") {
    return {
      allowed: false,
      message: typeof verdict.message === "string" && verdict.message ? verdict.message : null,
      snapshot: verdict.snapshot && typeof verdict.snapshot === "object" ? verdict.snapshot : null,
    };
  }
  return { allowed: false, message: null, snapshot: null };
}

/**
 * Call a hook without letting it break the game screen. Returns what the hook
 * returned (lessonsMount's handle), or undefined when there is no hook or it threw.
 */
export function callSafely(name, ...args) {
  const fn = hooks[name];
  if (typeof fn !== "function") return undefined;
  try {
    return fn(...args);
  } catch (error) {
    console.error(`JustChess: the ${name} hook threw`, error);
    return undefined;
  }
}
