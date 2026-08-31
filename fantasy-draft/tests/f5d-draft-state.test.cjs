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
    classList: { add() {}, remove() {}, toggle() {} }, addEventListener() {}, click() {}, close() {}, showModal() {}, focus() {},
  };
}

function boot(options = {}) {
  const elements = new Map();
  const storage = options.storage || new Map();
  let uuid = 0;
  const document = {
    body: element(), hidden: false,
    getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
    querySelectorAll() { return []; }, querySelector() { return null; }, addEventListener() {}, createElement() { return element(); },
  };
  const context = {
    console, document, structuredClone,
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) {
        if (options.setItem) return options.setItem({ key, value: String(value), storage });
        storage.set(key, String(value));
      },
      removeItem(key) { storage.delete(key); },
    },
    crypto: { randomUUID() { uuid += 1; return `session-${uuid}`; } },
    location: { origin: "https://tofo21.github.io", pathname: "/Cool-Tools/fantasy-draft/", search: "" },
    URL: { createObjectURL() { return "blob:test"; }, revokeObjectURL() {} }, Blob: class Blob {},
    setTimeout() { return 1; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {},
    requestAnimationFrame(callback) { callback(); }, confirm() { return false; }, prompt() { return null; },
    addEventListener() {}, dispatchEvent() {}, postMessage() {},
    CustomEvent: class CustomEvent { constructor(type, options = {}) { this.type = type; this.detail = options.detail; } },
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(read("data/players.js"), context, { filename: "players.js" });
  vm.runInContext(read("data/model-package.js"), context, { filename: "model-package.js" });
  vm.runInContext(read("model/model-adapter.js"), context, { filename: "model-adapter.js" });
  vm.runInContext(read("app.js"), context, { filename: "app.js" });
  return { context, storage, elements };
}

function quotaError() {
  const error = new Error("Browser storage quota exceeded");
  error.name = "QuotaExceededError";
  return error;
}

function snapshot(context, picks, overrides = {}) {
  return {
    source: "espn", syncKey: overrides.syncKey || "espn:same-room", teamCount: 10, rounds: 16,
    picks, timestamp: "2026-08-31T18:00:00Z", ...overrides,
  };
}

function pick(player, overall) {
  return { overall, playerName: player.name, externalId: `espn-${player.id}` };
}

// 1. Fresh state defaults to exact-source mode with no keeper seeds.
{
  const { context } = boot();
  const state = context.DraftCommandLive.state();
  assert.equal(state.keeperMode, false);
  assert.equal(state.keeperSeeds.length, 0);
  assert.equal(state.currentPick, 1);
}

// 2. A generic 160-pick mock completes from source observations with no duplicates.
{
  const { context } = boot();
  const picks = context.PLAYER_DATA.slice(0, 160).map((player, index) => pick(player, index + 1));
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, picks));
  const state = context.DraftCommandLive.state();
  assert.equal(result.ok, true);
  assert.equal(state.sourceObservations.length, 160);
  assert.equal(state.events.length, 160);
  assert.equal(new Set(state.events.map((event) => event.playerId)).size, 160);
  assert.equal(state.currentPick, 161);
}

// 3. Loading seeds is optional and future keeper costs do not jump past pick one.
{
  const { context } = boot();
  assert.equal(context.DraftCommandLive.setKeeperMode(true), true);
  const state = context.DraftCommandLive.state();
  assert.equal(state.keeperSeeds.length, 10);
  assert.equal(state.currentPick, 1);
}

// 3b. ESPN can expose a future keeper slot before the draft without creating false missing-pick alerts.
{
  const { context } = boot();
  const keeper = context.DraftCommandLive.configuredKeepers()[0];
  const player = context.PLAYER_DATA.find((item) => item.id === keeper.playerId);
  context.DraftCommandLive.ingestSnapshot(snapshot(context, [{ ...pick(player, keeper.overall), isKeeper: true }]));
  assert.equal(context.DraftCommandLive.state().currentPick, 1);
  assert.equal(context.DraftCommandLive.issues().length, 0);
}

