#!/usr/bin/env node
"use strict";

// Emits unsigned contract adapters to stdout. The Python wrapper applies the
// canonical draft-command payload signature and writes deterministic files.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const projectRoot = path.resolve(process.argv[2] || path.join(__dirname, ".."));
const snapshotId = "espn_2026_frozen_20260901T003012Z_3379127ab1c0";
const snapshotSha256 = "e333dfbc3196351ea1b04f6fa8a5525db5903067f38318c8d2a725d6f75bc2a2";
const marketArtifactVersion = snapshotId;
const simulationSeed = 20260831;
const simulationCount = 300;

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(projectRoot, relativePath), "utf8"));
}

function loadBrowserGlobal(relativePath, key) {
  const context = { window: {} };
  context.globalThis = context.window;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(projectRoot, relativePath), "utf8"), context, { filename: relativePath });
  return context.window[key] || context[key];
}

function teamNumber(teamId) {
  return Number(String(teamId).match(/([0-9]{2})$/)?.[1]);
}

function teamId(team) {
  return `team-${String(team).padStart(2, "0")}`;
}

function predictionStatus(value) {
  if (value === "CALIBRATED_BASELINE") return "calibrated";
  if (value === "CONTEXTUAL_UNVALIDATED") return "contextual";
  if (value === "FALLBACK") return "fallback";
  return "unvalidated";
}

function numericConfidence(value) {
  if (value === "HIGH") return 0.9;
  if (value === "MEDIUM") return 0.75;
  if (value === "LOW") return 0.55;
  return 0.25;
}

const players = loadBrowserGlobal("data/players.js", "PLAYER_DATA");
const opponentPackage = loadBrowserGlobal("data/opponent-intent-package.js", "OPPONENT_INTENT_PACKAGE");
if (!Array.isArray(players) || players.length !== 200) throw new Error(`Expected 200 Draft Command players, received ${players?.length}`);
if (!opponentPackage) throw new Error("Opponent Intent runtime package did not load.");

const marketSnapshot = readJson(`data/derived/espn_market/espn_2026_market_snapshot_${snapshotId}.json`);
const playerTruth = readJson("data/candidate/player-truth/player_truth_step14.json");
const leagueValue = readJson("data/candidate/league-value/espn_league_value_step15.json");
const marketByInternalId = new Map((marketSnapshot.players || [])
  .filter((record) => record.draft_command_player_id !== null
    && record.draft_command_player_id !== undefined
    && Number.isInteger(Number(record.draft_command_player_id)))
  .map((record) => [Number(record.draft_command_player_id), record]));

if (marketByInternalId.size !== 199) throw new Error(`Expected 199 resolved ESPN identities, received ${marketByInternalId.size}`);
if (marketByInternalId.has(190)) throw new Error("Jaydon Blue must remain the sole Draft Command player absent from the ESPN payload.");

const marketRecords = players.map((player, index) => {
  const source = marketByInternalId.get(Number(player.id));
  const ordinalAdpRank = source?.espn_adp_rank == null ? null : Number(source.espn_adp_rank);
  return {
    internalPlayerId: Number(player.id),
    draftCommandBoardRank: index + 1,
    position: player.pos,
    espnPlayerId: source?.espn_player_id == null ? null : String(source.espn_player_id),
    espnDefaultRank: source?.espn_official_ppr_rank == null ? null : Number(source.espn_official_ppr_rank),
    espnContinuousAdp: source?.espn_adp == null ? null : Number(source.espn_adp),
    liveRoomRank: source?.espn_live_draft_room_rank == null ? null : Number(source.espn_live_draft_room_rank),
    ordinalAdpRank,
    ordinalAdpRankSource: ordinalAdpRank == null ? null : `${source.source_id}#espn_adp_rank`,
    mappingConfidence: source?.mapping_confidence == null ? 0 : Number(source.mapping_confidence),
    captureStatus: source ? "captured" : "missing-market",
  };
});

