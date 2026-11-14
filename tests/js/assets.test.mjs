// Asset checks: every font and piece in static/ASSETS.md exists with its pinned sha256,
// the CSS only references files that exist, and the licence files ship with the assets.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const STATIC = fileURLToPath(new URL("../../static/", import.meta.url));
const ROW = /^\|\s*`([^`]+)`\s*\|.*\|\s*([0-9a-f]{64})\s*\|\s*$/;

function manifestRows() {
  return readFileSync(join(STATIC, "ASSETS.md"), "utf8")
    .split("\n")
    .map((line) => ROW.exec(line))
    .filter(Boolean)
    .map(([, path, sha256]) => ({ path, sha256 }));
}

test("every font and piece in ASSETS.md exists and matches its sha256", () => {
  const rows = manifestRows();
  const paths = rows.map((row) => row.path);
  assert.equal(paths.filter((p) => p.startsWith("fonts/") && p.endsWith(".woff2")).length, 6, "six font files");
  assert.equal(paths.filter((p) => p.startsWith("pieces/cburnett/") && p.endsWith(".svg")).length, 12, "twelve pieces");
  for (const { path, sha256 } of rows) {
    const file = join(STATIC, path);
    assert.ok(existsSync(file), `${path} is missing`);
    assert.equal(createHash("sha256").update(readFileSync(file)).digest("hex"), sha256, `${path} does not match its pinned sha256`);
  }
  const shipped = readdirSync(join(STATIC, "pieces/cburnett")).filter((f) => f.endsWith(".svg"));
  assert.deepEqual(shipped.map((f) => `pieces/cburnett/${f}`).sort(), paths.filter((p) => p.endsWith(".svg")).sort(),
    "every shipped piece is listed in ASSETS.md");
});

test("base.css, board.css and tokens.css only reference files that exist, all same-origin", () => {
  let references = 0;
  for (const name of ["tokens.css", "base.css", "board.css"]) {
    const file = join(STATIC, "css", name);
    const css = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    for (const [, raw] of css.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
      assert.doesNotMatch(raw, /^(https?:)?\/\//, `${name} must not load ${raw} from another origin`);
      if (raw.startsWith("data:")) continue;
      references += 1;
      assert.ok(existsSync(resolve(dirname(file), raw)), `${name} references missing ${raw}`);
    }
  }
  assert.equal(references, 6, "the six @font-face sources are checked");
});

test("licence files ship beside the fonts and the pieces", () => {
  for (const family of ["libre-caslon-display", "libre-caslon-text", "atkinson-hyperlegible"]) {
    const text = readFileSync(join(STATIC, "fonts", `LICENSE-${family}.txt`), "utf8");
    assert.match(text, /SIL Open Font License, Version 1\.1/, `${family} licence is the OFL`);
  }
  const pieces = readFileSync(join(STATIC, "pieces/cburnett/LICENSE.md"), "utf8");
  assert.match(pieces, /Pieces: cburnett, CC BY-SA 3\.0/);
  assert.match(pieces, /Colin M\.L\. Burnett/);
});
