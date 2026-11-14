/**
 * JustChess share dialog (P2 U1, BR3.1-BR3.6; mockups.md Screen 4).
 *
 *   const dialog = createShareDialog(dialogElement, { trigger, navigator, loadQr })
 *   dialog.open({ url, waiting, colour })   show it (or refresh its text when already open)
 *   dialog.close()
 *   dialog.isOpen
 *   dialog.destroy()
 *
 * dialogElement is the native <dialog> in templates/index.html. It opens with
 * showModal(), so the game screen behind it is inert and unchanged (BR3.1).
 * - Focus starts on "Copy link"; Tab and Shift+Tab cycle inside; Escape (the
 *   dialog's own cancel), Close or a click on the backdrop closes it, and focus
 *   returns to the trigger (BR3.5).
 * - Copy link copies with share.js copyText. When the clipboard refuses, the
 *   link field is selected instead. Either way the label reads "Copied" for
 *   COPIED_MS (BR3.2).
 * - Email, WhatsApp, Telegram and SMS are plain links from appLinks, so the
 *   dialog stays open (BR3.3). "More…" is shown only when the browser has a
 *   share sheet; a cancelled share does nothing.
 * - The QR code is drawn by qr-canvas.js, loaded with a dynamic import() on the
 *   first open (BR3.4). If that fails the area says "QR code unavailable", the
 *   error is logged, and the rest of the dialog works.
 * - The title and line follow the room state (dialogText, BR3.6).
 * The invite link carries only the room code; nothing secret is shown or logged.
 */

import { COPIED_MS, SHARE_TEXT, appLinks, chooseShareMethod, copyText, dialogText, shareLink } from "./share.js";

export const COPY_LABEL = "Copy link";
export const COPIED_TEXT = "Copied";
export const QR_UNAVAILABLE = "QR code unavailable";
export const QR_NOTE = "Scan with a phone camera to open the game.";

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])";

function part(dialog, testid) {
  const found = dialog.querySelector(`[data-testid="${testid}"]`);
  if (!found) throw new Error(`JustChess: the share dialog has no ${testid}`);
  return found;
}

function buildLink(link, doc) {
  const anchor = doc.createElement("a");
  anchor.className = "btn btn-secondary";
  anchor.href = link.href;
  anchor.textContent = link.label;
  anchor.dataset.testid = `share-app-${link.id}`;
  if (link.external) {
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
  }
  return anchor;
}

export function createShareDialog(dialog, { trigger = null, navigator: nav = globalThis.navigator, loadQr = () => import("./qr-canvas.js") } = {}) {
  if (!dialog || typeof dialog.showModal !== "function") throw new TypeError("createShareDialog needs a <dialog> element");
  const doc = dialog.ownerDocument;
  const els = {
    title: part(dialog, "share-title"),
    line: part(dialog, "share-line"),
    field: part(dialog, "share-link"),
    copy: part(dialog, "share-copy"),
    apps: part(dialog, "share-apps"),
    more: part(dialog, "share-more"),
    canvas: part(dialog, "share-qr"),
    note: part(dialog, "share-qr-note"),
    close: part(dialog, "share-close"),
  };
  let url = null;
  let copiedTimer = null;
  let qrFor = null;
  let qrRun = 0;

  function resetCopy() {
    if (copiedTimer !== null) clearTimeout(copiedTimer);
    copiedTimer = null;
    els.copy.textContent = COPY_LABEL;
  }

  function drawQrCode() {
    if (qrFor === url) return;
    qrFor = url;
    const run = (qrRun += 1);
    const text = url;
    els.canvas.hidden = false;
    els.note.textContent = QR_NOTE;
    Promise.resolve()
      .then(loadQr)
      .then((module) => {
        if (run === qrRun) module.drawQr(els.canvas, text);
      })
      .catch((error) => {
        console.error("JustChess: the QR code could not be drawn", error);
        if (run !== qrRun) return;
        qrFor = null; // try again on the next open
        els.canvas.hidden = true;
        els.note.textContent = QR_UNAVAILABLE;
      });
  }

  function fill({ waiting, colour }) {
    const text = dialogText({ waiting, colour });
    els.title.textContent = text.title;
    els.line.textContent = text.line;
    els.field.value = url;
    els.apps.replaceChildren(...appLinks(url, SHARE_TEXT).map((link) => buildLink(link, doc)));
    els.more.hidden = chooseShareMethod(nav) !== "share";
    els.canvas.setAttribute("aria-label", `QR code of the invite link ${url}`);
  }

  function open({ url: nextUrl, waiting = false, colour = "black" } = {}) {
    if (typeof nextUrl !== "string" || !nextUrl) throw new TypeError("the share dialog needs the invite url");
    url = nextUrl;
    fill({ waiting, colour });
    if (dialog.open) return;
    resetCopy();
    dialog.showModal();
    els.copy.focus();
    drawQrCode();
  }

  function close() {
    if (dialog.open) dialog.close();
  }

  async function onCopy() {
    const outcome = await copyText(url, { navigator: nav });
    if (outcome !== "copied") {
      els.field.focus();
      els.field.select();
    }
    resetCopy();
    els.copy.textContent = COPIED_TEXT;
    copiedTimer = setTimeout(() => {
      copiedTimer = null;
      els.copy.textContent = COPY_LABEL;
    }, COPIED_MS);
  }

  async function onMore() {
    try {
      await shareLink({ url }, { navigator: nav });
    } catch (error) {
      console.error("JustChess: the share sheet could not open", error);
    }
  }

  function onKeydown(event) {
    if (event.key !== "Tab") return;
    const items = [...dialog.querySelectorAll(FOCUSABLE)].filter((item) => !item.closest("[hidden]"));
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && doc.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && doc.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function onClick(event) {
    if (event.target === dialog) close(); // the backdrop: the dialog itself, outside its body
  }

  function onClose() {
    resetCopy();
    if (trigger && trigger.isConnected && !trigger.closest("[hidden]")) trigger.focus();
  }

  els.copy.addEventListener("click", onCopy);
  els.more.addEventListener("click", onMore);
  els.close.addEventListener("click", close);
  dialog.addEventListener("keydown", onKeydown);
  dialog.addEventListener("click", onClick);
  dialog.addEventListener("close", onClose);

  return {
    open,
    close,
    get isOpen() {
      return dialog.open;
    },
    destroy() {
      close();
      resetCopy();
      els.copy.removeEventListener("click", onCopy);
      els.more.removeEventListener("click", onMore);
      els.close.removeEventListener("click", close);
      dialog.removeEventListener("keydown", onKeydown);
      dialog.removeEventListener("click", onClick);
      dialog.removeEventListener("close", onClose);
    },
  };
}