// 4. Exact source/seed match confirms the seed without duplicating the roster event.
{
  const { context } = boot();
  context.DraftCommandLive.setKeeperMode(true);
  const keeper = context.DraftCommandLive.configuredKeepers()[0];
  const player = context.PLAYER_DATA.find((item) => item.id === keeper.playerId);
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(player, keeper.overall)]));
  const state = context.DraftCommandLive.state();
  assert.ok(result.reconciliation.some((item) => item.action === "seed-confirmed"));
  assert.equal(state.keeperSeeds.some((seed) => seed.overall === keeper.overall), false);
  assert.equal(state.events.length, 1);
  assert.equal(state.events[0].source, "espn-sync");
}

// 5. A different ESPN player at a seeded slot overrides that seed.
{
  const { context } = boot();
  context.DraftCommandLive.setKeeperMode(true);
  const keeper = context.DraftCommandLive.configuredKeepers()[0];
  const replacement = context.PLAYER_DATA.find((item) => !context.DraftCommandLive.configuredKeepers().some((seed) => seed.playerId === item.id));
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(replacement, keeper.overall)]));
  const state = context.DraftCommandLive.state();
  assert.ok(result.reconciliation.some((item) => item.action === "seed-overridden"));
  assert.equal(state.keeperSeeds.some((seed) => seed.overall === keeper.overall), false);
  assert.equal(state.events.find((event) => event.overall === keeper.overall).playerId, replacement.id);
}

// 6. ESPN observing a seeded player elsewhere moves it from the configured slot.
{
  const { context } = boot();
  context.DraftCommandLive.setKeeperMode(true);
  const keeper = context.DraftCommandLive.configuredKeepers()[0];
  const player = context.PLAYER_DATA.find((item) => item.id === keeper.playerId);
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(player, 1)]));
  const state = context.DraftCommandLive.state();
  assert.ok(result.reconciliation.some((item) => item.action === "seed-moved"));
  assert.equal(state.keeperSeeds.some((seed) => seed.playerId === player.id), false);
  assert.equal(state.events.find((event) => event.overall === 1).playerId, player.id);
}

// 7. An unknown player at 26 cannot stop picks 27-160 or the source-based cursor.
{
  const { context } = boot();
  const fullDraft = context.PLAYER_DATA.slice(0, 160).map((player, index) => pick(player, index + 1));
  fullDraft[25] = { overall: 26, playerName: "Unknown Practice Player", externalId: "unknown-26" };
  context.DraftCommandLive.ingestSnapshot(snapshot(context, fullDraft, { espnUrl: "https://fantasy.espn.com/football/mockdraft?fixture=1", bridgeVersion: "0.3.0" }));
  const state = context.DraftCommandLive.state();
  assert.equal(state.currentPick, 161);
  assert.equal(state.sourceObservations.length, 160);
  assert.equal(state.events.length, 159);
  assert.equal(new Set(state.events.map((event) => event.playerId)).size, 159);
  const observation = state.sourceObservations.find((item) => item.overall === 26);
  assert.equal(observation.round, 3);
  assert.equal(observation.roundPick, 6);
  assert.equal(observation.rawPlayerName, "Unknown Practice Player");
  assert.equal(observation.sourceUrl, "https://fantasy.espn.com/football/mockdraft?fixture=1");
  assert.equal(observation.resolutionStatus, "unresolved");
  const modeled = state.modeledEvents[0];
  assert.ok(modeled.playerId);
  assert.ok(modeled.manager);
  assert.equal(modeled.rosterAssignment, modeled.team);
  assert.equal(modeled.status, "source-confirmed");
  const issue = context.DraftCommandLive.issues().find((item) => item.overall === 26);
  assert.equal(issue.code, "PLAYER_NOT_ON_BOARD");
  assert.match(context.document.getElementById("draftAlerts").innerHTML, /Need pick for .* — Round 3, Pick 6/);
  const diagnostics = context.DraftCommandLive.auditExport().auditTrail.findLast((record) => record.action === "source-snapshot").details;
  assert.equal(diagnostics.rawSourcePickCount, 160);
  assert.equal(diagnostics.sourceObservedOveralls.length, 160);
  assert.equal(diagnostics.displayedNextPick, 161);
  assert.equal(diagnostics.unresolvedCount, 1);
  assert.ok(diagnostics.unresolvedReasonCodes.includes("PLAYER_NOT_ON_BOARD"));
}

