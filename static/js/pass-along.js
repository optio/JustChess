/**
 * Pass-along and join-request logic (P2 U3, BR1.1, BR2.3, BR2.4, BR4.1).
 * PURE except createJoinerPoller, whose timers and network call are injected,
 * so tests/js/pass-along.test.mjs drives everything in Node.
 *
 *   controlsFor(snapshot, { watching })
 *     -> { playHere, playComputer, waitForFriend, practiceNote, note }   which controls the game screen shows:
 *        "Play here while waiting" and "Play the computer while waiting" for seat A in a
 *        waiting room with seat B empty; "Wait for a friend instead" and the note
 *        (PRACTICE_NOTE or STAND_IN_NOTE) for seat A in pass-along or with the computer standing in.
 *
 *   countdownText(secondsLeft) -> "m:ss"           never negative
 *   bannerText(colour, secondsLeft)                "Someone wants to join as Black. They will take over
 *                                                   Black from this position. Expires in 9:41."
 *   requestDeadline(joinRequest, receivedAt)       ms deadline from the snapshot's expiresIn, read against
 *                                                   this device's clock when the snapshot arrived (no skew)
 *   BANNER_REFRESH_MS                              the banner text is refreshed once a minute (screen readers)
 *
 *   joinerReduce(state, event) -> state            the joiner's poll state machine
 *     state: { phase: "waiting" | "accepted" | "declined" | "lapsed" | "unknown", hidden }
 *     events: { type: "status", status }  { type: "hidden" }  { type: "visible" }
 *   shouldPoll(state)                              waiting and the page is visible
 *   refusalKind(answer)                            a failed join's refusal: "busy" | "declined_recently"
 *                                                   | "too_many" | null
 *   JOINER_TEXT                                    the joiner's messages for every phase and refusal
 *   waitingText(colour)                            the waiting text naming the colour from the 202, if known
 *
 *   createJoinerPoller({ check, onChange, setTimer, clearTimer, intervalMs })
 *     -> { start(), setHidden(hidden), stop(), state }
 *     Polls check() every 3 s while waiting and visible; stops for good on a
 *     final answer. A failed check (network) keeps waiting and tries again.
 *
 * Request tokens are never logged.
 */

export const POLL_MS = 3000;
export const BANNER_REFRESH_MS = 60_000;

export const JOINER_TEXT = Object.freeze({
  waiting: "Waiting for the creator to accept. You'll play Black from the current position.",
  accepted: "The creator accepted. Opening the game…",
  declined: "The creator declined. You can ask again later.",
  declined_recently: "The creator declined. You can ask again later.",
  lapsed: "Nobody answered. Try again later.",
  unknown: "This request is no longer valid. Try again later.",
  busy: "Someone else is already asking to join. Try again in a few minutes.",
  too_many: "Too many requests. Try again shortly.",
});

export const PASS_ALONG_SUB = "Hand the device over after each move. The invite link still works.";
export const PRACTICE_NOTE = "Practice game: the room score changes only once a friend joins.";
export const STAND_IN_NOTE = "The computer plays until your friend opens the invite link, then they take over from this position. The room score starts counting then.";
export const PRACTICE_OVER = "Practice game over";

const FINAL_PHASES = new Set(["accepted", "declined", "lapsed", "unknown"]);
const REFUSALS = new Set(["busy", "declined_recently", "too_many"]);

function capital(colour) {
  return colour === "black" ? "Black" : "White";
}

/** The joiner's waiting text, naming the colour they would take over when the 202 told it (not after a reload). */
export function waitingText(colour) {
  if (colour !== "white" && colour !== "black") return "Waiting for the creator to accept. You'll play from the current position.";
  return `Waiting for the creator to accept. You'll play ${capital(colour)} from the current position.`;
}

