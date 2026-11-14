/**
 * Puzzle screen state machine (P2 U5, W5, BR2.3-BR2.5). A PURE reducer, no DOM,
 * no timers, no network:
 *
 *   reduce(state, event) -> { state, effects }
 *
 * puzzle.js keeps the state, sends every board, button, timer and network event
 * here, and runs the effects in order.
 *
 * Phases (functional-spec.md W5):
 *   loading -> settingUp -> yourMove -> checking -> reply -> yourMove ...
 *                                    checking -> solved | wrong -> yourMove
 *              yourMove -> revealing -> seen;   solved | seen -> next puzzle
 *
 * State: { phase, puzzle, ply, position, pendingReply, hintLevel, revealed, reveal, message, seq }
 *   puzzle        GET /api/puzzles/{theme}/{id} (no solution)
 *   ply           index of the expected player move in the hidden move list (1, 3, 5...)
 *   position      { fen, legalMoves, check, lastMove } where the player moves next
 *   hintLevel     0 none, 1 piece shown, 2 arrow shown (BR2.5: two steps)
 *   revealed      Show solution was used: a later "solved" records no progress
 *   seq           every scheduled timer carries the seq it was made with; a timer
 *                 whose seq is no longer current is ignored (cancelling for free)
 *
 * Events:
 *   { type: "loaded", puzzle }        { type: "setupPlayed", seq }
 *   { type: "playerMove", uci }       { type: "checkResult", data } | { type: "checkError" }
 *   { type: "replyPlayed", seq }      { type: "takeBack", seq }
 *   { type: "hint" }                  { type: "hintResult", level, data } | { type: "hintError", message }
 *   { type: "showSolution" }          { type: "revealStep", seq }
 *   { type: "next" }
 *
 * Effects:
 *   { type: "setBoard", options }     board.set(options)
 *   { type: "arrow", uci, orientation }  draw (or clear, uci null) the hint arrow
 *   { type: "schedule", delay, event }   send event after delay ms (0 under reduced motion is the view's call)
 *   { type: "check", ply, uci }       POST .../check, answer checkResult / checkError
 *   { type: "hint", ply, level }      POST .../hint, answer hintResult / hintError
 *   { type: "rejectMove" }            board.reject(): slide the shown move back
 *   { type: "progress", theme, id }   record the solved puzzle (BR3.2)
 *   { type: "next" }                  open the next unsolved puzzle of the theme
 */

export const SETUP_DELAY_MS = 600;
export const REPLY_DELAY_MS = 300;
export const WRONG_MS = 600;
export const REVEAL_MS = 800;
export const PHASES = Object.freeze(["loading", "settingUp", "yourMove", "checking", "reply", "solved", "wrong", "revealing", "seen"]);

export const TEXT = Object.freeze({
  wrong: "Not this one. Try again.",
  checkFailed: "Couldn't check that move. Try again.",
  solved: "Solved",
  revealing: "Here is the solution.",
  seen: "That was the solution. Try the next puzzle.",
  arrow: "The arrow shows the move.",
  unreadable: "That puzzle could not be read.",
});

const NONE = Object.freeze([]);
const SIDES = ["white", "black"];

export function initialState() {
  return {
    phase: "loading",
    puzzle: null,
    ply: 1,
    position: null,
    pendingReply: null,
    pendingUci: null,
    hintLevel: 0,
    hintUci: null,
    revealed: false,
    reveal: null,
    message: null,
    seq: 0,
  };
}

/** True when the detail has the shape GET /api/puzzles/{theme}/{id} promises. */
export function isPuzzle(puzzle) {
  return Boolean(puzzle) && typeof puzzle.id === "string" && typeof puzzle.theme === "string"
    && typeof puzzle.fen === "string" && typeof puzzle.setup === "string" && typeof puzzle.afterSetup === "string"
    && Array.isArray(puzzle.legalMoves) && SIDES.includes(puzzle.side);
}

/** "White to move: find the fork" (the theme's goal comes from THEME_GOALS). */
export const THEME_GOALS = Object.freeze({
  fork: "find the fork",
  pin: "find the pin",
  skewer: "find the skewer",
  discoveredAttack: "find the discovered attack",
  mateIn1: "find mate in 1",
  mateIn2: "find mate in 2",
});

export function statusText(puzzle) {
  if (!puzzle) return "";
  const side = puzzle.side === "black" ? "Black" : "White";
  return `${side} to move: ${THEME_GOALS[puzzle.theme] || "find the best move"}`;
}

// --- helpers --------------------------------------------------------------------

const unchanged = (state) => ({ state, effects: NONE });