// 8. A missing source pick before a later observation holds the cursor at the actual gap.
{
  const { context } = boot();
  const picks = context.PLAYER_DATA.slice(0, 27).map((player, index) => pick(player, index + 1)).filter((item) => item.overall !== 26);
  context.DraftCommandLive.ingestSnapshot(snapshot(context, picks));
  assert.equal(context.DraftCommandLive.state().currentPick, 26);
  assert.equal(context.DraftCommandLive.issues().find((item) => item.overall === 26).code, "SOURCE_PICK_MISSING");
}

// 9. An unresolved observation can be manually mapped without changing its source position.
{
  const { context } = boot();
  context.DraftCommandLive.ingestSnapshot(snapshot(context, [{ overall: 1, playerName: "Mystery Player", externalId: "mystery" }]));
  const player = context.PLAYER_DATA[0];
  assert.equal(context.DraftCommandLive.resolveObservation(1, player.id), true);
  const state = context.DraftCommandLive.state();
  assert.equal(state.events[0].source, "manual-resolution");
  assert.equal(state.sourceObservations[0].manualPlayerId, player.id);
  assert.equal(state.currentPick, 2);
}

// 10. Keeper players and slots have no permanent protection while seeds are off.
{
  const { context } = boot();
  const keeper = context.DraftCommandLive.configuredKeepers()[0];
  const player = context.PLAYER_DATA.find((item) => item.id === keeper.playerId);
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(player, 1)]));
  assert.equal(result.added, 1);
  assert.equal(context.DraftCommandLive.state().events[0].overall, 1);
}

// 11. Duplicate source players count as observations but never duplicate modeled rosters.
{
  const { context } = boot();
  const player = context.PLAYER_DATA[0];
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(player, 1), pick(player, 2)]));
  const state = context.DraftCommandLive.state();
  assert.equal(result.conflicts.length, 1);
  assert.equal(state.sourceObservations.length, 2);
  assert.equal(state.events.length, 1);
  assert.equal(state.currentPick, 3);
}

// 12. Hard reset clears every dynamic layer, turns seeds off, clears recovery, and is idempotent.
{
  const { context, storage } = boot();
  storage.set("draft-command-live-sync-v1", JSON.stringify({ source: "espn", sleeperDraftId: "old" }));
  context.DraftCommandLive.setKeeperMode(true);
  context.DraftCommandLive.recordManualPick(context.PLAYER_DATA.find((item) => !context.DraftCommandLive.configuredKeepers().some((seed) => seed.playerId === item.id)).id);
  const firstGeneration = context.DraftCommandLive.state().generation;
  assert.equal(context.DraftCommandLive.hardReset({ confirmed: true }), true);
  let state = context.DraftCommandLive.state();
  assert.equal(state.events.length, 0);
  assert.equal(state.sourceObservations.length, 0);
  assert.equal(state.keeperMode, false);
  assert.equal(state.keeperSeeds.length, 0);
  assert.equal(state.auditLog.length, 0);
  assert.equal(state.currentPick, 1);
  assert.equal(state.sourceIngestionPaused, true);
  assert.equal(storage.has("draft-command-2026-snapshots-v3"), false);
  assert.equal(storage.has("draft-command-live-sync-v1"), false);
  assert.equal(state.generation, firstGeneration + 1);
  context.DraftCommandLive.hardReset({ confirmed: true });
  state = context.DraftCommandLive.state();
  assert.equal(state.currentPick, 1);
  assert.equal(state.generation, firstGeneration + 2);
}

