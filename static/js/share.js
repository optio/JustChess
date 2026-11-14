/**
 * JustChess sharing (U3, BR2.1, BR1.6).
 *
 *   chooseShareMethod(navigatorLike) -> "share" | "clipboard" | "field"
 *   shareLink({ url, title, text }, { navigator }) -> Promise<"shared" | "cancelled" | "copied" | "field">
 *   copyText(text, { navigator }) -> Promise<"copied" | "field">
 *   inviteUrl(origin, code), continueUrl(origin, code, continueToken)
 *   appLinks(url, text) -> [{ id, label, href, external }]   (P2 U1, BR3.3)
 *   dialogText({ waiting, colour }) -> { title, line }        (P2 U1, BR3.6)
 *
 * The share sheet is used when the browser has navigator.share. A user
 * cancel (AbortError) does nothing. Any other share failure falls back to the
 * clipboard, and a clipboard failure (or no clipboard) asks the caller to show
 * the read-only link field ("field"). Nothing here touches the DOM.
 */

export const SHARE_TITLE = "Play chess with me on JustChess";
export const SHARE_TEXT = "Play chess with me on JustChess";
export const COPIED_LABEL = "Link copied";
export const COPIED_MS = 1600;
export const EMAIL_SUBJECT = "Play chess with me";

export function chooseShareMethod(nav) {
  if (nav && typeof nav.share === "function") return "share";
  if (nav && nav.clipboard && typeof nav.clipboard.writeText === "function") return "clipboard";
  return "field";
}

export function inviteUrl(origin, code) {
  return `${origin}/r/${encodeURIComponent(code)}`;
}

export function continueUrl(origin, code, continueToken) {
  return `${inviteUrl(origin, code)}#continue=${encodeURIComponent(continueToken)}`;
}

export async function copyText(text, { navigator: nav = globalThis.navigator } = {}) {
  if (!nav || !nav.clipboard || typeof nav.clipboard.writeText !== "function") return "field";
  try {
    await nav.clipboard.writeText(text);
    return "copied";
  } catch (error) {
    console.error(`JustChess: copying to the clipboard failed (${error && error.name})`);
    return "field";
  }
}

/**
 * P2 U1, BR3.3: the share dialog's app links, every value URL-encoded.
 * Returns [{ id, label, href, external }] for email, WhatsApp, Telegram and SMS.
 * external is true for the web links (they open in a new tab).
 */
export function appLinks(url, text = SHARE_TEXT) {
  if (typeof url !== "string" || !url) throw new TypeError("appLinks needs a url");
  if (typeof text !== "string") throw new TypeError("appLinks text must be a string");
  const message = encodeURIComponent(`${text} ${url}`);
  return [
    { id: "email", label: "Email", href: `mailto:?subject=${encodeURIComponent(EMAIL_SUBJECT)}&body=${message}`, external: false },
    { id: "whatsapp", label: "WhatsApp", href: `https://wa.me/?text=${message}`, external: true },
    { id: "telegram", label: "Telegram", href: `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`, external: true },
    { id: "sms", label: "SMS", href: `sms:?body=${message}`, external: false },
  ];
}

/**
 * P2 U1, BR3.6: the dialog's title and line. waiting: the room waits for an
 * opponent; colour: the colour whoever joins will play ("white" | "black").
 */
export function dialogText({ waiting, colour } = {}) {
  if (!waiting) return { title: "Share this game", line: "Anyone with the link can watch; seats are taken." };
  if (colour !== "white" && colour !== "black") throw new TypeError(`dialogText needs the joiner's colour, got ${JSON.stringify(colour)}`);
  return { title: "Invite a friend", line: `Send this link. Whoever opens it first plays ${colour}.` };
}

export async function shareLink({ url, title = SHARE_TITLE, text = SHARE_TEXT }, { navigator: nav = globalThis.navigator } = {}) {
  if (typeof url !== "string" || !url) throw new TypeError("shareLink needs a url");
  if (chooseShareMethod(nav) === "share") {
    try {
      await nav.share({ title, text, url });
      return "shared";
    } catch (error) {
      if (error && error.name === "AbortError") return "cancelled";
      console.error(`JustChess: the share sheet failed, copying instead (${error && error.name})`);
    }
  }
  return copyText(url, { navigator: nav });
}
