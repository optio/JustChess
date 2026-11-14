/**
 * JustChess blunder warnings (U4): the move hook and the dialog text. Pure
 * logic with injected dependencies, so tests/js/blunder.test.mjs drives it with
 * fakes; the DOM dialog lives in screens/blunder-dialog.js.
 *
 *   dialogText(warning, { opponent }) -> { title, body, confirmLabel, cancelLabel }
 *     BR3.2. warning is the server's Warning (mate_in_one or hanging_piece);
 *     opponent is "White" or "Black". Throws TypeError for a malformed warning.
 *
 *   createBlunderHook({ api, settings, openDialog, timeoutMs = 2500, timers, logger })
 *     -> beforeMove(uci, snapshot) -> Promise<true | false | { allow: false, message?, snapshot? }>
 *     api.checkMove(code, uci, version, { signal }) posts to
 *     /api/rooms/{code}/check-move (app.js binds the seat token).
 *     openDialog(text, { uci, snapshot, warning }) -> Promise<"confirm" | "cancel" | "superseded">
 *
 * Decisions (BR3.1, BR3.4 and the design review's failure mapping):
 *   - "Warn me before blunders" off: true at once, no request.
 *   - no warning: true. A warning: the dialog; "confirm" -> true, "cancel" -> false,
 *     "superseded" (a newer snapshot arrived) -> { allow: false }.
 *   - 409: { allow: false, message, snapshot } (the newer position takes over).
 *   - 400 or 403: { allow: false, message }.
 *   - timeout (2.5 s, AbortController), network failure, 404, 413, 422, 429, any
 *     5xx, any other status and a 200 with a malformed body: true (the move goes
 *     ahead) with console.warn.
 *   - The whole hook body sits in try/catch, so a failing settings read or a
 *     dialog that cannot be built also lets the move go ahead. It never throws.
 */

export const CHECK_TIMEOUT_MS = 2500;
export const MATE_TITLE = "This allows checkmate";
export const CANCEL_LABEL = "Choose another move";
export const CHOICES = Object.freeze({ confirm: "confirm", cancel: "cancel", superseded: "superseded" });

const PIECE_WORDS = Object.freeze({ K: "King", Q: "Queen", R: "Rook", B: "Bishop", N: "Knight" });
const HANGING_PIECES = new Set(["knight", "bishop", "rook", "queen"]);
const CAPTURERS = new Set(["pawn", "knight", "bishop", "rook", "queen", "king"]);
const SQUARE = /^[a-h][1-8]$/;
const SAN_MOVE = /^([KQRBN])?[a-h]?[1-8]?(x)?([a-h][1-8])(?:=([QRBN]))?$/;
const OPPONENTS = new Set(["White", "Black"]);

function nonEmpty(value) {
  return typeof value === "string" && value.length > 0;
}

