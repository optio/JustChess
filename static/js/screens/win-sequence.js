/**
 * JustChess win sequence (U3, BR4.1, design-system-mapping.md motion tokens).
 *
 *   const run = playWinSequence({ boardRoot, resultCell, resultText, winner, onReveal, instant })
 *   run.done      Promise that settles when the sequence has finished or was cancelled
 *   run.cancel()  stop at once (a new game started); leaves the end state as it is
 *   run.clear()   cancel and remove every trace (tip, dim, glow, inked result)
 *
 * Order: the losing king tips 80 degrees (700 ms), the board dims (600 ms), the
 * result is inked into the scoresheet one character per 250 ms, onReveal()
 * shows the overlay, and the winner's pieces glow brass. A draw (winner null)
 * skips the tip and the glow. Under reduced motion, or with instant: true (a
 * page opened on a finished game), the end state is drawn at once with no
 * animation.
 *
 * Motion uses the Web Animations API. When a step finishes, its end state is
 * kept by a CSS class (is-tipped, is-ended, is-glow in app.css) and the
 * animation is cancelled, so later board redraws cannot undo it.
 */

import { clientGameplay } from "../gameplay.js";

export const TIP_MS = 700;
export const DIM_MS = 600;
export const INK_MS_PER_CHAR = 250;
const EASE = "cubic-bezier(.5, 0, .6, 1.4)";

function prefersReducedMotion() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function canAnimate() {
  return typeof Element !== "undefined" && typeof Element.prototype.animate === "function";
}

function pieces(boardRoot, colour) {
  return [...boardRoot.querySelectorAll("img.piece:not(.piece-ghost)")].filter((img) => {
    const letter = img.dataset.shown || "";
    return colour === "white" ? letter === letter.toUpperCase() && letter !== "" : letter === letter.toLowerCase() && letter !== "";
  });
}

function king(boardRoot, colour) {
  return boardRoot.querySelector(`img.piece:not(.piece-ghost)[data-shown="${colour === "white" ? "K" : "k"}"]`);
}

export function playWinSequence({ boardRoot, resultCell, resultText = "", winner = null, celebrate = false, onReveal = () => {}, instant = false, timers = globalThis } = {}) {
  if (!(boardRoot instanceof Element)) throw new TypeError("playWinSequence needs the board element");
  const grid = boardRoot.querySelector(".board-grid") || boardRoot;
  const loser = winner === "white" ? "black" : winner === "black" ? "white" : null;
  const running = new Set();
  const pending = new Map(); // timer id -> resolve of its wait()
  let cancelled = false;
  let tipped = null;
  let revealed = false;
  let confetti = null;

  function clearConfetti() { confetti?.remove(); confetti = null; }

  function celebrateWin() {
    if (!celebrate || !winner || instant || prefersReducedMotion() || !clientGameplay().confettiMs) return;
    confetti = boardRoot.ownerDocument.createElement("div");
    confetti.className = "winner-confetti";
    confetti.setAttribute("aria-hidden", "true");
    confetti.setAttribute("data-testid", "winner-confetti");
    for (let i = 0; i < 40; i += 1) {
      const bit = boardRoot.ownerDocument.createElement("i");
      bit.style.setProperty("--x", `${(i * 37) % 100}%`);
      bit.style.setProperty("--spin", `${i % 2 ? 540 : -540}deg`);
      bit.style.setProperty("--confetti-ms", `${clientGameplay().confettiMs}ms`);
      bit.style.background = ["#ba923e", "#27785b", "#d7c8a6", "#b44e42"][i % 4];
      confetti.append(bit);
    }
    boardRoot.append(confetti);
    wait(clientGameplay().confettiMs).then(clearConfetti);
  }

  function reveal() {
    if (revealed || cancelled) return;
    revealed = true;
    celebrateWin();
    try {
      onReveal();
    } catch (error) {
      console.error("JustChess: showing the end-of-game overlay failed", error);
    }
  }

  function glow() {
    if (!winner) return;
    for (const img of pieces(boardRoot, winner)) img.classList.add("is-glow");
  }

  function tipNow() {
    if (!loser) return;
    tipped = king(boardRoot, loser);
    if (tipped) tipped.classList.add("is-tipped");
  }

  function endState() {
    tipNow();
    grid.classList.add("is-ended");
    if (resultCell) resultCell.textContent = resultText;
    reveal();
    glow();
  }

  async function animate(element, keyframes, duration, endClass) {
    if (!element || cancelled) return;
    const animation = element.animate(keyframes, { duration, easing: EASE, fill: "forwards" });
    running.add(animation);
    try {
      await animation.finished;
    } catch {
      /* cancelled */
    }
    running.delete(animation);
    if (cancelled) return;
    element.classList.add(endClass);
    animation.cancel();
  }

  function wait(ms) {
    return new Promise((resolve) => {
      const id = timers.setTimeout(() => {
        pending.delete(id);
        resolve();
      }, ms);
      pending.set(id, resolve);
    });
  }

  async function run() {
    if (instant || prefersReducedMotion() || !canAnimate()) {
      endState();
      return;
    }
    if (loser) {
      tipped = king(boardRoot, loser);
      await animate(tipped, [{ transform: "rotate(0deg)" }, { transform: "rotate(80deg) translate(8%, 6%)" }], TIP_MS, "is-tipped");
    }
    if (cancelled) return;
    await animate(grid, [{ filter: "none" }, { filter: "saturate(.7) brightness(.86)" }], DIM_MS, "is-ended");
    if (resultCell && !cancelled) {
      resultCell.textContent = "";
      for (const char of resultText) {
        if (cancelled) return;
        resultCell.textContent += char;
        await wait(INK_MS_PER_CHAR);
      }
    }
    if (cancelled) return;
    reveal();
    glow();
  }

  function cancel() {
    cancelled = true;
    clearConfetti();
    for (const animation of running) {
      try {
        animation.cancel();
      } catch {
        /* already gone */
      }
    }
    running.clear();
    for (const [id, resolve] of pending) {
      timers.clearTimeout(id);
      resolve();
    }
    pending.clear();
  }

  const done = run().catch((error) => {
    console.error("JustChess: the win sequence failed; showing the end state", error);
    if (!cancelled) endState();
  });

  return {
    done,
    cancel,
    clear() {
      cancel();
      grid.classList.remove("is-ended");
      for (const img of boardRoot.querySelectorAll("img.piece.is-glow, img.piece.is-tipped")) img.classList.remove("is-glow", "is-tipped");
      if (resultCell) resultCell.textContent = "";
    },
    get revealed() {
      return revealed;
    },
  };
}
