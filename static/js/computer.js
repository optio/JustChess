/**
 * JustChess "Play the computer" logic (P2 U4, BR3.5, BR5.4, BR8.1-BR8.4). PURE: no DOM, no network, no clock.
 *
 *   levelName(level)                  "club" -> "Club" ("Unknown level" otherwise)
 *   opponentLabel(level)              "Computer · Club" (BR8.2)
 *   statusText(computer)              the computer's status line for a snapshot's `computer`, or null when idle
 *   controlsFor(snapshot, ctx)        { takeback, hint, resign } each { show, enabled } (BR8.2, BR4.1, BR6.1)
 *   shouldResume(snapshot)            the page should call computer-move (BR5.4): computer to move, state idle
 *   nextRetry({ attempts, lastAttemptAt, now, limit?, delayMs? })  "call" | "wait" (delayMs) | "give-up":
 *                                     3 retries 5 s apart by default (gameplay.js clientGameplay())
 *   hintArrow(hint, orientation)      { shaft, head } in board percent from a hint's from/to squares
 *   scoreLine(score)                  "This level: You 2 · Computer 3 · Draws 1" (BR8.2)
 *   readChoice(storage) / writeChoice(storage, choice)   the lobby panel's remembered colour and level (BR8.1)
 *   panelModel(engineStatus)          { playEnabled, message } for the panel (unavailable engine, BR8.1)
 *   findComputerSeat(seats, level)    the saved seat for a level (BR3.5), most recently saved first
 *
 * A snapshot's `computer` is { state: idle|queued|thinking|unavailable, queuePosition, reason, level,
 * available, message } (BR7.1); `message` carries a busy refusal in one HTTP answer only.
 * Storage reads and writes are wrapped in try/catch: a blocked storage just means defaults.
 */

import { CLIENT_DEFAULTS, clientGameplay } from "./gameplay.js";
import { arrowGeometry, arrowShape } from "./training/arrow.js";

export const LEVELS = Object.freeze(["beginner", "casual", "club", "strong", "maximum"]);
export const LEVEL_NAMES = Object.freeze({ beginner: "Beginner", casual: "Casual", club: "Club", strong: "Strong", maximum: "Maximum" });
export const COLOURS = Object.freeze(["white", "black", "random"]);
export const COLOUR_NAMES = Object.freeze({ white: "White", black: "Black", random: "Random" });
export const DEFAULT_CHOICE = Object.freeze({ colour: "random", level: "casual" });
export const CHOICE_KEY = "justchess.computer.choice";
// Built-in values; gameplay.yaml's client section (gameplay.js) can change them.
export const RETRY_LIMIT = CLIENT_DEFAULTS.computerRetryLimit;
export const RETRY_DELAY_MS = CLIENT_DEFAULTS.computerRetryDelayMs;
export const THINKING_TEXT = "Computer is thinking…";
export const NO_ANSWER_TEXT = "The computer didn't answer.";
export const UNAVAILABLE_PANEL_TEXT = "Play the computer is unavailable";
export const RESIGN_QUESTION = "Resign this game? The computer wins it.";

export function levelName(level) {
  return Object.hasOwn(LEVEL_NAMES, level) ? LEVEL_NAMES[level] : "Unknown level";
}

export function opponentLabel(level) {
  return `Computer · ${levelName(level)}`;
}

/** BR8.2: the status for thinking, queued and unavailable; null when idle (the normal status applies). */
export function statusText(computer) {
  if (!computer || typeof computer !== "object") return null;
  if (computer.state === "thinking") return THINKING_TEXT;
  if (computer.state === "queued") {
    const ahead = Number.isInteger(computer.queuePosition) && computer.queuePosition > 0 ? computer.queuePosition : 1;
    return `Waiting for the computer… (${ahead} ahead)`;
  }
  if (computer.state === "unavailable") {
    const reason = typeof computer.reason === "string" && computer.reason ? computer.reason : "it is not available";
    return `The computer can't move right now: ${reason}. You can still look through the game.`;
  }
  return null;
}

function plyCount(moveList) {
  if (!Array.isArray(moveList)) return 0;
  return moveList.reduce((n, row) => n + (row.white ? 1 : 0) + (row.black ? 1 : 0), 0);
}

/** How many half-moves the player (seat A, `colour`) has made, from the move list. */
export function playerMoves(snapshot) {
  const plies = plyCount(snapshot.moveList);
  return snapshot.colour === "white" ? Math.ceil(plies / 2) : Math.floor(plies / 2);
}

