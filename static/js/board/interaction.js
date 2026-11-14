/**
 * Board interaction state machine (U2). A pure reducer, no DOM:
 *
 *   reduce(state, event, ctx) -> { state, effects }
 *
 * board.js keeps the state, calls reduce for every user or caller event, and
 * runs the returned effects. Rules: BR2.1 (selection), BR2.2 (promotion),
 * BR2.3 (pending lock), BR2.4 (Escape); functional-spec.md state machine.
 *
 * State: { mode, selected, promoting, pending }
 *   mode       "idle" | "selected" | "promoting" | "pending" | "locked"
 *   selected   square or null
 *   promoting  { from, to } while the picker is open, else null
 *   pending    { uci, from, to, promotion } after a move was emitted, else null.
 *              It survives "locked": it ends only with a position or reject.
 *
 * ctx: { legalMoves: string[], interactive: boolean, shown: pieceMap }
 *
 * Events:
 *   { type: "tap", square }                 pointer tap, Enter or Space
 *   { type: "escape" }
 *   { type: "promotionChosen", piece }       "q"|"r"|"b"|"n" or null (cancel)
 *   { type: "setInteractive", value }
 *   { type: "position", next, lastMove }     the caller set a new position
 *   { type: "legalMoves" }                   ctx.legalMoves changed, same position
 *   { type: "reject" }                       the caller refused the pending move
 *
 * Effects (run by board.js in order):
 *   { type: "applyOptimistic", from, to, promotion }  show the piece on the target now
 *   { type: "emitMove", uci }                          call onMove once
 *   { type: "openPromotion", from, to }
 *   { type: "closePromotion" }                         resolve an open picker with null
 *   { type: "render", animation }                      draw the event's next position;
 *                                                      animation is a diffMove result or null
 *                                                      (null when it equals the shown,
 *                                                      e.g. optimistic, position)
 *   { type: "slideBack", from, to }                    undo the optimistic move (to -> from)
 *   { type: "focus", square }
 *   { type: "rejectedTap", from, to }                  U6: a piece was selected and the tap
 *                                                      chose an empty square or an opponent's
 *                                                      piece that is not one of its targets.
 *                                                      board.js calls onRejectedTap(from, to).
 *
 * rejectedTap never comes from: retapping the selected piece (deselect),
 * Escape, tapping another own piece (it reselects, or clears the selection
 * when that piece cannot move), or any tap while locked, pending or promoting.
 */

import { diffMove, isPromotionTarget, pieceColour, samePieces, targetsFrom } from "./geometry.js";

export function initialState(interactive = false) {
  return { mode: interactive ? "idle" : "locked", selected: null, promoting: null, pending: null };
}

function restingMode(state, ctx) {
  if (state.pending) return "pending";
  if (!ctx.interactive) return "locked";
  if (state.promoting) return "promoting";
  return state.selected ? "selected" : "idle";
}

function settle(state, ctx, effects = []) {
  return { state: { ...state, mode: restingMode(state, ctx) }, effects };
}

function emit(state, ctx, from, to, promotion) {
  const uci = from + to + (promotion || "");
  const pending = { uci, from, to, promotion: promotion || null };
  return settle({ ...state, selected: null, promoting: null, pending }, ctx, [
    { type: "applyOptimistic", from, to, promotion: promotion || null },
    { type: "emitMove", uci },
    { type: "focus", square: to },
  ]);
}

function onTap(state, event, ctx) {
  if (state.mode === "locked" || state.mode === "pending" || state.mode === "promoting") {
    return { state, effects: [] };
  }
  const { square } = event;
  if (state.selected && targetsFrom(state.selected, ctx.legalMoves).has(square)) {
    if (isPromotionTarget(state.selected, square, ctx.legalMoves)) {
      const promoting = { from: state.selected, to: square };
      return settle({ ...state, promoting }, ctx, [{ type: "openPromotion", ...promoting }]);
    }
    return emit(state, ctx, state.selected, square, null);
  }
  if (targetsFrom(square, ctx.legalMoves).size > 0) {
    const selected = state.selected === square ? null : square;
    return settle({ ...state, selected }, ctx);
  }
  if (state.selected && !isOwnPiece(ctx.shown, state.selected, square)) {
    return settle({ ...state, selected: null }, ctx, [{ type: "rejectedTap", from: state.selected, to: square }]);
  }
  return settle({ ...state, selected: null }, ctx);
}

/** True when square holds a piece of the same colour as the piece on selected. */
function isOwnPiece(shown, selected, square) {
  const mover = shown && shown[selected];
  const other = shown && shown[square];
  return Boolean(mover && other) && pieceColour(mover) === pieceColour(other);
}

function onPromotionChosen(state, event, ctx) {
  if (state.mode !== "promoting" || !state.promoting) return { state, effects: [] };
  const { from, to } = state.promoting;
  if (!event.piece) return settle({ ...state, selected: null, promoting: null }, ctx, [{ type: "focus", square: from }]);
  return emit(state, ctx, from, to, event.piece);
}

function onSetInteractive(state, event, ctx) {
  const nextCtx = { ...ctx, interactive: Boolean(event.value) };
  if (nextCtx.interactive) return settle(state, nextCtx);
  const effects = state.promoting ? [{ type: "closePromotion" }] : [];
  return { state: { ...state, selected: null, promoting: null, mode: state.pending ? "pending" : "locked" }, effects };
}

function keepSelection(state, ctx) {
  return state.selected && targetsFrom(state.selected, ctx.legalMoves).size > 0 ? state.selected : null;
}

function onPosition(state, event, ctx) {
  const effects = state.promoting ? [{ type: "closePromotion" }] : [];
  const animation = samePieces(ctx.shown, event.next) ? null : diffMove(ctx.shown, event.next, event.lastMove);
  effects.push({ type: "render", animation });
  // A picker closed by the update ends like a cancel: the selection clears.
  const selected = state.promoting ? null : keepSelection(state, ctx);
  return settle({ ...state, pending: null, promoting: null, selected }, ctx, effects);
}

function onLegalMoves(state, ctx) {
  return settle({ ...state, selected: keepSelection(state, ctx) }, ctx);
}

function onReject(state, ctx) {
  if (!state.pending) return { state, effects: [] };
  const { from, to } = state.pending;
  return settle({ ...state, pending: null }, ctx, [
    { type: "slideBack", from, to },
    { type: "focus", square: from },
  ]);
}

function onEscape(state, ctx) {
  if (state.mode === "promoting") {
    return settle({ ...state, promoting: null, selected: null }, ctx, [{ type: "closePromotion" }]);
  }
  if (state.mode === "selected") return settle({ ...state, selected: null }, ctx);
  return { state, effects: [] };
}

export function reduce(state, event, ctx) {
  switch (event.type) {
    case "tap": return onTap(state, event, ctx);
    case "escape": return onEscape(state, ctx);
    case "promotionChosen": return onPromotionChosen(state, event, ctx);
    case "setInteractive": return onSetInteractive(state, event, ctx);
    case "position": return onPosition(state, event, ctx);
    case "legalMoves": return onLegalMoves(state, ctx);
    case "reject": return onReject(state, ctx);
    default:
      throw new TypeError(`unknown board event ${JSON.stringify(event && event.type)}`);
  }
}
