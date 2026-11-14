/**
 * JustChess blunder dialog (U4, BR3.2, BR3.3, NFR6). The DOM half of the
 * blunder warning; the text and the hook logic are in ../blunder.js.
 *
 *   const dialog = createBlunderDialog(container, { doc = document })
 *   dialog.open(text, { version, game, returnFocus }) -> Promise<"confirm" | "cancel" | "superseded">
 *       text: { title, body, confirmLabel, cancelLabel } from dialogText().
 *       version, game: the snapshot the move was made on.
 *       returnFocus(): called when the dialog closes (app.js focuses the
 *       move's from-square on the board).
 *   dialog.supersede(snapshot)   a newer snapshot (another game, or a higher
 *                                version) closes an open dialog with "superseded"
 *   dialog.close()               closes an open dialog with "superseded" (leaving the room)
 *   dialog.isOpen
 *   dialog.destroy()
 *
 * Accessibility: role="alertdialog", aria-modal="true", aria-labelledby the
 * title and aria-describedby the body. Focus starts on "Choose another move"
 * (the safe default) and Tab stays between the two buttons. Escape cancels;
 * it is caught on the document in the capture phase and stopped there, so the
 * board never sees it. Focus outside the dialog is pulled back in. Buttons are
 * at least 44 px high (styles in static/css/app.css).
 */

import { CHOICES } from "../blunder.js";

function make(doc, tag, attributes = {}, text) {
  const node = doc.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "className") node.className = value;
    else node.setAttribute(name, value);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

function validText(text) {
  return Boolean(text) && ["title", "body", "confirmLabel", "cancelLabel"].every((key) => typeof text[key] === "string" && text[key]);
}

export function createBlunderDialog(container, { doc = document } = {}) {
  if (!container || typeof container.append !== "function") throw new TypeError("createBlunderDialog needs a container element");

  const scrim = make(doc, "div", { className: "blunder-scrim", "data-testid": "blunder-scrim" });
  scrim.hidden = true;
  const dialog = make(doc, "div", {
    className: "blunder-dialog",
    role: "alertdialog",
    "aria-modal": "true",
    "aria-labelledby": "blunder-title",
    "aria-describedby": "blunder-body",
    "data-testid": "blunder-dialog",
  });
  const title = make(doc, "h2", { className: "blunder-title", id: "blunder-title", "data-testid": "blunder-title" });
  const body = make(doc, "p", { className: "blunder-body", id: "blunder-body", "data-testid": "blunder-body" });
  const actions = make(doc, "div", { className: "blunder-actions" });
  const cancel = make(doc, "button", { className: "btn btn-secondary", type: "button", "data-testid": "blunder-cancel" });
  const confirm = make(doc, "button", { className: "btn btn-primary", type: "button", "data-testid": "blunder-confirm" });
  actions.append(cancel, confirm);
  dialog.append(title, body, actions);
  scrim.append(dialog);
  container.append(scrim);

  let current = null; // { resolve, version, game, returnFocus }

  function finish(choice) {
    if (!current) return;
    const { resolve, returnFocus } = current;
    current = null;
    scrim.hidden = true;
    doc.removeEventListener("keydown", onKeydown, true);
    doc.removeEventListener("focusin", onFocusIn, true);
    if (typeof returnFocus === "function") {
      try {
        returnFocus();
      } catch (error) {
        console.error("JustChess: focus could not return to the board", error);
      }
    }
    resolve(choice);
  }

  function onKeydown(event) {
    if (!current) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopImmediatePropagation();
      finish(CHOICES.cancel);
    } else if (event.key === "Tab") {
      event.preventDefault();
      const next = doc.activeElement === cancel ? confirm : cancel;
      next.focus({ preventScroll: true });
    }
  }

  function onFocusIn(event) {
    if (current && !dialog.contains(event.target)) cancel.focus({ preventScroll: true });
  }

  cancel.addEventListener("click", () => finish(CHOICES.cancel));
  confirm.addEventListener("click", () => finish(CHOICES.confirm));

  return {
    open(text, { version = null, game = null, returnFocus = null } = {}) {
      if (!validText(text)) return Promise.reject(new TypeError("the blunder dialog needs a title, a body and two labels"));
      finish(CHOICES.superseded); // a dialog still open belongs to an older move
      title.textContent = text.title;
      body.textContent = text.body;
      cancel.textContent = text.cancelLabel;
      confirm.textContent = text.confirmLabel;
      return new Promise((resolve) => {
        current = { resolve, version, game, returnFocus };
        scrim.hidden = false;
        doc.addEventListener("keydown", onKeydown, true);
        doc.addEventListener("focusin", onFocusIn, true);
        cancel.focus({ preventScroll: true });
      });
    },
    supersede(snapshot) {
      if (!current || !snapshot || typeof snapshot.version !== "number") return;
      const otherGame = current.game !== null && snapshot.game !== current.game;
      const newer = current.version !== null && snapshot.version > current.version;
      if (otherGame || newer) finish(CHOICES.superseded);
    },
    close() {
      finish(CHOICES.superseded);
    },
    get isOpen() {
      return current !== null;
    },
    destroy() {
      finish(CHOICES.superseded);
      scrim.remove();
    },
  };
}