export function controlsFor(snapshot, { watching = false } = {}) {
  const none = { playHere: false, playComputer: false, waitForFriend: false, practiceNote: false, note: null };
  if (!snapshot || watching || snapshot.slot !== "A") return none;
  const seatB = snapshot.seats && snapshot.seats.B ? snapshot.seats.B.presence : "empty";
  if (snapshot.mode === "pass_along") return { ...none, waitForFriend: true, practiceNote: true, note: PRACTICE_NOTE };
  if (snapshot.mode === "computer" && snapshot.standIn) return { ...none, waitForFriend: true, practiceNote: true, note: STAND_IN_NOTE };
  if (snapshot.mode === "waiting" && seatB === "empty") return { ...none, playHere: true, playComputer: true };
  return none;
}

export function countdownText(secondsLeft) {
  const total = Math.max(0, Math.ceil(Number(secondsLeft) || 0));
  const minutes = Math.floor(total / 60);
  const seconds = String(total % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export function bannerText(colour, secondsLeft) {
  const name = capital(colour);
  return `Someone wants to join as ${name}. They will take over ${name} from this position. Expires in ${countdownText(secondsLeft)}.`;
}

export function requestDeadline(joinRequest, receivedAt) {
  if (!joinRequest || !Number.isFinite(joinRequest.expiresIn)) return null;
  return receivedAt + Math.max(0, joinRequest.expiresIn) * 1000;
}

export function initialJoinerState() {
  return { phase: "waiting", hidden: false };
}

export function joinerReduce(state, event) {
  if (!event || typeof event.type !== "string") throw new TypeError("a joiner event needs a type");
  if (FINAL_PHASES.has(state.phase)) return state; // a final answer never changes
  switch (event.type) {
    case "status":
      if (event.status === "pending") return state;
      if (FINAL_PHASES.has(event.status)) return { ...state, phase: event.status };
      return state; // an unexpected value: keep waiting
    case "hidden":
      return state.hidden ? state : { ...state, hidden: true };
    case "visible":
      return state.hidden ? { ...state, hidden: false } : state;
    default:
      throw new TypeError(`unknown joiner event ${JSON.stringify(event.type)}`);
  }
}

export function shouldPoll(state) {
  return state.phase === "waiting" && !state.hidden;
}

export function refusalKind(answer) {
  if (!answer || answer.ok) return null;
  if (answer.status === 429) return "too_many";
  if (answer.status === 409 && REFUSALS.has(answer.error)) return answer.error;
  return null;
}

export function createJoinerPoller({ check, onChange = () => {}, setTimer = setTimeout, clearTimer = clearTimeout, intervalMs = POLL_MS }) {
  if (typeof check !== "function") throw new TypeError("createJoinerPoller needs a check function");
  let state = initialJoinerState();
  let timer = null;
  let running = false;
  let inFlight = false;

  function dispatch(event) {
    const next = joinerReduce(state, event);
    if (next === state) return;
    const phaseChanged = next.phase !== state.phase;
    state = next;
    if (phaseChanged) onChange(state);
  }

  function schedule(delay) {
    if (timer !== null) clearTimer(timer);
    timer = running && shouldPoll(state) ? setTimer(tick, delay) : null;
  }

  async function tick() {
    timer = null;
    if (!running || !shouldPoll(state) || inFlight) return;
    inFlight = true;
    try {
      const answer = await check();
      if (running && answer && answer.ok && answer.data) dispatch({ type: "status", status: answer.data.status });
    } catch (error) {
      console.error("JustChess: the join request status could not be read", error && error.name);
    } finally {
      inFlight = false;
    }
    schedule(intervalMs);
  }

  return {
    start() {
      running = true;
      schedule(0);
    },
    setHidden(hidden) {
      dispatch({ type: hidden ? "hidden" : "visible" });
      schedule(hidden ? intervalMs : 0);
    },
    stop() {
      running = false;
      if (timer !== null) clearTimer(timer);
      timer = null;
    },
    get state() {
      return state;
    },
  };
}
