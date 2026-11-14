/**
 * U2 demo page logic (static/demo/board.html). Exercises the design system
 * and the board without a server: a practice position you can play (with
 * promotion, castling and an optional refusal to test reject()), a scripted
 * game (capture, check, castling) and a promotion script, the settings panel,
 * a board-theme gallery and a contrast self-check of tokens.css.
 *
 * Positions and legal moves were generated with python-chess, so they are
 * real chess. Serve the page over HTTP (ES modules), e.g. the app's /static.
 */

import { createBoard } from "../js/board/board.js";
import { applyToDocument, createSettings } from "../js/settings.js";
import { renderSettingsPanel } from "../js/settings-panel.js";
import { buildPalette, contrastFailures, contrastReport } from "../js/contrast.js";

const PIECES = new URL("../pieces/cburnett/", import.meta.url).href;
const TOKENS = new URL("../css/tokens.css", import.meta.url).href;
const STEP_MS = 900;
const SERVER_DELAY_MS = 300;

// [fen, lastMove, check, san]
const SCRIPTED_GAME = [
  ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", null, false, null],
  ["rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "e2e4", false, "e4"],
  ["rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "d7d5", false, "d5"],
  ["rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2", "e4d5", false, "exd5"],
  ["rnb1kbnr/ppp1pppp/8/3q4/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3", "d8d5", false, "Qxd5"],
  ["rnb1kbnr/ppp1pppp/8/3q4/8/2N5/PPPP1PPP/R1BQKBNR b KQkq - 1 3", "b1c3", false, "Nc3"],
  ["rnb1kbnr/ppp1pppp/8/4q3/8/2N5/PPPP1PPP/R1BQKBNR w KQkq - 2 4", "d5e5", true, "Qe5+"],
  ["rnb1kbnr/ppp1pppp/8/4q3/8/2N5/PPPPBPPP/R1BQK1NR b KQkq - 3 4", "f1e2", false, "Be2"],
  ["rn2kbnr/ppp1pppp/8/4q3/6b1/2N5/PPPPBPPP/R1BQK1NR w KQkq - 4 5", "c8g4", false, "Bg4"],
  ["rn2kbnr/ppp1pppp/8/4q3/6b1/2N2N2/PPPPBPPP/R1BQK2R b KQkq - 5 5", "g1f3", false, "Nf3"],
  ["rn2kbnr/ppp1pppp/8/4q3/8/2N2b2/PPPPBPPP/R1BQK2R w KQkq - 0 6", "g4f3", false, "Bxf3"],
  ["rn2kbnr/ppp1pppp/8/4q3/8/2N2P2/PPPPBP1P/R1BQK2R b KQkq - 0 6", "g2f3", false, "gxf3"],
  ["r3kbnr/ppp1pppp/2n5/4q3/8/2N2P2/PPPPBP1P/R1BQK2R w KQkq - 1 7", "b8c6", false, "Nc6"],
  ["r3kbnr/ppp1pppp/2n5/4q3/8/2N2P2/PPPPBP1P/R1BQ1RK1 b kq - 2 7", "e1g1", false, "O-O"],
];

const PROMOTION_SCRIPT = [
  ["8/1P2k3/8/8/8/8/5K2/8 w - - 0 1", null, false, null],
  ["1Q6/4k3/8/8/8/8/5K2/8 b - - 0 1", "b7b8", false, "b8=Q"],
  ["1Q6/3k4/8/8/8/8/5K2/8 w - - 1 2", "e7d7", false, "Kd7"],
  ["8/3k4/8/1Q6/8/8/5K2/8 b - - 2 2", "b8b5", true, "Qb5+"],
];

const PRACTICE_FEN = "r3k2r/1P6/8/8/8/8/8/R3K2R w KQkq - 0 1";
// uci -> [resulting fen, check]
const PRACTICE_REPLIES = {
  a1a2: ["r3k2r/1P6/8/8/8/8/R7/4K2R b Kkq - 1 1", false],
  a1a3: ["r3k2r/1P6/8/8/8/R7/8/4K2R b Kkq - 1 1", false],
  a1a4: ["r3k2r/1P6/8/8/R7/8/8/4K2R b Kkq - 1 1", false],
  a1a5: ["r3k2r/1P6/8/R7/8/8/8/4K2R b Kkq - 1 1", false],
  a1a6: ["r3k2r/1P6/R7/8/8/8/8/4K2R b Kkq - 1 1", false],
  a1a7: ["r3k2r/RP6/8/8/8/8/8/4K2R b Kkq - 1 1", false],
  a1a8: ["R3k2r/1P6/8/8/8/8/8/4K2R b Kk - 0 1", true],
  a1b1: ["r3k2r/1P6/8/8/8/8/8/1R2K2R b Kkq - 1 1", false],
  a1c1: ["r3k2r/1P6/8/8/8/8/8/2R1K2R b Kkq - 1 1", false],
  a1d1: ["r3k2r/1P6/8/8/8/8/8/3RK2R b Kkq - 1 1", false],
  b7a8b: ["B3k2r/8/8/8/8/8/8/R3K2R b KQk - 0 1", false],
  b7a8n: ["N3k2r/8/8/8/8/8/8/R3K2R b KQk - 0 1", false],
  b7a8q: ["Q3k2r/8/8/8/8/8/8/R3K2R b KQk - 0 1", true],
  b7a8r: ["R3k2r/8/8/8/8/8/8/R3K2R b KQk - 0 1", true],
  b7b8b: ["rB2k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", false],
  b7b8n: ["rN2k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", false],
  b7b8q: ["rQ2k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", true],
  b7b8r: ["rR2k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", true],
  e1c1: ["r3k2r/1P6/8/8/8/8/8/2KR3R b kq - 1 1", false],
  e1d1: ["r3k2r/1P6/8/8/8/8/8/R2K3R b kq - 1 1", false],
  e1d2: ["r3k2r/1P6/8/8/8/8/3K4/R6R b kq - 1 1", false],
  e1e2: ["r3k2r/1P6/8/8/8/8/4K3/R6R b kq - 1 1", false],
  e1f1: ["r3k2r/1P6/8/8/8/8/8/R4K1R b kq - 1 1", false],
  e1f2: ["r3k2r/1P6/8/8/8/8/5K2/R6R b kq - 1 1", false],
  e1g1: ["r3k2r/1P6/8/8/8/8/8/R4RK1 b kq - 1 1", false],
  h1f1: ["r3k2r/1P6/8/8/8/8/8/R3KR2 b Qkq - 1 1", false],
  h1g1: ["r3k2r/1P6/8/8/8/8/8/R3K1R1 b Qkq - 1 1", false],
  h1h2: ["r3k2r/1P6/8/8/8/8/7R/R3K3 b Qkq - 1 1", false],
  h1h3: ["r3k2r/1P6/8/8/8/7R/8/R3K3 b Qkq - 1 1", false],
  h1h4: ["r3k2r/1P6/8/8/7R/8/8/R3K3 b Qkq - 1 1", false],
  h1h5: ["r3k2r/1P6/8/7R/8/8/8/R3K3 b Qkq - 1 1", false],
  h1h6: ["r3k2r/1P6/7R/8/8/8/8/R3K3 b Qkq - 1 1", false],
  h1h7: ["r3k2r/1P5R/8/8/8/8/8/R3K3 b Qkq - 1 1", false],
  h1h8: ["r3k2R/1P6/8/8/8/8/8/R3K3 b Qq - 0 1", true],
};

const $ = (selector) => document.querySelector(selector);
const store = createSettings();
applyToDocument(store);

const status = $("#demo-status");
let scriptTimer = null;

function say(text, yours = false) {
  status.textContent = text;
  status.classList.toggle("is-yours", yours);
}

function practiceOptions() {
  return { fen: PRACTICE_FEN, lastMove: null, check: false, legalMoves: Object.keys(PRACTICE_REPLIES), interactive: true };
}

function onMove(uci) {
  const reply = PRACTICE_REPLIES[uci];
  if ($("#refuse").checked || !reply) {
    $("#refuse").checked = false;
    setTimeout(() => {
      board.reject();
      board.liveRegion.textContent = `Move ${uci} was refused.`;
      say("The server refused that move (demo). Your move.", true);
    }, SERVER_DELAY_MS);
    return;
  }
  setTimeout(() => {
    board.set({ fen: reply[0], lastMove: uci.slice(0, 4), check: reply[1], legalMoves: [], interactive: false });
    board.liveRegion.textContent = `White played ${uci}.`;
    say(`You played ${uci}${reply[1] ? ", check" : ""}. Reset to try another move.`);
  }, SERVER_DELAY_MS);
}

const board = createBoard($("#main-board"), {
  ...practiceOptions(),
  orientation: "white",
  labels: store.get("labels"),
  piecePath: PIECES,
  onMove,
});

function stopScript() {
  clearTimeout(scriptTimer);
  scriptTimer = null;
}

function playScript(steps, title) {
  stopScript();
  let index = 0;
  const step = () => {
    const [fen, lastMove, check, san] = steps[index];
    board.set({ fen, lastMove, check, legalMoves: [], interactive: false });
    if (san) board.liveRegion.textContent = `${index % 2 === 1 ? "White" : "Black"} played ${san}.`;
    say(san ? `${title}: ${san}` : `${title}: starting position`);
    index += 1;
    if (index < steps.length) scriptTimer = setTimeout(step, STEP_MS);
    else say(`${title}: finished. Reset to play the practice position.`);
  };
  step();
}

function resetPractice() {
  stopScript();
  board.set(practiceOptions());
  say("Your move as White. Try promoting the pawn on b7, or castling.", true);
}

$("#play-game").addEventListener("click", () => playScript(SCRIPTED_GAME, "Scripted game"));
$("#play-promo").addEventListener("click", () => playScript(PROMOTION_SCRIPT, "Promotion"));
$("#reset").addEventListener("click", resetPractice);
for (const input of document.querySelectorAll("input[name=orientation]")) {
  input.addEventListener("change", () => board.set({ orientation: input.value }));
}

const continueRow = document.createElement("p");
continueRow.className = "t-small t-muted";
continueRow.textContent = "Slot for U3's \"Get a private continue link\" row.";

renderSettingsPanel($("#settings"), store, {
  extraRows: continueRow,
  async onNotificationsToggle(value) {
    if (!value) return false;
    if (typeof Notification === "undefined") throw new Error("This browser has no notifications");
    return (await Notification.requestPermission()) === "granted";
  },
});

store.subscribe((key, value) => {
  if (key === "labels") board.set({ labels: value });
});

const galleryFen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3";
for (const holder of document.querySelectorAll(".gallery-board")) {
  createBoard(holder, { fen: galleryFen, lastMove: { from: "f1", to: "c4" }, piecePath: PIECES });
}

function describeMotion() {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const update = () => {
    $("#motion-note").textContent = reduced.matches
      ? "Reduced motion is on: moves, captures and the check pulse jump straight to the end state."
      : "Reduced motion is off. Turn it on in your device settings to check that every animation is skipped.";
  };
  update();
  reduced.addEventListener("change", update);
}

async function contrastSelfCheck() {
  const target = $("#contrast");
  try {
    const response = await fetch(TOKENS);
    if (!response.ok) throw new Error(`tokens.css answered ${response.status}`);
    const report = contrastReport(buildPalette(await response.text()));
    const total = report.pieces.length + report.labels.length + report.lastMove.length + report.theme.length;
    const failures = contrastFailures(report);
    if (failures.length === 0) {
      target.innerHTML = "";
      const ok = document.createElement("p");
      ok.className = "contrast-ok";
      ok.textContent = `All ${total} pairs pass.`;
      target.append(ok);
      return;
    }
    const list = document.createElement("ul");
    list.className = "contrast-list";
    for (const failure of failures) {
      const item = document.createElement("li");
      item.className = "contrast-fail";
      item.textContent = `${failure.name}: ${failure.ratio.toFixed(2)}:1, needs ${failure.min}:1`;
      list.append(item);
    }
    target.replaceChildren(list);
  } catch (error) {
    console.error("JustChess demo: contrast self-check failed", error);
    target.textContent = `The contrast self-check could not run: ${error.message}`;
  }
}

describeMotion();
contrastSelfCheck();
say("Your move as White. Try promoting the pawn on b7, or castling.", true);