/** "Bxa3+" -> "Bishop takes a3"; "g4" -> "Pawn to g4"; "O-O" -> "Castling kingside". Unknown text is returned as is. */
export function moveWords(san) {
  const plain = String(san ?? "").replace(/[+#]+$/, "");
  if (plain === "O-O-O") return "Castling queenside";
  if (plain === "O-O") return "Castling kingside";
  const match = SAN_MOVE.exec(plain);
  if (!match) return String(san ?? "");
  const [, piece, takes, square, promotion] = match;
  const words = `${piece ? PIECE_WORDS[piece] : "Pawn"} ${takes ? "takes" : "to"} ${square}`;
  return promotion ? `${words}, promoting to a ${PIECE_WORDS[promotion].toLowerCase()}` : words;
}

/** True for a Warning the dialog can show. */
export function isWarning(value) {
  if (!value || typeof value !== "object" || !nonEmpty(value.move)) return false;
  if (value.kind === "mate_in_one") return nonEmpty(value.mate);
  if (value.kind !== "hanging_piece") return false;
  const { piece, square, capturer, defended } = value;
  return HANGING_PIECES.has(piece) && SQUARE.test(String(square)) && typeof defended === "boolean"
    && Boolean(capturer) && CAPTURERS.has(capturer.piece) && SQUARE.test(String(capturer.square));
}

/** True for a CheckResult: { warning: Warning | null, san, version }. */
export function isCheckResult(data) {
  return Boolean(data) && typeof data === "object" && (data.warning === null || isWarning(data.warning))
    && nonEmpty(data.san) && Number.isInteger(data.version);
}

export function dialogText(warning, { opponent } = {}) {
  if (!isWarning(warning)) throw new TypeError("dialogText needs a mate_in_one or hanging_piece warning");
  if (!OPPONENTS.has(opponent)) throw new TypeError(`dialogText needs the opponent's colour name, not ${JSON.stringify(opponent)}`);
  const labels = { confirmLabel: `Play ${warning.move} anyway`, cancelLabel: CANCEL_LABEL };
  if (warning.kind === "mate_in_one") {
    return { title: MATE_TITLE, body: `${opponent} can play ${warning.mate}.`, ...labels };
  }
  const { piece, square, capturer, defended } = warning;
  const ending = defended ? "you lose material" : "nothing takes back";
  return {
    title: `Your ${piece} can be taken for free`,
    body: `After ${moveWords(warning.move)}, ${opponent}'s ${capturer.piece} on ${capturer.square} takes your ${piece} on ${square} and ${ending}.`,
    ...labels,
  };
}

/** The opponent of the side to move, as "White" or "Black". */
function opponentOf(snapshot) {
  const mover = snapshot.turn === "white" || snapshot.turn === "black" ? snapshot.turn : snapshot.colour;
  if (mover !== "white" && mover !== "black") throw new TypeError("the snapshot names no side to move");
  return mover === "white" ? "Black" : "White";
}

export function createBlunderHook({ api, settings, openDialog, timeoutMs = CHECK_TIMEOUT_MS, timers = globalThis, logger = console } = {}) {
  if (!api || typeof api.checkMove !== "function") throw new TypeError("createBlunderHook needs api.checkMove");
  if (!settings || typeof settings.get !== "function") throw new TypeError("createBlunderHook needs the settings store");
  if (typeof openDialog !== "function") throw new TypeError("createBlunderHook needs openDialog");

  function goAhead(reason, detail) {
    if (detail === undefined) logger.warn(`JustChess: the blunder check was skipped (${reason}); the move goes ahead`);
    else logger.warn(`JustChess: the blunder check was skipped (${reason}); the move goes ahead`, detail);
    return true;
  }

  /** Post the check; resolves the api's answer, or { ok: false, status: 0, timedOut: true } after timeoutMs. */
  async function requestCheck(uci, snapshot) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    let timer = null;
    const timeout = new Promise((resolve) => {
      timer = timers.setTimeout(() => {
        if (controller) controller.abort();
        resolve({ ok: false, status: 0, timedOut: true });
      }, timeoutMs);
    });
    try {
      const request = api.checkMove(snapshot.code, uci, snapshot.version, controller ? { signal: controller.signal } : {});
      return await Promise.race([request, timeout]);
    } finally {
      timers.clearTimeout(timer);
    }
  }

  async function confirmWarning(warning, uci, snapshot) {
    const text = dialogText(warning, { opponent: opponentOf(snapshot) });
    const choice = await openDialog(text, { uci, snapshot, warning });
    if (choice === CHOICES.confirm) return true;
    if (choice === CHOICES.superseded) return { allow: false };
    return false;
  }

  async function decide(answer, uci, snapshot) {
    if (answer.ok) {
      if (!isCheckResult(answer.data)) return goAhead("the answer was not a check result");
      if (answer.data.warning === null) return true;
      return confirmWarning(answer.data.warning, uci, snapshot);
    }
    if (answer.status === 409) {
      const refusal = { allow: false, message: answer.message || null };
      if (answer.snapshot && typeof answer.snapshot === "object") refusal.snapshot = answer.snapshot;
      return refusal;
    }
    if (answer.status === 400 || answer.status === 403) return { allow: false, message: answer.message || null };
    if (answer.timedOut) return goAhead(`no answer within ${timeoutMs} ms`);
    return goAhead(answer.status === 0 ? "the server could not be reached" : `the server answered ${answer.status}`);
  }

  return async function beforeMove(uci, snapshot) {
    try {
      if (!settings.get("blunderWarnings")) return true;
      if (!snapshot || typeof snapshot.code !== "string" || !Number.isInteger(snapshot.version)) {
        return goAhead("no current snapshot");
      }
      const answer = await requestCheck(uci, snapshot);
      if (!answer || typeof answer !== "object") return goAhead("no answer");
      return await decide(answer, uci, snapshot);
    } catch (error) {
      return goAhead("it failed", error);
    }
  };
}