function isComputerSeat(snapshot) {
  return Boolean(snapshot) && snapshot.mode === "computer" && snapshot.slot === "A" && Boolean(snapshot.computer);
}

/** BR8.2: Take back, Hint and Resign for seat A of a computer room. ctx: { watching, hintPending }. */
export function controlsFor(snapshot, { watching = false, hintPending = false } = {}) {
  const hidden = { show: false, enabled: false };
  if (watching || !isComputerSeat(snapshot)) return { takeback: hidden, hint: hidden, resign: hidden };
  const playing = snapshot.status === "playing";
  const state = snapshot.computer.state;
  const yourTurn = playing && snapshot.colour === snapshot.turn;
  const replying = state === "queued" || state === "thinking";
  const takeback = playing && !replying && playerMoves(snapshot) >= 1 && (yourTurn || state === "unavailable");
  const hint = yourTurn && snapshot.computer.available === true && !hintPending;
  return {
    takeback: { show: true, enabled: takeback },
    hint: { show: true, enabled: hint },
    resign: { show: true, enabled: playing },
  };
}

/** BR5.4: the computer is to move, nothing is asked yet, and the engine is up. */
export function shouldResume(snapshot) {
  if (!isComputerSeat(snapshot) || snapshot.status !== "playing") return false;
  return snapshot.turn !== snapshot.colour && snapshot.computer.state === "idle" && snapshot.computer.available === true;
}

/**
 * BR5.4: the page's resume calls. The first call goes at once; each further one at least
 * RETRY_DELAY_MS after the last; after RETRY_LIMIT retries it gives up ("The computer didn't answer.").
 * attempts counts the calls already made for this position.
 */
export function nextRetry({
  attempts = 0, lastAttemptAt = null, now = 0,
  limit = clientGameplay().computerRetryLimit, delayMs = clientGameplay().computerRetryDelayMs,
} = {}) {
  if (attempts > limit) return { action: "give-up", delayMs: 0 };
  if (attempts === 0 || lastAttemptAt === null) return { action: "call", delayMs: 0 };
  const wait = lastAttemptAt + delayMs - now;
  return wait > 0 ? { action: "wait", delayMs: wait } : { action: "call", delayMs: 0 };
}

/** W6: the arrow from a hint's from-square to its to-square for the board orientation (board percent). */
export function hintArrow(hint, orientation) {
  if (!hint || typeof hint.from !== "string" || typeof hint.to !== "string") return null;
  return arrowShape(arrowGeometry(hint.from, hint.to, orientation));
}

export function scoreLine(score) {
  const value = (key) => (score && Number.isFinite(score[key]) ? score[key] : 0);
  return `This level: You ${value("A")} · Computer ${value("B")} · Draws ${value("draws")}`;
}

function cleanChoice(value) {
  const colour = value && COLOURS.includes(value.colour) ? value.colour : DEFAULT_CHOICE.colour;
  const level = value && LEVELS.includes(value.level) ? value.level : DEFAULT_CHOICE.level;
  return { colour, level };
}

/** BR8.1: the remembered choice, or the defaults (Random, Casual) when none or unreadable. */
export function readChoice(storage) {
  try {
    const raw = storage ? storage.getItem(CHOICE_KEY) : null;
    return cleanChoice(raw ? JSON.parse(raw) : null);
  } catch {
    return { ...DEFAULT_CHOICE };
  }
}

/** BR8.1: remember a choice; returns false when storage refused (the choice still applies now). */
export function writeChoice(storage, choice) {
  try {
    if (!storage) return false;
    storage.setItem(CHOICE_KEY, JSON.stringify(cleanChoice(choice)));
    return true;
  } catch {
    return false;
  }
}

/** BR8.1: Play is enabled only when /api/engine says available; otherwise the panel shows why. */
export function panelModel(engineStatus) {
  if (engineStatus && engineStatus.available === true) return { playEnabled: true, message: null, reason: null };
  const reason = engineStatus && typeof engineStatus.reason === "string" && engineStatus.reason ? engineStatus.reason : null;
  return { playEnabled: false, message: UNAVAILABLE_PANEL_TEXT, reason };
}

/** BR3.5: the saved computer seat for this level (most recently saved first), or null. */
export function findComputerSeat(seats, level) {
  if (!seats || typeof seats.validSeats !== "function") return null;
  return seats.validSeats().find((seat) => seat.kind === "computer" && seat.computerLevel === level) || null;
}
