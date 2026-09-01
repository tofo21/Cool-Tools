"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const draftRoot = path.resolve(__dirname, "..");
const fixtureRoot = path.join(__dirname, "fixtures", "runtime-contract");
const validator = path.join(draftRoot, "research", "validate_draft_runtime_bundle.py");
const builder = path.join(draftRoot, "research", "build_draft_runtime_bundle.py");
const asOf = "2026-08-31T23:00:00Z";
const fixtures = Object.freeze({
  playerTruth: path.join(fixtureRoot, "synthetic_player_truth.json"),
  espnMarket: path.join(fixtureRoot, "synthetic_espn_market.json"),
  leagueValue: path.join(fixtureRoot, "synthetic_league_value.json"),
  opponentIntent: path.join(fixtureRoot, "synthetic_opponent_intent.json"),
  runtimeBundle: path.join(draftRoot, "data", "candidate", "runtime-contract", "synthetic_runtime_bundle.json"),
  manifest: path.join(draftRoot, "data", "candidate", "runtime-contract", "synthetic_runtime_bundle_manifest.json"),
  expectedRuntimeBundle: path.join(fixtureRoot, "expected_runtime_bundle.json"),
});
const realArtifacts = Object.freeze({
  playerTruth: path.join(draftRoot, "data", "candidate", "player-truth", "player_truth_step14.json"),
  espnMarket: path.join(draftRoot, "data", "candidate", "espn-market", "espn_market_frozen.json"),
  leagueValue: path.join(draftRoot, "data", "candidate", "league-value", "espn_league_value_step15.json"),
  opponentIntent: path.join(draftRoot, "data", "candidate", "opponent-intent", "opponent_intent_streamlined.json"),
});

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
}

function sign(value) {
  const signed = structuredClone(value);
  delete signed.integrity.payloadSha256;
  const digest = crypto.createHash("sha256").update(JSON.stringify(canonical(signed))).digest("hex");
  value.integrity.payloadSha256 = digest;
  return value;
}

function writeFixture(tempDir, name, source, mutate, { signPayload = true } = {}) {
  const value = JSON.parse(fs.readFileSync(source, "utf8"));
  mutate(value);
  if (signPayload) sign(value);
  const target = path.join(tempDir, name);
  fs.writeFileSync(target, `${JSON.stringify(value, null, 2)}\n`);
  return target;
}

function validate(overrides = {}, extra = []) {
  const selected = { ...fixtures, ...overrides };
  const args = [
    validator,
    "--player-truth", selected.playerTruth,
    "--espn-market", selected.espnMarket,
    "--league-value", selected.leagueValue,
    "--opponent-intent", selected.opponentIntent,
    "--as-of", asOf,
    "--json",
    ...extra,
  ];
  const result = spawnSync("python3", args, { encoding: "utf8" });
  let payload = null;
  try { payload = JSON.parse(result.stdout); } catch {}
  return { ...result, payload };
}

function validateReal(overrides = {}, extra = []) {
  const selected = { ...realArtifacts, ...overrides };
  const result = spawnSync("python3", [
    validator,
    "--player-truth", selected.playerTruth,
    "--espn-market", selected.espnMarket,
    "--league-value", selected.leagueValue,
    "--opponent-intent", selected.opponentIntent,
    "--approve-missing-projection", "143",
    "--as-of", "2026-09-01T04:04:09Z",
    "--json",
    ...extra,
  ], { encoding: "utf8" });
  let payload = null;
  try { payload = JSON.parse(result.stdout); } catch {}
  return { ...result, payload };
}

function issueCodes(result) {
  return new Set((result.payload?.issues || []).map((issue) => issue.code));
}

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "draft-runtime-contract-"));

