"use strict";

const assert = require("node:assert/strict");
const { CONTRACT_VERSION, createAdapter, validatePackage } = require("../model/model-adapter.js");

const players = [
  { id: 1, name: "Alpha Runner", pos: "RB", espn: 10, sleeper: 12 },
  { id: 2, name: "Beta Receiver", pos: "WR", espn: 20, sleeper: 18 },
];

function packageFixture(overrides = {}) {
  return {
    schemaVersion: "1.0.0",
    packageId: "fixture-v1",
    season: 2026,
    leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
    metadata: {
      status: "candidate",
      modelVersion: "fixture-1",
      generatedAt: "2026-08-31T00:00:00Z",
      effectiveAt: "2026-08-31T00:00:00Z",
      sources: [{ id: "fixture", layer: "player-truth" }],
    },
    decisionPolicy: { takeMaxSurvival: 0.2, waitMinSurvival: 0.55, valueMinGap: 7 },
    players: [{
      playerId: 1,
      outcome: { ceilingProbability: 0.42, bustProbability: 0.12 },
      leagueValue: { score: 91, rank: 3, fairPick: 7, tierId: "RB-1", tierLabel: "Elite" },
      market: { espn: { price: 9, defaultRank: 8, adp: 10, sigma: 4 } },
      survival: { espn: { center: 9, scale: 4, anchors: { "16": 0.31 } } },
      decision: { confidence: 0.81, reasons: ["projection-market agreement"] },
    }],
    ...overrides,
  };
}

assert.equal(CONTRACT_VERSION, "1.0.0");
assert.equal(validatePackage(packageFixture(), {
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  knownPlayerIds: players.map((player) => player.id),
}).ok, true);

const adapter = createAdapter({
  packageData: packageFixture(),
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(adapter.health().mode, "research");
assert.equal(adapter.health().coveredPlayers, 1);
assert.equal(adapter.health().coverage, 0.5);
assert.equal(adapter.number(players[0], "leagueValue.score", 50), 91);
assert.equal(adapter.number(players[1], "leagueValue.score", 50), 50);
assert.equal(adapter.market(players[0], "espn", 99).price, 9);
assert.equal(adapter.market(players[1], "espn", 99).price, 99);
assert.equal(adapter.survival(players[0], "espn", 16, 0.5), 0.31);
assert.ok(adapter.survival(players[0], "espn", 20, 0.5) < 0.1);
assert.equal(adapter.tier(players[0]).label, "Elite");
assert.equal(adapter.outcome(players[0]).ceilingProbability, 0.42);
assert.deepEqual(adapter.list(players[0], "decision.reasons"), ["projection-market agreement"]);
assert.equal(adapter.health().decisionPolicyApproved, false);
assert.equal(adapter.health().decisionMode, "advisory");
assert.equal(adapter.decisionTag({ override: "TAKE", reach: 0, survival: 0.01, quality: true, cliff: 20, valueGap: 20, ceilingProbability: 0.9 }), "ADVISORY");
assert.equal(adapter.survivalDetail(players[0], "espn", 16, 0.5).calibrated, false);

const approvedPackage = packageFixture();
approvedPackage.metadata = { ...approvedPackage.metadata, status: "production", expiresAt: "2099-01-01T00:00:00Z" };
approvedPackage.decisionPolicy = {
  ...approvedPackage.decisionPolicy,
  approval: { status: "approved", calibrated: true, version: "policy-fixture-1", approvedAt: "2026-08-31T01:00:00Z" },
};
approvedPackage.players[0].survival.espn.calibrationVersion = "survival-fixture-1";
const approved = createAdapter({
  packageData: approvedPackage,
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(approved.health().decisionPolicyApproved, true);
assert.equal(approved.health().decisionMode, "calibrated");
assert.equal(approved.decisionTag({ reach: 13, survival: 0.1, quality: true, cliff: 5, valueGap: 10, ceilingProbability: 0.5 }), "FADE AT PRICE");
assert.equal(approved.decisionTag({ reach: 0, survival: 0.19, quality: true, cliff: 1, valueGap: 0, ceilingProbability: 0.1 }), "TAKE");
assert.equal(approved.decisionTag({ reach: 0, survival: 0.4, quality: true, cliff: 5, valueGap: 0, ceilingProbability: 0.1 }), "POSITION CLIFF");
assert.equal(approved.decisionTag({ reach: 0, survival: 0.7, quality: true, cliff: 1, valueGap: 8, ceilingProbability: 0.1 }), "VALUE");
assert.equal(approved.survivalDetail(players[0], "espn", 16, 0.5).calibrated, true);

const unapprovedProductionPackage = packageFixture();
unapprovedProductionPackage.metadata = { ...unapprovedProductionPackage.metadata, status: "production", expiresAt: "2099-01-01T00:00:00Z" };
const unapprovedProduction = createAdapter({
  packageData: unapprovedProductionPackage,
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(unapprovedProduction.health().decisionPolicyApproved, false);
assert.match(unapprovedProduction.health().decisionPolicyReason, /approval is missing/i);
assert.equal(unapprovedProduction.decisionTag({ override: "TAKE" }), "ADVISORY");

const wrongSeason = createAdapter({
  packageData: packageFixture({ season: 2025 }),
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(wrongSeason.health().mode, "fallback");
assert.equal(wrongSeason.health().valid, false);
assert.equal(wrongSeason.decisionTag({ override: "TAKE" }), "ADVISORY");
assert.equal(wrongSeason.number(players[0], "leagueValue.score", 44), 44);

const wrongSchema = createAdapter({
  packageData: packageFixture({ schemaVersion: "2.0.0" }),
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(wrongSchema.health().mode, "fallback");
assert.equal(wrongSchema.health().valid, false);
assert.match(wrongSchema.health().errors[0], /unsupported model schema/i);

const missingPackage = createAdapter({
  packageData: null,
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(missingPackage.health().mode, "fallback");
assert.equal(missingPackage.health().valid, false);
assert.equal(missingPackage.survivalDetail(players[0], "espn", 16, 0.5).qualification, "heuristic");

const provisional = createAdapter({
  packageData: packageFixture({ metadata: { ...packageFixture().metadata, status: "provisional" }, players: [] }),
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(provisional.health().mode, "fallback");
assert.equal(provisional.health().label, "Provisional");
assert.equal(provisional.health().decisionPolicyApproved, false);

const stale = createAdapter({
  packageData: packageFixture({ metadata: { ...packageFixture().metadata, expiresAt: "2020-01-01T00:00:00Z" } }),
  players,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  fallbackVersion: "fallback-test",
});
assert.equal(stale.health().mode, "fallback");
assert.equal(stale.health().stale, true);
assert.equal(stale.health().label, "Research stale");
assert.equal(stale.decisionTag({ override: "POSITION CLIFF" }), "ADVISORY");

console.log("model-adapter tests passed");
