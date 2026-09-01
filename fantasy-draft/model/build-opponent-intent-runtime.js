#!/usr/bin/env node
"use strict";

// Builds the public, compact Opponent Intent browser bundle from private research
// outputs. Raw drafts, pick ledgers, identity crosswalks and API responses never
// enter the generated asset.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");

const MARKET_LOCK = Object.freeze({
  snapshotId: "espn_2026_frozen_20260901T003012Z_3379127ab1c0",
  captureTimestampUtc: "2026-09-01T00:30:12Z",
  publicationCommit: "49951ca1d45b92a906f84366a02d40c8c2e07e12",
  snapshotSha256: "e333dfbc3196351ea1b04f6fa8a5525db5903067f38318c8d2a725d6f75bc2a2",
  schemaVersion: "espn-market-2026-v1.1",
  status: "frozen",
  snapshotPath: "data/derived/espn_market/espn_2026_market_snapshot_espn_2026_frozen_20260901T003012Z_3379127ab1c0.json",
  manifestPath: "data/production/espn_2026_market_manifest_espn_2026_frozen_20260901T003012Z_3379127ab1c0.json",
  qaPath: "data/derived/espn_market/espn_2026_market_qa_espn_2026_frozen_20260901T003012Z_3379127ab1c0.json",
  leagueVerificationPath: "data/derived/espn_market/espn_2026_league_keeper_verification_espn_2026_frozen_20260901T003012Z_3379127ab1c0.json",
});

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function expectEqual(actual, expected, label) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    fail(`${label}: expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

function validateFrozenMarket(projectRoot) {
  const snapshotFile = path.join(projectRoot, MARKET_LOCK.snapshotPath);
  const manifestFile = path.join(projectRoot, MARKET_LOCK.manifestPath);
  const snapshotBytes = fs.readFileSync(snapshotFile);
  const market = JSON.parse(snapshotBytes.toString("utf8"));
  const manifest = readJson(manifestFile);
  const qa = readJson(path.join(projectRoot, MARKET_LOCK.qaPath));
  const leagueVerification = readJson(path.join(projectRoot, MARKET_LOCK.leagueVerificationPath));

  expectEqual(sha256(snapshotBytes), MARKET_LOCK.snapshotSha256, "Frozen ESPN snapshot SHA-256 mismatch");
  expectEqual(manifest.snapshot_id, MARKET_LOCK.snapshotId, "Frozen ESPN manifest snapshot ID mismatch");
  expectEqual(manifest.schema_version, MARKET_LOCK.schemaVersion, "Frozen ESPN manifest schema mismatch");
  expectEqual(manifest.status, MARKET_LOCK.status, "Frozen ESPN manifest status mismatch");
  expectEqual(manifest.generation_time_utc, MARKET_LOCK.captureTimestampUtc, "Frozen ESPN capture timestamp mismatch");
  expectEqual(manifest.artifacts?.snapshot_json, `fantasy-draft/${MARKET_LOCK.snapshotPath}`, "Frozen ESPN manifest snapshot path mismatch");
  expectEqual(manifest.processed_file_hashes?.[`fantasy-draft/${MARKET_LOCK.snapshotPath}`], MARKET_LOCK.snapshotSha256, "Frozen ESPN manifest snapshot hash mismatch");
  expectEqual(manifest.row_counts, { mapped_to_draft_command: 199, source: 500 }, "Frozen ESPN manifest row coverage mismatch");
  expectEqual(manifest.identity_match_coverage, { count: 199, denominator: 200, percentage: 0.995 }, "Frozen ESPN identity coverage mismatch");
  expectEqual(manifest.rank_coverage, { count: 199, denominator: 199, percentage: 1 }, "Frozen ESPN rank coverage mismatch");
  expectEqual(manifest.adp_coverage, { count: 199, denominator: 199, percentage: 1 }, "Frozen ESPN ADP coverage mismatch");
  expectEqual(manifest.keeper_coverage, 1, "Frozen ESPN keeper coverage mismatch");
  expectEqual(qa.source_row_count, 500, "Frozen ESPN source-row benchmark mismatch");
  expectEqual(qa.top_160_unresolved, [], "Frozen ESPN top-160 resolution benchmark mismatch");
  expectEqual(qa.duplicate_internal_player_ids, [], "Frozen ESPN duplicate internal-ID benchmark mismatch");
  expectEqual(qa.duplicate_espn_player_ids, [], "Frozen ESPN duplicate ESPN-ID benchmark mismatch");
  expectEqual(qa.missing_draft_command_player_ids, [190], "Frozen ESPN sole Draft Command miss mismatch");
  expectEqual(leagueVerification.keepers?.length, 10, "Frozen ESPN keeper-row benchmark mismatch");
  expectEqual(leagueVerification.keepers?.filter((keeper) => keeper.mapped).length, 10, "Frozen ESPN mapped-keeper benchmark mismatch");
  expectEqual(market.metadata?.snapshot_id, MARKET_LOCK.snapshotId, "Frozen ESPN snapshot metadata ID mismatch");
  expectEqual(market.metadata?.captured_at_utc, MARKET_LOCK.captureTimestampUtc, "Frozen ESPN snapshot metadata timestamp mismatch");
  expectEqual(market.metadata?.schema_version, MARKET_LOCK.schemaVersion, "Frozen ESPN snapshot metadata schema mismatch");
  expectEqual(market.metadata?.status, MARKET_LOCK.status, "Frozen ESPN snapshot metadata status mismatch");

  return { market, manifest, qa, leagueVerification };
}

function loadPlayers(file) {
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  return Array.from(context.window.PLAYER_DATA || []);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted && char === '"' && text[index + 1] === '"') { field += '"'; index += 1; continue; }
    if (char === '"') { quoted = !quoted; continue; }
    if (!quoted && char === ",") { row.push(field); field = ""; continue; }
    if (!quoted && (char === "\n" || char === "\r")) {
      if (char === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field); field = "";
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      continue;
    }
    field += char;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const headers = (rows.shift() || []).map((header) => header.replace(/^\uFEFF/, ""));
  return rows.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])));
}

function quantile(values, probability) {
  if (!values.length) return null;
  const sorted = values.slice().sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.round((sorted.length - 1) * probability)))];
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function aggregateHistory(rows, managerName) {
  const managerRows = rows.filter((row) => row.manager === managerName && row.selection_type === "LIVE" && Number(row.round) <= 6);
  const seasons = [...new Set(managerRows.map((row) => Number(row.season)))].sort();
  const seasonGroups = new Map(seasons.map((season) => [season, managerRows.filter((row) => Number(row.season) === season).sort((a, b) => Number(a.overall_pick) - Number(b.overall_pick))]));
  let transitions = 0;
  let doubleTaps = 0;
  for (const picks of seasonGroups.values()) {
    for (let index = 1; index < picks.length; index += 1) {
      transitions += 1;
      if (picks[index].position === picks[index - 1].position) doubleTaps += 1;
    }
  }
  const positionCounts = ["QB", "RB", "WR", "TE"].map((position) => managerRows.filter((row) => row.position === position).length);
  const total = positionCounts.reduce((sum, count) => sum + count, 0);
  const entropy = total ? -positionCounts.reduce((sum, count) => {
    if (!count) return sum;
    const probability = count / total;
    return sum + probability * Math.log(probability);
  }, 0) / Math.log(4) : null;
  const rankJumps = managerRows.map((row) => Number(row.board_jump_rank)).filter(Number.isFinite);
  const adpJumps = managerRows.map((row) => Number(row.board_jump_adp)).filter(Number.isFinite);
  const draftsWithEarlyQb = [...seasonGroups.values()].filter((picks) => picks.some((row) => Number(row.round) <= 3 && row.position === "QB")).length;
  const draftsWithPremiumTe = [...seasonGroups.values()].filter((picks) => picks.some((row) => Number(row.round) <= 3 && row.position === "TE")).length;
  const r4To6 = managerRows.filter((row) => Number(row.round) >= 4);
  const flexPicks = r4To6.filter((row) => ["RB", "WR", "TE"].includes(row.position)).length;
  return {
    sampleSizeRounds1To6: managerRows.length,
    seasonsRepresented: seasons,
    draftSlotHistory: seasons.map((season) => ({ season, draftSlot: Number(seasonGroups.get(season)[0]?.draft_slot) })),
    recent2023To2025Share: managerRows.length ? managerRows.filter((row) => Number(row.season) >= 2023).length / managerRows.length : null,
    earlyQbDraftRate: seasons.length ? draftsWithEarlyQb / seasons.length : null,
    premiumTeDraftRate: seasons.length ? draftsWithPremiumTe / seasons.length : null,
    positionDoubleTapRate: transitions ? doubleTaps / transitions : null,
    previousTurnSamePositionRate: transitions ? doubleTaps / transitions : null,
    flexEligibleShareRounds4To6: r4To6.length ? flexPicks / r4To6.length : null,
    positionConcentrationEntropy: entropy,
    espnRankReach: { mean: rankJumps.length ? rankJumps.reduce((sum, value) => sum + value, 0) / rankJumps.length : null, median: quantile(rankJumps, 0.5), p90: quantile(rankJumps, 0.9) },
    espnAdpReach: { mean: adpJumps.length ? adpJumps.reduce((sum, value) => sum + value, 0) / adpJumps.length : null, median: quantile(adpJumps, 0.5), p90: quantile(adpJumps, 0.9) },
  };
}

const [researchRootArg, outputArg] = process.argv.slice(2);
if (!researchRootArg || !outputArg) {
  fail("Usage: node build-opponent-intent-runtime.js <private-research-root> <output-js>");
}

const projectRoot = path.resolve(__dirname, "..");
const researchRoot = path.resolve(researchRootArg);
const output = path.resolve(outputArg);
const players = loadPlayers(path.join(projectRoot, "data", "players.js"));
const model = readJson(path.join(researchRoot, "engine", "F_survival_model", "opponent_intent", "opponent_intent_model_v1.json"));
const profiles = readJson(path.join(researchRoot, "data", "derived", "C_manager_profiles", "espn_manager_static_profiles_2026.json"));
const priors = readJson(path.join(researchRoot, "data", "derived", "C_manager_profiles", "espn_manager_selection_priors_2026.recovered.json"));
const { market } = validateFrozenMarket(projectRoot);
const enrichedHistory = parseCsv(fs.readFileSync(path.join(researchRoot, "data", "raw", "B_enriched_history", "espn_historical_draft_events_enriched_stepb_2020_2025.csv"), "utf8"));

if (Number(model.position_model?.manager_overlay_weight) !== 0 || Number(model.player_model?.profile_overlay_weight) !== 0) {
  fail("Manager residuals are not eligible for public runtime promotion; expected zero weights.");
}

const marketByDraftCommandId = new Map((market.players || [])
  .filter((entry) => entry.draft_command_player_id !== null && entry.draft_command_player_id !== undefined && Number.isInteger(Number(entry.draft_command_player_id)))
  .map((entry) => [Number(entry.draft_command_player_id), entry]));

const playerMarket = players.map((player) => {
  const source = marketByDraftCommandId.get(Number(player.id));
  const sourceRank = numberOrNull(source?.espn_official_ppr_rank);
  const sourceAdp = numberOrNull(source?.espn_adp);
  return {
    playerId: Number(player.id),
    espnDefaultRank: sourceRank ?? numberOrNull(player.espn),
    espnAdp: sourceAdp,
    marketCoverage: source ? "matched-current-espn" : "default-rank-only",
  };
});

expectEqual(market.players?.length, 500, "Frozen ESPN runtime source-row benchmark mismatch");
expectEqual(marketByDraftCommandId.size, 199, "Frozen ESPN runtime mapped-identity benchmark mismatch");
expectEqual(playerMarket.filter((entry) => entry.marketCoverage === "matched-current-espn").length, 199, "Frozen ESPN runtime player mapping mismatch");
expectEqual(playerMarket.filter((entry) => entry.marketCoverage === "matched-current-espn" && entry.espnDefaultRank !== null).length, 199, "Frozen ESPN runtime rank coverage mismatch");
expectEqual(playerMarket.filter((entry) => entry.marketCoverage === "matched-current-espn" && entry.espnAdp !== null).length, 199, "Frozen ESPN runtime ADP coverage mismatch");
expectEqual(playerMarket.filter((entry) => entry.marketCoverage !== "matched-current-espn").map((entry) => entry.playerId), [190], "Frozen ESPN runtime sole miss mismatch");

const priorByManager = new Map(priors.managers.map((prior) => [prior.manager, prior]));
const managers = profiles.managers.map((profile) => {
  const prior = priorByManager.get(profile.manager) || {};
  const historicalEvidence = aggregateHistory(enrichedHistory, profile.manager);
  return ({
  espnTeamId: Number(profile.espn_team_id),
  draftSlot: Number(profile.draft_slot),
  manager: profile.manager,
  teamName: profile.team_name,
  keeper: {
    name: profile.keeper,
    position: profile.keeper_position,
    round: Number(profile.keeper_round),
  },
  sampleSize: Number(profile.sample_n_live_r1_6),
  seasonsRepresented: historicalEvidence.seasonsRepresented,
  sampleConfidence: profile.sample_confidence,
  boardStyle: profile.board_style,
  alignment: profile.alignment_label,
  boardModeProbability: Number(profile.board_mode_probability),
  convictionModeProbability: Number(profile.conviction_mode_probability),
  espnRankWeight: Number(profile.espn_rank_weight),
  espnAdpWeight: Number(profile.espn_adp_weight),
  round1To3PositionProfile: profile.r1_3_position_probabilities,
  round4To6PositionProfile: profile.r4_6_position_probabilities,
  ordinaryTeNeedMultiplier: Number(profile.ordinary_te_need_multiplier_at_start),
  premiumTeAfterOwnedMultiplier: Number(profile.premium_te_after_te_owned_multiplier),
  profileSummary: profile.profile_notes,
  behavior: {
    rankTop5Rate: Number(profile.behavior_metrics?.rank_top5_pct) / 100,
    rankTop10Rate: Number(profile.behavior_metrics?.rank_top10_pct) / 100,
    rankReach10PlusRate: Number(profile.behavior_metrics?.rank_jump10plus_pct) / 100,
    adpTop5Rate: Number(profile.behavior_metrics?.adp_top5_pct) / 100,
    adpReach10PlusRate: Number(profile.behavior_metrics?.adp_jump10plus_pct) / 100,
  },
  historicalEvidence: {
    ...historicalEvidence,
    deepConvictionGivenConviction: numberOrNull(prior.mixture?.deep_conviction_given_conviction),
    boardJumpMeanShrunk: numberOrNull(prior.board_signal?.board_jump_mean_shrunk),
    convictionJumpMeanShrunk: numberOrNull(prior.board_signal?.conviction_jump_mean_shrunk),
    historicalPositionPosterior: prior.historical_position_posterior_before_2026_profile || null,
    profileMultipliers: prior.profile_multipliers_source_stepb || null,
    seasonWeights: priors.season_weights || null,
    keeperEffectPolicy: "Confirmed keeper initializes roster needs; no separate keeper residual is promoted.",
  },
  });
});

const payload = {
  schemaVersion: "1.0.0",
  packageId: "espn-opponent-intent-runtime-2026-08-31",
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  leagueId: "167404",
  metadata: {
    status: "candidate",
    modelVersion: model.model_id,
    generatedAt: model.metadata.build_timestamp_utc,
    effectiveAt: MARKET_LOCK.captureTimestampUtc,
    sourceVersions: {
      ...model.metadata.source_versions,
      market: MARKET_LOCK.snapshotId,
    },
    market: {
      snapshotId: MARKET_LOCK.snapshotId,
      captureTimestampUtc: MARKET_LOCK.captureTimestampUtc,
      publicationCommit: MARKET_LOCK.publicationCommit,
      snapshotSha256: MARKET_LOCK.snapshotSha256,
      schemaVersion: MARKET_LOCK.schemaVersion,
      status: MARKET_LOCK.status,
      canonicalSnapshotPath: `fantasy-draft/${MARKET_LOCK.snapshotPath}`,
      canonicalManifestPath: `fantasy-draft/${MARKET_LOCK.manifestPath}`,
      coverage: {
        sourceRows: 500,
        draftCommandIdentities: { mapped: 199, total: 200 },
        mappedWithEspnDefaultRank: { count: 199, total: 199 },
        mappedWithContinuousEspnAdp: { count: 199, total: 199 },
        keepersRepresented: { count: 10, total: 10 },
        unresolvedEspnTop160: 0,
        duplicateInternalPlayerIds: 0,
        duplicateEspnPlayerIds: 0,
        draftCommandOnlyMisses: [{ playerId: 190, reason: "outside ESPN payload", blocking: false }],
      },
      fieldPolicy: {
        espnDefaultRank: "distinct nullable ESPN PPR default-rank field",
        espnAdp: "distinct nullable continuous ESPN ADP field",
        ordinalAdpRankCreated: false,
        rankAdpBlended: false,
      },
    },
    historicalCoverage: model.metadata.coverage,
    calibratedRounds: model.scope.calibrated_rounds,
    confidencePolicy: model.metadata.confidence_policy,
    knownLimitations: [
      "Rounds 7-16 are contextual and unvalidated.",
      "Authenticated league-settings verification remains incomplete; the public market lock did not verify private scoring, roster or IR/Stash settings.",
      "Manager profiles remain explanatory and do not alter probabilities.",
      "Runtime Monte Carlo sampling adds finite-simulation noise, controlled by a fixed seed.",
    ],
    publicAssetPolicy: "Aggregate runtime features only; raw history and pick-level ledgers excluded.",
  },
  policy: {
    positionManagerResidualWeight: Number(model.position_model.manager_overlay_weight),
    playerManagerResidualWeight: Number(model.player_model.profile_overlay_weight),
    promotionStatus: model.policy.manager_overlay_promotion_status,
    rosterAndRoomContextEnabled: true,
    profileEvidenceExplanationOnly: true,
    tonyValuesAffectSelectionProbability: false,
    tierLabelsAffectSelectionProbability: false,
  },
  positionModel: {
    dynamicBase: model.position_model.dynamic_base,
    roomBaselines: model.position_model.room_baselines,
  },
  playerModel: {
    rankWeight: Number(model.player_model.market_signal.rank_weight),
    adpWeight: Number(model.player_model.market_signal.adp_weight),
    boardDecayLambda: Number(model.player_model.market_signal.board_decay_lambda),
  },
  validation: model.validation_summary,
  managers,
  playerMarket,
};

const banner = [
  "// Generated compact Opponent Intent runtime bundle.",
  "// Contains aggregate coefficients/profile features only; no raw league history.",
  "(() => {",
  "  const deepFreeze = (value) => {",
  "    if (!value || typeof value !== \"object\" || Object.isFrozen(value)) return value;",
  "    Object.freeze(value);",
  "    Object.values(value).forEach(deepFreeze);",
  "    return value;",
  "  };",
  `  window.OPPONENT_INTENT_PACKAGE = deepFreeze(${JSON.stringify(payload, null, 2).replace(/\n/g, "\n  ")});`,
  "})();",
  "",
].join("\n");

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, banner, "utf8");
process.stdout.write(`Wrote ${output} with ${managers.length} managers and ${playerMarket.length} player-market rows.\n`);
