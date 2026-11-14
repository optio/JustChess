/**
 * Board geometry for the JustChess board (U2). Pure functions, no DOM.
 *
 * Squares are algebraic strings ("a1".."h8"). A piece is a FEN letter
 * (upper case white, lower case black). A piece map is a plain object
 * { square: letter } holding only occupied squares.
 *
 * Rules implemented here: BR1.1 (square colour), BR1.2 (orientation),
 * BR1.3 (label placement), BR2.1/BR2.2 (targets, promotion), BR2.4 (focus
 * moves), BR3.1 (king in check), BR3.2 (accessible names), BR4.1 (move diff).
 *
 * Imported by board.js in the browser and by tests/js/geometry.test.mjs in Node.
 */

export const FILES = "abcdefgh";
export const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const PIECE_NAMES = { k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" };
const PIECE_LETTERS = "kqrbnpKQRBNP";
const SQUARE_PATTERN = /^[a-h][1-8]$/;
const UCI_PATTERN = /^([a-h][1-8])([a-h][1-8])([qrbn])?$/;

/** Thrown by parseFen for a malformed position (the caller's bug). */
export class FenError extends Error {
  constructor(message, fen) {
    super(message);
    this.name = "FenError";
    this.fen = fen;
  }
}

export function isSquare(value) {
  return typeof value === "string" && SQUARE_PATTERN.test(value);
}

export function fileIndex(square) {
  return FILES.indexOf(square[0]);
}

export function rankIndex(square) {
  return Number(square[1]) - 1;
}

export function squareAt(file, rank) {
  if (file < 0 || file > 7 || rank < 0 || rank > 7) return null;
  return FILES[file] + String(rank + 1);
}

/** BR1.1: dark when file + rank is even (a=0, rank 1=0), so a1 is dark. */
export function isDarkSquare(square) {
  return (fileIndex(square) + rankIndex(square)) % 2 === 0;
}

function checkOrientation(orientation) {
  if (orientation !== "white" && orientation !== "black") {
    throw new TypeError(`orientation must be "white" or "black", got ${JSON.stringify(orientation)}`);
  }
}

/**
 * BR1.2: the 8 visual rows, top to bottom, each listing squares left to
 * right. White: rank 8 on top, file a on the left. Black: both reversed.
 */
export function squaresInOrder(orientation) {
  checkOrientation(orientation);
  const rows = [];
  for (let row = 0; row < 8; row += 1) {
    const rank = orientation === "white" ? 7 - row : row;
    const squares = [];
    for (let col = 0; col < 8; col += 1) {
      const file = orientation === "white" ? col : 7 - col;
      squares.push(squareAt(file, rank));
    }
    rows.push(squares);
  }
  return rows;
}

/**
 * BR1.3, inside mode: the label text a square carries. File letters sit in
 * the visual bottom row, rank numbers in the visual left column.
 */
export function squareLabels(square, orientation) {
  const rows = squaresInOrder(orientation);
  return {
    file: rows[7].includes(square) ? square[0] : null,
    rank: rows.some((row) => row[0] === square) ? square[1] : null,
  };
}

/** BR1.3, frame mode: file letters left to right, rank numbers top to bottom. */
export function frameLabels(orientation) {
  const rows = squaresInOrder(orientation);
  return {
    files: rows[7].map((square) => square[0]),
    ranks: rows.map((row) => row[0][1]),
  };
}

function parsePlacement(placement, fen) {
  const ranks = placement.split("/");
  if (ranks.length !== 8) throw new FenError(`FEN needs 8 ranks, found ${ranks.length}`, fen);
  const pieces = {};
  ranks.forEach((row, index) => {
    const rank = 7 - index;
    let file = 0;
    for (const char of row) {
      if (char >= "1" && char <= "8") {
        file += Number(char);
      } else if (PIECE_LETTERS.includes(char)) {
        if (file > 7) throw new FenError(`rank ${rank + 1} has more than 8 squares`, fen);
        pieces[squareAt(file, rank)] = char;
        file += 1;
      } else {
        throw new FenError(`unexpected character ${JSON.stringify(char)} in FEN`, fen);
      }
    }
    if (file !== 8) throw new FenError(`rank ${rank + 1} has ${file} squares, not 8`, fen);
  });
  return pieces;
}

/**
 * Parse a FEN into { pieces, turn }. Only the placement and side-to-move
 * fields are used. Throws FenError when the FEN is malformed or a side has
 * other than one king.
 */
export function parseFen(fen) {
  if (typeof fen !== "string" || fen.trim() === "") throw new FenError("FEN must be a non-empty string", fen);
  const [placement, turn = "w"] = fen.trim().split(/\s+/);
  if (turn !== "w" && turn !== "b") throw new FenError(`side to move must be w or b, got ${JSON.stringify(turn)}`, fen);
  const pieces = parsePlacement(placement, fen);
  const letters = Object.values(pieces);
  for (const king of ["K", "k"]) {
    const count = letters.filter((letter) => letter === king).length;
    if (count !== 1) throw new FenError(`FEN must have exactly one ${king === "K" ? "white" : "black"} king, found ${count}`, fen);
  }
  return { pieces, turn: turn === "w" ? "white" : "black" };
}

export function pieceColour(letter) {
  return letter === letter.toUpperCase() ? "white" : "black";
}

export function samePieces(a, b) {
  const keysA = Object.keys(a);
  if (keysA.length !== Object.keys(b).length) return false;
  return keysA.every((square) => a[square] === b[square]);
}

/** Split a UCI move into { from, to, promotion }, or null when malformed. */
export function parseUci(uci) {
  const match = typeof uci === "string" ? UCI_PATTERN.exec(uci) : null;
  if (!match) return null;
  return { from: match[1], to: match[2], promotion: match[3] || null };
}

/** Accepts { from, to } or a UCI string; returns { from, to } or null. */
export function normaliseLastMove(lastMove) {
  if (lastMove == null) return null;
  if (typeof lastMove === "string") {
    const move = parseUci(lastMove);
    return move ? { from: move.from, to: move.to } : null;
  }
  if (isSquare(lastMove.from) && isSquare(lastMove.to)) return { from: lastMove.from, to: lastMove.to };
  return null;
}

/** BR2.1: the target squares of the moves in legalMoves that start on square. */
export function targetsFrom(square, legalMoves) {
  const targets = new Set();
  for (const uci of legalMoves) {
    const move = parseUci(uci);
    if (move && move.from === square) targets.add(move.to);
  }
  return targets;
}

/** BR2.2: true when from-to exists only as promotion moves (5th UCI character). */
export function isPromotionTarget(from, to, legalMoves) {
  let promotes = false;
  for (const uci of legalMoves) {
    const move = parseUci(uci);
    if (!move || move.from !== from || move.to !== to) continue;
    if (!move.promotion) return false;
    promotes = true;
  }
  return promotes;
}

function castlingRook(piece, from, to) {
  if (piece.toLowerCase() !== "k" || Math.abs(fileIndex(to) - fileIndex(from)) !== 2) return null;
  const rank = rankIndex(from);
  return fileIndex(to) > fileIndex(from)
    ? { from: squareAt(7, rank), to: squareAt(5, rank) }
    : { from: squareAt(0, rank), to: squareAt(3, rank) };
}

function enPassantVictim(prev, piece, from, to) {
  if (piece.toLowerCase() !== "p" || fileIndex(from) === fileIndex(to) || prev[to]) return null;
  return squareAt(fileIndex(to), rankIndex(from));
}

/**
 * Apply a move to a piece map (no legality check). Handles castling by the
 * king's two-square move, en passant and promotion. Used for optimistic
 * placement and to verify diffMove.
 */
export function applyMove(pieces, from, to, promotion = null) {
  const piece = pieces[from];
  if (!piece) return null;
  const next = { ...pieces };
  delete next[from];
  const victim = enPassantVictim(pieces, piece, from, to);
  if (victim) delete next[victim];
  const rook = castlingRook(piece, from, to);
  if (rook && next[rook.from]) {
    next[rook.to] = next[rook.from];
    delete next[rook.from];
  }
  const white = piece === piece.toUpperCase();
  next[to] = promotion ? (white ? promotion.toUpperCase() : promotion.toLowerCase()) : piece;
  return next;
}

function promotionOf(piece, nextPiece) {
  if (piece.toLowerCase() !== "p" || !nextPiece || nextPiece.toLowerCase() === "p") return null;
  return nextPiece.toLowerCase();
}

/**
 * BR4.1: describe how to animate prev -> next given lastMove. Returns
 * { moves: [{ piece, from, to, becomes }], captured: [{ piece, square }] }
 * or null when the change is not exactly that one move (redraw instead).
 */
export function diffMove(prev, next, lastMove) {
  const move = normaliseLastMove(lastMove);
  if (!move) return null;
  const { from, to } = move;
  const piece = prev[from];
  if (!piece || !next[to] || next[from]) return null;
  if (pieceColour(next[to]) !== pieceColour(piece)) return null;
  const promotion = promotionOf(piece, next[to]);
  if (next[to] !== piece && !promotion) return null;
  const expected = applyMove(prev, from, to, promotion);
  if (!samePieces(expected, next)) return null;
  const moves = [{ piece, from, to, becomes: next[to] }];
  const rook = castlingRook(piece, from, to);
  if (rook && prev[rook.from]) moves.push({ piece: prev[rook.from], from: rook.from, to: rook.to, becomes: prev[rook.from] });
  const captured = [];
  const victim = enPassantVictim(prev, piece, from, to);
  if (victim && prev[victim]) captured.push({ piece: prev[victim], square: victim });
  if (prev[to]) captured.push({ piece: prev[to], square: to });
  return { moves, captured };
}

const ARROWS = {
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
};

/** BR2.4: move focus one square in visual space, stopping at the edges. */
export function moveFocus(square, key, orientation) {
  checkOrientation(orientation);
  const step = ARROWS[key];
  if (!step || !isSquare(square)) return square;
  const sign = orientation === "white" ? 1 : -1;
  const target = squareAt(fileIndex(square) + step[0] * sign, rankIndex(square) - step[1] * sign);
  return target || square;
}

export function pieceName(letter) {
  return `${pieceColour(letter)} ${PIECE_NAMES[letter.toLowerCase()]}`;
}

/** BR3.2: "e4, white pawn", "e4, empty", plus ", selected" and ", legal move". */
export function squareName(square, piece, { selected = false, target = false } = {}) {
  let name = `${square}, ${piece ? pieceName(piece) : "empty"}`;
  if (selected) name += ", selected";
  if (target) name += ", legal move";
  return name;
}

export function kingSquare(pieces, colour) {
  const king = colour === "white" ? "K" : "k";
  return Object.keys(pieces).find((square) => pieces[square] === king) || null;
}

/** BR3.1: the square of the side-to-move's king when check is true, else null. */
export function checkSquare(pieces, turn, check) {
  return check ? kingSquare(pieces, turn) : null;
}
