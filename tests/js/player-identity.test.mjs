import test from "node:test";
import assert from "node:assert/strict";
import { createPlayerIdentity, recoveryFragment } from "../../static/js/player-identity.js";

const token = "a".repeat(43), recovery = "b".repeat(43), newer = "c".repeat(43);
function storage() { const map = new Map(); return { getItem:k => map.get(k) || null, setItem:(k,v) => map.set(k,v) }; }

test("fragment parser accepts only bounded private tokens", () => {
  assert.equal(recoveryFragment(`#player=${recovery}`), recovery);
  for (const bad of ["#player=bad", `?player=${recovery}`, `#player=${recovery}&other=1`]) assert.equal(recoveryFragment(bad), null);
});

test("restore replaces local seats only on success and keeps secrets out of request URLs", async () => {
  const calls = [], removed = [], added = [];
  const seats = { validSeats: () => [{code:"OLD001",token:"old"}], remove:c => removed.push(c), set:(c,s) => added.push([c,s]) };
  const fake = async (url, init) => {
    calls.push([url, init]);
    return { ok:true, json:async () => ({ token, playerId:"id", nickname:"Alice", seats:[{code:"NEW001",token,slot:"A"}] }) };
  };
  const player = createPlayerIdentity({fetchImpl:fake,storage:storage(),seats});
  await player.init(recovery);
  assert.equal(player.nicknameValue,"Alice");
  assert.deepEqual(removed,["OLD001"]);
  assert.equal(added[0][0],"NEW001");
  assert.equal(player.link("https://chess.test"),`https://chess.test/#player=${recovery}`);
  assert.equal(calls[0][0],"/api/player/restore");
  assert.equal(JSON.parse(calls[0][1].body).recovery,recovery);
});

test("regeneration replaces recovery while retaining this device's session", async () => {
  let action;
  const player = createPlayerIdentity({storage:storage(), fetchImpl:async (url, init) => {
    action = [url,init]; return {ok:true,json:async () => url.endsWith("create") ? {token,recovery,seats:[]} : {recovery:newer}};
  }});
  await player.init(); await player.regenerate();
  assert.equal(player.token,token);
  assert.equal(player.link("https://chess.test"),`https://chess.test/#player=${newer}`);
  assert.equal(action[1].headers["X-Player-Token"],token);
});
