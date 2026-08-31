"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

function element() {
  return {
    textContent: "", innerHTML: "", value: "", hidden: false, disabled: false, style: {}, dataset: {}, className: "",
    classList: { add() {}, remove() {}, toggle() {} }, addEventListener() {}, setAttribute() {}, click() {}, close() {}, showModal() {}, focus() {},
  };
}

function boot({ storage = new Map(), packageOverride = null } = {}) {
  const elements = new Map();
  const timerQueue = [];
  const cancelled = new Set();
  let timerId = 0;
  let uuid = 0;
  const document = {
    hidden: false, body: element(),
    getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
    querySelectorAll() { return []; }, querySelector() { return null; }, addEventListener() {}, createElement() { return element(); },
  };
  const context = {
    console, document, structuredClone,
    __DRAFT_COMMAND_TEST__: true,
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); },
      removeItem(key) { storage.delete(key); },
    },
    crypto: { randomUUID() { uuid += 1; return `session-${uuid}`; } },
    location: { origin: "https://tofo21.github.io", pathname: "/Cool-Tools/fantasy-draft/", search: "" },
    URL: { createObjectURL() { return "blob:test"; }, revokeObjectURL() {} }, Blob: class Blob {},
    setTimeout(callback) { timerId += 1; timerQueue.push({ id: timerId, callback }); return timerId; },
    clearTimeout(id) { cancelled.add(id); }, setInterval() { return 1; }, clearInterval() {},
    requestAnimationFrame(callback) { callback(); }, confirm() { return true; }, prompt() { return null; },
    addEventListener() {}, dispatchEvent() {}, postMessage() {},
    CustomEvent: class CustomEvent { constructor(type, options = {}) { this.type = type; this.detail = options.detail; } },
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(read("data/players.js"), context, { filename: "players.js" });
  vm.runInContext(read("data/model-package.js"), context, { filename: "model-package.js" });
  vm.runInContext(read("data/opponent-intent-package.js"), context, { filename: "opponent-intent-package.js" });
  if (packageOverride) context.OPPONENT_INTENT_PACKAGE = packageOverride(context.OPPONENT_INTENT_PACKAGE);
  vm.runInContext(read("model/model-adapter.js"), context, { filename: "model-adapter.js" });
  vm.runInContext(read("model/opponent-intent.js"), context, { filename: "opponent-intent.js" });
  vm.runInContext(read("app.js"), context, { filename: "app.js" });
  function flushTimers(max = 100) {
    let count = 0;
    while (timerQueue.length && count < max) {
      const timer = timerQueue.shift();
      if (!cancelled.has(timer.id)) timer.callback();
      count += 1;
    }
    if (timerQueue.length) throw new Error("timer queue did not settle");
  }
  return { context, elements, storage, flushTimers };
}

function snapshot(picks) {
  return { source: "espn", syncKey: "integration-fixture", teamCount: 10, rounds: 16, picks, timestamp: "2026-08-31T23:00:00Z" };
}

function sourcePick(player, overall) {
  return { overall, playerName: player.name, externalId: `espn-${player.id}` };
}

// Initial live views populate, and simulation remains outside persisted state.
const initial = boot();
initial.flushTimers();
assert.equal(initial.context.DraftCommandLive.opponentModelHealth().mode, "live");
assert.equal(initial.context.DraftCommandLive.opponentModelHealth().managerWeights.position, 0);
assert.equal(initial.context.DraftCommandLive.opponentModelHealth().managerWeights.player, 0);
assert.match(initial.elements.get("onClockManagerCard").innerHTML, /Justin Gerkin/);
assert.match(initial.elements.get("opponentBoard").innerHTML, /BEFORE TONY/);
assert.match(initial.elements.get("threatBoardStatus").textContent, /8 seeded runs/);
assert.match(initial.elements.get("threatBoard").innerHTML, /taken/);
const storedInitial = initial.storage.get("draft-command-2026-v3");
assert.doesNotMatch(storedInitial, /OPPONENT_INTENT|managerThreatBreakdown|probabilityTakenBeforeTony/);

// Manual picks refresh the manager card and remove unavailable players.
assert.equal(initial.context.DraftCommandLive.recordManualPick(1), undefined);
initial.flushTimers();
assert.equal(initial.context.DraftCommandLive.state().currentPick, 2);
assert.match(initial.elements.get("onClockManagerCard").innerHTML, /Dan Merrick/);
assert.ok(!initial.context.DraftCommandLive.decisionBoard().some((player) => player.id === 1));
assert.ok(!initial.context.DraftCommandLive.opponentWindow({ simulations: 12 }).threats.some((player) => player.playerId === 1));

