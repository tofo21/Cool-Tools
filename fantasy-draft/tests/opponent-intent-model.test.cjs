"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const vm = require("node:vm");
const { createEngine, validatePackage } = require("../model/opponent-intent.js");

const root = path.resolve(__dirname, "..");
function loadBrowserValue(file, key) {
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, file), "utf8"), context, { filename: file });
  return context.window[key];
}

const players = Array.from(loadBrowserValue("data/players.js", "PLAYER_DATA"), (player) => ({ ...player }));
const packageData = loadBrowserValue("data/opponent-intent-package.js", "OPPONENT_INTENT_PACKAGE");
const schema = JSON.parse(fs.readFileSync(path.join(root, "model/opponent-intent-package.schema.json"), "utf8"));
const manifest = JSON.parse(fs.readFileSync(path.join(root, "model/opponent-intent-runtime-manifest.json"), "utf8"));
const managers = [
  null,
  { id: 1, name: "Justin Gerkin", espnTeamId: 10 },
  { id: 2, name: "Dan Merrick", espnTeamId: 1 },
  { id: 3, name: "Matt Castleman", espnTeamId: 8 },
  { id: 4, name: "Matt Hull", espnTeamId: 4 },
  { id: 5, name: "Tony Fontana", espnTeamId: 9 },
  { id: 6, name: "Matt Runge", espnTeamId: 7 },
  { id: 7, name: "Jon Merrick", espnTeamId: 2 },
  { id: 8, name: "Matt Sloka", espnTeamId: 5 },
  { id: 9, name: "Kyle Cavanaugh", espnTeamId: 11 },
  { id: 10, name: "Brenden Lautenbach", espnTeamId: 12 },
];
const keepers = [
  { overall: 60, team: 1, playerId: 68, source: "keeper-seed" },
  { overall: 59, team: 2, playerId: 24, source: "keeper-seed" },
  { overall: 98, team: 3, playerId: 45, source: "keeper-seed" },
  { overall: 84, team: 4, playerId: 50, source: "keeper-seed" },
  { overall: 156, team: 5, playerId: 90, source: "keeper-seed" },
  { overall: 66, team: 6, playerId: 30, source: "keeper-seed" },
  { overall: 114, team: 7, playerId: 47, source: "keeper-seed" },
  { overall: 133, team: 8, playerId: 52, source: "keeper-seed" },
  { overall: 89, team: 9, playerId: 26, source: "keeper-seed" },
  { overall: 90, team: 10, playerId: 33, source: "keeper-seed" },
];

function engine(data = packageData, playerData = players) {
  return createEngine({ packageData: data, players: playerData, managers, season: 2026, leagueProfileId: "espn-keeper-10-ppr-2flex-2026", teamCount: 10, tonyTeam: 5 });
}

// Public package contract and stable ESPN identities.
assert.equal(validatePackage(packageData, { season: 2026, leagueProfileId: "espn-keeper-10-ppr-2flex-2026", players }).ok, true);
assert.equal(packageData.managers.length, 9);
assert.deepEqual(Array.from(packageData.managers, (profile) => profile.espnTeamId), [10, 1, 8, 4, 7, 2, 5, 11, 12]);
assert.equal(packageData.policy.positionManagerResidualWeight, 0);
assert.equal(packageData.policy.playerManagerResidualWeight, 0);
assert.ok(schema.required.every((field) => Object.hasOwn(packageData, field)), "runtime package must satisfy required schema fields");
for (const artifact of manifest.artifacts) {
  const bytes = fs.readFileSync(path.join(root, artifact.path));
  assert.equal(bytes.length, artifact.bytes, `${artifact.path} byte count must match manifest`);
  assert.equal(crypto.createHash("sha256").update(bytes).digest("hex"), artifact.sha256, `${artifact.path} hash must match manifest`);
}

const model = engine();
assert.equal(model.health().mode, "live");
assert.equal(model.health().managerWeights.position, 0);

// Leakage-safe pre-pick roster reconstruction: all known keepers initialize,
// while future live events are excluded by the beforeOverall cutoff.
const reconstruction = model.createLiveState({
  keeperSeeds: keepers,
  events: [
    { overall: 1, team: 1, playerId: 1, source: "espn-sync" },
    { overall: 2, team: 2, playerId: 2, source: "espn-sync" },
  ],
  beforeOverall: 2,
});
assert.equal(reconstruction.managers["1"].rosterCounts.TE, 1);
assert.equal(reconstruction.managers["1"].rosterCounts.RB, 1);
assert.equal(reconstruction.managers["2"].rosterCounts.RB, 0, "future pick must not leak into pre-pick state");
assert.ok(!reconstruction.availablePlayerIds.includes(68), "keepers must be removed from the available pool");

const liveState = model.createLiveState({ keeperSeeds: keepers, beforeOverall: 1 });
for (let team = 1; team <= 10; team += 1) {
  if (team === 5) continue;
  const prediction = model.predict(team, team < 5 ? team : team + 1, liveState);
  const positionTotal = Object.values(prediction.positionProbabilities).reduce((sum, value) => sum + value, 0);
  const playerTotal = prediction.topPlayers.reduce((sum, player) => sum + player.probability, 0) + prediction.otherProbability;
  assert.ok(Math.abs(positionTotal - 1) < 1e-10, `team ${team} position probabilities must normalize`);
  assert.ok(Math.abs(playerTotal - 1) < 1e-10, `team ${team} top-five plus other must normalize`);
  assert.ok(prediction.topPlayers.every((player) => liveState.availablePlayerIds.includes(player.playerId)));
}

