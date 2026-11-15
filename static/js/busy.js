/**
 * Progress for actions that can take time: while `run` is in flight the button
 * shows a spinner (.is-busy) and says aria-busy="true", and further clicks are
 * ignored. The button is not disabled, so keyboard focus stays on it and the
 * guard never fights a screen's own render of `disabled` or `aria-disabled`.
 */
const running = new WeakSet();

export function isBusy(button) {
  return running.has(button);
}

/** Run `run` once for `button`; a click while it is still running returns null. */
export async function runBusy(button, run) {
  if (!button || running.has(button)) return null;
  running.add(button);
  button.classList.add("is-busy");
  button.setAttribute("aria-busy", "true");
  try {
    return await run();
  } finally {
    running.delete(button);
    button.classList.remove("is-busy");
    button.removeAttribute("aria-busy");
  }
}

/** A click handler that runs `run` through runBusy for its button. */
export function busyClick(button, run) {
  const handler = (event) => runBusy(button, () => run(event));
  button.addEventListener("click", handler);
  return handler;
}
