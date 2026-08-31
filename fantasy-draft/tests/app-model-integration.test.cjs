"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

function element() {
  return {
    textContent: "",
    innerHTML: "",
    value: "",
    hidden: false,
    disabled: false,
    style: {},
    dataset: {},
    className: "",
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {},
    click() {},
    close() {},
    showModal() {},
    focus() {},
  };
}

function boot(modelPackageOverride) {
  const elements = new Map();
  const store = new Map();
  const document = {
    hidden: false,
    body: element(),
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    addEventListener() {},
    createElement() { return element(); },
  };
  const context = {
    console,
    document,
    localStorage: {
      getItem(key) { return store.has(key) ? store.get(key) : null; },
      setItem(key, value) { store.set(key, String(value)); },
    },
    location: { origin: "https://example.test", pathname: "/fantasy-draft/", search: "" },
    navigator: {},
    URL: { createObjectURL() { return "blob:test"; }, revokeObjectURL() {} },
    Blob: class Blob {},
    setTimeout,
    clearTimeout,
    setInterval() { return 1; },
    clearInterval() {},
    requestAnimationFrame(callback) { callback(); },
    confirm() { return false; },
    addEventListener() {},
    postMessage() {},
    structuredClone,
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(read("data/players.js"), context, { filename: "players.js" });
  vm.runInContext(read("data/model-package.js"), context, { filename: "model-package.js" });
  if (modelPackageOverride) context.DRAFT_INTELLIGENCE_PACKAGE = modelPackageOverride(context.PLAYER_DATA);
  vm.runInContext(read("model/model-adapter.js"), context, { filename: "model-adapter.js" });
  vm.runInContext(read("app.js"), context, { filename: "app.js" });
  return { context, elements };
}

const fallback = boot();
assert.equal(fallback.context.DraftCommandLive.modelHealth().mode, "fallback");
assert.equal(fallback.elements.get("modelStatusBadge").textContent, "Provisional");
assert.match(fallback.elements.get("modelStatusCopy").textContent, /adapter is ready/i);
const fallbackRecommendations = fallback.context.DraftCommandLive.recommendations();
for (const key of ["bestPlayer", "bestValue", "bestFit", "bestCeiling", "safestWait", "projectedTarget", "bestPickNow"]) {
  assert.ok(fallbackRecommendations[key]?.player, `${key} should resolve a player`);
}
assert.doesNotMatch(fallback.elements.get("playerTable").innerHTML, /call-pass/);
const mismatch = fallback.context.DraftCommandLive.ingestSnapshot({ source: "sleeper", teamCount: 12, rounds: 16, picks: [] });
assert.equal(mismatch.ok, false);
assert.equal(mismatch.code, "FORMAT_MISMATCH");
const firstPlayer = fallback.context.PLAYER_DATA.find((player) => player.id === 1);
const syncResult = fallback.context.DraftCommandLive.ingestSnapshot({
  source: "sleeper",
  syncKey: "test-draft",
  teamCount: 10,
  rounds: 16,
  picks: [{ overall: 1, playerName: firstPlayer.name, externalId: "fixture-1" }],
});
assert.equal(syncResult.ok, true);
assert.equal(syncResult.added, 1);
assert.equal(fallback.context.DraftCommandLive.state().currentPick, 2);
assert.equal(fallback.context.DraftCommandLive.modelHealth().mode, "fallback");

const research = boot((players) => ({
  schemaVersion: "1.0.0",
  packageId: "integration-fixture",
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  metadata: {
    status: "candidate",
    modelVersion: "candidate-integration-1",
    generatedAt: "2026-08-31T00:00:00Z",
    effectiveAt: "2026-08-31T00:00:00Z",
    sources: [{ id: "fixture", layer: "player-truth" }],
  },
  decisionPolicy: {},
  players: [{
    playerId: players.find((player) => player.name === "Justin Jefferson").id,
    outcome: { ceilingProbability: 0.99, bustProbability: 0.01, eliteProbability: 0.99 },
    leagueValue: { score: 500, fairPick: 1, tierId: "WR-X", tierLabel: "Research fixture" },
    market: { espn: { price: 5 } },
    survival: { espn: { anchors: { "16": 0.77 } } },
    decision: { confidence: 0.99, reasons: ["fixture reason"] },
  }],
}));
const health = research.context.DraftCommandLive.modelHealth();
assert.equal(health.mode, "research");
assert.equal(health.modelVersion, "candidate-integration-1");
assert.equal(research.context.DraftCommandLive.recommendations().bestPlayer.player.name, "Justin Jefferson");
assert.equal(research.elements.get("modelStatusBadge").textContent, "Research candidate");
assert.match(research.elements.get("bestOverallCard").innerHTML, /Research fixture/);

const index = read("index.html");
const scripts = [...index.matchAll(/<script src="([^"]+)"/g)].map((match) => match[1]);
assert.deepEqual(scripts.slice(-5), [
  "./data/players.js",
  "./data/model-package.js",
  "./model/model-adapter.js",
  "./app.js",
  "./sync.js",
]);
for (const id of ["modelStatusBadge", "modelVersion", "modelFreshness", "modelCoverage", "modelStatusCopy", "modelSourceNote", "snapshotNote", "decisionLenses"]) {
  assert.match(index, new RegExp(`id="${id}"`));
}

console.log("app model-integration tests passed");