const board = model.fullBoard({ currentOverallPick: 1, nextTonyPick: 5, liveState });
assert.equal(board.opponentCount, 9);
assert.equal(board.opponents.filter((row) => row.picksBeforeTony).length, 4);
assert.deepEqual(Array.from(board.opponents.filter((row) => row.picksBeforeTony), (row) => row.team), [1, 2, 3, 4]);

// Manager features are strongly shrunken to exactly zero predictive weight.
const lowSamplePackage = JSON.parse(JSON.stringify(packageData));
lowSamplePackage.managers[0].sampleSize = 0;
lowSamplePackage.managers[0].round1To3PositionProfile = { QB: 0.97, RB: 0.01, WR: 0.01, TE: 0.01 };
const highSamplePackage = JSON.parse(JSON.stringify(packageData));
highSamplePackage.managers[0].sampleSize = 999;
highSamplePackage.managers[0].round1To3PositionProfile = { QB: 0.01, RB: 0.97, WR: 0.01, TE: 0.01 };
const low = engine(lowSamplePackage).predict(1, 1, engine(lowSamplePackage).createLiveState({ keeperSeeds: keepers }),);
const highEngine = engine(highSamplePackage);
const high = highEngine.predict(1, 1, highEngine.createLiveState({ keeperSeeds: keepers }));
assert.deepEqual(low.positionProbabilities, high.positionProbabilities, "unpromoted manager profile residuals must not affect probability");

// Missing-manager and missing-market fields fall back without blocking.
const missingManager = model.predict(99, 1, liveState);
assert.equal(missingManager.confidence, "LOW");
assert.match(missingManager.profileSummary, /No manager profile/);
const sparsePlayers = players.map((player, index) => index === 0 ? { ...player, espn: null, adp: null } : player);
const sparsePackage = JSON.parse(JSON.stringify(packageData));
sparsePackage.playerMarket[0].espnDefaultRank = null;
sparsePackage.playerMarket[0].espnAdp = null;
assert.ok(engine(sparsePackage, sparsePlayers).predict(1, 1, engine(sparsePackage, sparsePlayers).createLiveState({ keeperSeeds: keepers })).topPlayers.length === 5);

// Selection enforcement, roster updates and sequential depletion.
const mutable = model.createLiveState({ keeperSeeds: keepers });
const beforeRb = mutable.managers["1"].rosterCounts.RB;
model.applyPick(mutable, 1, 1, 1);
assert.equal(mutable.managers["1"].rosterCounts.RB, beforeRb + 1);
assert.ok(!mutable.availablePlayerIds.includes(1));
assert.throws(() => model.applyPick(mutable, 2, 2, 1), /not available/);

const options = { currentOverallPick: 1, nextTonyPick: 5, liveState, targetPlayerIds: liveState.availablePlayerIds.slice(0, 30), simulations: 80, seed: 20260831 };
const simulationA = model.simulateTonyWindow(options);
const simulationB = model.simulateTonyWindow(options);
assert.deepEqual(simulationA, simulationB, "fixed-seed simulation must be deterministic");
assert.deepEqual(Array.from(simulationA.interveningPicks), [1, 2, 3, 4]);
assert.ok(simulationA.threats.every((threat) => Math.abs(threat.probabilityTakenBeforeTony + threat.probabilitySurviving - 1) < 1e-12));
assert.ok(simulationA.threats.every((threat) => new Set(threat.managerThreatBreakdown.map((row) => row.team)).size === threat.managerThreatBreakdown.length));

// External target/tier grouping is reporting-only and cannot alter selections.
const tiered = model.simulateTonyWindow({ ...options, tiers: { "Tony read-only tier": options.targetPlayerIds.slice(0, 5) } });
assert.deepEqual(
  Array.from(tiered.threats, (threat) => [threat.playerId, threat.probabilityTakenBeforeTony, threat.managerThreatBreakdown]),
  Array.from(simulationA.threats, (threat) => [threat.playerId, threat.probabilityTakenBeforeTony, threat.managerThreatBreakdown]),
);
assert.ok(tiered.tierSurvival["Tony read-only tier"].expectedRemaining >= 0);

// Opponent Intent never mutates Tony-side player truth or league-value fields.
const frozenPlayerSnapshot = JSON.stringify(players);
model.predict(1, 1, liveState);
model.simulateTonyWindow({ ...options, simulations: 10 });
assert.equal(JSON.stringify(players), frozenPlayerSnapshot);

// Malformed or missing bundles fail safely and retain a contextual fallback.
const unavailable = engine({ schemaVersion: "99.0.0", season: 2025, managers: [] });
assert.equal(unavailable.health().mode, "fallback");
const fallbackState = unavailable.createLiveState({ keeperSeeds: keepers });
assert.doesNotThrow(() => unavailable.predict(1, 1, fallbackState));
unavailable.disable("fixture failure");
assert.match(unavailable.health().errors.at(-1), /fixture failure/);

console.log("opponent intent model tests passed");
