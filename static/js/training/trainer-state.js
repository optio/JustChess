/**
 * Opening trainer state machine (U6). A PURE reducer, no DOM, no timers:
 *
 *   reduce(state, event) -> { state, effects }
 *
 * trainer.js keeps the state, sends every user, board, timer and network event
 * here, and runs the returned effects in order. Rules: BR3.1 (walkthrough),
 * BR4.1-BR4.5 (practice), functional-spec.md state machine, plus the design
 * review decisions in the code generation plan:
 *   - "Other lessons" leaves every phase;
 *   - a legal move off the line is shown on the board (from POST
 *     /api/position/move) and the board stays locked until the learner picks
 *     "Keep playing freely" or "Back to the line";
 *   - Hint is always available on a learner ply and highlights the from-square;
 *   - the third miss on a step draws the arrow and says "The move is <san>. <note>";
 *   - leaving practice cancels the trainer's reply timer, and leaving free play
 *     or the off-line choice aborts a request in flight.
 *
 * Phases: "choosing" | "walkthrough" | "practice" | "offLine" | "freePlay" | "complete"
 *
 * State: { phase, lesson, index, side, misses, hintShown, arrow, offLine, free,
 *          message, trainerSeq, trainerPending, request }
 *   index           the step about to be played (0..steps.length)
 *   side            the learner's side in practice; the board orientation
 *   misses          misses on the current step; reset when the step is played
 *   arrow           step.uci once misses reach 3, else null
 *   offLine         { uci, fen, legalMoves, outcome, check } while the choice is open
 *   free            { fen, legalMoves, lastMove, outcome, check, returnIndex } in free play
 *   message         { text, tone } for the role="status" line, or null
 *   trainerPending  the seq of the scheduled trainer reply, or null
 *   request         { purpose: "offLine" | "free", uci } while a position move is in flight
 *
 * Events:
 *   { type: "lessonLoaded", lesson }        a lesson from GET /api/lessons/{id}
 *   { type: "next" } | { type: "back" } | { type: "restart" }      walkthrough
 *   { type: "startPractice", side? }        Practise / Practise again (side defaults to the current)
 *   { type: "switchSide", side }            the "Practise as" switch: restart on that side
 *   { type: "learnerMove", uci }            the board's onMove (practice or free play)
 *   { type: "rejectedTap", from, to }       the board's onRejectedTap
 *   { type: "trainerMove", seq }            the reply timer fired
 *   { type: "hint" }
 *   { type: "positionResult", data }        POST /api/position/move answered 200
 *   { type: "positionError", message }      it failed (400, network, server)
 *   { type: "keepPlaying" } | { type: "backToLine" } | { type: "otherLessons" }
 *
 * Effects:
 *   { type: "setBoard", options }           board.set(options); options are U2 board options
 *   { type: "arrow", uci, orientation }     draw the arrow (uci null removes it)
 *   { type: "scheduleTrainer", seq }        after 500 ms (0 under reduced motion) send trainerMove
 *   { type: "cancelTrainer" }               clear that timer
 *   { type: "positionMove", fen, uci }      POST /api/position/move, answer with positionResult/Error
 *   { type: "abortRequest" }                abort the request in flight
 *   { type: "rejectMove" }                  board.reject(): slide the pending move back
 *   { type: "showList" }                    show the lesson list
 *   { type: "progress", lessonId, kind, arrowShown }   P2 U5 BR3.2: the practice run reached
 *                                           "complete"; record it per device. A run where the
 *                                           arrow was shown still counts (it only appears after
 *                                           3 misses); arrowShown says whether it was.
 *
 * P2 U5: state.arrowShown is true once the arrow was drawn during the current
 * practice run; Practise / Practise again / a side switch reset it.
 */

export const TRAINER_DELAY_MS = 500;
export const ARROW_AFTER_MISSES = 3;
export const PHASES = Object.freeze(["choosing", "walkthrough", "practice", "offLine", "freePlay", "complete"]);