// A. Schema and artifact integrity.
{
  const valid = validate();
  assert.equal(valid.status, 0, valid.stderr || valid.stdout);
  assert.equal(valid.payload.promotionEligible, true);
  assert.equal(valid.payload.issueCounts.BLOCKING, 0);

  const requiredMissing = writeFixture(tempDir, "required-missing.json", fixtures.playerTruth, (value) => {
    delete value.players[0].normalizedName;
  });
  const missingResult = validate({ playerTruth: requiredMissing });
  assert.equal(missingResult.status, 1);
  assert.ok(issueCodes(missingResult).has("SCHEMA_REQUIRED"));

  const optionalNull = writeFixture(tempDir, "optional-null.json", fixtures.playerTruth, (value) => {
    value.players[0].fullPprPointsP10 = null;
    value.players[0].eliteProbability = null;
  });
  assert.equal(validate({ playerTruth: optionalNull }).status, 0, "nullable research outputs must validate");

  const invalidPosition = writeFixture(tempDir, "invalid-position.json", fixtures.playerTruth, (value) => {
    value.players[0].position = "K";
  });
  assert.ok(issueCodes(validate({ playerTruth: invalidPosition })).has("SCHEMA_ENUM"));

  const raw = fs.readFileSync(fixtures.playerTruth, "utf8").replace(/"projectedPpg": [0-9.]+/, '"projectedPpg": NaN');
  const nonfinite = path.join(tempDir, "nonfinite.json");
  fs.writeFileSync(nonfinite, raw);
  assert.ok(issueCodes(validate({ playerTruth: nonfinite })).has("INVALID_JSON"));

  const malformed = validate({ opponentIntent: path.join(fixtureRoot, "failures", "malformed_probabilities.json") });
  assert.equal(malformed.status, 1);
  assert.ok(issueCodes(malformed).has("POSITION_PROBABILITY_SUM"));

  const corrupt = validate({ espnMarket: path.join(fixtureRoot, "failures", "corrupt_hash_espn_market.json") });
  assert.equal(corrupt.status, 1);
  assert.ok(issueCodes(corrupt).has("HASH_MISMATCH"));

  const incompatible = validate({ playerTruth: path.join(fixtureRoot, "failures", "incompatible_player_truth.json") });
  assert.equal(incompatible.status, 1);
  assert.ok(issueCodes(incompatible).has("SCHEMA_CONST"));

  const duplicate = validate({ playerTruth: path.join(fixtureRoot, "failures", "duplicate_player_truth.json") });
  assert.equal(duplicate.status, 1);
  assert.ok(issueCodes(duplicate).has("DUPLICATE_INTERNAL_PLAYER_ID"));

  const stale = validate({ espnMarket: path.join(fixtureRoot, "failures", "stale_espn_market.json") });
  assert.equal(stale.status, 1);
  assert.ok(issueCodes(stale).has("STALE_ARTIFACT"));

  const fallbackIntent = validate({ opponentIntent: path.join(fixtureRoot, "failures", "fallback_opponent_intent.json") });
  assert.equal(fallbackIntent.status, 0, fallbackIntent.stderr || fallbackIntent.stdout);
  assert.ok(issueCodes(fallbackIntent).has("ARTIFACT_FALLBACK"));

  const missingIntent = spawnSync("python3", [
    validator,
    "--player-truth", fixtures.playerTruth,
    "--espn-market", fixtures.espnMarket,
    "--league-value", fixtures.leagueValue,
    "--allow-missing-opponent-intent",
    "--as-of", asOf,
    "--json",
  ], { encoding: "utf8" });
  assert.equal(missingIntent.status, 0, missingIntent.stderr || missingIntent.stdout);
  assert.ok(new Set(JSON.parse(missingIntent.stdout).issues.map((issue) => issue.code)).has("MISSING_OPTIONAL_ARTIFACT"));

  const missingMarket = spawnSync("python3", [
    validator,
    "--player-truth", fixtures.playerTruth,
    "--league-value", fixtures.leagueValue,
    "--opponent-intent", fixtures.opponentIntent,
    "--allow-missing-espn-market",
    "--as-of", asOf,
    "--json",
  ], { encoding: "utf8" });
  assert.equal(missingMarket.status, 0, missingMarket.stderr || missingMarket.stdout);

  const fallbackBuildDir = path.join(tempDir, "fallback-build");
  const fallbackBuild = spawnSync("python3", [
    builder,
    "--player-truth", fixtures.playerTruth,
    "--espn-market", fixtures.espnMarket,
    "--league-value", fixtures.leagueValue,
    "--allow-missing-opponent-intent",
    "--output-dir", fallbackBuildDir,
    "--as-of", asOf,
  ], { encoding: "utf8" });
  assert.equal(fallbackBuild.status, 0, fallbackBuild.stderr || fallbackBuild.stdout);
  const fallbackBundle = JSON.parse(fs.readFileSync(path.join(fallbackBuildDir, "draft_runtime_bundle.json"), "utf8"));
  assert.equal(fallbackBundle.status, "fallback");
  assert.equal(fallbackBundle.modelState, "fallback");
  assert.equal(fallbackBundle.opponentIntent, null);
  assert.equal(fallbackBundle.featureAvailability.opponentIntent, false);

  const frozenDir = path.join(tempDir, "frozen-output");
  fs.mkdirSync(frozenDir);
  fs.writeFileSync(path.join(frozenDir, "draft_runtime_bundle.json"), '{"status":"frozen"}\n');
  const frozenBuild = spawnSync("python3", [
    builder,
    "--player-truth", fixtures.playerTruth,
    "--espn-market", fixtures.espnMarket,
    "--league-value", fixtures.leagueValue,
    "--opponent-intent", fixtures.opponentIntent,
    "--output-dir", frozenDir,
    "--as-of", asOf,
  ], { encoding: "utf8" });
  assert.equal(frozenBuild.status, 1);
  assert.match(frozenBuild.stderr, /refusing to overwrite frozen artifact/i);
}

