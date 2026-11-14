/**
 * Trainer hub tab registry and ARIA tablist keyboard logic (P2 U5, BR3.1).
 * PURE: no DOM, so it runs in Node tests.
 *
 *   const registry = createTabRegistry(defaults = DEFAULT_TABS)
 *   registry.registerTab({ id, label, order, load? })   add a tab (U6 adds "endgames")
 *   registry.tabs()                                    tabs sorted by order
 *   registerTab(tab) / listTabs()                      the shared registry the hub uses
 *   nextTabIndex(current, key, count) -> index | null  Left/Right wrap, Home/End jump
 *   countLabel(solved, total)       -> "2/10"
 *
 * A tab's id is one of TAB_IDS. ``load`` is optional: the hub has built-in
 * loaders for openings, traps, tactics and defence; a tab added later (U6
 * Endgames) brings its own ``load(context) -> Promise<{rows, solved, total, note?}>``.
 */

export const TAB_IDS = Object.freeze(["openings", "traps", "endgames", "tactics", "defence"]);

export const DEFAULT_TABS = Object.freeze([
  Object.freeze({ id: "openings", label: "Openings", order: 10 }),
  Object.freeze({ id: "traps", label: "Traps", order: 20 }),
  Object.freeze({ id: "tactics", label: "Tactics", order: 40 }),
  Object.freeze({ id: "defence", label: "Defence", order: 50 }),
]);

function checkTab(tab) {
  if (!tab || typeof tab !== "object") throw new TypeError("a tab must be an object");
  if (!TAB_IDS.includes(tab.id)) throw new TypeError(`unknown tab id ${JSON.stringify(tab.id)}`);
  if (typeof tab.label !== "string" || !tab.label.trim()) throw new TypeError("a tab needs a label");
  if (!Number.isFinite(tab.order)) throw new TypeError("a tab needs a numeric order");
  if (tab.load !== undefined && typeof tab.load !== "function") throw new TypeError("load must be a function");
}

export function createTabRegistry(defaults = DEFAULT_TABS) {
  const entries = new Map();

  function registerTab(tab) {
    checkTab(tab);
    if (entries.has(tab.id)) throw new TypeError(`tab ${JSON.stringify(tab.id)} is already registered`);
    entries.set(tab.id, Object.freeze({ ...tab }));
  }

  for (const tab of defaults) registerTab(tab);

  return {
    registerTab,
    tabs() {
      return [...entries.values()].sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
    },
    has(id) {
      return entries.has(id);
    },
  };
}

const shared = createTabRegistry();

/** Register a tab in the shared registry used by the /learn hub (U6: Endgames). */
export function registerTab(tab) {
  shared.registerTab(tab);
}

export function listTabs() {
  return shared.tabs();
}

export const sharedRegistry = shared;

/** ARIA tablist keys: the new selected index, or null for any other key. */
export function nextTabIndex(current, key, count) {
  if (!Number.isInteger(count) || count < 1) return null;
  const index = Number.isInteger(current) && current >= 0 && current < count ? current : 0;
  switch (key) {
    case "ArrowRight": return (index + 1) % count;
    case "ArrowLeft": return (index - 1 + count) % count;
    case "Home": return 0;
    case "End": return count - 1;
    default: return null;
  }
}

export function countLabel(solved, total) {
  const safeTotal = Number.isInteger(total) && total > 0 ? total : 0;
  const safeSolved = Number.isInteger(solved) && solved > 0 ? Math.min(solved, safeTotal) : 0;
  return `${safeSolved}/${safeTotal}`;
}
