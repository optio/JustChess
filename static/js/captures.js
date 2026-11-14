/**
 * JustChess captured pieces (P2 U1, BR1.6). Pure functions, no DOM.
 *
 *   capturedPieces(moves, pending = null) -> { byWhite: letter[], byBlack: letter[] }
 *   captureLabel(pieces, owner) -> "Pieces you captured: black pawn, black knight"
 *   sanToMove(pieces, san, colour) -> { from, to, promotion }
 *
 * The list is derived from the move list, never counted from the board: the
 * game is replayed from the start position with geometry.js's applyMove, and
 * each capture's victim (en passant included) is recorded. byWhite holds the
 * black pieces White took, byBlack the white pieces Black took, each ordered
 * queen, rook, bishop, knight, pawn.
 *
 * moves: the snapshot's moveList rows ({ white, black } SAN) or a flat SAN
 * array. The server sends SAN only, so SAN is resolved here: the piece that
 * can reach the target, narrowed by the disambiguation, then by legality (a
 * pinned piece is not a candidate). pending: the player's own optimistic move
 * as UCI or { from, to, promotion }, applied after the list.
 *
 * A move that cannot be resolved throws SanError: the caller logs it and hides
 * the row rather than show a row that disagrees with the move list.
 */

import { START_FEN, applyMove, fileIndex, parseFen, parseUci, pieceColour, pieceName, rankIndex, squareAt } from "./board/geometry.js";

export const CAPTURE_ORDER = "qrbnp";

/** Thrown when a SAN move cannot be resolved against the replayed position. */
export class SanError extends Error {
  constructor(message, san) {
    super(message);
    this.name = "SanError";
    this.san = san;
  }
}

const SAN_PATTERN = /^([KQRBN])?([a-h])?([1-8])?(x)?([a-h][1-8])(?:=?([QRBN]))?$/;
const KNIGHT_STEPS = [[1, 2], [2, 1], [2, -1], [1, -2], [-1, -2], [-2, -1], [-2, 1], [-1, 2]];
const KING_STEPS = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
const ROOK_RAYS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const BISHOP_RAYS = [[1, 1], [1, -1], [-1, 1], [-1, -1]];

function letterFor(type, colour) {
  return colour === "white" ? type.toUpperCase() : type.toLowerCase();
}

function step(square, df, dr) {
  return squareAt(fileIndex(square) + df, rankIndex(square) + dr);
}

function slides(pieces, from, to, rays) {
  for (const [df, dr] of rays) {
    for (let square = step(from, df, dr); square; square = step(square, df, dr)) {
      if (square === to) return true;
      if (pieces[square]) break;
    }
  }
  return false;
}

function leaps(from, to, steps) {
  return steps.some(([df, dr]) => step(from, df, dr) === to);
}

/** Can the piece on `from` reach `to` by its movement rule (pawns excluded), ignoring check? */
function reaches(pieces, from, to) {
  switch (pieces[from].toLowerCase()) {
    case "n": return leaps(from, to, KNIGHT_STEPS);
    case "k": return leaps(from, to, KING_STEPS);
    case "r": return slides(pieces, from, to, ROOK_RAYS);
    case "b": return slides(pieces, from, to, BISHOP_RAYS);
    case "q": return slides(pieces, from, to, ROOK_RAYS) || slides(pieces, from, to, BISHOP_RAYS);
    default: return false;
  }
}

function pawnAttacks(from, to, colour) {
  const dr = colour === "white" ? 1 : -1;
  return step(from, 1, dr) === to || step(from, -1, dr) === to;
}

function attacked(pieces, square, byColour) {
  return Object.entries(pieces).some(([from, letter]) => {
    if (pieceColour(letter) !== byColour) return false;
    return letter.toLowerCase() === "p" ? pawnAttacks(from, square, byColour) : reaches(pieces, from, square);
  });
}

function leavesKingSafe(pieces, from, to, colour) {
  const after = applyMove(pieces, from, to, null);
  const king = Object.keys(after).find((square) => after[square] === letterFor("k", colour));
  return Boolean(king) && !attacked(after, king, colour === "white" ? "black" : "white");
}

function pawnOrigins(pieces, to, colour, isCapture, fromFile) {
  const dr = colour === "white" ? 1 : -1;
  const pawn = letterFor("p", colour);
  if (isCapture) {
    return [-1, 1]
      .map((df) => step(to, df, -dr))
      .filter((square) => square && pieces[square] === pawn && (!fromFile || square[0] === fromFile));
  }
  const one = step(to, 0, -dr);
  if (one && pieces[one] === pawn) return [one];
  const two = one && !pieces[one] ? step(one, 0, -dr) : null;
  const startRank = colour === "white" ? 1 : 6;
  return two && pieces[two] === pawn && rankIndex(two) === startRank ? [two] : [];
}

