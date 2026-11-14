/**
 * Trainer hub at /learn (P2 U5, W4, BR3.1-BR3.4).
 *
 *   const hub = mountHub(element, { api, progress?, registry?, storage?, initialTab?, onOpenLesson, onOpenTheme })
 *   hub.select(tabId)    show a tab (as if it was clicked)
 *   hub.destroy()        abort the loads and remove the DOM
 *
 *   api          a lessons-api.js client
 *   progress     a trainer-progress.js store (the "Done" marks and the counts)
 *   registry     a hub-tabs.js registry (default: the shared one, so U6 can add Endgames)
 *   storage      where the selected tab is remembered per device (default localStorage,
 *                every access in try/catch; without storage the first tab is used)
 *   onOpenLesson(id)     a lesson row's Learn button (the app opens /learn/<id>)
 *   onOpenTheme(theme)   a theme row's Solve button (the app opens /learn/tactics/<theme>)
 *
 * Tabs follow the ARIA tablist pattern: one tab in the tab order, Left/Right
 * move (wrapping), Home/End jump, and the selection follows focus. Each tab
 * reads "<label> <solved>/<total>". Lesson tabs load GET /api/lessons?kind=...;
 * the Tactics tab loads GET /api/puzzles, one row per theme
 * ("300 puzzles · 12 solved"), its total is the sum over the themes, and the
 * Lichess credit sits under its list (BR3.3). Every tab loads at start so all
 * counts are shown; a tab registered with its own load() (U6) is loaded the
 * same way.
 */

import { countLabel, nextTabIndex, sharedRegistry } from "./hub-tabs.js";
import { createLessonsApi } from "./lessons-api.js";
import { CREDIT, NOT_INSTALLED } from "./puzzle.js";
import { sideName } from "./trainer-state.js";

export const HUB_TITLE = "Train";
export const TAB_STORAGE_KEY = "justchess.trainer.tab";
export const LOADING_TEXT = "Loading…";
const LESSON_TABS = Object.freeze({ openings: "opening", traps: "trap", defence: "defence" });

function make(tag, attributes = {}, text) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "className") node.className = value;
    else node.setAttribute(name, value);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

function defaultStorage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

function readTab(storage) {
  try {
    return storage ? storage.getItem(TAB_STORAGE_KEY) : null;
  } catch {
    return null;
  }
}

function writeTab(storage, id) {
  try {
    if (storage) storage.setItem(TAB_STORAGE_KEY, id);
  } catch {
    // remembering the tab is a convenience; without storage the first tab opens next time
  }
}

function safeDone(progress, group, id) {
  try {
    return Boolean(progress) && progress.isDone(group, id);
  } catch {
    return false;
  }
}

function safeCount(progress, group, prefix) {
  try {
    return progress ? progress.countDone(group, prefix) : 0;
  } catch {
    return 0;
  }
}

/** Built-in loader for a lesson tab: rows with Learn, solved = lessons done on this device. */
function lessonLoader(tabId, kind) {
  return async ({ api, progress, signal, onOpenLesson }) => {
    const answer = await api.list({ signal, kind });
    if (!answer.ok) return { error: answer.message, aborted: answer.aborted, rows: [], solved: 0, total: 0 };
    const rows = answer.data.map((lesson) => ({
      id: lesson.id,
      title: lesson.name,
      subtitle: [lesson.eco, `${lesson.moves} ${lesson.moves === 1 ? "move" : "moves"}`, `as ${sideName(lesson.side)}`]
        .filter(Boolean).join(" · "),
      done: safeDone(progress, tabId, lesson.id),
      action: "Learn",
      onAction: () => onOpenLesson(lesson.id),
    }));
    return { rows, solved: rows.filter((row) => row.done).length, total: rows.length };
  };
}

/** Built-in loader for Tactics: one row per theme; the tab total is the sum of puzzles. */
async function tacticsLoader({ api, progress, signal, onOpenTheme }) {
  const answer = await api.themes({ signal });
  if (!answer.ok) return { error: answer.message, aborted: answer.aborted, rows: [], solved: 0, total: 0, credit: CREDIT };
  if (answer.data.length === 0) return { rows: [], solved: 0, total: 0, note: NOT_INSTALLED, credit: CREDIT };
  let solved = 0;
  let total = 0;
  const rows = answer.data.map((entry) => {
    const done = Math.min(safeCount(progress, "tactics", entry.theme), entry.count);
    solved += done;
    total += entry.count;
    return {
      id: entry.theme,
      title: entry.label,
      subtitle: `${entry.count} ${entry.count === 1 ? "puzzle" : "puzzles"} · ${done} solved`,
      done: entry.count > 0 && done >= entry.count,
      action: "Solve",
      disabled: entry.count === 0,
      onAction: () => onOpenTheme(entry.theme),
    };
  });
  return { rows, solved, total, credit: CREDIT };
}

function loaderFor(tab) {
  if (typeof tab.load === "function") return tab.load;
  if (LESSON_TABS[tab.id]) return lessonLoader(tab.id, LESSON_TABS[tab.id]);
  if (tab.id === "tactics") return tacticsLoader;
  return async () => ({ rows: [], solved: 0, total: 0, note: "Coming soon." });
}

