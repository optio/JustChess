/**
 * The page's gameplay settings (P2 U4 tuning): from gameplay.yaml's `client` section, which the
 * server renders into the app shell as <script type="application/json" id="gameplay-config">.
 *
 *   loadFromDocument(doc)        read and apply the shell's settings once (app.js does this at start-up)
 *   readGameplay(raw) -> object  PURE: the settings from a parsed object, each bad or missing key
 *                                replaced by its built-in value (CLIENT_DEFAULTS)
 *   applyGameplay(raw)           make readGameplay(raw) the current settings
 *   clientGameplay()             the current settings (the built-in values until something is applied)
 *
 * Keys (all milliseconds or counts): captureAnimationMs (the capture shrink-and-fade; reduced motion
 * still turns it off), yourGamesRefreshMs (the lobby's "Your games" refresh), computerRetryLimit and
 * computerRetryDelayMs (the page's computer-move retries), joinPollMs (the joiner's request poll).
 * A missing or broken shell value never stops the page: the built-in values apply.
 */

export const CLIENT_DEFAULTS = Object.freeze({
  captureAnimationMs: 260,
  yourGamesRefreshMs: 60_000,
  computerRetryLimit: 3,
  computerRetryDelayMs: 5_000,
  joinPollMs: 3_000,
});

const RANGES = Object.freeze({
  captureAnimationMs: [0, 2_000],
  yourGamesRefreshMs: [10_000, 3_600_000],
  computerRetryLimit: [0, 20],
  computerRetryDelayMs: [1_000, 300_000],
  joinPollMs: [1_000, 60_000],
});

export const CONFIG_ELEMENT_ID = "gameplay-config";

let current = { ...CLIENT_DEFAULTS };

export function readGameplay(raw) {
  const settings = { ...CLIENT_DEFAULTS };
  if (!raw || typeof raw !== "object") return settings;
  for (const [key, [low, high]] of Object.entries(RANGES)) {
    const value = raw[key];
    if (Number.isInteger(value) && value >= low && value <= high) settings[key] = value;
  }
  return settings;
}

export function applyGameplay(raw) {
  current = readGameplay(raw);
  return current;
}

export function clientGameplay() {
  return current;
}

export function loadFromDocument(doc = globalThis.document) {
  const element = doc && typeof doc.getElementById === "function" ? doc.getElementById(CONFIG_ELEMENT_ID) : null;
  if (!element) return applyGameplay(null);
  try {
    return applyGameplay(JSON.parse(element.textContent || "null"));
  } catch (error) {
    console.warn("JustChess: the page's gameplay settings could not be read; using the built-in values", error && error.name);
    return applyGameplay(null);
  }
}