// B. Identity and coverage.
{
  const truth = JSON.parse(fs.readFileSync(fixtures.playerTruth, "utf8"));
  const market = JSON.parse(fs.readFileSync(fixtures.espnMarket, "utf8"));
  const league = JSON.parse(fs.readFileSync(fixtures.leagueValue, "utf8"));
  const bundle = JSON.parse(fs.readFileSync(fixtures.runtimeBundle, "utf8"));
  const playerIds = new Set(truth.players.map((player) => player.internalPlayerId));
  const mappedIds = new Set(truth.players.filter((player) => player.identityMatchMethod !== "unresolved").map((player) => player.internalPlayerId));
  assert.equal(playerIds.size, truth.players.length);
  assert.equal(new Set(market.records.map((record) => record.internalPlayerId)).size, market.records.length);
  assert.equal(new Set(market.records.filter((record) => record.espnPlayerId !== null).map((record) => record.espnPlayerId)).size, market.records.filter((record) => record.espnPlayerId !== null).length);
  assert.ok([...mappedIds].every((id) => league.records.some((record) => record.internalPlayerId === id)), "one League Value record per mapped player");
  assert.equal(league.leagueConfiguration.keepers.length, 10);
  assert.ok(league.leagueConfiguration.keepers.every((keeper) => playerIds.has(keeper.internalPlayerId)));
  assert.equal(bundle.coverage.keeperIdentities.resolved, 10);
  assert.equal(bundle.coverage.keeperIdentities.expected, 10);
  assert.equal(bundle.coverage.unresolvedIdentities.length, 1);
  assert.equal(bundle.coverage.unresolvedIdentities[0].blocking, false);
  assert.equal(bundle.coverage.byBoardRange["1-50"].eligible, 23);

  const forbiddenNameJoin = writeFixture(tempDir, "forbidden-name-join.json", fixtures.espnMarket, (value) => {
    value.records[0].internalPlayerId = 999999;
    value.records[0].normalizedName = truth.players[0].normalizedName;
  });
  const forbiddenResult = validate({ espnMarket: forbiddenNameJoin });
  assert.equal(forbiddenResult.status, 1);
  assert.ok(issueCodes(forbiddenResult).has("SCHEMA_ADDITIONALPROPERTIES"));
  assert.ok(issueCodes(forbiddenResult).has("UNKNOWN_STABLE_ID"));

  const unknownIntent = writeFixture(tempDir, "unknown-opponent-player.json", fixtures.opponentIntent, (value) => {
    value.opponents["team-01"].topFivePlayerProbabilities[0].internalPlayerId = 999997;
    value.targetSurvival[0].internalPlayerId = 999998;
  });
  const unknownIntentValidation = validate({ opponentIntent: unknownIntent });
  assert.equal(unknownIntentValidation.status, 0, unknownIntentValidation.stderr || unknownIntentValidation.stdout);
  assert.ok(issueCodes(unknownIntentValidation).has("OPPONENT_PLAYER_UNKNOWN_ID"));
  assert.ok(issueCodes(unknownIntentValidation).has("OPPONENT_TARGET_UNKNOWN_ID"));
  const mismatchBuildDir = path.join(tempDir, "mismatch-build");
  const mismatchBuild = spawnSync("python3", [
    builder,
    "--player-truth", fixtures.playerTruth,
    "--espn-market", fixtures.espnMarket,
    "--league-value", fixtures.leagueValue,
    "--opponent-intent", unknownIntent,
    "--output-dir", mismatchBuildDir,
    "--as-of", asOf,
  ], { encoding: "utf8" });
  assert.equal(mismatchBuild.status, 0, mismatchBuild.stderr || mismatchBuild.stdout);
  const mismatchBundle = JSON.parse(fs.readFileSync(path.join(mismatchBuildDir, "draft_runtime_bundle.json"), "utf8"));
  assert.equal(mismatchBundle.opponentIntent.opponents["team-01"].topFivePlayerProbabilities.some((item) => item.internalPlayerId === 999997), false);
  assert.equal(mismatchBundle.opponentIntent.opponents["team-01"].otherProbability, 0.63);
  assert.equal(mismatchBundle.opponentIntent.targetSurvival.some((item) => item.internalPlayerId === 999998), false);

  const missingTop160 = path.join(fixtureRoot, "failures", "top160_missing_league_value.json");
  const blocked = validate({ leagueValue: missingTop160 });
  assert.equal(blocked.status, 1);
  assert.ok(issueCodes(blocked).has("TOP160_IDENTITY_GAP"));
  const approved = validate({ leagueValue: missingTop160 }, ["--approve-top160-identity-gap", "1001"]);
  assert.equal(approved.status, 0, approved.stderr || approved.stdout);
  assert.ok(issueCodes(approved).has("APPROVED_TOP160_IDENTITY_GAP"));

  const duplicateEspn = validate({ espnMarket: path.join(fixtureRoot, "failures", "duplicate_espn_id.json") });
  assert.equal(duplicateEspn.status, 1);
  assert.ok(issueCodes(duplicateEspn).has("DUPLICATE_ESPN_PLAYER_ID"));

  // The narrow Keenan exception cannot hide an unresolved ID or a new top-160 omission.
  const resolvedMissingProjection = validateReal();
  assert.equal(resolvedMissingProjection.status, 0, resolvedMissingProjection.stderr || resolvedMissingProjection.stdout);
  assert.ok(issueCodes(resolvedMissingProjection).has("APPROVED_MISSING_PROJECTION"));
  assert.equal(resolvedMissingProjection.payload.coverage.overall.eligible, 200);
  assert.equal(resolvedMissingProjection.payload.coverage.overall.playerTruth, 199);

  const unresolvedApprovedMarket = writeFixture(tempDir, "real-keenan-unresolved.json", realArtifacts.espnMarket, (value) => {
    const record = value.records.find((item) => item.internalPlayerId === 143);
    record.espnPlayerId = null;
    record.mappingConfidence = 0;
  });
  const unresolvedApproved = validateReal({ espnMarket: unresolvedApprovedMarket });
  assert.equal(unresolvedApproved.status, 1);
  assert.ok(issueCodes(unresolvedApproved).has("APPROVED_MISSING_PROJECTION_UNRESOLVED_IDENTITY"));

  const accidentalTop160Truth = writeFixture(tempDir, "real-top160-missing-truth.json", realArtifacts.playerTruth, (value) => {
    value.players = value.players.filter((player) => player.internalPlayerId !== 1);
  });
  const accidentalTop160 = validateReal({ playerTruth: accidentalTop160Truth });
  assert.equal(accidentalTop160.status, 1);
  assert.ok(issueCodes(accidentalTop160).has("TOP160_PLAYER_TRUTH_GAP"));
}

