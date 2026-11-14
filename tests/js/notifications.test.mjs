// Tests for static/js/notifications.js (U5: BR3.1 toggle flow, BR3.2 page alerts, BR3.4 turning off).
// Notification, serviceWorker, pushManager and fetch are fakes; nothing touches a real browser or network.
import { test } from "node:test";
import assert from "node:assert/strict";

import { createSettings, decideNotifications, NOTIFICATIONS_BLOCKED } from "../../static/js/settings.js";
import { SHOWN_STORAGE_KEY, UNSUPPORTED, createNotifications } from "../../static/js/notifications.js";

const KEY = "BPxkXNx5jXuW_TPs4-MAEFQYQH6pweJz6fv7IRuu_T3u2KGtWZuCYlVK78D-yLGLxUQPSKhjrJ4KlW6wz1tMwIw";
const SEAT = { code: "ROOM01", token: "seat-token-aaaaaaaaaaaaaaaa", slot: "B" };

function memoryStorage() {
  const data = new Map();
  return { data, getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), removeItem: (k) => data.delete(k) };
}

function fakeBrowser({ answer = "granted", pushKey = KEY, permission = "default" } = {}) {
  const calls = { requested: 0, registered: [], subscribed: [], unsubscribed: 0, shown: [], fetches: [] };
  class FakeNotification {
    static permission = permission;
    static requestPermission() {
      calls.requested += 1;
      FakeNotification.permission = answer;
      return Promise.resolve(answer);
    }
  }
  let current = null;
  const pushManager = {
    getSubscription: async () => current,
    subscribe: async (options) => {
      calls.subscribed.push(options);
      current = {
        endpoint: `https://fcm.googleapis.com/fcm/send/browser-${calls.subscribed.length}`,
        options: { applicationServerKey: options.applicationServerKey.buffer },
        toJSON() { return { endpoint: this.endpoint, keys: { p256dh: "p256dh-value", auth: "auth-value" } }; },
        unsubscribe: async () => { calls.unsubscribed += 1; current = null; return true; },
      };
      return current;
    },
  };
  let registration = null;
  const reg = { pushManager, showNotification: async (title, options) => { calls.shown.push({ title, options }); } };
  const serviceWorker = {
    getRegistration: async () => registration,
    register: async (url, options) => { calls.registered.push({ url, options }); registration = reg; return reg; },
  };
  async function fetchImpl(url, init = {}) {
    calls.fetches.push({ url, method: init.method || "GET", body: init.body ? JSON.parse(init.body) : null });
    if (url === "/api/push/key") {
      return pushKey ? { ok: true, status: 200, json: async () => ({ enabled: true, publicKey: pushKey }) }
        : { ok: false, status: 404, json: async () => ({ enabled: false }) };
    }
    return { ok: true, status: 200, json: async () => ({ ok: true }) };
  }
  const win = { Notification: FakeNotification, navigator: { serviceWorker } };
  return { win, calls, fetchImpl, posts: () => calls.fetches.filter((f) => f.method === "POST") };
}

function setup(options = {}, { notificationsOn = false, visible = true } = {}) {
  const browser = fakeBrowser(options);
  const settings = createSettings(memoryStorage(), { events: null });
  if (notificationsOn) settings.set("notifications", true);
  const doc = { visibilityState: visible ? "visible" : "hidden" };
  const storage = memoryStorage();
  const timers = { setTimeout: () => 1, clearTimeout: () => {} };
  const notify = createNotifications({ win: browser.win, doc, settings, fetchImpl: browser.fetchImpl, storage, timers });
  return { ...browser, settings, doc, storage, notify };
}

test("turning on: permission is asked inside the click, push subscribes and posts the seat's subscription", async () => {
  const { notify, calls, posts } = setup();
  await notify.setSeat(SEAT);
  const pending = notify.toggle(true);
  assert.equal(calls.requested, 1, "requestPermission ran synchronously, before any await");
  assert.equal(await pending, true);
  assert.equal(notify.mode, "push");
  assert.deepEqual(calls.registered, [{ url: "/sw.js", options: { scope: "/" } }]);
  assert.equal(calls.subscribed[0].userVisibleOnly, true);
  assert.equal(calls.subscribed[0].applicationServerKey.length, 65);
  assert.deepEqual(posts(), [{ url: "/api/rooms/ROOM01/push/subscribe", method: "POST",
    body: { token: SEAT.token, endpoint: "https://fcm.googleapis.com/fcm/send/browser-1", keys: { p256dh: "p256dh-value", auth: "auth-value" } } }]);
});

