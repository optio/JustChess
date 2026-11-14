/**
 * JustChess settings panel (U2): the controls for the settings store.
 *
 *   renderSettingsPanel(container, store, hooks = {}) -> { destroy }
 *
 * Radio groups for theme, board and coordinates; switches for blunder
 * warnings and notifications; the credit "Pieces: cburnett, CC BY-SA 3.0";
 * and "Settings won't be kept after you close this tab." whenever the store
 * is not persistent (BR6.2). Every control is a native input with a visible
 * label and a 44 px target. Requires base.css.
 *
 * hooks.onNotificationsToggle(value) -> Promise<boolean> lets U5 run the
 *   permission prompt. The switch is disabled while it runs; the stored value
 *   is the resolved boolean. false or a rejection when turning on reverts the
 *   switch, stores false and shows "Notifications are blocked in this browser"
 *   (or the error's message). With no hook the value is stored directly.
 * hooks.extraRows: a Node, or an array of Nodes, appended in a slot after the
 *   switches (U3's "Get a private continue link" row).
 */

import { NOT_PERSISTENT_NOTICE, decideNotifications } from "./settings.js";

const RADIO_GROUPS = [
  { key: "theme", legend: "Theme", options: [["device", "Device"], ["light", "Light"], ["dark", "Dark"]] },
  { key: "board", legend: "Board", options: [["walnut-maple", "Walnut and maple"], ["tournament", "Tournament green"], ["rosewood", "Rosewood"]] },
  { key: "labels", legend: "Coordinates", options: [["inside", "On squares"], ["frame", "In the frame"]] },
];

const SWITCHES = [
  { key: "blunderWarnings", label: "Warn me before blunders" },
  { key: "notifications", label: "Notifications" },
];

const CREDIT = "Pieces: cburnett, CC BY-SA 3.0";

let panelCount = 0;

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function radioGroup(group, prefix, store) {
  const fieldset = make("fieldset");
  fieldset.setAttribute("data-testid", `settings-${group.key}`);
  fieldset.append(make("legend", "", group.legend));
  const options = make("div", "settings-options");
  for (const [value, text] of group.options) {
    const label = make("label", "settings-choice");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = `${prefix}-${group.key}`;
    input.value = value;
    input.checked = store.get(group.key) === value;
    input.setAttribute("data-testid", `settings-${group.key}-${value}`);
    label.append(input, make("span", "", text));
    options.append(label);
  }
  fieldset.append(options);
  return fieldset;
}

function switchRow(item, store) {
  const label = make("label", "settings-switch");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.setAttribute("role", "switch");
  input.dataset.key = item.key;
  input.checked = store.get(item.key) === true;
  input.setAttribute("data-testid", `settings-${item.key}`);
  label.append(make("span", "", item.label), input);
  return label;
}

function appendExtraRows(slot, extraRows) {
  if (!extraRows) return;
  const rows = Array.isArray(extraRows) ? extraRows : [extraRows];
  for (const row of rows) {
    if (!(row instanceof Node)) throw new TypeError("hooks.extraRows must be a Node or an array of Nodes");
    slot.append(row);
  }
}

export function renderSettingsPanel(container, store, hooks = {}) {
  if (!(container instanceof Element)) throw new TypeError("renderSettingsPanel needs a container element");
  if (!store || typeof store.get !== "function" || typeof store.subscribe !== "function") {
    throw new TypeError("renderSettingsPanel needs a settings store");
  }
  panelCount += 1;
  const prefix = `settings-${panelCount}`;
  const root = make("form", "settings");
  root.setAttribute("aria-label", "Game settings");
  root.setAttribute("data-testid", "settings-panel");
  root.addEventListener("submit", (event) => event.preventDefault());

  const notice = make("p", "settings-notice");
  notice.setAttribute("role", "status");
  notice.setAttribute("data-testid", "settings-not-persistent");
  const alert = make("p", "settings-alert");
  alert.setAttribute("role", "status");
  alert.setAttribute("data-testid", "settings-alert");
  const extra = make("div", "settings-extra");
  appendExtraRows(extra, hooks.extraRows);

  root.append(notice, ...RADIO_GROUPS.map((group) => radioGroup(group, prefix, store)));
  root.append(...SWITCHES.map((item) => switchRow(item, store)), alert, extra, make("p", "settings-credit", CREDIT));
  container.append(root);

  function showPersistence() {
    notice.textContent = store.persistent ? "" : NOT_PERSISTENT_NOTICE;
  }

  function sync() {
    for (const input of root.querySelectorAll("input[type=radio]")) {
      input.checked = store.get(input.name.slice(prefix.length + 1)) === input.value;
    }
    for (const input of root.querySelectorAll("input[role=switch]")) {
      if (!input.disabled) input.checked = store.get(input.dataset.key) === true;
    }
    showPersistence();
  }

  function apply(key, value) {
    try {
      store.set(key, value);
    } catch (error) {
      console.error(`JustChess settings: could not set ${key}`, error);
    }
    sync();
  }

  async function toggleNotifications(input) {
    const requested = input.checked;
    input.disabled = true;
    alert.textContent = "";
    try {
      const { value, notice: message } = await decideNotifications(requested, hooks.onNotificationsToggle);
      apply("notifications", value);
      input.checked = value;
      alert.textContent = message || "";
    } finally {
      input.disabled = false;
    }
  }

  function onChange(event) {
    const input = event.target;
    if (input.type === "radio") apply(input.name.slice(prefix.length + 1), input.value);
    else if (input.dataset.key === "notifications") toggleNotifications(input);
    else if (input.dataset.key) apply(input.dataset.key, input.checked);
  }

  root.addEventListener("change", onChange);
  const unsubscribe = store.subscribe(sync);
  showPersistence();

  return {
    element: root,
    destroy() {
      unsubscribe();
      root.removeEventListener("change", onChange);
      root.remove();
    },
  };
}