export function mountHub(element, {
  api = createLessonsApi(),
  progress = null,
  registry = sharedRegistry,
  storage = defaultStorage(),
  initialTab = null,
  onOpenLesson = () => {},
  onOpenTheme = () => {},
} = {}) {
  if (!(element instanceof Element)) throw new TypeError("mountHub needs a container element");
  const tabs = registry.tabs();
  if (tabs.length === 0) throw new TypeError("the hub needs at least one tab");

  const root = make("section", { className: "hub", "aria-labelledby": "hub-title", "data-testid": "hub" });
  const title = make("h1", { className: "hub-title", id: "hub-title" }, HUB_TITLE);
  const tablist = make("div", { className: "hub-tabs", role: "tablist", "aria-label": "Training groups", "data-testid": "hub-tabs" });
  const panel = make("div", { className: "hub-panel", role: "tabpanel", id: "hub-panel", tabindex: "0", "data-testid": "hub-panel" });
  const summary = make("p", { className: "hub-summary t-muted", role: "status", "data-testid": "hub-summary" });
  const list = make("ul", { className: "hub-rows", "data-testid": "hub-rows" });
  const credit = make("p", { className: "hub-credit t-muted", "data-testid": "hub-credit" });
  panel.append(summary, list, credit);
  root.append(title, tablist, panel);
  element.append(root);

  const buttons = tabs.map((tab) => {
    const tabButton = make("button", {
      className: "hub-tab", type: "button", role: "tab", id: `hub-tab-${tab.id}`, "aria-controls": "hub-panel",
      "aria-selected": "false", tabindex: "-1", "data-tab": tab.id, "data-testid": `hub-tab-${tab.id}`,
    });
    tabButton.append(make("span", { className: "hub-tab-label" }, tab.label),
      make("span", { className: "hub-tab-count", "data-testid": `hub-count-${tab.id}` }, ""));
    tablist.append(tabButton);
    return tabButton;
  });

  let destroyed = false;
  const results = new Map();
  const controller = new AbortController();
  const wanted = initialTab || readTab(storage);
  let selected = Math.max(0, tabs.findIndex((tab) => tab.id === wanted));

  function renderRows(result) {
    list.replaceChildren(...result.rows.map((row) => {
      const item = make("li", { className: "hub-row", "data-testid": `hub-row-${row.id}` });
      const text = make("div", { className: "hub-row-text" });
      text.append(make("strong", { className: "hub-row-title" }, row.title));
      if (row.subtitle) text.append(make("span", { className: "hub-row-subtitle" }, row.subtitle));
      const done = make("span", { className: "hub-row-done", "data-testid": `hub-done-${row.id}` }, row.done ? "Done" : "");
      done.hidden = !row.done;
      const action = make("button", { className: "btn btn-secondary hub-row-action", type: "button", "data-testid": `hub-action-${row.id}` },
        row.action);
      action.setAttribute("aria-label", `${row.action} ${row.title}`);
      action.disabled = Boolean(row.disabled);
      action.addEventListener("click", () => row.onAction());
      item.append(text, done, action);
      return item;
    }));
  }

  function render() {
    tabs.forEach((tab, i) => {
      const isSelected = i === selected;
      buttons[i].setAttribute("aria-selected", String(isSelected));
      buttons[i].tabIndex = isSelected ? 0 : -1;
      const result = results.get(tab.id);
      buttons[i].querySelector(".hub-tab-count").textContent = result && !result.error ? countLabel(result.solved, result.total) : "";
    });
    const tab = tabs[selected];
    panel.setAttribute("aria-labelledby", buttons[selected].id);
    root.dataset.tab = tab.id;
    const result = results.get(tab.id);
    if (!result) {
      summary.textContent = LOADING_TEXT;
      list.replaceChildren();
      credit.textContent = "";
      return;
    }
    if (result.error) summary.textContent = result.error;
    else if (result.note) summary.textContent = result.note;
    else summary.textContent = `${result.solved} of ${result.total} done on this device`;
    renderRows(result);
    credit.textContent = result.credit || "";
    credit.hidden = !result.credit;
  }

  function select(index, { focus = false } = {}) {
    if (index < 0 || index >= tabs.length) return;
    selected = index;
    writeTab(storage, tabs[index].id);
    render();
    if (focus) buttons[index].focus();
  }

  async function load(tab) {
    try {
      const result = await loaderFor(tab)({ api, progress, signal: controller.signal, onOpenLesson, onOpenTheme });
      if (destroyed || (result && result.aborted)) return;
      results.set(tab.id, result || { rows: [], solved: 0, total: 0 });
    } catch (error) {
      if (destroyed) return;
      console.error(`JustChess hub: the ${tab.id} tab could not be loaded`, error);
      results.set(tab.id, { error: "This list could not be loaded. Try again.", rows: [], solved: 0, total: 0 });
    }
    render();
  }

  buttons.forEach((tabButton, i) => tabButton.addEventListener("click", () => select(i)));
  tablist.addEventListener("keydown", (event) => {
    const next = nextTabIndex(selected, event.key, tabs.length);
    if (next === null) return;
    event.preventDefault();
    select(next, { focus: true });
  });

  render();
  for (const tab of tabs) load(tab);

  return {
    select(id) {
      const index = tabs.findIndex((tab) => tab.id === id);
      if (index >= 0) select(index);
    },
    get selectedTab() {
      return tabs[selected].id;
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      controller.abort();
      root.remove();
    },
  };
}
