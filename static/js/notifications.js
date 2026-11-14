/**
 * JustChess notifications (U5): the permission prompt, the service worker, Web
 * Push subscriptions, the in-page banner and local notifications.
 *
 *   const notify = createNotifications({ win, doc, settings, fetchImpl, storage, timers })
 *   notify.toggle(requested) -> Promise<boolean>   hooks.notifications (U2's onNotificationsToggle)
 *   notify.onSnapshot(snapshot, view) -> action    called from hooks.onSnapshot on each new snapshot
 *   notify.setSeat({ code, token, slot } | null)   the current seat; a new seat re-subscribes
 *   notify.attachBanner(element)                   the game screen's banner slot
 *   notify.init()                                  at start-up: re-register the worker if already on
 *
 * Turning on (BR3.1): Notification.requestPermission() is called synchronously
 * inside the click, before anything is awaited. Granted: register /sw.js, fetch
 * /api/push/key; with a key, subscribe to push and POST the subscription for
 * the current seat ("push" mode); without one, local notifications only. The
 * result is true whenever permission was granted. Denied: false, and U2's panel
 * says "Notifications are blocked in this browser". No Notification API at all
 * rejects with UNSUPPORTED, which the panel shows.
 *
 * Turning off (BR3.4): the browser subscription is unsubscribed and the
 * endpoint is always sent with the unsubscribe. No system notification is shown
 * after that; the visible-page banner stays, as part of the game screen.
 *
 * Each snapshot (BR3.2, plan decision): the event key comes from notify-core's
 * eventFor (the server's keys), and decide() picks the banner (page visible),
 * a local notification through the service worker (page hidden, setting on,
 * permission granted, with or without push), or nothing. Keys already shown
 * are kept in sessionStorage (in memory when it cannot be used) and never shown
 * twice. Push and local notifications share the tag "<code>:<key>" with
 * renotify false, so if both arrive the second silently replaces the first.
 *
 * Seat tokens go only into POST bodies; endpoints and tokens are never logged.
 */

import { NOTIFICATIONS_BLOCKED } from "./settings.js";
import { decide, eventFor } from "./notify-core.js";

export { NOTIFICATIONS_BLOCKED };
export const UNSUPPORTED = "This browser can't show notifications";
export const SHOWN_STORAGE_KEY = "justchess.notify.shown.v1";
export const SHOWN_LIMIT = 50;
export const BANNER_MS = 6000;
export const WORKER_URL = "/sw.js";

/** base64url (no padding) -> Uint8Array, for applicationServerKey. */
export function base64UrlToBytes(text) {
  const clean = String(text || "").replace(/-/g, "+").replace(/_/g, "/");
  const padded = clean + "=".repeat((4 - (clean.length % 4)) % 4);
  const binary = globalThis.atob(padded);
  return Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
}

function sameBytes(a, b) {
  if (!a || !b) return false;
  const left = new Uint8Array(a);
  if (left.length !== b.length) return false;
  return left.every((value, i) => value === b[i]);
}

function safeSessionStorage(win) {
  try {
    const storage = win && win.sessionStorage;
    if (!storage) return null;
    storage.setItem(`${SHOWN_STORAGE_KEY}.probe`, "1");
    storage.removeItem(`${SHOWN_STORAGE_KEY}.probe`);
    return storage;
  } catch {
    return null;
  }
}

function loadShown(storage) {
  if (!storage) return new Set();
  try {
    const parsed = JSON.parse(storage.getItem(SHOWN_STORAGE_KEY) || "[]");
    return new Set(Array.isArray(parsed) ? parsed.filter((tag) => typeof tag === "string").slice(-SHOWN_LIMIT) : []);
  } catch {
    return new Set();
  }
}

function defaultTimers() {
  return { setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms), clearTimeout: (id) => globalThis.clearTimeout(id) };
}