// 13. Future ESPN keeper slots can be observed before the draft without moving pick one or raising false gap alerts.
{
  const { context } = boot();
  const futureKeepers = context.DraftCommandLive.configuredKeepers().map((keeper) => {
    const player = context.PLAYER_DATA.find((item) => item.id === keeper.playerId);
    return { ...pick(player, keeper.overall), isKeeper: true };
  });
  context.DraftCommandLive.ingestSnapshot(snapshot(context, futureKeepers));
  assert.equal(context.DraftCommandLive.state().sourceObservations.length, 10);
  assert.equal(context.DraftCommandLive.state().currentPick, 1);
  assert.equal(context.DraftCommandLive.issues().filter((item) => item.code === "SOURCE_PICK_MISSING").length, 0);
}

// 14. Old generation/session snapshots are rejected after reset.
{
  const { context } = boot();
  const old = context.DraftCommandLive.syncIdentity();
  context.DraftCommandLive.hardReset({ confirmed: true });
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(context.PLAYER_DATA[0], 1)], { sessionId: old.sessionId, generation: old.generation }));
  assert.equal(result.ok, false);
  assert.equal(result.code, "STALE_GENERATION");
  assert.equal(context.DraftCommandLive.state().currentPick, 1);
}

// 15. The same ESPN URL can be reingested in the new generation from pick one.
{
  const { context } = boot();
  const room = "espn:/football/draft?leagueId=fixture";
  context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(context.PLAYER_DATA[0], 1)], { syncKey: room }));
  context.DraftCommandLive.hardReset({ confirmed: true });
  const identity = context.DraftCommandLive.syncIdentity();
  context.DraftCommandLive.resumeSourceIngestion({ source: "espn-bridge", bridgeVersion: "0.3.0" });
  const result = context.DraftCommandLive.ingestSnapshot(snapshot(context, [pick(context.PLAYER_DATA[1], 1)], { syncKey: room, ...identity }));
  assert.equal(result.ok, true);
  assert.equal(context.DraftCommandLive.state().events[0].playerId, context.PLAYER_DATA[1].id);
  assert.equal(context.DraftCommandLive.state().currentPick, 2);
}

// 16. A genuinely missing source slot can be manually recovered in place.
{
  const { context } = boot();
  const picks = [pick(context.PLAYER_DATA[0], 1), pick(context.PLAYER_DATA[2], 3)];
  context.DraftCommandLive.ingestSnapshot(snapshot(context, picks));
  assert.equal(context.DraftCommandLive.state().currentPick, 2);
  assert.equal(context.DraftCommandLive.resolveMissingPick(2, context.PLAYER_DATA[1].id), true);
  const state = context.DraftCommandLive.state();
  assert.equal(state.currentPick, 4);
  assert.equal(state.events.find((event) => event.overall === 2).source, "manual-recovery");
  assert.equal(state.sourceObservations.find((item) => item.overall === 2).reasonCode, "SOURCE_PICK_MANUALLY_RECOVERED");
}

// 17. Audit export is read-only and carries source/model/session diagnostics.
{
  const { context } = boot();
  context.DraftCommandLive.recordManualPick(context.PLAYER_DATA[0].id);
  const exported = context.DraftCommandLive.auditExport();
  const before = context.DraftCommandLive.state();
  assert.equal(exported.schemaVersion, "draft-command-audit-v2");
  assert.equal(exported.sourceObservations.length, 1);
  assert.ok(exported.sessionId);
  assert.equal(exported.model.decisionPolicyApproved, false);
  exported.draftEvents.length = 0;
  const after = context.DraftCommandLive.state();
  assert.equal(after.events.length, 1);
  assert.equal(after.sourceIngestionPaused, before.sourceIngestionPaused);
  assert.equal(after.generation, before.generation);
}

// 18. Manual-board/BPA operation remains immediate with no sync or model dependency.
{
  const { context } = boot();
  const player = context.DraftCommandLive.recommendations().bestPlayer.player;
  context.DraftCommandLive.recordManualPick(player.id);
  const state = context.DraftCommandLive.state();
  assert.equal(state.events[0].source, "manual");
  assert.equal(state.sourceObservations[0].source, "manual");
  assert.equal(state.currentPick, 2);
}