function board(state, position, interactive) {
  return {
    type: "setBoard",
    options: {
      fen: position.fen,
      lastMove: position.lastMove || null,
      check: Boolean(position.check),
      orientation: state.puzzle.side,
      interactive,
      legalMoves: interactive ? [...position.legalMoves] : [],
      hintSquare: null,
    },
  };
}

function arrow(state, uci = null) {
  return { type: "arrow", uci, orientation: state.puzzle ? state.puzzle.side : "white" };
}

function schedule(state, delay, type) {
  const seq = state.seq + 1;
  return { seq, effect: { type: "schedule", delay, event: { type, seq } } };
}

// --- handlers -------------------------------------------------------------------

function onLoaded(state, { puzzle }) {
  if (!isPuzzle(puzzle)) return unchanged({ ...initialState(), seq: state.seq, message: { text: TEXT.unreadable, tone: "error" } });
  const base = { ...initialState(), seq: state.seq, phase: "settingUp", puzzle };
  const timer = schedule(base, SETUP_DELAY_MS, "setupPlayed");
  const next = { ...base, seq: timer.seq };
  const start = { fen: puzzle.fen, legalMoves: [], check: false, lastMove: null };
  return { state: next, effects: [board(next, start, false), arrow(next), timer.effect] };
}

function onSetupPlayed(state, { seq }) {
  if (state.phase !== "settingUp" || seq !== state.seq) return unchanged(state);
  const { puzzle } = state;
  const position = { fen: puzzle.afterSetup, legalMoves: [...puzzle.legalMoves], check: Boolean(puzzle.check), lastMove: puzzle.setup };
  const next = { ...state, phase: "yourMove", position };
  return { state: next, effects: [board(next, position, true)] };
}

function onPlayerMove(state, { uci }) {
  if (state.phase !== "yourMove" || typeof uci !== "string") return { state, effects: [{ type: "rejectMove" }] };
  const next = { ...state, phase: "checking", pendingUci: uci };
  return { state: next, effects: [{ type: "check", ply: state.ply, uci }] };
}

function solved(state, data) {
  const position = { fen: data.fen, legalMoves: [], check: data.check, lastMove: state.pendingUci };
  const next = { ...state, phase: "solved", position, message: { text: TEXT.solved, tone: "success" } };
  const effects = [board(next, position, false), arrow(next)];
  if (!state.revealed) effects.push({ type: "progress", theme: state.puzzle.theme, id: state.puzzle.id });
  return { state: next, effects };
}

function onCheckResult(state, { data }) {
  if (state.phase !== "checking" || !data) return unchanged(state);
  if (data.result === "solved" && typeof data.fen === "string") return solved(state, data);
  if (data.result === "wrong") {
    const timer = schedule(state, WRONG_MS, "takeBack");
    return { state: { ...state, phase: "wrong", seq: timer.seq, message: { text: TEXT.wrong, tone: "warn" } }, effects: [timer.effect] };
  }
  if (data.result === "correct" && typeof data.fen === "string" && typeof data.reply === "string"
      && typeof data.replyFen === "string" && Array.isArray(data.legalMoves)) {
    const shown = { fen: data.fen, legalMoves: [], check: data.check, lastMove: state.pendingUci };
    const pendingReply = { fen: data.replyFen, legalMoves: [...data.legalMoves], check: Boolean(data.replyCheck), lastMove: data.reply };
    const timer = schedule(state, REPLY_DELAY_MS, "replyPlayed");
    const next = { ...state, phase: "reply", seq: timer.seq, position: shown, pendingReply, message: null };
    return { state: next, effects: [board(next, shown, false), arrow(next), timer.effect] };
  }
  return onCheckError(state);
}

function onCheckError(state) {
  if (state.phase !== "checking") return unchanged(state);
  const next = { ...state, phase: "yourMove", pendingUci: null, message: { text: TEXT.checkFailed, tone: "error" } };
  return { state: next, effects: [{ type: "rejectMove" }, board(next, state.position, true)] };
}

function onReplyPlayed(state, { seq }) {
  if (state.phase !== "reply" || seq !== state.seq || !state.pendingReply) return unchanged(state);
  const position = state.pendingReply;
  const next = { ...state, phase: "yourMove", ply: state.ply + 2, position, pendingReply: null, pendingUci: null,
    hintLevel: 0, hintUci: null };
  return { state: next, effects: [board(next, position, true)] };
}

