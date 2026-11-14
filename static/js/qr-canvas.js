/**
 * JustChess QR canvas (P2 U1, BR3.4; ADR-008).
 *
 *   qrMatrix(text) -> boolean[][]   the QR modules at error correction level M
 *                                   (true = dark), without the quiet zone
 *   drawQr(canvas, text, { cssSize, devicePixelRatio }) -> { version, size }
 *
 * The encoder is the vendored vendor/qrcode.js; nothing is requested from the
 * network. drawQr draws black modules on white with a 4-module quiet zone and
 * scales the canvas backing store by the device pixel ratio so the code stays
 * sharp. share-dialog.js loads this module with a dynamic import() the first
 * time the dialog opens. Throws QrTooLongError (re-exported) for text that does
 * not fit version 10, and TypeError for a missing canvas.
 */

import { QrTooLongError, encodeQr } from "./vendor/qrcode.js";

export { QrTooLongError };
export const QUIET_ZONE = 4;
export const DEFAULT_CSS_SIZE = 176;

export function qrMatrix(text) {
  if (typeof text !== "string" || text === "") throw new TypeError("qrMatrix needs a non-empty string");
  return encodeQr(text, { ecl: "M" }).modules;
}

export function drawQr(canvas, text, { cssSize = DEFAULT_CSS_SIZE, devicePixelRatio } = {}) {
  if (!canvas || typeof canvas.getContext !== "function") throw new TypeError("drawQr needs a canvas element");
  const modules = qrMatrix(text);
  const ratio = devicePixelRatio || globalThis.devicePixelRatio || 1;
  const count = modules.length + QUIET_ZONE * 2;
  const scale = Math.max(1, Math.floor((cssSize * ratio) / count));
  const pixels = scale * count;
  canvas.width = pixels;
  canvas.height = pixels;
  canvas.style.width = `${pixels / ratio}px`;
  canvas.style.height = `${pixels / ratio}px`;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("JustChess: the QR canvas has no 2D context");
  context.fillStyle = "#FFFFFF";
  context.fillRect(0, 0, pixels, pixels);
  context.fillStyle = "#000000";
  modules.forEach((row, y) => row.forEach((dark, x) => {
    if (dark) context.fillRect((x + QUIET_ZONE) * scale, (y + QUIET_ZONE) * scale, scale, scale);
  }));
  return { version: (modules.length - 17) / 4, size: modules.length };
}