const espnMarket = {
  schemaVersion: "1.0.0",
  artifactType: "espn-market",
  artifactId: `espn-market-contract-${snapshotId}`,
  artifactVersion: marketArtifactVersion,
  generatedAt: marketSnapshot.metadata.captured_at_utc,
  effectiveAt: marketSnapshot.metadata.captured_at_utc,
  expiresAt: null,
  status: "frozen",
  season: 2026,
  captureTimestamp: marketSnapshot.metadata.captured_at_utc,
  captureStatus: "complete",
  sourceArtifactId: snapshotId,
  sourceHash: snapshotSha256,
  integrity: { canonicalization: "draft-command-canonical-json-v1", payloadSha256: "" },
  coverage: {
    eligiblePlayerCount: players.length,
    mappedPlayerCount: marketRecords.filter((record) => record.espnPlayerId !== null).length,
    rankCoverage: marketRecords.filter((record) => record.espnDefaultRank !== null).length / players.length,
    adpCoverage: marketRecords.filter((record) => record.espnContinuousAdp !== null).length / players.length,
  },
  records: marketRecords,
};

const { createEngine } = require(path.join(projectRoot, "model/opponent-intent.js"));
const managers = [null, ...Array.from({ length: 10 }, (_, index) => ({
  id: index + 1,
  name: `M${String(index + 1).padStart(2, "0")}`,
  espnTeamId: opponentPackage.managers.find((manager) => Number(manager.draftSlot) === index + 1)?.espnTeamId ?? null,
}))];
const engine = createEngine({
  packageData: opponentPackage,
  players,
  managers,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  teamCount: 10,
  tonyTeam: 5,
});
if (engine.health().mode !== "live") throw new Error(`Opponent Intent engine is not live: ${engine.health().errors.join("; ")}`);

const keeperSeeds = leagueValue.leagueConfiguration.keepers.map((keeper) => ({
  overall: keeper.overallPick,
  team: teamNumber(keeper.teamId),
  playerId: keeper.internalPlayerId,
  source: "keeper-seed",
}));
const initialState = engine.createLiveState({ keeperSeeds, beforeOverall: 1 });
const initialBoard = engine.fullBoard({ currentOverallPick: 1, nextTonyPick: 5, liveState: initialState });
const keeperIds = new Set(keeperSeeds.map((keeper) => keeper.playerId));
const truthIds = playerTruth.players.map((player) => player.internalPlayerId).filter((playerId) => !keeperIds.has(playerId));
const tierDefinitions = {
  "LV-01-12": leagueValue.records.filter((record) => record.leagueValueRank <= 12 && !keeperIds.has(record.internalPlayerId)).map((record) => record.internalPlayerId),
  "LV-13-24": leagueValue.records.filter((record) => record.leagueValueRank >= 13 && record.leagueValueRank <= 24 && !keeperIds.has(record.internalPlayerId)).map((record) => record.internalPlayerId),
  "LV-25-48": leagueValue.records.filter((record) => record.leagueValueRank >= 25 && record.leagueValueRank <= 48 && !keeperIds.has(record.internalPlayerId)).map((record) => record.internalPlayerId),
  "LV-49-96": leagueValue.records.filter((record) => record.leagueValueRank >= 49 && record.leagueValueRank <= 96 && !keeperIds.has(record.internalPlayerId)).map((record) => record.internalPlayerId),
};
const initialWindow = engine.simulateTonyWindow({
  currentOverallPick: 1,
  nextTonyPick: 5,
  liveState: initialState,
  targetPlayerIds: truthIds,
  tiers: tierDefinitions,
  simulations: simulationCount,
  seed: simulationSeed,
});

const starterTargets = leagueValue.leagueConfiguration.rosterFormat.starters;
function openRosterPositions(team) {
  const roster = initialState.managers[String(team)]?.rosterCounts || { QB: 0, RB: 0, WR: 0, TE: 0 };
  const mandatory = {
    QB: Math.max(0, starterTargets.QB - roster.QB),
    RB: Math.max(0, starterTargets.RB - roster.RB),
    WR: Math.max(0, starterTargets.WR - roster.WR),
    TE: Math.max(0, starterTargets.TE - roster.TE),
  };
  const skillExtras = Math.max(0, roster.RB - starterTargets.RB)
    + Math.max(0, roster.WR - starterTargets.WR)
    + Math.max(0, roster.TE - starterTargets.TE);
  return {
    ...mandatory,
    FLEX: Math.max(0, starterTargets.FLEX - skillExtras),
    BENCH: leagueValue.leagueConfiguration.rosterFormat.bench,
  };
}

