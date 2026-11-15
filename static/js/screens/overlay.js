/**
 * JustChess end-of-game overlay (U3, BR4.2, BR4.3, W7, W8).
 *
 *   const overlay = createOverlay(container, { onPlayAgain, onShareResult, onShareLink })
 *   overlay.render(view.overlay, { visible })   null or hidden closes it
 *   overlay.setMessage(text)                     a one-line result ("Link copied", an error)
 *   overlay.destroy()
 *
 * Not modal: role="region" labelled by its title, so the board and scoresheet
 * stay readable and usable. When it opens, focus moves to "Play again" (or the
 * first action a watcher has). The rematch button follows view.overlay.rematch:
 *   offer          "Play again"
 *   waiting        "Waiting for opponent" (aria-disabled, so focus stays on it)
 *   opponentReady  "Play again (your opponent is ready)"
 *   lapsed         "Your opponent left. Share the link to play again." and a Share button
 *   none           a watcher: no rematch button
 */
import { runBusy } from "../busy.js";

export const REMATCH_LABELS = Object.freeze({
  offer: "Play again",
  waiting: "Waiting for opponent",
  opponentReady: "Play again (your opponent is ready)",
});

export const LAPSED_NOTE = "Your opponent left. Share the link to play again.";

function make(tag, attributes = {}, text) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "className") node.className = value;
    else node.setAttribute(name, value);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

export function createOverlay(container, { onPlayAgain, onShareResult, onShareLink } = {}) {
  if (!(container instanceof Element)) throw new TypeError("createOverlay needs a container element");
  const root = make("section", { className: "overlay", role: "region", "aria-labelledby": "overlay-title", "data-testid": "overlay" });
  root.hidden = true;
  const card = make("div", { className: "overlay-card" });
  const title = make("h2", { className: "overlay-title", id: "overlay-title", tabindex: "-1", "data-testid": "overlay-title" });
  const subtitle = make("p", { className: "overlay-subtitle", "data-testid": "overlay-subtitle" });
  const note = make("p", { className: "overlay-note", "data-testid": "overlay-note" });
  const actions = make("div", { className: "overlay-actions" });
  const again = make("button", { className: "btn btn-primary", type: "button", "data-testid": "play-again" }, REMATCH_LABELS.offer);
  const shareLinkButton = make("button", { className: "btn btn-primary", type: "button", "data-testid": "overlay-share-link" }, "Share the link");
  const shareResult = make("button", { className: "btn btn-secondary", type: "button", "data-testid": "share-result" }, "Share result");
  const message = make("p", { className: "overlay-message", role: "status", "data-testid": "overlay-message" });
  actions.append(again, shareLinkButton, shareResult);
  card.append(title, subtitle, note, actions, message);
  root.append(card);
  container.append(root);

  let open = false;
  let rematch = "offer";

  function onAgain() {
    if (again.getAttribute("aria-disabled") === "true") return;
    if (typeof onPlayAgain === "function") runBusy(again, () => onPlayAgain());
  }

  again.addEventListener("click", onAgain);
  shareResult.addEventListener("click", () => typeof onShareResult === "function" && onShareResult());
  shareLinkButton.addEventListener("click", () => typeof onShareLink === "function" && onShareLink());

  function primaryAction() {
    if (!again.hidden) return again;
    if (!shareLinkButton.hidden) return shareLinkButton;
    return shareResult.hidden ? title : shareResult;
  }

  function render(view, { visible = true } = {}) {
    const show = Boolean(view) && visible;
    if (!show) {
      root.hidden = true;
      if (open) message.textContent = "";
      open = false;
      return;
    }
    title.textContent = view.title;
    subtitle.textContent = view.subtitle || "";
    rematch = view.rematch;
    const lapsed = rematch === "lapsed";
    note.textContent = lapsed ? LAPSED_NOTE : "";
    note.hidden = !lapsed;
    again.hidden = lapsed || rematch === "none";
    shareLinkButton.hidden = !lapsed;
    shareResult.hidden = view.share === false; // P2 U4: no share controls against the computer
    if (Object.hasOwn(REMATCH_LABELS, rematch)) again.textContent = REMATCH_LABELS[rematch];
    if (rematch === "waiting") again.setAttribute("aria-disabled", "true");
    else again.removeAttribute("aria-disabled");
    const opening = !open;
    root.hidden = false;
    open = true;
    if (opening) primaryAction().focus({ preventScroll: true });
  }

  return {
    element: root,
    render,
    setMessage(text) {
      message.textContent = text || "";
    },
    get isOpen() {
      return open;
    },
    destroy() {
      again.removeEventListener("click", onAgain);
      root.remove();
    },
  };
}
