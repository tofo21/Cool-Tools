"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { createAdapter } = require("../model/model-adapter.js");
const { CONTRACT_VERSION, calibration, createEngine, keeperOverall, pickOwner } = require("../replay/replay-engine.js");

const root = path.resolve(__dirname, "..");
const context = { window: {} };
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, "data/players.js"), "utf8"), context);
vm.runInContext(fs.readFileSync(path.join(root, "data/model-package.js"), "utf8"), context);

const adapter = createAdapter({
  packageData: context.DRAFT_INTELLIGENCE_PACKAGE,
  players: context.PLAYER_DATA,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "test-fallback",
});
const engine = createEngine({ players: context.PLAYER_DATA, model: adapter });

assert.equal(CONTRACT_VERSION, "1.0.0");
assert.equal(pickOwner(5), 5);
assert.equal(pickOwner(16), 5);
assert.equal(keeperOverall(16, 5), 156);
assert.equal(engine.profile.keepers.find((keeper) => keeper.playerId === 90).overall, 156);

const sample = engine.sampleLog("espn");
assert.equal(sample.events.length, 150);
assert.equal(sample.events.some((event) => event.overall === 156), false);
assert.equal(new Set(sample.events.map((event) => event.playerId)).size, sample.events.length);
const report = engine.run(sample);
assert.equal(report.ok, true);
assert.equal(report.summary.decisions, 15);
assert.equal(report.summary.completeThrough, 160);
assert.equal(report.strategies.length, 4);
assert.ok(report.summary.individualCalibration.count > 100);
assert.ok(report.summary.individualCalibration.brier >= 0 && report.summary.individualCalibration.brier <= 1);
assert.ok(report.decisions.every((decision) => decision.recommendation?.name));
assert.equal(report.modelHealth.mode, "fallback");

const sleeperPlayer = context.PLAYER_DATA.find((player) => player.id === 1);
const normalizedSleeper = engine.normalizeLog({
  source: "sleeper",
  settings: { teams: 10, rounds: 16 },
  picks: [{ pick_no: 1, draft_slot: 1, player_id: "external-1", metadata: { first_name: sleeperPlayer.name.split(" ")[0], last_name: sleeperPlayer.name.split(" ").slice(1).join(" ") } }],
});
assert.equal(normalizedSleeper.ok, true);
assert.equal(normalizedSleeper.platform, "sleeper");
assert.equal(normalizedSleeper.events[0].playerId, sleeperPlayer.id);
assert.equal(engine.normalizeLog([{ pick_no: 1, metadata: { name: sleeperPlayer.name } }]).platform, "sleeper");

const espnPlayer = context.PLAYER_DATA.find((player) => player.id === 2);
const normalizedEspn = engine.normalizeLog({
  platform: "espn",
  teamCount: 10,
  rounds: 16,
  events: [{ pickNumber: 1, teamId: 9, player: { name: espnPlayer.name } }],
});
assert.equal(normalizedEspn.ok, true);
assert.equal(normalizedEspn.events[0].team, 1);
assert.ok(normalizedEspn.issues.some((issue) => issue.code === "OWNER_REPAIRED"));

const invalid = engine.normalizeLog({ teamCount: 12, picks: [{ overall: 999, name: "Nobody" }] });
assert.equal(invalid.ok, false);
assert.ok(invalid.issues.some((issue) => issue.code === "TEAM_COUNT"));
assert.ok(invalid.issues.some((issue) => issue.code === "INVALID_PICK"));

const incomplete = engine.run({
  platform: "espn",
  completeThrough: 16,
  events: sample.events.filter((event) => event.overall <= 16 && event.overall !== 7),
});
assert.equal(incomplete.ok, true);
assert.equal(incomplete.summary.decisions, 2);
assert.equal(incomplete.decisions[0].calibrationReady, false);
assert.equal(incomplete.summary.individualCalibration.count, 0);

const cal = calibration([
  { probability: 0.9, observed: true },
  { probability: 0.1, observed: false },
]);
assert.equal(cal.count, 2);
assert.equal(cal.brier, 0.01);
assert.equal(cal.ece, 0.1);

const source = fs.readFileSync(path.join(root, "replay/replay-engine.js"), "utf8");
for (const forbidden of ["localStorage", "sessionStorage", "draft-command-2026-v2", "draft-command-2026-snapshots-v2"]) {
  assert.doesNotMatch(source, new RegExp(forbidden), `replay engine must not reference ${forbidden}`);
}

console.log("replay-engine tests passed");
