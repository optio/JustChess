// Tests for static/js/gameplay.js: the page's gameplay settings from the shell, with built-in fallbacks.
import { test } from "node:test";
import assert from "node:assert/strict";

import { CLIENT_DEFAULTS, applyGameplay, clientGameplay, loadFromDocument, readGameplay } from "../../static/js/gameplay.js";
import { nextRetry } from "../../static/js/computer.js";

function fakeDocument(text) {
  return { getElementById: (id) => (id === "gameplay-config" && text !== null ? { textContent: text } : null) };
}

test("the built-in values match the shipped gameplay.yaml", () => {
  assert.deepEqual({ ...CLIENT_DEFAULTS }, {
    captureAnimationMs: 260, yourGamesRefreshMs: 60000, computerRetryLimit: 3, computerRetryDelayMs: 5000, joinPollMs: 3000,
  });
  assert.deepEqual(readGameplay(null), { ...CLIENT_DEFAULTS });
});

test("valid values are taken; a bad or unknown value falls back alone", () => {
  const settings = readGameplay({ computerRetryLimit: 5, joinPollMs: 2000, captureAnimationMs: -1, yourGamesRefreshMs: "60", extra: 1 });
  assert.equal(settings.computerRetryLimit, 5);
  assert.equal(settings.joinPollMs, 2000);
  assert.equal(settings.captureAnimationMs, 260, "out of range");
  assert.equal(settings.yourGamesRefreshMs, 60000, "not a number");
  assert.equal("extra" in settings, false);
});

test("the shell's settings are read once; a missing or broken element keeps the built-in values", () => {
  try {
    assert.equal(loadFromDocument(fakeDocument('{"computerRetryLimit": 1, "computerRetryDelayMs": 2000}')).computerRetryLimit, 1);
    assert.equal(clientGameplay().computerRetryDelayMs, 2000);
    assert.deepEqual(nextRetry({ attempts: 2, lastAttemptAt: 0, now: 99_999 }), { action: "give-up", delayMs: 0 },
      "the computer retries follow the applied limit");
    assert.deepEqual(nextRetry({ attempts: 1, lastAttemptAt: 1000, now: 2000 }), { action: "wait", delayMs: 1000 });
    assert.deepEqual(loadFromDocument(fakeDocument("{not json")), { ...CLIENT_DEFAULTS });
    assert.deepEqual(loadFromDocument(fakeDocument(null)), { ...CLIENT_DEFAULTS });
  } finally {
    applyGameplay(null); // other test files share this module
  }
});
