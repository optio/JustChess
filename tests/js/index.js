"use strict";
// Entry point for the recorded unit command `node --test tests/js/`.
//
// Node 24 treats a directory argument to `--test` as a module path, so it
// resolves this folder to index.js. This file loads every *.test.mjs file here,
// in name order, into the test runner. Running a single file directly
// (`node --test tests/js/geometry.test.mjs`) also works.

const { readdirSync } = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

async function loadAll() {
  const files = readdirSync(__dirname).filter((name) => name.endsWith(".test.mjs")).sort();
  if (files.length === 0) throw new Error(`no *.test.mjs files found in ${__dirname}`);
  for (const name of files) {
    await import(pathToFileURL(path.join(__dirname, name)).href);
  }
}

loadAll().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