// C. Mathematical and semantic artifact validation.
{
  const badRank = writeFixture(tempDir, "bad-rank.json", fixtures.leagueValue, (value) => {
    value.records[0].leagueValueScore = -500;
  });
  const badRankResult = validate({ leagueValue: badRank });
  assert.equal(badRankResult.status, 1);
  assert.ok(issueCodes(badRankResult).has("LEAGUE_VALUE_RANK_INCONSISTENT"));

  const badOrdinal = writeFixture(tempDir, "derived-ordinal.json", fixtures.espnMarket, (value) => {
    value.records[0].ordinalAdpRank = 1;
    value.records[0].ordinalAdpRankSource = null;
  });
  assert.ok(issueCodes(validate({ espnMarket: badOrdinal })).has("ORDINAL_ADP_WITHOUT_SOURCE"));

  const truth = JSON.parse(fs.readFileSync(fixtures.playerTruth, "utf8"));
  const bundle = JSON.parse(fs.readFileSync(fixtures.runtimeBundle, "utf8"));
  const manifest = JSON.parse(fs.readFileSync(fixtures.manifest, "utf8"));
  assert.equal(fs.readFileSync(fixtures.runtimeBundle, "utf8"), fs.readFileSync(fixtures.expectedRuntimeBundle, "utf8"), "built bytes match the committed expected runtime fixture");
  const firstTruth = truth.players[0];
  const firstRuntime = bundle.playerRecords.find((player) => player.internalPlayerId === firstTruth.internalPlayerId);
  const firstMarket = bundle.marketRecords.find((player) => player.internalPlayerId === firstTruth.internalPlayerId);
  assert.equal(firstRuntime.outcome.projectedFullPprPoints, firstTruth.projectedFullPprPoints, "market data cannot overwrite Player Truth");
  assert.notEqual(firstMarket.defaultRank, firstMarket.continuousAdp, "ESPN rank and continuous ADP remain separate");
  const missingDistribution = bundle.playerRecords.find((player) => player.internalPlayerId === 1006);
  assert.equal(missingDistribution.outcome.p10, null);
  assert.equal(missingDistribution.outcome.eliteProbability, null);
  const missingRank = bundle.marketRecords.find((record) => record.internalPlayerId === 1007);
  assert.equal(missingRank.defaultRank, null);
  assert.notEqual(missingRank.defaultRank, 0);
  assert.equal(manifest.gates.result, "pass");
  assert.equal(manifest.determinism.identicalInputsProduceIdenticalBytes, true);
}

console.log("draft runtime artifact-contract tests passed");