const opponents = Object.fromEntries(initialBoard.opponents.map((prediction) => {
  const stableTeamId = teamId(prediction.team);
  const roster = initialState.managers[String(prediction.team)]?.players || [];
  return [stableTeamId, {
    teamId: stableTeamId,
    displayLabel: `M${String(prediction.team).padStart(2, "0")}`,
    nextOverallPick: prediction.overallPick,
    currentRoster: roster.map((player) => ({
      internalPlayerId: player.playerId,
      position: player.position,
      rosterSlot: player.acquisitionType === "KEEPER" ? "KEEPER" : "ROSTER",
    })),
    openRosterPositions: openRosterPositions(prediction.team),
    positionProbabilities: prediction.positionProbabilities,
    topFivePlayerProbabilities: prediction.topPlayers.map((player) => ({
      internalPlayerId: player.playerId,
      probability: player.probability,
    })),
    otherProbability: prediction.otherProbability,
    confidence: numericConfidence(prediction.confidence),
    predictionStatus: predictionStatus(prediction.status),
    explanatoryDrivers: [...new Set(prediction.drivers || [])],
    limitations: [
      "Rounds 1-6 are calibrated; Rounds 7-16 remain contextual and unvalidated.",
      "Manager history is explanatory only and both manager residual weights are zero.",
    ],
  }];
}));

const opponentIntent = {
  schemaVersion: "1.0.0",
  artifactType: "opponent-intent",
  artifactId: "opponent-intent-streamlined-2026-initial-state",
  artifactVersion: "opponent-intent-streamlined-2026.1",
  modelArtifactVersion: opponentPackage.metadata.modelVersion,
  generatedAt: [playerTruth.generatedAt, leagueValue.generatedAt, marketSnapshot.metadata.captured_at_utc].sort().at(-1),
  effectiveAt: marketSnapshot.metadata.captured_at_utc,
  expiresAt: null,
  status: "validated",
  espnLeagueId: leagueValue.leagueConfiguration.leagueId,
  tonyTeamId: leagueValue.leagueConfiguration.tonyTeamId,
  tonyNextOverallPick: 5,
  runtimeBridge: {
    architecture: "dynamic-browser-engine",
    engineContractVersion: engine.contractVersion,
    engineAsset: "fantasy-draft/model/opponent-intent.js",
    packageAsset: "fantasy-draft/data/opponent-intent-package.js",
    workerAsset: "fantasy-draft/model/opponent-intent-worker.js",
    recalculationTriggers: ["espn-synchronized-pick", "manual-pick", "keeper-initialization", "refresh-recovery", "hard-reset"],
    liveInputs: ["accepted-picks", "current-rosters", "available-player-ids", "snake-calendar", "frozen-espn-market"],
    initialSnapshot: { overallPick: 1, nextTonyPick: 5 },
    initialSnapshotAuthoritativeAfterPick: false,
    ingestionBlocking: false,
    deterministicSeed: simulationSeed,
  },
  integrity: { canonicalization: "draft-command-canonical-json-v1", payloadSha256: "" },
  simulation: { seed: simulationSeed, count: simulationCount },
  opponents,
  targetSurvival: initialWindow.threats.map((threat) => ({
    internalPlayerId: threat.playerId,
    probabilityTakenBeforeTony: threat.probabilityTakenBeforeTony,
    probabilitySurvives: threat.probabilitySurviving,
    mostLikelyTakerTeamId: threat.mostLikelyTaker ? teamId(threat.mostLikelyTaker.team) : null,
    secondMostLikelyTakerTeamId: threat.secondMostLikelyTaker ? teamId(threat.secondMostLikelyTaker.team) : null,
  })),
  tierSurvival: Object.entries(initialWindow.tierSurvival).map(([tierId, value]) => ({
    tierId,
    probabilityAtLeastOneSurvives: value.probabilityAtLeastOneSurvives,
    expectedSurvivors: value.expectedRemaining,
  })),
  sourceVersions: {
    playerTruth: playerTruth.artifactVersion,
    espnMarket: marketArtifactVersion,
    leagueValue: leagueValue.artifactVersion,
    opponentModel: opponentPackage.metadata.modelVersion,
  },
  limitations: [
    "Rounds 1-6 are calibrated; Rounds 7-16 remain contextual and unvalidated.",
    "Manager residual weights are zero and manager history remains explanatory only.",
    "Outputs are advisory and may never block draft tracking, Manual mode, or ESPN synchronization.",
    "The embedded predictions are an initial-state acceptance snapshot; the browser engine recalculates after every accepted pick.",
  ],
};

process.stdout.write(JSON.stringify({ espnMarket, opponentIntent }));