function onTakeBack(state, { seq }) {
  if (state.phase !== "wrong" || seq !== state.seq) return unchanged(state);
  const next = { ...state, phase: "yourMove", pendingUci: null };
  const effects = [{ type: "rejectMove" }, board(next, state.position, true)];
  if (state.hintLevel >= 2 && state.hintUci) effects.push(arrow(next, state.hintUci));
  return { state: next, effects };
}

function onHint(state) {
  if (state.phase !== "yourMove" || state.hintLevel >= 2) return unchanged(state);
  return { state, effects: [{ type: "hint", ply: state.ply, level: state.hintLevel === 0 ? "piece" : "move" }] };
}

function onHintResult(state, { level, data }) {
  if (!data) return unchanged(state);
  if (level === "solution") return onSolution(state, data);
  if (state.phase !== "yourMove") return unchanged(state);
  if (level === "piece" && typeof data.from === "string") {
    const next = { ...state, hintLevel: 1, message: { text: `Move the piece on ${data.from}.`, tone: "info" } };
    return { state: next, effects: [{ type: "setBoard", options: { hintSquare: data.from } }] };
  }
  if (level === "move" && typeof data.uci === "string") {
    const next = { ...state, hintLevel: 2, hintUci: data.uci, message: { text: TEXT.arrow, tone: "info" } };
    return { state: next, effects: [arrow(next, data.uci)] };
  }
  return unchanged(state);
}

function onHintError(state, { message }) {
  if (state.phase !== "yourMove" && state.phase !== "revealing") return unchanged(state);
  const text = typeof message === "string" && message ? message : "Something went wrong. Try again.";
  if (state.phase === "revealing") {
    const back = { ...state, phase: "yourMove", message: { text, tone: "error" } };
    return { state: back, effects: [board(back, state.position, true)] };
  }
  return unchanged({ ...state, message: { text, tone: "error" } });
}

function onShowSolution(state) {
  if (state.phase !== "yourMove" && state.phase !== "wrong") return unchanged(state);
  const fromWrong = state.phase === "wrong";
  const next = { ...state, phase: "revealing", seq: state.seq + 1, revealed: true, pendingUci: null,
    message: { text: TEXT.revealing, tone: "info" } };
  const effects = fromWrong ? [{ type: "rejectMove" }] : [];
  effects.push(board(next, state.position, false), arrow(next), { type: "hint", ply: state.ply, level: "solution" });
  return { state: next, effects };
}

function onSolution(state, data) {
  if (state.phase !== "revealing" || !Array.isArray(data.line) || !Array.isArray(data.fens) || data.line.length !== data.fens.length) {
    return unchanged(state);
  }
  const timer = schedule(state, REVEAL_MS, "revealStep");
  const next = { ...state, seq: timer.seq, reveal: { line: [...data.line], fens: [...data.fens], index: 0 } };
  return { state: next, effects: [timer.effect] };
}

function onRevealStep(state, { seq }) {
  if (state.phase !== "revealing" || seq !== state.seq || !state.reveal) return unchanged(state);
  const { line, fens, index } = state.reveal;
  const position = { fen: fens[index], legalMoves: [], check: false, lastMove: line[index] };
  const reveal = { ...state.reveal, index: index + 1 };
  if (reveal.index >= line.length) {
    const done = { ...state, phase: "seen", position, reveal, message: { text: TEXT.seen, tone: "info" } };
    return { state: done, effects: [board(done, position, false)] };
  }
  const timer = schedule(state, REVEAL_MS, "revealStep");
  const next = { ...state, seq: timer.seq, position, reveal };
  return { state: next, effects: [board(next, position, false), timer.effect] };
}

function onNext(state) {
  if (state.phase === "loading") return unchanged(state);
  const next = { ...initialState(), seq: state.seq + 1 };
  return { state: next, effects: [arrow(state), { type: "next" }] };
}

export function reduce(state, event) {
  if (!event || typeof event.type !== "string") throw new TypeError("puzzle event needs a type");
  switch (event.type) {
    case "loaded": return onLoaded(state, event);
    case "setupPlayed": return onSetupPlayed(state, event);
    case "playerMove": return onPlayerMove(state, event);
    case "checkResult": return onCheckResult(state, event);
    case "checkError": return onCheckError(state, event);
    case "replyPlayed": return onReplyPlayed(state, event);
    case "takeBack": return onTakeBack(state, event);
    case "hint": return onHint(state);
    case "hintResult": return onHintResult(state, event);
    case "hintError": return onHintError(state, event);
    case "showSolution": return onShowSolution(state);
    case "revealStep": return onRevealStep(state, event);
    case "next": return onNext(state);
    default:
      throw new TypeError(`unknown puzzle event ${JSON.stringify(event.type)}`);
  }
}
