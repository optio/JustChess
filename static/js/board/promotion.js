/**
 * Promotion picker for the JustChess board (U2, BR2.2).
 *
 *   openPromotion(anchorSquareEl, colour, piecePath) -> Promise<"q"|"r"|"b"|"n"|null>
 *
 * Renders div[role=dialog][aria-label="Promote pawn to"] with queen, rook,
 * bishop and knight buttons in a column over the promotion square, opening
 * towards the board's centre. Focus starts on the queen and is trapped
 * inside; arrow keys move between pieces; Enter or Space picks; Escape or a
 * pointer press outside resolves null. Focus returns to the square on close.
 *
 * The returned promise also has cancel(), which closes the picker and resolves
 * null; board.js uses it when the board locks or a new position arrives.
 * Requires the board DOM from board.js (the square must sit inside
 * .board-inlay) and board.css.
 */

const CHOICES = [
  { piece: "q", name: "Queen" },
  { piece: "r", name: "Rook" },
  { piece: "b", name: "Bishop" },
  { piece: "n", name: "Knight" },
];

function pieceFile(colour, piece) {
  return `${colour === "white" ? "w" : "b"}${piece.toUpperCase()}.svg`;
}

function buildDialog(colour, piecePath) {
  const dialog = document.createElement("div");
  dialog.className = "promo";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-label", "Promote pawn to");
  dialog.setAttribute("data-testid", "board-promotion");
  const buttons = CHOICES.map(({ piece, name }) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.piece = piece;
    button.setAttribute("aria-label", name);
    button.setAttribute("data-testid", `board-promotion-${name.toLowerCase()}`);
    const img = document.createElement("img");
    img.src = piecePath + pieceFile(colour, piece);
    img.alt = "";
    if (colour === "black") img.className = "is-black";
    button.append(img);
    dialog.append(button);
    return button;
  });
  return { dialog, buttons };
}

function place(dialog, anchor, container) {
  const box = container.getBoundingClientRect();
  const square = anchor.getBoundingClientRect();
  const opensUp = square.top + square.height / 2 > box.top + box.height / 2;
  dialog.classList.toggle("opens-up", opensUp);
  // Absolute offsets are measured from the padding box, inside the inlay border.
  const border = container.clientLeft;
  dialog.style.left = `${square.left - box.left - border}px`;
  dialog.style.width = `${square.width}px`;
  if (opensUp) dialog.style.bottom = `${box.bottom - square.bottom - border}px`;
  else dialog.style.top = `${square.top - box.top - border}px`;
}

export function openPromotion(anchorSquareEl, colour, piecePath) {
  const container = anchorSquareEl && anchorSquareEl.closest(".board-inlay");
  if (!container) return Promise.reject(new Error("openPromotion: the anchor square must be inside a .board-inlay"));
  if (colour !== "white" && colour !== "black") return Promise.reject(new TypeError(`openPromotion: bad colour ${colour}`));

  const { dialog, buttons } = buildDialog(colour, piecePath);
  let finish;
  const promise = new Promise((resolve) => {
    let done = false;
    finish = (choice) => {
      if (done) return;
      done = true;
      document.removeEventListener("pointerdown", onOutside, true);
      dialog.remove();
      if (anchorSquareEl.isConnected) anchorSquareEl.focus({ preventScroll: true });
      resolve(choice);
    };
  });

  function onOutside(event) {
    if (!dialog.contains(event.target)) finish(null);
  }

  function onKeydown(event) {
    const index = buttons.indexOf(document.activeElement);
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      finish(null);
    } else if (["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(event.key)) {
      event.preventDefault();
      const forward = event.key === "ArrowDown" || event.key === "ArrowRight";
      const reversed = dialog.classList.contains("opens-up") && (event.key === "ArrowDown" || event.key === "ArrowUp");
      const step = forward !== reversed ? 1 : -1;
      buttons[(Math.max(index, 0) + step + buttons.length) % buttons.length].focus();
    } else if (event.key === "Tab") {
      event.preventDefault();
      const step = event.shiftKey ? -1 : 1;
      buttons[(Math.max(index, 0) + step + buttons.length) % buttons.length].focus();
    }
  }

  dialog.addEventListener("keydown", onKeydown);
  dialog.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-piece]");
    if (button) finish(button.dataset.piece);
  });

  container.append(dialog);
  place(dialog, anchorSquareEl, container);
  buttons[0].focus({ preventScroll: true });
  document.addEventListener("pointerdown", onOutside, true);

  promise.cancel = () => finish(null);
  return promise;
}