export const TEXT = Object.freeze({
  illegal: "That move isn't legal.",
  offLine: "Legal, but not this line",
  free: "Free play — not part of the lesson",
  complete: "Line complete",
  walkStart: "Press Next to play the first move.",
  backToLine: "Back to the line. Your move.",
  unreadable: "That lesson could not be read.",
});

export const OUTCOME_TEXT = Object.freeze({
  checkmate: "Checkmate.",
  stalemate: "Stalemate: a draw.",
  insufficient_material: "Draw: neither side has enough material to checkmate.",
  fifty_moves: "A draw can be claimed: fifty moves without a capture or a pawn move.",
  seventyfive_moves: "Draw: seventy-five moves without a capture or a pawn move.",
});

const SIDES = ["white", "black"];

export function initialState() {
  return {
    phase: "choosing",
    lesson: null,
    index: 0,
    side: "white",
    misses: 0,
    hintShown: false,
    arrow: null,
    arrowShown: false,
    offLine: null,
    free: null,
    message: null,
    trainerSeq: 0,
    trainerPending: null,
    request: null,
  };
}

// --- lesson helpers -------------------------------------------------------------

function validStep(step) {
  return Boolean(step) && typeof step.uci === "string" && typeof step.san === "string"
    && typeof step.fenBefore === "string" && typeof step.fenAfter === "string"
    && Array.isArray(step.legalBefore) && SIDES.includes(step.side);
}

/** True when the lesson has the shape GET /api/lessons/{id} promises. */
export function isLesson(lesson) {
  return Boolean(lesson) && typeof lesson.name === "string" && SIDES.includes(lesson.side)
    && Array.isArray(lesson.steps) && lesson.steps.length > 0 && lesson.steps.every(validStep);
}

export function sideName(side) {
  return side === "black" ? "Black" : "White";
}

export function otherSide(side) {
  return side === "black" ? "white" : "black";
}

/** "1. e4" for White, "1… e5" for Black; the number comes from the FEN before the move. */
export function moveLabel(step) {
  const number = Number(String(step.fenBefore).split(" ")[5]) || 1;
  return step.side === "white" ? `${number}. ${step.san}` : `${number}… ${step.san}`;
}

export function currentStep(state) {
  return state.lesson ? state.lesson.steps[state.index] || null : null;
}

export function isLearnerPly(state) {
  const step = currentStep(state);
  return state.phase === "practice" && Boolean(step) && step.side === state.side;
}

function fenAt(lesson, index) {
  return index === 0 ? lesson.steps[0].fenBefore : lesson.steps[index - 1].fenAfter;
}

function previous(lesson, index) {
  return index === 0 ? null : lesson.steps[index - 1];
}

