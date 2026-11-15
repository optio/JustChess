import test from "node:test";
import assert from "node:assert/strict";
import { createNicknameEditor, createPlayerIdentity, recoveryFragment } from "../../static/js/player-identity.js";

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

test("nickname editor preserves drafts across refresh and returns saved names to display", async () => {
  let saved = "", value;
  const editor = createNicknameEditor({getName: () => saved, save: async draft => { value = draft; saved = draft; return {ok:true}; }});
  assert.deepEqual(editor.state, {draft:"",editing:true,pending:false});
  editor.change("Alice"); await editor.submit();
  assert.equal(value,"Alice"); assert.equal(editor.state.editing,false);
  editor.begin(); editor.change("Draft"); saved = "Name from another device"; editor.sync();
  assert.equal(editor.state.draft,"Draft"); assert.equal(editor.state.editing,true);
  await editor.submit(); assert.equal(saved,"Draft"); assert.equal(editor.state.editing,false);
  editor.begin(); editor.change(""); await editor.submit();
  assert.equal(editor.state.editing,true); assert.equal(editor.state.draft,"");
});

test("pending nickname save blocks duplicates and failures retain editable draft", async () => {
  let finish, calls = 0, saved = "Alice";
  const editor = createNicknameEditor({getName:() => saved, save:() => {calls++; return new Promise(resolve => {finish = resolve;});}});
  editor.begin(); editor.change("Invalid draft");
  const pending = editor.submit();
  assert.equal(editor.state.pending,true);
  assert.equal(await editor.submit(),null); assert.equal(calls,1);
  saved = "Refreshed name"; editor.sync(); assert.equal(editor.state.draft,"Invalid draft");
  finish({ok:false,message:"Choose another nickname"});
  assert.equal((await pending).ok,false); assert.equal(editor.state.pending,false);
  assert.equal(editor.state.editing,true); assert.equal(editor.state.draft,"Invalid draft");
});