// Sorting uses numeric fields, while search/position filtering and exclusion remain intact.
initial.context.DraftCommandLive.setBoardSort("leagueValue");
assert.equal(initial.context.DraftCommandLive.boardSort().direction, "desc");
const sorted = initial.context.DraftCommandLive.decisionBoard();
assert.ok(sorted.every((player, index) => index === 0 || sorted[index - 1].leagueValue >= player.leagueValue));
initial.context.DraftCommandLive.setPositionFilter("WR");
initial.context.DraftCommandLive.setPlayerSearch("Chase");
const filtered = initial.context.DraftCommandLive.decisionBoard();
assert.ok(filtered.length >= 1);
assert.ok(filtered.every((player) => player.position === "WR" && /chase/i.test(player.name)));
assert.ok(filtered.every((player) => player.id !== 1));

// ESPN observations, including an unresolved middle pick, do not stop later forecasts.
const espn = boot();
const p1 = espn.context.PLAYER_DATA[0];
const p3 = espn.context.PLAYER_DATA[2];
const ingestion = espn.context.DraftCommandLive.ingestSnapshot(snapshot([
  sourcePick(p1, 1),
  { overall: 2, playerName: "Unmapped Fixture Player", externalId: "unknown-2" },
  sourcePick(p3, 3),
]));
espn.flushTimers();
assert.equal(ingestion.ok, true);
assert.equal(espn.context.DraftCommandLive.state().currentPick, 4);
assert.match(espn.elements.get("onClockManagerCard").innerHTML, /Matt Hull/);
assert.equal(espn.context.DraftCommandLive.opponentBoard().opponents.length, 9);

// Refresh reconstructs forecasts from canonical observations only.
const refreshed = boot({ storage: espn.storage });
refreshed.flushTimers();
assert.equal(refreshed.context.DraftCommandLive.state().currentPick, 4);
assert.match(refreshed.elements.get("onClockManagerCard").innerHTML, /Matt Hull/);

// Hard Reset clears dynamic prediction inputs and returns to the initial room.
assert.equal(refreshed.context.DraftCommandLive.hardReset({ confirmed: true }), true);
refreshed.flushTimers();
assert.equal(refreshed.context.DraftCommandLive.state().events.length, 0);
assert.equal(refreshed.context.DraftCommandLive.state().currentPick, 1);
assert.match(refreshed.elements.get("onClockManagerCard").innerHTML, /Justin Gerkin/);

// Malformed Opponent Intent fails safely; Manual remains usable and no loading state sticks.
const malformed = boot({ packageOverride: () => ({ schemaVersion: "99.0.0", season: 2025, managers: [] }) });
malformed.flushTimers();
assert.equal(malformed.context.DraftCommandLive.opponentModelHealth().mode, "fallback");
assert.doesNotMatch(malformed.elements.get("opponentIntentStatus").textContent, /loading/i);
assert.doesNotThrow(() => malformed.context.DraftCommandLive.recordManualPick(2));
assert.equal(malformed.context.DraftCommandLive.state().events.length, 1);

// Complete 160-pick ingestion remains intact with the public runtime loaded.
const complete = boot();
const picks = complete.context.PLAYER_DATA.slice(0, 160).map((player, index) => sourcePick(player, index + 1));
const completeResult = complete.context.DraftCommandLive.ingestSnapshot(snapshot(picks));
complete.flushTimers();
assert.equal(completeResult.ok, true);
assert.equal(complete.context.DraftCommandLive.state().events.length, 160);
assert.equal(complete.context.DraftCommandLive.state().currentPick, 161);
assert.equal(complete.context.DraftCommandLive.opponentBoard().opponents.length, 9);
assert.match(complete.elements.get("threatBoardStatus").textContent, /Complete/);
const persisted = complete.storage.get("draft-command-2026-v3");
const persistedBytes = Buffer.byteLength(persisted, "utf8");
assert.ok(persistedBytes < 400_000, `active state should remain bounded; got ${persistedBytes} bytes`);
assert.doesNotMatch(persisted, /managerThreatBreakdown|tierSurvival|playerMarket/);

console.log(`opponent intent app tests passed (160 picks; ${persistedBytes} persisted bytes)`);