function givesCheck(step) {
  return Boolean(step) && /[+#]$/.test(step.san);
}

function arrowMessage(step) {
  return { text: `The move is ${step.san}. ${step.note}`, tone: "warn" };
}

function noteMessage(step, prefix = "") {
  return { text: `${prefix}${moveLabel(step)}: ${step.note}`, tone: "note" };
}

// --- effects --------------------------------------------------------------------

const NONE = Object.freeze([]);

function unchanged(state) {
  return { state, effects: NONE };
}

function setBoard(options) {
  return { type: "setBoard", options };
}

function arrowEffect(state) {
  return { type: "arrow", uci: state.phase === "practice" ? state.arrow : null, orientation: state.side };
}

function walkBoard(state) {
  const before = previous(state.lesson, state.index);
  return setBoard({
    fen: fenAt(state.lesson, state.index),
    lastMove: before ? before.uci : null,
    check: givesCheck(before),
    orientation: state.side,
    interactive: false,
    legalMoves: [],
    hintSquare: null,
  });
}

/** Board options for the lesson position at state.index in practice or on completion. */
function lineBoard(state) {
  const before = previous(state.lesson, state.index);
  const step = currentStep(state);
  const learner = isLearnerPly(state);
  return setBoard({
    fen: fenAt(state.lesson, state.index),
    lastMove: before ? before.uci : null,
    check: givesCheck(before),
    orientation: state.side,
    interactive: learner,
    legalMoves: learner ? [...step.legalBefore] : [],
    hintSquare: learner && state.hintShown ? step.uci.slice(0, 2) : null,
  });
}

function positionBoard(position, options = {}) {
  return setBoard({
    fen: position.fen,
    lastMove: position.lastMove,
    check: Boolean(position.check),
    interactive: options.interactive ?? false,
    legalMoves: options.interactive ? [...position.legalMoves] : [],
    hintSquare: null,
  });
}

// --- walkthrough (BR3.1) --------------------------------------------------------

function walkMessage(lesson, index) {
  return index === 0 ? { text: TEXT.walkStart, tone: "info" } : noteMessage(lesson.steps[index - 1]);
}

function walkTo(state, index) {
  if (state.phase !== "walkthrough" || index < 0 || index > state.lesson.steps.length) return unchanged(state);
  const next = { ...state, index, message: walkMessage(state.lesson, index) };
  return { state: next, effects: [walkBoard(next), arrowEffect(next)] };
}

function onLessonLoaded(state, { lesson }) {
  if (!isLesson(lesson)) return unchanged({ ...state, message: { text: TEXT.unreadable, tone: "error" } });
  const next = {
    ...initialState(),
    trainerSeq: state.trainerSeq,
    phase: "walkthrough",
    lesson,
    side: lesson.side,
    message: walkMessage(lesson, 0),
  };
  return { state: next, effects: [walkBoard(next), arrowEffect(next)] };
}

// --- practice (BR4.1-BR4.5) -----------------------------------------------------

/** Set up the ply at state.index: the learner's turn, a scheduled trainer reply, or completion. */
function enterPly(state, effects = []) {
  const step = currentStep(state);
  if (!step) {
    const done = { ...state, phase: "complete", trainerPending: null, misses: 0, hintShown: false, arrow: null };
    const last = state.lesson.steps[state.lesson.steps.length - 1];
    const message = { text: `${TEXT.complete}. The last move was ${moveLabel(last)}.`, tone: "success" };
    const progress = { type: "progress", lessonId: state.lesson.id, kind: state.lesson.kind || "opening", arrowShown: state.arrowShown };
    return { state: { ...done, message }, effects: [...effects, lineBoard(done), arrowEffect(done), progress] };
  }
  if (step.side === state.side) {
    return { state, effects: [...effects, lineBoard(state), arrowEffect(state)] };
  }
  const seq = state.trainerSeq + 1;
  const waiting = { ...state, trainerSeq: seq, trainerPending: seq };
  return { state: waiting, effects: [...effects, lineBoard(waiting), arrowEffect(waiting), { type: "scheduleTrainer", seq }] };
}

function onStartPractice(state, side) {
  if (state.phase === "choosing" || !state.lesson) return unchanged(state);
  const learner = SIDES.includes(side) ? side : state.side;
  const next = {
    ...state,
    phase: "practice",
    index: 0,
    side: learner,
    misses: 0,
    hintShown: false,
    arrow: null,
    arrowShown: false,
    offLine: null,
    free: null,
    request: null,
    trainerPending: null,
    message: { text: `You play ${sideName(learner)}; the trainer plays ${sideName(otherSide(learner))}.`, tone: "info" },
  };
  return enterPly(next);
}

function miss(state) {
  const step = currentStep(state);
  const misses = state.misses + 1;
  const arrow = misses >= ARROW_AFTER_MISSES ? step.uci : state.arrow;
  return { ...state, misses, arrow, arrowShown: state.arrowShown || arrow !== null };
}

function onCorrect(state, step) {
  const advanced = {
    ...state,
    index: state.index + 1,
    misses: 0,
    hintShown: false,
    arrow: null,
    message: noteMessage(step, "Correct. "),
  };
  return enterPly(advanced);
}

function onOffLine(state, step, uci) {
  const missed = miss(state);
  const next = {
    ...missed,
    phase: "offLine",
    offLine: { uci, fen: null, legalMoves: [], outcome: null, check: false },
    request: { purpose: "offLine", uci },
    message: { text: TEXT.offLine, tone: "warn" },
  };
  return { state: next, effects: [{ type: "positionMove", fen: step.fenBefore, uci }, arrowEffect(next)] };
}

function onLearnerMove(state, { uci }) {
  if (state.phase === "freePlay") return onFreeMove(state, uci);
  if (!isLearnerPly(state)) return { state, effects: [{ type: "rejectMove" }] };
  const step = currentStep(state);
  if (uci === step.uci) return onCorrect(state, step);
  if (step.legalBefore.includes(uci)) return onOffLine(state, step, uci);
  // The board only offers legal moves, so this is a defensive refusal.
  const missed = miss(state);
  const next = { ...missed, message: missed.arrow ? arrowMessage(step) : { text: TEXT.illegal, tone: "error" } };
  return { state: next, effects: [{ type: "rejectMove" }, arrowEffect(next)] };
}

function onRejectedTap(state) {
  if (!isLearnerPly(state)) return unchanged(state);
  const step = currentStep(state);
  const missed = miss(state);
  const next = { ...missed, message: missed.arrow ? arrowMessage(step) : { text: TEXT.illegal, tone: "error" } };
  return { state: next, effects: [arrowEffect(next)] };
}

function onTrainerMove(state, { seq }) {
  const step = currentStep(state);
  if (state.phase !== "practice" || state.trainerPending === null || seq !== state.trainerPending) return unchanged(state);
  if (!step || step.side === state.side) return unchanged({ ...state, trainerPending: null });
  const next = {
    ...state,
    index: state.index + 1,
    trainerPending: null,
    message: noteMessage(step, `${sideName(step.side)} plays `),
  };
  return enterPly(next);
}

function onHint(state) {
  if (!isLearnerPly(state)) return unchanged(state);
  const step = currentStep(state);
  const from = step.uci.slice(0, 2);
  const next = { ...state, hintShown: true, message: { text: `Move the piece on ${from}.`, tone: "info" } };
  return { state: next, effects: [setBoard({ hintSquare: from })] };
}

// --- off the line and free play (BR4.2, BR4.4) ----------------------------------

function onPositionResult(state, { data }) {
  const request = state.request;
  if (!request || !data || typeof data.fen !== "string" || !Array.isArray(data.legalMoves)) return unchanged(state);
  const position = {
    fen: data.fen,
    legalMoves: [...data.legalMoves],
    lastMove: request.uci,
    outcome: data.outcome || null,
    check: Boolean(data.check),
  };
  if (request.purpose === "offLine" && state.phase === "offLine") {
    const next = { ...state, request: null, offLine: { ...position, uci: request.uci } };
    return { state: next, effects: [positionBoard(position)] };
  }
  if (request.purpose === "free" && state.phase === "freePlay") {
    const free = { ...state.free, ...position };
    const text = position.outcome ? OUTCOME_TEXT[position.outcome] || TEXT.free : TEXT.free;
    const next = { ...state, request: null, free, message: { text, tone: position.outcome ? "warn" : "info" } };
    return { state: next, effects: [positionBoard(free, { interactive: !free.outcome })] };
  }
  return unchanged(state);
}

function onPositionError(state, { message }) {
  const request = state.request;
  const text = typeof message === "string" && message ? message : "Something went wrong. Try again.";
  if (!request) return unchanged(state);
  if (request.purpose === "offLine" && state.phase === "offLine") {
    const back = { ...state, phase: "practice", offLine: null, request: null, message: { text, tone: "error" } };
    return { state: back, effects: [lineBoard(back), arrowEffect(back)] };
  }
  if (request.purpose === "free" && state.phase === "freePlay") {
    return { state: { ...state, request: null, message: { text, tone: "error" } }, effects: [{ type: "rejectMove" }] };
  }
  return unchanged(state);
}

function onKeepPlaying(state) {
  if (state.phase !== "offLine" || !state.offLine || state.offLine.fen === null) return unchanged(state);
  const { uci, ...position } = state.offLine;
  const free = { ...position, lastMove: uci, returnIndex: state.index };
  const text = free.outcome ? OUTCOME_TEXT[free.outcome] || TEXT.free : TEXT.free;
  const next = { ...state, phase: "freePlay", offLine: null, free, message: { text, tone: "info" } };
  return { state: next, effects: [positionBoard(free, { interactive: !free.outcome }), arrowEffect(next)] };
}

function onFreeMove(state, uci) {
  if (state.request || !state.free.legalMoves.includes(uci)) {
    return { state: { ...state, message: { text: TEXT.illegal, tone: "error" } }, effects: [{ type: "rejectMove" }] };
  }
  const next = { ...state, request: { purpose: "free", uci } };
  return { state: next, effects: [{ type: "positionMove", fen: state.free.fen, uci }] };
}

function onBackToLine(state) {
  if (state.phase !== "offLine" && state.phase !== "freePlay") return unchanged(state);
  const index = state.free ? state.free.returnIndex : state.index;
  const back = { ...state, phase: "practice", index, offLine: null, free: null, request: null };
  const step = currentStep(back);
  const next = { ...back, message: back.arrow ? arrowMessage(step) : { text: TEXT.backToLine, tone: "info" } };
  return { state: next, effects: [lineBoard(next), arrowEffect(next)] };
}

function onOtherLessons(state) {
  if (state.phase === "choosing") return unchanged(state);
  const next = { ...initialState(), trainerSeq: state.trainerSeq };
  return { state: next, effects: [{ type: "arrow", uci: null, orientation: state.side }, { type: "showList" }] };
}

// --- reducer --------------------------------------------------------------------

function handle(state, event) {
  switch (event.type) {
    case "lessonLoaded": return onLessonLoaded(state, event);
    case "next": return walkTo(state, state.index + 1);
    case "back": return walkTo(state, state.index - 1);
    case "restart": return walkTo(state, 0);
    case "startPractice": return onStartPractice(state, event.side);
    case "switchSide": return onStartPractice(state, event.side);
    case "learnerMove": return onLearnerMove(state, event);
    case "rejectedTap": return onRejectedTap(state, event);
    case "trainerMove": return onTrainerMove(state, event);
    case "hint": return onHint(state);
    case "positionResult": return onPositionResult(state, event);
    case "positionError": return onPositionError(state, event);
    case "keepPlaying": return onKeepPlaying(state);
    case "backToLine": return onBackToLine(state);
    case "otherLessons": return onOtherLessons(state);
    default:
      throw new TypeError(`unknown trainer event ${JSON.stringify(event && event.type)}`);
  }
}

/**
 * Apply one event. Besides the handler's own effects, a scheduled trainer
 * reply that the new state no longer waits for is cancelled, and a request in
 * flight that the new state no longer waits for is aborted, whatever the
 * event was (Other lessons, Practise again, a side switch, Back to the line).
 */
export function reduce(state, event) {
  if (!event || typeof event.type !== "string") throw new TypeError("trainer event needs a type");
  const result = handle(state, event);
  const next = result.state;
  const lead = [];
  if (state.trainerPending !== null && next.trainerPending !== state.trainerPending && event.type !== "trainerMove") {
    lead.push({ type: "cancelTrainer" });
  }
  if (state.request && !next.request && event.type !== "positionResult" && event.type !== "positionError") {
    lead.push({ type: "abortRequest" });
  }
  return lead.length ? { state: next, effects: [...lead, ...result.effects] } : result;
}
