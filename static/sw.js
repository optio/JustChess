/*
 * JustChess service worker (U5, BR3.3). Served at /sw.js by the app with
 * Service-Worker-Allowed: / and Cache-Control: no-cache. It caches nothing.
 *
 * push: the payload { title, body, tag, url, code } is checked, then the
 *   notification is shown with tag "<code>:<key>" and renotify false, so a
 *   repeat (push and a local notification for the same event) replaces rather
 *   than stacks. It is always shown, also when a visible page for the room
 *   exists (a rare race: it is shown quietly then), so the browser never shows
 *   its generic "updated in the background" notice. An unreadable payload
 *   still shows a plain JustChess notification for the same reason.
 * notificationclick: focus the room's page when one is open, else open /r/<code>
 *   on this origin. A URL from the payload is never opened.
 *
 * This is a classic worker (module workers are not supported everywhere), so
 * it cannot import static/js/notify-core.js. The block between the "shared
 * with sw.js" markers is a copy of that module's block, without "export";
 * tests/js/notify-core.test.mjs fails when the two differ.
 */
"use strict";

// --- shared with sw.js (keep identical; tests/js/notify-core.test.mjs compares them) ---
function roomPath(code) {
  return typeof code === "string" && /^[A-Z0-9]{6}$/.test(code) ? `/r/${code}` : null;
}

function notificationFromPush(payload) {
  if (!payload || typeof payload !== "object") return null;
  const path = roomPath(payload.code);
  if (!path || typeof payload.title !== "string" || typeof payload.tag !== "string") return null;
  if (!payload.tag.startsWith(`${payload.code}:`)) return null;
  const url = path; // always the room page on this origin, never a URL taken from the payload
  return {
    code: payload.code,
    title: payload.title.slice(0, 60),
    options: {
      body: typeof payload.body === "string" ? payload.body.slice(0, 140) : "",
      tag: payload.tag,
      renotify: false,
      data: { url, code: payload.code },
    },
  };
}

function swDecision({ clients, code, origin }) {
  const path = roomPath(code);
  const visiblePage = (clients || []).some((client) => {
    if (!client || client.visibilityState !== "visible" || typeof client.url !== "string") return false;
    try {
      const url = new URL(client.url);
      return url.origin === origin && url.pathname === path;
    } catch {
      return false;
    }
  });
  // Always show (never trigger the browser's generic "updated in the background" notice);
  // when the room's page is visible it is a rare race, so show it quietly.
  return { show: true, silent: visiblePage };
}
// --- end shared with sw.js ---

const FALLBACK = { title: "JustChess", options: { body: "Something happened in your game.", tag: "justchess", renotify: false, data: { url: "/" } } };

function readPayload(event) {
  try {
    return event.data ? event.data.json() : null;
  } catch (error) {
    console.warn("JustChess worker: a push payload could not be read", error && error.name);
    return null;
  }
}

async function windows() {
  return self.clients.matchAll({ type: "window", includeUncontrolled: true });
}

async function handlePush(event) {
  const note = notificationFromPush(readPayload(event));
  if (!note) {
    await self.registration.showNotification(FALLBACK.title, FALLBACK.options);
    return;
  }
  const open = await windows();
  const decision = swDecision({
    clients: open.map((client) => ({ url: client.url, visibilityState: client.visibilityState })),
    code: note.code,
    origin: self.location.origin,
  });
  if (!decision.show) return;
  await self.registration.showNotification(note.title, { ...note.options, silent: decision.silent });
}

function clickPath(data) {
  if (!data) return "/";
  if (roomPath(data.code)) return roomPath(data.code);
  // a room path only (never another origin or page)
  return typeof data.url === "string" && /^\/r\/[A-Z0-9]{6}$/.test(data.url) ? data.url : "/";
}

async function focusOrOpen(data) {
  const path = clickPath(data);
  const target = new URL(path, self.location.origin);
  for (const client of await windows()) {
    try {
      if (new URL(client.url).pathname === target.pathname && typeof client.focus === "function") return client.focus();
    } catch {
      /* a client with an unreadable URL is skipped */
    }
  }
  return self.clients.openWindow(target.href);
}

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  event.waitUntil(handlePush(event));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(focusOrOpen(event.notification.data));
});