// 19. A full browser-storage quota cannot freeze initialization before Manual mode renders.
{
  const storage = new Map();
  const persisted = {
    schemaVersion: 3,
    events: [],
    modeledEvents: [],
    sourceObservations: [],
    keeperMode: false,
    keeperSeeds: [],
    seedReconciliations: [],
    sessionId: "persisted-session",
    generation: 1,
    sourceIngestionPaused: false,
    platform: "espn",
    rosterTeam: 5,
    auditLog: [],
  };
  storage.set("draft-command-2026-v3", JSON.stringify(persisted));
  storage.set("draft-command-2026-snapshots-v3", JSON.stringify([{ ...persisted, auditLog: [{ recordedAt: "2026-08-31T20:00:00Z", payload: "x".repeat(1000) }] }]));
  let quotaFailures = 0;
  const first = boot({
    storage,
    setItem({ key, value, storage: liveStorage }) {
      if (key === "draft-command-2026-v3" && liveStorage.has("draft-command-2026-snapshots-v3")) {
        quotaFailures += 1;
        throw quotaError();
      }
      liveStorage.set(key, value);
    },
  });
  assert.equal(quotaFailures, 1);
  assert.equal(first.context.DraftCommandLive.state().currentPick, 1);
  assert.equal(first.context.DraftCommandLive.state().keeperMode, false);
  assert.match(first.elements.get("modelVersion").textContent, /fallback-/i);
  assert.match(first.elements.get("playerTable").innerHTML, /Jahmyr Gibbs/);
  assert.equal(storage.has("draft-command-2026-snapshots-v3"), false);

  const refreshed = boot({ storage });
  assert.equal(refreshed.context.DraftCommandLive.state().currentPick, 1);
  assert.match(refreshed.elements.get("modelVersion").textContent, /fallback-/i);
  assert.match(refreshed.elements.get("playerTable").innerHTML, /Jahmyr Gibbs/);
}

// 20. Rolling recovery snapshots omit the duplicated audit trail.
{
  const { context, storage } = boot();
  context.DraftCommandLive.recordManualPick(context.PLAYER_DATA[0].id);
  const snapshots = JSON.parse(storage.get("draft-command-2026-snapshots-v3"));
  assert.equal(snapshots.length, 1);
  assert.equal(Object.hasOwn(snapshots[0], "auditLog"), false);
  assert.equal(snapshots[0].events.length, 1);
  assert.equal(snapshots[0].sourceObservations.length, 1);
}

// 21. A full 160-pick draft remains live and reloadable when detailed audit data exceeds storage capacity.
{
  const storage = new Map();
  const storageLimit = 900_000;
  const limitedSetItem = ({ key, value, storage: liveStorage }) => {
    const candidate = new Map(liveStorage);
    candidate.set(key, value);
    const size = [...candidate].reduce((total, [storedKey, storedValue]) => total + (storedKey.length + storedValue.length) * 2, 0);
    if (size > storageLimit) throw quotaError();
    liveStorage.set(key, value);
  };
  const first = boot({ storage, setItem: limitedSetItem });
  const picks = first.context.PLAYER_DATA.slice(0, 160).map((player, index) => pick(player, index + 1));
  assert.doesNotThrow(() => first.context.DraftCommandLive.ingestSnapshot(snapshot(first.context, picks)));
  assert.equal(first.context.DraftCommandLive.state().currentPick, 161);
  assert.equal(first.context.DraftCommandLive.state().events.length, 160);
  assert.equal(new Set(first.context.DraftCommandLive.state().events.map((event) => event.playerId)).size, 160);
  const persisted = JSON.parse(storage.get("draft-command-2026-v3"));
  assert.equal(persisted.auditRebuildRequired, true);
  assert.equal(persisted.auditLog.length, 0);

  const refreshed = boot({ storage, setItem: limitedSetItem });
  assert.equal(refreshed.context.DraftCommandLive.state().currentPick, 161);
  assert.equal(refreshed.context.DraftCommandLive.state().events.length, 160);
  assert.equal(new Set(refreshed.context.DraftCommandLive.state().events.map((event) => event.playerId)).size, 160);
  assert.match(refreshed.elements.get("modelVersion").textContent, /fallback-/i);
}

console.log("F5D draft-state tests passed");
