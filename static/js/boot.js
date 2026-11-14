/*
 * JustChess boot script (U2). Load it synchronously in <head>, before the
 * stylesheets paint:  <script src="/static/js/boot.js"></script>
 *
 * Sets data-theme (omitted for "device") and data-board on <html> from the
 * saved settings so the first paint already has the right theme (W1 step 3).
 * It is a classic script, not a module, so it runs before first paint, and an
 * external file rather than inline, so a later Content-Security-Policy needs
 * no hash. Key and allow-lists match static/js/settings.js; the test
 * tests/js/settings.test.mjs runs this file and checks they agree.
 *
 * Blocked or corrupt storage falls back to the defaults on purpose: the
 * settings store then reports itself not persistent and the panel says so.
 */
(function () {
  "use strict";
  var KEY = "justchess.settings.v1";
  var THEMES = ["device", "light", "dark"];
  var BOARDS = ["walnut-maple", "tournament", "rosewood"];
  var saved = {};
  try {
    var raw = window.localStorage.getItem(KEY);
    var parsed = raw ? JSON.parse(raw) : {};
    if (parsed && typeof parsed === "object") saved = parsed;
  } catch (error) {
    saved = {};
  }
  var theme = THEMES.indexOf(saved.theme) >= 0 ? saved.theme : "device";
  var board = BOARDS.indexOf(saved.board) >= 0 ? saved.board : "walnut-maple";
  var root = document.documentElement;
  if (theme === "device") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  root.setAttribute("data-board", board);
})();
