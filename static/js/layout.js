/**
 * JustChess board fit (P2 U1, BR2.1-BR2.4; functional-spec.md W2). Pure.
 *
 *   boardMode(width, height) -> "landscape-phone" | "desktop" | "portrait"
 *   boardSide(width, height) -> the board frame's side in CSS px
 *
 * These mirror the CSS in app.css ("board fit" section) so the rules can be
 * unit-tested and the browser test can compare against them. Nothing calls
 * them at runtime: the layout is pure CSS.
 *
 * Modes, checked in this order (the landscape-phone media query comes after
 * the desktop one in app.css, so it wins when both match):
 *   landscape-phone  landscape and height <= 500   side = height - 24, floor 288 (8 x 36)
 *   desktop          width >= 1024                 side = min(640, height - 110), floor 352
 *   portrait         otherwise                     side = min(width, height - 152), floor 352
 * Portrait width: edge to edge under 400 px; 400-767 px keeps the existing
 * 8 px gutters (width - 16); 768 px and up keeps the 16 px page gutters
 * (width - 32).
 */

export const LANDSCAPE_MAX_HEIGHT = 500;
export const DESKTOP_MIN_WIDTH = 1024;
export const EDGE_TO_EDGE_BELOW = 400;
export const PHONE_MAX_WIDTH = 767;
export const DESKTOP_CAP = 640;
export const RESERVE = Object.freeze({ portrait: 152, desktop: 110, "landscape-phone": 24 });
export const FLOOR = Object.freeze({ portrait: 352, desktop: 352, "landscape-phone": 288 });
/** In landscape-phone the panel beside the board keeps at least this much width (plus the gutters). */
export const LANDSCAPE_PANEL_MIN = 240;

function checkSize(width, height) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new TypeError(`viewport size must be positive numbers, got ${width} x ${height}`);
  }
}

export function boardMode(width, height) {
  checkSize(width, height);
  if (width > height && height <= LANDSCAPE_MAX_HEIGHT) return "landscape-phone";
  if (width >= DESKTOP_MIN_WIDTH) return "desktop";
  return "portrait";
}

function portraitWidth(width) {
  if (width < EDGE_TO_EDGE_BELOW) return width;
  if (width <= PHONE_MAX_WIDTH) return width - 16;
  return width - 32;
}

export function boardSide(width, height) {
  const mode = boardMode(width, height);
  const available = height - RESERVE[mode];
  let side;
  if (mode === "landscape-phone") side = Math.min(available, width - 32 - LANDSCAPE_PANEL_MIN);
  else if (mode === "desktop") side = Math.min(DESKTOP_CAP, available);
  else side = Math.min(portraitWidth(width), available);
  return Math.max(FLOOR[mode], side);
}
