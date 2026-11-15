/** Private anonymous player credentials. Recovery travels in fragments/body only. */
import { safeStorage } from "./seat-store.js";

export const PLAYER_KEY = "justchess.player.v1";
const TOKEN = /^[A-Za-z0-9_-]{43}$/;

export function recoveryFragment(hash) {
  const match = /^#player=([A-Za-z0-9_-]{43})$/.exec(hash || "");
  return match ? match[1] : null;
}

export function createPlayerIdentity({ fetchImpl = (...args) => globalThis.fetch(...args), storage = safeStorage(), seats, onChange = () => {} } = {}) {
  let saved = {}, persistent = Boolean(storage), error = "";
  try { saved = JSON.parse(storage?.getItem(PLAYER_KEY) || "{}"); } catch { saved = {}; }
  if (!saved || !TOKEN.test(saved.token || "")) saved = {};
  let profile = null;

  function keep(value) {
    saved = value;
    try { if (storage) storage.setItem(PLAYER_KEY, JSON.stringify(saved)); }
    catch { persistent = false; }
  }

  async function call(action, body = {}, token = saved.token) {
    try {
      const response = await fetchImpl(`/api/player/${action}`, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", ...(token ? { "X-Player-Token": token } : {}) },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      return response.ok ? { ok: true, data } : { ok: false, message: data.detail || "Could not save your player." };
    } catch { return { ok: false, message: "Could not reach the server. Your current player has been kept." }; }
  }

  function apply(data, replace = false) {
    profile = data;
    if (replace) for (const seat of seats?.validSeats() || []) seats.remove(seat.code);
    for (const seat of data.seats || []) seats?.set(seat.code, seat);
    onChange();
  }

  async function attach(code, token) {
    if (!saved.token || !code || !token) return;
    const answer = await call("seats", { code, token });
    if (answer.ok) apply(answer.data);
  }

  return {
    async init(recovery) {
      if (recovery) {
        const answer = await call("restore", { recovery });
        if (answer.ok) {
          keep({ token: answer.data.token, recovery });
          apply(answer.data, true);
          return;
        }
        error = answer.message;
      }
      let answer = saved.token ? await call("profile") : null;
      if (answer && !answer.ok && !answer.message.includes("session is invalid")) {
        error ||= answer.message; onChange(); return;
      }
      if (!answer?.ok) {
        answer = await call("create");
        if (answer.ok) keep({ token: answer.data.token, recovery: answer.data.recovery });
      }
      if (answer.ok) {
        apply(answer.data);
        for (const seat of seats?.validSeats() || []) await attach(seat.code, seat.token);
      } else error ||= answer.message;
      onChange();
    },
    attach,
    async refresh() { const answer = await call("profile"); if (answer.ok) apply(answer.data); },
    async nickname(value) {
      const answer = await call("nickname", { nickname: value });
      if (answer.ok) { error = ""; apply(answer.data); }
      return answer;
    },
    async regenerate() {
      const answer = await call("regenerate");
      if (answer.ok) { keep({ ...saved, recovery: answer.data.recovery }); onChange(); }
      return answer;
    },
    get token() { return saved.token || null; },
    get nicknameValue() { return profile?.nickname || ""; },
    get error() { return error; },
    get persistent() { return persistent; },
    link(origin) { return saved.recovery ? `${origin}/#player=${saved.recovery}` : ""; },
  };
}

export function mountPlayerFooter(doc, win, player) {
  const root = doc.getElementById("player-footer");
  if (!root) return { render() {} };
  const name = root.querySelector("[data-testid=player-nickname]");
  const link = root.querySelector("[data-testid=player-link]");
  const message = root.querySelector("[data-testid=player-message]");
  function render() {
    if (doc.activeElement !== name) name.value = player.nicknameValue;
    const url = player.link(win.location.origin);
    link.href = url || "#";
    link.hidden = !url;
    message.textContent = player.error || (!player.persistent ? "Storage is blocked. Save your private link to keep this player." : "");
  }
  root.querySelector("form").addEventListener("submit", async event => {
    event.preventDefault();
    const answer = await player.nickname(name.value);
    message.textContent = answer.ok ? "Nickname saved" : answer.message;
  });
  root.querySelector("[data-testid=player-copy]").addEventListener("click", async () => {
    const url = player.link(win.location.origin);
    if (!url) { message.textContent = "Your private link is not ready. Reload to try again."; return; }
    try { await win.navigator.clipboard.writeText(url); message.textContent = "Private player link copied"; }
    catch { message.textContent = "Copy or bookmark the Save my player link."; link.focus(); }
  });
  root.querySelector("[data-testid=player-regenerate]").addEventListener("click", async () => {
    if (!win.confirm("Replace your private link? Existing bookmarks will stop working. Your signed-in devices will stay connected.")) return;
    const answer = await player.regenerate();
    message.textContent = answer.ok ? "New private link ready. Update your bookmarks." : answer.message;
  });
  win.addEventListener("focus", () => player.refresh());
  return { render };
}
