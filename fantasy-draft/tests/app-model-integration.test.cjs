"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

function element() {
  const listeners = new Map();
  const attributes = new Map();
  const children = new Map();
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
    addEventListener(type, listener) { listeners.set(type, listener); },
    dispatch(type, event = {}) { listeners.get(type)?.(event); },
    setAttribute(name, value) { attributes.set(name, String(value)); },
    getAttribute(name) { return attributes.get(name) || null; },
    querySelector(selector) { if (!children.has(selector)) children.set(selector, element()); return children.get(selector); },
    click() {},
    close() {},
    showModal() {},
    focus() {},
  };
}

function boot(modelPackageOverride) {
  const elements = new Map();
  const store = new Map();
  const documentListeners = new Map();
  const document = {
    hidden: false,
    body: element(),
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    addEventListener(type, listener) { documentListeners.set(type, listener); },
    createElement() { return element(); },
  };
  const context = {
    console,
    document,
    localStorage: {
      getItem(key) { return store.has(key) ? store.get(key) : null; },
      setItem(key, value) { store.set(key, String(value)); },
      removeItem(key) { store.delete(key); },
    },
    location: { origin: "https://example.test", pathname: "/fantasy-draft/", search: "" },
    navigator: {},
    URL: { createObjectURL() { return "blob:test"; }, revokeObjectURL() {} },
    Blob: class Blob {},
    setTimeout() { return 1; },
    clearTimeout() {},
    setInterval() { return 1; },
    clearInterval() {},
    requestAnimationFrame(callback) { callback(); },
    confirm() { return false; },
    prompt() { return null; },
    CustomEvent: class CustomEvent { constructor(type, options = {}) { this.type = type; this.detail = options.detail; } },
    addEventListener() {},
    postMessage() {},
    structuredClone,
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(read("data/players.js"), context, { filename: "players.js" });
  vm.runInContext(read("data/model-package.js"), context, { filename: "model-package.js" });
  vm.runInContext(read("data/opponent-intent-package.js"), context, { filename: "opponent-intent-package.js" });
  if (modelPackageOverride) context.DRAFT_INTELLIGENCE_PACKAGE = modelPackageOverride(context.PLAYER_DATA);
  vm.runInContext(read("model/model-adapter.js"), context, { filename: "model-adapter.js" });
  vm.runInContext(read("model/opponent-intent.js"), context, { filename: "opponent-intent.js" });
  vm.runInContext(read("app.js"), context, { filename: "app.js" });
  return { context, elements, documentListeners };
}

function clickDocument(booted, selector, dataset) {
  booted.documentListeners.get("click")({
    target: { closest: (requested) => requested === selector ? { dataset } : null },
  });
}

const fallback = boot();
assert.equal(fallback.context.DraftCommandLive.modelHealth().mode, "fallback");
assert.equal(fallback.elements.get("modelStatusBadge").textContent, "Provisional");
assert.match(fallback.elements.get("modelStatusCopy").textContent, /ADVISORY \/ UNCALIBRATED/i);
assert.match(fallback.elements.get("decisionStrip").innerHTML, /ADVISORY/);
assert.match(fallback.elements.get("decisionStrip").innerHTML, /UNCALIBRATED/);
assert.match(fallback.elements.get("playerTable").innerHTML, /UNCAL\./);
assert.match(fallback.elements.get("playerTable").innerHTML, /call-advisory/);
assert.doesNotMatch(fallback.elements.get("playerTable").innerHTML, /call-(take|wait|position-cliff)/);
const fallbackRecommendations = fallback.context.DraftCommandLive.recommendations();
for (const key of ["bestPlayer", "bestValue", "bestFit", "bestCeiling", "safestWait", "projectedTarget", "bestPickNow"]) {
  assert.ok(fallbackRecommendations[key]?.player, `${key} should resolve a player`);
}
assert.doesNotMatch(fallback.elements.get("playerTable").innerHTML, /call-pass/);
assert.equal(fallback.context.PLAYER_DATA_META.snapshotDate, "2026-08-27");
const espnBoard = fallback.context.DraftCommandLive.boardOrder();
assert.deepEqual(Array.from(espnBoard.slice(0, 4), (player) => player.name), ["Jahmyr Gibbs", "Bijan Robinson", "Ja'Marr Chase", "Puka Nacua"]);
assert.ok(espnBoard.every((player, index) => index === 0 || espnBoard[index - 1].roomRank <= player.roomRank), "ESPN board should be in ascending room-rank order");
assert.equal(espnBoard[4].name, "Jonathan Taylor");
const sleeperBoard = fallback.context.DraftCommandLive.boardOrder("sleeper");
assert.equal(sleeperBoard[4].name, "Christian McCaffrey");
assert.ok(sleeperBoard.every((player, index) => index === 0 || sleeperBoard[index - 1].roomRank <= player.roomRank), "Sleeper board should be in ascending room-rank order");
assert.match(fallback.elements.get("boardOrderNote").textContent, /ESPN default room rank.*low to high/i);
assert.match(fallback.elements.get("modelSourceNote").innerHTML, /Aug\. 27, 2026/);
assert.equal(fallback.context.DraftCommandLive.opponentModelHealth().mode, "live");
assert.equal(fallback.context.DraftCommandLive.opponentBoard().opponents.length, 9);
assert.match(fallback.elements.get("onClockManagerCard").innerHTML, /Justin Gerkin/);
assert.match(fallback.elements.get("opponentBoard").innerHTML, /ESPN 10/);

const leagueValueDescending = fallback.context.DraftCommandLive.decisionBoard({ key: "leagueValue", direction: "desc" });
assert.ok(leagueValueDescending.every((player, index) => index === 0 || leagueValueDescending[index - 1].leagueValue >= player.leagueValue), "League Value must sort best to worst on first click");
fallback.context.DraftCommandLive.setBoardSort("leagueValue");
assert.match(fallback.elements.get("boardOrderNote").textContent, /League Value.*high to low/i);
fallback.context.DraftCommandLive.setBoardSort("leagueValue");
assert.match(fallback.elements.get("boardOrderNote").textContent, /League Value.*low to high/i);
const opponentWindow = fallback.context.DraftCommandLive.opponentWindow({ simulations: 20, targetPlayerIds: fallback.context.PLAYER_DATA.slice(0, 8).map((player) => player.id) });
assert.equal(opponentWindow.interveningPicks.length, 4);
assert.ok(opponentWindow.threats.every((threat) => Math.abs(threat.probabilityTakenBeforeTony + threat.probabilitySurviving - 1) < 1e-12));

// Decision Board sorting is a deterministic view-only operation.
const boardUI = boot();
const pickBeforeSort = boardUI.context.DraftCommandLive.state().currentPick;
const recommendationBeforeSort = boardUI.context.DraftCommandLive.recommendations().bestPickNow.player.id;
clickDocument(boardUI, "[data-board-sort]", { boardSort: "leagueValue" });
let sortedBoard = boardUI.context.DraftCommandLive.decisionBoard();
assert.ok(sortedBoard.every((player, index) => index === 0 || sortedBoard[index - 1].leagueValue >= player.leagueValue), "first League Value click should sort best value to worst");
assert.equal(boardUI.context.DraftCommandLive.boardSort().key, "leagueValue");
assert.equal(boardUI.context.DraftCommandLive.boardSort().direction, "desc");
assert.match(boardUI.elements.get("boardOrderNote").textContent, /League Value.*high to low/i);
assert.equal(boardUI.context.DraftCommandLive.state().currentPick, pickBeforeSort);
assert.equal(boardUI.context.DraftCommandLive.recommendations().bestPickNow.player.id, recommendationBeforeSort);

clickDocument(boardUI, "[data-board-sort]", { boardSort: "leagueValue" });
sortedBoard = boardUI.context.DraftCommandLive.decisionBoard();
assert.ok(sortedBoard.every((player, index) => index === 0 || sortedBoard[index - 1].leagueValue <= player.leagueValue), "second League Value click should reverse the numeric order");
assert.equal(boardUI.context.DraftCommandLive.boardSort().direction, "asc");

clickDocument(boardUI, "[data-board-sort]", { boardSort: "espnPrice" });
sortedBoard = boardUI.context.DraftCommandLive.boardOrder();
assert.ok(sortedBoard.every((player, index) => index === 0 || sortedBoard[index - 1].roomRank <= player.roomRank), "platform Price click should independently restore best room order first");
assert.equal(boardUI.context.DraftCommandLive.boardSort().key, "espnPrice");
assert.equal(boardUI.context.DraftCommandLive.boardSort().direction, "asc");

clickDocument(boardUI, "[data-board-sort]", { boardSort: "leagueValue" });
clickDocument(boardUI, "[data-pos]", { pos: "RB" });
sortedBoard = boardUI.context.DraftCommandLive.decisionBoard();
assert.ok(sortedBoard.length > 1 && sortedBoard.every((player) => player.position === "RB"), "position filtering should remain active while sorted");
assert.ok(sortedBoard.every((player, index) => index === 0 || sortedBoard[index - 1].leagueValue >= player.leagueValue));
const searchedPlayer = sortedBoard[0];
boardUI.elements.get("playerSearch").dispatch("input", { target: { value: searchedPlayer.name } });
sortedBoard = boardUI.context.DraftCommandLive.decisionBoard();
assert.deepEqual(Array.from(sortedBoard, (player) => player.id), [searchedPlayer.id], "search should compose with position and numeric sorting");
assert.equal(boardUI.context.DraftCommandLive.recordManualPick(searchedPlayer.id), undefined);
assert.equal(boardUI.context.DraftCommandLive.decisionBoard().some((player) => player.id === searchedPlayer.id), false, "drafted players must remain excluded from every sorted view");
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
assert.equal(fallback.context.DraftCommandLive.modelHealth().decisionPolicyApproved, false);
const syncPlayers = fallback.context.PLAYER_DATA.filter((player) => ![68, 24, 45, 50, 90, 30, 47, 52, 26, 33].includes(player.id)).slice(0, 5);
const syncThroughTony = fallback.context.DraftCommandLive.ingestSnapshot({
  source: "sleeper",
  syncKey: "test-draft",
  teamCount: 10,
  rounds: 16,
  picks: syncPlayers.map((player, index) => ({ overall: index + 1, playerName: player.name, externalId: `fixture-${index + 1}` })),
});
assert.equal(syncThroughTony.ok, true);
assert.equal(fallback.context.DraftCommandLive.state().currentPick, 6);
const audit = fallback.context.DraftCommandLive.auditExport();
assert.equal(audit.schemaVersion, "draft-command-audit-v2");
assert.equal(audit.draftEvents.length, 5);
assert.ok(audit.auditTrail.length >= 5);
assert.equal(audit.sourceObservations.length, 5);
const tonyAudit = audit.auditTrail.find((record) => record.event?.overall === 5 && record.recommendationBeforeTonyPick);
assert.ok(tonyAudit.recommendationBeforeTonyPick);
assert.equal(tonyAudit.recommendationBeforeTonyPick.advisoryState.label, "ADVISORY");
assert.equal(tonyAudit.recommendationBeforeTonyPick.advisoryState.calibrated, false);
assert.equal(tonyAudit.model.modelVersion, "fallback-2026.08.27");
assert.equal(tonyAudit.marketSnapshot.snapshotDate, "2026-08-27");
assert.equal(tonyAudit.source, "sleeper-sync");
assert.equal(tonyAudit.rosterState.teams.length, 10);
assert.ok(tonyAudit.recommendationBeforeTonyPick.components.bestPlayer.name);

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
assert.equal(health.decisionPolicyApproved, false);
assert.equal(research.context.DraftCommandLive.recommendations().bestPlayer.player.name, "Justin Jefferson");
assert.equal(research.elements.get("modelStatusBadge").textContent, "Research candidate");
assert.match(research.elements.get("bestOverallCard").innerHTML, /Research fixture/);
assert.match(research.elements.get("decisionStrip").innerHTML, /ADVISORY/);

const invalidPackage = boot(() => ({ schemaVersion: "99.0.0", season: 2025, players: [] }));
assert.equal(invalidPackage.context.DraftCommandLive.modelHealth().mode, "fallback");
assert.equal(invalidPackage.context.DraftCommandLive.modelHealth().valid, false);
assert.ok(invalidPackage.context.DraftCommandLive.recommendations().bestPlayer.player);
assert.match(invalidPackage.elements.get("playerTable").innerHTML, /data-draft-id/);
assert.match(invalidPackage.elements.get("decisionStrip").innerHTML, /ADVISORY/);
const invalidSync = invalidPackage.context.DraftCommandLive.ingestSnapshot({ source: "espn", teamCount: 12, rounds: 16, picks: [] });
assert.equal(invalidSync.ok, false);
assert.equal(invalidPackage.context.DraftCommandLive.state().currentPick, 1);

const index = read("index.html");
const scripts = [...index.matchAll(/<script src="([^"]+)"/g)].map((match) => match[1]);
assert.deepEqual(scripts.slice(-7), [
  "./data/players.js",
  "./data/model-package.js",
  "./data/opponent-intent-package.js",
  "./model/model-adapter.js",
  "./model/opponent-intent.js",
  "./app.js",
  "./sync.js",
]);
for (const id of ["modelStatusBadge", "modelVersion", "modelFreshness", "modelCoverage", "modelStatusCopy", "modelSourceNote", "snapshotNote", "decisionLenses", "roomRankNote", "boardOrderNote", "exportAuditLog", "nextPickHeader", "callHeader", "onClockManagerCard", "opponentBoard", "threatBoard", "espnAdpHeader", "takenBeforeTonyHeader", "opponentThreatHeader"]) {
  assert.match(index, new RegExp(`id="${id}"`));
}

const css = read("styles.css");
for (const tinySize of ["6px", "7px", "8px", "9px"]) {
  assert.doesNotMatch(css, new RegExp(`font(?:-size)?:[^;\\n]*\\b${tinySize}\\b`), `readability pass should remove ${tinySize} interface type`);
}

console.log("app model-integration tests passed");