test("granted with push disabled on the server: local-only mode, still true", async () => {
  const { notify, calls, posts } = setup({ pushKey: null });
  await notify.setSeat(SEAT);
  assert.equal(await notify.toggle(true), true);
  assert.equal(notify.mode, "local");
  assert.equal(calls.registered.length, 1, "the worker is still registered for local notifications");
  assert.equal(calls.subscribed.length, 0);
  assert.deepEqual(posts(), []);
});

test("denied: false, and the panel says notifications are blocked; no Notification API rejects with a message", async () => {
  const { notify, calls } = setup({ answer: "denied" });
  assert.deepEqual(await decideNotifications(true, notify.toggle), { value: false, notice: NOTIFICATIONS_BLOCKED });
  assert.equal(calls.registered.length, 0);

  const bare = createNotifications({ win: {}, doc: null, settings: createSettings(memoryStorage(), { events: null }),
    fetchImpl: async () => ({ ok: false }) });
  await assert.rejects(bare.toggle(true), { message: UNSUPPORTED });
  assert.deepEqual(await decideNotifications(true, bare.toggle), { value: false, notice: UNSUPPORTED });
});

test("turning off unsubscribes the browser and always posts the endpoint", async () => {
  const { notify, calls, posts } = setup();
  await notify.setSeat(SEAT);
  await notify.toggle(true);
  assert.equal(await notify.toggle(false), false);
  assert.equal(calls.unsubscribed, 1);
  assert.equal(notify.mode, "off");
  assert.deepEqual(posts().at(-1), { url: "/api/rooms/ROOM01/push/unsubscribe", method: "POST",
    body: { token: SEAT.token, endpoint: "https://fcm.googleapis.com/fcm/send/browser-1" } });
});

test("joining another room re-subscribes for that seat when notifications are on", async () => {
  const { notify, posts } = setup({ permission: "granted" }, { notificationsOn: true });
  await notify.setSeat(SEAT);
  await notify.setSeat({ code: "ROOM02", token: "other-seat-token-bbbbbbbbbbbb", slot: "A" });
  await notify.setSeat({ code: "ROOM02", token: "other-seat-token-bbbbbbbbbbbb", slot: "A" }); // unchanged: nothing new
  assert.deepEqual(posts().map((p) => [p.url, p.body.token]), [
    ["/api/rooms/ROOM01/push/subscribe", SEAT.token],
    ["/api/rooms/ROOM02/push/subscribe", "other-seat-token-bbbbbbbbbbbb"],
  ]);
  const off = setup({ permission: "granted" });
  await off.notify.setSeat(SEAT);
  assert.deepEqual(off.posts(), [], "with the setting off, nothing is subscribed");
});

function snapshots() {
  const seats = { A: { presence: "connected", colour: "white" }, B: { presence: "connected", colour: "black" } };
  const base = { code: "ROOM01", game: 1, status: "playing", endReason: null, result: null, seats, slot: "B" };
  return [
    { ...base, turn: "white", moveList: [] },
    { ...base, turn: "black", moveList: [{ number: 1, white: "e4", black: null }] },
  ];
}

test("a hidden page shows a local notification with the room tag, once; a visible page shows the banner", async () => {
  const hidden = setup({ permission: "granted" }, { notificationsOn: true, visible: false });
  await hidden.notify.init();
  const [before, after] = snapshots();
  assert.equal(hidden.notify.onSnapshot(before), "none");
  assert.equal(hidden.notify.onSnapshot(after), "local");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(hidden.calls.shown.length, 1);
  assert.deepEqual(hidden.calls.shown[0].options, { body: "Your opponent played e4.", tag: "ROOM01:move:1:1",
    renotify: false, data: { url: "/r/ROOM01", code: "ROOM01" } });
  hidden.notify.onSnapshot(before);
  assert.equal(hidden.notify.onSnapshot(after), "none", "a key already shown is never shown again");
  assert.deepEqual(JSON.parse(hidden.storage.getItem(SHOWN_STORAGE_KEY)), ["ROOM01:move:1:1"]);

  const visible = setup({}, { visible: true });
  const banner = { textContent: "", hidden: true, addEventListener() {} };
  visible.notify.attachBanner(banner);
  visible.notify.onSnapshot(before);
  assert.equal(visible.notify.onSnapshot(after), "banner");
  assert.deepEqual([banner.textContent, banner.hidden], ["Your move", false]);
  assert.equal(visible.calls.shown.length, 0);
});