export function createNotifications({
  win = globalThis.window,
  doc = globalThis.document,
  settings,
  fetchImpl = (...args) => win.fetch(...args),
  storage = safeSessionStorage(win),
  timers = defaultTimers(),
} = {}) {
  if (!settings || typeof settings.get !== "function") throw new TypeError("createNotifications needs the settings store");
  let seat = null; // { code, token, slot }
  let lastSnapshot = null;
  let banner = null;
  let bannerTimer = null;
  let mode = "off"; // "off" | "local" | "push"
  const shown = loadShown(storage);

  const hasNotificationApi = () => Boolean(win && typeof win.Notification === "function");
  const permission = () => (hasNotificationApi() ? win.Notification.permission : "denied");
  const workers = () => (win && win.navigator && win.navigator.serviceWorker) || null;
  const isVisible = () => !doc || doc.visibilityState !== "hidden";

  function remember(tag) {
    shown.delete(tag);
    shown.add(tag);
    while (shown.size > SHOWN_LIMIT) shown.delete(shown.values().next().value);
    if (!storage) return;
    try {
      storage.setItem(SHOWN_STORAGE_KEY, JSON.stringify([...shown]));
    } catch (error) {
      console.warn("JustChess: shown notifications are kept for this page only", error && error.name);
    }
  }

  async function postJson(path, body) {
    try {
      const response = await fetchImpl(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!response.ok) console.warn(`JustChess: ${path.replace(/\/api\/rooms\/[A-Z0-9]{6}/, "/api/rooms/…")} answered ${response.status}`);
      return response.ok;
    } catch (error) {
      console.warn("JustChess: a notifications request could not reach the server", error && error.name);
      return false;
    }
  }

  async function fetchKey() {
    try {
      const response = await fetchImpl("/api/push/key", { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return null;
      const data = await response.json();
      return data && typeof data.publicKey === "string" && data.publicKey ? data.publicKey : null;
    } catch (error) {
      console.warn("JustChess: the push key could not be fetched; local notifications only", error && error.name);
      return null;
    }
  }

  async function registration() {
    const sw = workers();
    if (!sw) return null;
    return (await sw.getRegistration("/")) || sw.register(WORKER_URL, { scope: "/" });
  }

  async function subscribePush(reg, key) {
    const manager = reg && reg.pushManager;
    if (!manager) return null;
    const bytes = base64UrlToBytes(key);
    let current = await manager.getSubscription();
    if (current && !sameBytes(current.options && current.options.applicationServerKey, bytes)) {
      await current.unsubscribe(); // the server's key changed: subscribe again with the new one
      current = null;
    }
    return current || manager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes });
  }

  async function sendSubscription(subscription) {
    if (!seat || !subscription) return false;
    const json = typeof subscription.toJSON === "function" ? subscription.toJSON() : subscription;
    return postJson(`/api/rooms/${seat.code}/push/subscribe`, { token: seat.token, endpoint: json.endpoint, keys: json.keys });
  }

  /** Register the worker and, when the server has a key, subscribe for the current seat. */
  async function enable() {
    mode = "local";
    try {
      const reg = await registration();
      if (!reg) return mode;
      const key = await fetchKey();
      if (!key) return mode;
      const subscription = await subscribePush(reg, key);
      if (subscription && (await sendSubscription(subscription))) mode = "push";
    } catch (error) {
      console.warn("JustChess: push is unavailable here; local notifications only", error && error.name);
    }
    return mode;
  }

  async function disable() {
    mode = "off";
    try {
      const sw = workers();
      const reg = sw ? await sw.getRegistration("/") : null;
      const subscription = reg && reg.pushManager ? await reg.pushManager.getSubscription() : null;
      if (!subscription) return;
      const { endpoint } = subscription;
      await subscription.unsubscribe();
      if (seat && endpoint) await postJson(`/api/rooms/${seat.code}/push/unsubscribe`, { token: seat.token, endpoint });
    } catch (error) {
      console.warn("JustChess: the push subscription could not be removed", error && error.name);
    }
  }

  async function toggle(requested) {
    if (!requested) {
      await disable();
      return false;
    }
    if (!hasNotificationApi()) throw new Error(UNSUPPORTED);
    // Called synchronously, still inside the click (nothing has been awaited yet).
    const asked = win.Notification.requestPermission();
    const answer = (await Promise.resolve(asked)) || win.Notification.permission;
    if (answer !== "granted") {
      mode = "off";
      return false;
    }
    await enable();
    return true;
  }

  function hideBanner() {
    if (bannerTimer !== null) timers.clearTimeout(bannerTimer);
    bannerTimer = null;
    if (banner) banner.hidden = true;
  }

  function showBanner(text) {
    if (!banner) return;
    banner.textContent = text;
    banner.hidden = false;
    if (bannerTimer !== null) timers.clearTimeout(bannerTimer);
    bannerTimer = timers.setTimeout(hideBanner, BANNER_MS);
  }

  async function showLocal(event, code) {
    try {
      const sw = workers();
      const reg = sw ? (await sw.getRegistration("/")) || (await registration()) : null;
      if (!reg || typeof reg.showNotification !== "function") {
        console.warn("JustChess: no service worker to show a notification");
        return;
      }
      await reg.showNotification(event.title, {
        body: event.body,
        tag: event.tag,
        renotify: false,
        data: { url: `/r/${code}`, code },
      });
    } catch (error) {
      console.warn("JustChess: a local notification could not be shown", error && error.name);
    }
  }

  function onSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return "none";
    const prev = lastSnapshot && lastSnapshot.code === snapshot.code ? lastSnapshot : null;
    lastSnapshot = snapshot;
    const event = eventFor(prev, snapshot, snapshot.slot);
    if (!event) return "none";
    const action = decide({
      visible: isVisible(),
      permission: permission(),
      enabled: settings.get("notifications") === true,
      shownKeys: shown,
      key: event.tag,
    });
    if (action === "none") return action;
    remember(event.tag);
    if (action === "banner") showBanner(event.banner);
    else showLocal(event, snapshot.code);
    return action;
  }

  function setSeat(next) {
    const previous = seat;
    seat = next && next.code && next.token ? { code: next.code, token: next.token, slot: next.slot || null } : null;
    if (!seat || !lastSnapshot || lastSnapshot.code !== seat.code) lastSnapshot = null;
    const changed = seat && (!previous || previous.code !== seat.code || previous.token !== seat.token);
    if (changed && settings.get("notifications") === true && permission() === "granted") return enable();
    return Promise.resolve(mode);
  }

  function attachBanner(element) {
    hideBanner();
    banner = element || null;
    if (banner) {
      banner.hidden = true;
      if (typeof banner.addEventListener === "function") banner.addEventListener("click", hideBanner);
    }
  }

  function init() {
    if (settings.get("notifications") === true && permission() === "granted") {
      return registration().catch((error) => {
        console.warn("JustChess: the service worker could not be registered", error && error.name);
        return null;
      });
    }
    return Promise.resolve(null);
  }

  return {
    toggle,
    onSnapshot,
    setSeat,
    attachBanner,
    init,
    get mode() {
      return mode;
    },
  };
}