function castle(san, colour) {
  const rank = colour === "white" ? "1" : "8";
  if (/^(O-O|0-0)$/.test(san)) return { from: `e${rank}`, to: `g${rank}`, promotion: null };
  if (/^(O-O-O|0-0-0)$/.test(san)) return { from: `e${rank}`, to: `c${rank}`, promotion: null };
  return null;
}

/** Resolve one SAN move for `colour` against a piece map. Throws SanError. */
export function sanToMove(pieces, san, colour) {
  const plain = String(san ?? "").replace(/[+#!?]+$/, "");
  const castling = castle(plain, colour);
  if (castling) return castling;
  const match = SAN_PATTERN.exec(plain);
  if (!match) throw new SanError(`not a SAN move: ${JSON.stringify(san)}`, san);
  const [, type = "P", fromFile, fromRank, capture, to, promotion] = match;
  let origins;
  if (type === "P") {
    origins = pawnOrigins(pieces, to, colour, Boolean(capture), fromFile);
  } else {
    const letter = letterFor(type, colour);
    origins = Object.keys(pieces).filter((square) => pieces[square] === letter
      && (!fromFile || square[0] === fromFile) && (!fromRank || square[1] === fromRank)
      && reaches(pieces, square, to));
  }
  if (origins.length > 1) origins = origins.filter((from) => leavesKingSafe(pieces, from, to, colour));
  if (origins.length !== 1) {
    throw new SanError(`${JSON.stringify(san)} matches ${origins.length} ${colour} pieces`, san);
  }
  return { from: origins[0], to, promotion: promotion ? promotion.toLowerCase() : null };
}

/** The piece a move from-to removes from `pieces` (en passant included), or null. */
export function victimOf(pieces, from, to) {
  const piece = pieces[from];
  if (!piece) return null;
  if (pieces[to]) return pieceColour(pieces[to]) === pieceColour(piece) ? null : pieces[to];
  if (piece.toLowerCase() === "p" && from[0] !== to[0]) {
    const square = squareAt(fileIndex(to), rankIndex(from));
    return pieces[square] && pieceColour(pieces[square]) !== pieceColour(piece) ? pieces[square] : null;
  }
  return null;
}

function flatten(moves) {
  if (!Array.isArray(moves)) throw new TypeError("capturedPieces needs a move list");
  const sans = [];
  for (const entry of moves) {
    if (typeof entry === "string") sans.push(entry);
    else if (entry && typeof entry === "object") {
      if (entry.white) sans.push(entry.white);
      if (entry.black) sans.push(entry.black);
    }
  }
  return sans;
}

function normalisePending(pending) {
  if (pending == null) return null;
  const move = typeof pending === "string" ? parseUci(pending) : pending;
  if (!move || typeof move.from !== "string" || typeof move.to !== "string") throw new TypeError("pending must be a UCI move");
  return { from: move.from, to: move.to, promotion: move.promotion || null };
}

function byOrder(a, b) {
  return CAPTURE_ORDER.indexOf(a.toLowerCase()) - CAPTURE_ORDER.indexOf(b.toLowerCase());
}

export function capturedPieces(moves, pending = null) {
  const sans = flatten(moves);
  const extra = normalisePending(pending);
  let pieces = parseFen(START_FEN).pieces;
  const result = { byWhite: [], byBlack: [] };
  const play = ({ from, to, promotion }, colour) => {
    const victim = victimOf(pieces, from, to);
    if (victim) (colour === "white" ? result.byWhite : result.byBlack).push(victim);
    const next = applyMove(pieces, from, to, promotion);
    if (!next) throw new SanError(`no piece on ${from}`, `${from}${to}`);
    pieces = next;
  };
  sans.forEach((san, ply) => {
    const colour = ply % 2 === 0 ? "white" : "black";
    play(sanToMove(pieces, san, colour), colour);
  });
  if (extra) play(extra, sans.length % 2 === 0 ? "white" : "black");
  result.byWhite.sort(byOrder);
  result.byBlack.sort(byOrder);
  return result;
}

/**
 * The accessible label of one captured row. owner: "you", "opponent",
 * "white" or "black" (a watcher sees the colours).
 */
export function captureLabel(pieces, owner) {
  const who = { you: "you", opponent: "your opponent", white: "White", black: "Black" }[owner];
  if (!who) throw new TypeError(`unknown captured-row owner ${JSON.stringify(owner)}`);
  const names = (pieces || []).map((letter) => pieceName(letter));
  return `Pieces ${who} captured: ${names.length ? names.join(", ") : "none"}`;
}
