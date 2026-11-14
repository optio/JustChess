// Tests for sharing static/js/share.js (BR2.1, BR1.6).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  EMAIL_SUBJECT, SHARE_TEXT, SHARE_TITLE, appLinks, chooseShareMethod, continueUrl, copyText, dialogText, inviteUrl, shareLink,
} from "../../static/js/share.js";

const URL_ = "https://chess.example/r/ABC123";

function quietly(fn) {
  const original = console.error;
  console.error = () => {};
  return Promise.resolve(fn()).finally(() => {
    console.error = original;
  });
}

test("the share sheet is used when the browser has one; a user cancel does nothing", async () => {
  const shared = [];
  const nav = { share: async (data) => shared.push(data), clipboard: { writeText: async () => assert.fail("must not copy") } };
  assert.equal(chooseShareMethod(nav), "share");
  assert.equal(await shareLink({ url: URL_ }, { navigator: nav }), "shared");
  assert.deepEqual(shared, [{ title: SHARE_TITLE, text: "Play chess with me on JustChess", url: URL_ }]);

  const cancelling = { share: async () => { throw Object.assign(new Error("cancel"), { name: "AbortError" }); } };
  assert.equal(await shareLink({ url: URL_ }, { navigator: cancelling }), "cancelled");
  await assert.rejects(() => shareLink({ url: "" }, { navigator: nav }), TypeError);
});

test("without a share sheet the link is copied; a failing share sheet also falls back to the clipboard", async () => {
  const copied = [];
  const nav = { clipboard: { writeText: async (text) => copied.push(text) } };
  assert.equal(chooseShareMethod(nav), "clipboard");
  assert.equal(await shareLink({ url: URL_ }, { navigator: nav }), "copied");
  const broken = { share: async () => { throw Object.assign(new Error("no"), { name: "NotAllowedError" }); }, ...nav };
  assert.equal(await quietly(() => shareLink({ url: URL_ }, { navigator: broken })), "copied");
  assert.deepEqual(copied, [URL_, URL_]);
  assert.equal(inviteUrl("https://chess.example", "ABC123"), URL_);
  assert.equal(continueUrl("https://chess.example", "ABC123", "tok_en-1"), `${URL_}#continue=tok_en-1`);
});

test("no clipboard, or a denied clipboard, asks for the read-only link field", async () => {
  assert.equal(chooseShareMethod({}), "field");
  assert.equal(chooseShareMethod(undefined), "field");
  assert.equal(await shareLink({ url: URL_ }, { navigator: {} }), "field");
  const denied = { clipboard: { writeText: async () => { throw Object.assign(new Error("denied"), { name: "NotAllowedError" }); } } };
  assert.equal(await quietly(() => copyText(URL_, { navigator: denied })), "field");
});

// --- P2 U1: the share dialog's helpers (BR3.3, BR3.6) ---------------------------

function linkMap(url, text) {
  return Object.fromEntries(appLinks(url, text).map((link) => [link.id, link]));
}

test("app links: email, WhatsApp, Telegram and SMS, in that order, with the right shapes", () => {
  const links = appLinks(URL_);
  assert.deepEqual(links.map((l) => [l.id, l.label]), [["email", "Email"], ["whatsapp", "WhatsApp"], ["telegram", "Telegram"], ["sms", "SMS"]]);
  const byId = linkMap(URL_);
  const message = encodeURIComponent(`${SHARE_TEXT} ${URL_}`);
  assert.equal(byId.email.href, `mailto:?subject=${encodeURIComponent(EMAIL_SUBJECT)}&body=${message}`);
  assert.equal(byId.whatsapp.href, `https://wa.me/?text=${message}`);
  assert.equal(byId.telegram.href, `https://t.me/share/url?url=${encodeURIComponent(URL_)}&text=${encodeURIComponent(SHARE_TEXT)}`);
  assert.equal(byId.sms.href, `sms:?body=${message}`);
  assert.deepEqual(links.map((l) => l.external), [false, true, true, false], "only the web links open a new tab");
});

test("app links encode &, # and spaces so the link and text survive intact", () => {
  const tricky = "https://chess.example/r/ABC123?a=1&b=2#frag";
  const byId = linkMap(tricky, "Tom & Jerry #1 play");
  const expectedParams = { email: ["subject", "body"], whatsapp: ["text"], telegram: ["url", "text"], sms: ["body"] };
  for (const link of Object.values(byId)) {
    assert.doesNotMatch(link.href, /[ #]/, `${link.id}: no raw space or # in ${link.href}`);
    const params = link.href.slice(link.href.indexOf("?") + 1).split("&").map((pair) => pair.split("=")[0]);
    assert.deepEqual(params, expectedParams[link.id], `${link.id}: the & in the link did not split the query`);
  }
  assert.equal(decodeURIComponent(byId.sms.href.split("body=")[1]), `Tom & Jerry #1 play ${tricky}`);
  const telegram = new URL(byId.telegram.href);
  assert.equal(telegram.searchParams.get("url"), tricky);
  assert.equal(telegram.searchParams.get("text"), "Tom & Jerry #1 play");
  const whatsapp = new URL(byId.whatsapp.href);
  assert.equal(whatsapp.searchParams.get("text"), `Tom & Jerry #1 play ${tricky}`);
  assert.equal(whatsapp.hash, "", "the fragment stays inside the encoded text");
});

test("app links refuse a missing url or a non-string text", () => {
  assert.throws(() => appLinks(""), TypeError);
  assert.throws(() => appLinks(undefined), TypeError);
  assert.throws(() => appLinks(URL_, 42), TypeError);
});

test("dialog text while the room waits names the colour the joiner will play", () => {
  assert.deepEqual(dialogText({ waiting: true, colour: "black" }),
    { title: "Invite a friend", line: "Send this link. Whoever opens it first plays black." });
  assert.equal(dialogText({ waiting: true, colour: "white" }).line, "Send this link. Whoever opens it first plays white.");
  assert.throws(() => dialogText({ waiting: true }), TypeError, "a waiting room needs the joiner's colour");
});

test("dialog text once both seats are taken invites watchers", () => {
  const joined = { title: "Share this game", line: "Anyone with the link can watch; seats are taken." };
  assert.deepEqual(dialogText({ waiting: false, colour: "black" }), joined);
  assert.deepEqual(dialogText({ waiting: false }), joined);
  assert.deepEqual(dialogText(), joined);
});
