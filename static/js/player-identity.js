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
  let initialized = false;

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
      try {
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
      } finally {
        initialized = true;
        onChange();
      }
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
    get initialized() { return initialized; },
    get nicknameValue() { return profile?.nickname || ""; },
    get error() { return error; },
    get persistent() { return persistent; },
    link(origin) { return saved.recovery ? `${origin}/#player=${saved.recovery}` : ""; },
  };
}

/** Small explicit editor state: profile refreshes cannot erase a draft. */
export function createNicknameEditor({ getName, save, onChange = () => {} }) {
  let draft = getName(), editing = !draft, touched = false, pending = false;
  function sync() {
    if (!touched && !pending) { draft = getName(); editing = !draft; }
  }
  return {
    sync,
    begin() { draft = getName(); editing = true; touched = true; onChange(); },
    change(value) { draft = value; editing = true; touched = true; },
    async submit() {
      if (pending) return null;
      pending = true; onChange();
      let answer;
      try { answer = await save(draft); }
      catch { answer = { ok: false, message: "Could not save your nickname. Try again." }; }
      pending = false;
      if (answer.ok) { touched = false; sync(); }
      onChange();
      return answer;
    },
    get state() { return { draft, editing, pending }; },
  };
}

function footerDialog(dialog, { canClose = () => true } = {}) {
  const doc = dialog.ownerDocument;
  let trigger = null;
  function returnFocus() { if (trigger?.isConnected) trigger.focus({ preventScroll: true }); }
  function close() {
    if (canClose() && dialog.open) { dialog.close(); returnFocus(); }
  }
  dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
  dialog.addEventListener("click", event => { if (event.target === dialog) close(); });
  dialog.addEventListener("close", returnFocus);
  dialog.addEventListener("keydown", event => {
    if (event.key !== "Tab") return;
    const items = [...dialog.querySelectorAll("a[href], button:not([disabled]), input:not([disabled])")]
      .filter(item => !item.closest("[hidden]"));
    const first = items[0], last = items.at(-1);
    if (!first) return;
    if (event.shiftKey && doc.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && doc.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  return {
    open(from, focus) {
      trigger = from;
      if (!dialog.open) dialog.showModal();
      focus?.focus({ preventScroll: true });
    },
    close,
  };
}

export function mountPlayerFooter(doc, win, player) {
  const root = doc.getElementById("player-footer");
  if (!root) return { render() {} };
  const part = id => doc.querySelector(`[data-testid="${id}"]`);
  const name = part("player-nickname"), display = part("player-display"), field = part("player-editor");
  const loading = part("player-loading"), nameForm = root.querySelector("form");
  const save = part("player-save"), edit = part("player-edit"), message = part("player-message");
  const copy = part("player-copy"), regenerate = part("player-regenerate"), help = part("player-help");
  const link = part("player-link"), linkField = part("player-link-field");
  const helpMessage = part("player-help-message"), helpClose = part("player-help-close");
  const regenerateElement = part("player-regenerate-dialog"), confirm = part("player-regenerate-confirm");
  const cancel = part("player-regenerate-cancel"), regenerateMessage = part("player-regenerate-message");
  let feedback = "", copying = false, regenerating = false;
  const editor = createNicknameEditor({ getName: () => player.nicknameValue, save: value => player.nickname(value), onChange: render });
  const helpDialog = footerDialog(part("player-help-dialog"));
  const regenerateDialog = footerDialog(regenerateElement, { canClose: () => !regenerating });

  function render() {
    const isLoading = !player.initialized;
    root.hidden = isLoading;
    loading.hidden = !isLoading;
    if (isLoading) return;

    editor.sync();
    const state = editor.state;
    field.hidden = !state.editing;
    display.hidden = state.editing;
    if (name.value !== state.draft) name.value = state.draft;
    part("player-name").textContent = player.nicknameValue;
    name.disabled = state.pending;
    save.disabled = state.pending;
    edit.disabled = state.pending;
    save.setAttribute("aria-label", state.pending ? "Saving nickname" : "Save nickname");
    nameForm.setAttribute("aria-busy", String(isLoading || state.pending));
    const url = player.link(win.location.origin);
    link.href = url || "#";
    link.hidden = !url;
    linkField.value = url;
    linkField.disabled = !url;
    copy.disabled = copying || !url;
    regenerate.disabled = regenerating || !player.token;
    message.textContent = feedback || player.error || (!player.persistent ? "Storage is blocked. Copy your private player link to keep this player." : "");
  }

  edit.addEventListener("click", () => { feedback = ""; editor.begin(); name.focus(); name.select(); });
  name.addEventListener("input", () => { editor.change(name.value); feedback = ""; });
  root.querySelector("form").addEventListener("submit", async event => {
    event.preventDefault();
    if (editor.state.pending) return;
    editor.change(name.value); feedback = "";
    const answer = await editor.submit();
    if (answer) feedback = answer.ok ? "Nickname saved" : answer.message;
    render();
  });
  help.addEventListener("click", () => { helpMessage.textContent = ""; render(); helpDialog.open(help, helpClose); });
  helpClose.addEventListener("click", () => helpDialog.close());
  copy.addEventListener("click", async () => {
    if (copying) return;
    const url = player.link(win.location.origin);
    if (!url) { feedback = "Your private link is not ready. Reload to try again."; render(); return; }
    copying = true; feedback = ""; render();
    try {
      await win.navigator.clipboard.writeText(url);
      feedback = "Player link copied. Keep it private.";
    } catch {
      helpMessage.textContent = "Clipboard unavailable. Copy the selected private link, or bookmark the link below.";
      helpDialog.open(copy, linkField);
      linkField.select();
      feedback = "Copy or bookmark your private link in the dialog.";
    } finally { copying = false; render(); }
  });
  regenerate.addEventListener("click", () => {
    if (regenerating) return;
    regenerateMessage.textContent = "";
    regenerateDialog.open(regenerate, cancel);
  });
  cancel.addEventListener("click", () => regenerateDialog.close());
  confirm.addEventListener("click", async () => {
    if (regenerating) return;
    regenerating = true;
    confirm.disabled = true; cancel.disabled = true;
    confirm.textContent = "Generating…";
    regenerateElement.setAttribute("aria-busy", "true");
    regenerateMessage.textContent = "";
    render();
    let answer;
    try { answer = await player.regenerate(); }
    catch { answer = { ok: false, message: "Could not replace your player link. Try again." }; }
    regenerating = false;
    confirm.disabled = false; cancel.disabled = false;
    confirm.textContent = "Generate new link";
    regenerateElement.setAttribute("aria-busy", "false");
    if (answer.ok) {
      feedback = "New player link ready. Update your bookmarks.";
      render();
      regenerateDialog.close();
    } else { regenerateMessage.textContent = answer.message; render(); }
  });
  win.addEventListener("focus", () => player.refresh());
  return { render };
}
