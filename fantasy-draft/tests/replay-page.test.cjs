"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const index = fs.readFileSync(path.join(root, "replay/index.html"), "utf8");
const appIndex = fs.readFileSync(path.join(root, "index.html"), "utf8");
const replayScript = fs.readFileSync(path.join(root, "replay/replay.js"), "utf8");

const scripts = [...index.matchAll(/<script src="([^"]+)"/g)].map((match) => match[1]);
assert.deepEqual(scripts, [
  "../data/players.js",
  "../data/model-package.js",
  "../model/model-adapter.js",
  "./replay-engine.js",
  "./replay.js",
]);
for (const id of ["fileInput", "loadSample", "runReplay", "exportReport", "strategyRows", "calibrationChart", "decisionRows", "issuesPanel"]) {
  assert.match(index, new RegExp(`id="${id}"`));
}
assert.match(appIndex, /href="\.\/replay\/"/);
assert.doesNotMatch(replayScript, /localStorage|sessionStorage/);

console.log("replay-page tests passed");
