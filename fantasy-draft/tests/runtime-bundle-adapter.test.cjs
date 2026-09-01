"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const draftRoot = path.resolve(__dirname, "..");
const bundlePath = path.join(draftRoot, "data", "candidate", "runtime-contract", "draft_runtime_bundle.json");
const manifestPath = path.join(draftRoot, "data", "candidate", "runtime-contract", "draft_runtime_bundle_manifest.json");
const bundleText = fs.readFileSync(bundlePath, "utf8");
const manifestText = fs.readFileSync(manifestPath, "utf8");
const bundle = JSON.parse(bundleText);
const manifest = JSON.parse(manifestText);
const { createAdapter, validateBundle } = require(path.join(draftRoot, "model", "runtime-bundle-adapter.js"));

function boardPlayers() {
  const context = {};
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(draftRoot, "data", "players.js"), "utf8"), context);
  return context.PLAYER_DATA;
}

const players = boardPlayers();
const knownIds = players.map((player) => player.id);

// The real four-artifact bundle is accepted as a definite ready state.
{
  const validation = validateBundle(bundle, knownIds);
  assert.equal(validation.ok, true, validation.errors.join("\n"));
  const adapter = createAdapter({ players });
  assert.equal(adapter.health().modelState, "fallback");
  assert.notEqual(adapter.health().modelState, "loading");
  const health = adapter.load(structuredClone(bundle), { manifest });
  assert.equal(health.modelState, "ready");
  assert.equal(health.label, "Validated League Value");
  assert.equal(health.coveredPlayers, 199);
  assert.equal(health.totalPlayers, 200);
  assert.equal(adapter.bundle().leagueConfiguration.keepers.length, 10);

  const keenan = adapter.playerTruth(143);
  assert.equal(keenan, null);
  assert.equal(adapter.leagueValue(143), null);
  assert.equal(adapter.market(143).defaultRank, 201);
  assert.equal(adapter.market(143).continuousAdp, 165.64);
  assert.equal(adapter.approvedException(143).exceptionType, "resolved-identity-missing-projection");

  assert.equal(adapter.playerTruth(190).name, "Jaydon Blue");
  assert.equal(adapter.leagueValue(190).leagueValueRank, 192);
  assert.equal(adapter.market(190).defaultRank, null);
  assert.equal(adapter.market(190).continuousAdp, null);

  const jacobs = adapter.playerTruth(34);
  assert.equal(jacobs.availability.status, "out");
  assert.equal(jacobs.outcome.p50, 256.85);
  assert.equal(jacobs.outcome.expectedGames, 17);
  assert.equal(jacobs.outcome.p10, null);
  assert.equal(jacobs.outcome.p90, null);
  assert.ok(jacobs.limitations.some((item) => item.includes("COMMISSIONER_EXEMPT")));
  assert.ok(jacobs.limitations.some((item) => item.includes("No numerical games adjustment")));
  assert.equal(adapter.auditMetadata().manifestBundleSha256, manifest.outputs.bundle.sha256);
  assert.equal(adapter.auditMetadata().approvedExceptions.length, 1);
}

// Required-layer corruption fails closed; compatibility rejection is distinct.
for (const mutation of [
  (value) => value.playerRecords.pop(),
  (value) => value.marketRecords.pop(),
  (value) => value.leagueValueRecords.pop(),
  (value) => value.leagueValueRecords.push({ ...value.leagueValueRecords[0] }),
  (value) => { value.leagueValueRecords[0].leagueValueScore = Number.POSITIVE_INFINITY; },
]) {
  const candidate = structuredClone(bundle);
  mutation(candidate);
  const adapter = createAdapter({ players });
  assert.equal(adapter.load(candidate).modelState, "fallback");
  assert.equal(adapter.health().valid, false);
  assert.notEqual(adapter.health().modelState, "loading");
}

{
  const incompatible = structuredClone(bundle);
  incompatible.schemaVersion = "9.0.0";
  const adapter = createAdapter({ players });
  assert.equal(adapter.load(incompatible).modelState, "rejected");
  assert.match(adapter.health().errors[0], /unsupported runtime schema/i);
}

// Optional Opponent Intent degradation retains the validated base indexes.
{
  const degraded = structuredClone(bundle);
  degraded.modelState = "fallback";
  degraded.status = "fallback";
  degraded.overallStatus = "fallback";
  degraded.opponentIntent = null;
  degraded.featureAvailability.opponentIntent = false;
  degraded.featureAvailability.roomSurvival = false;
  const adapter = createAdapter({ players });
  const health = adapter.load(degraded);
  assert.equal(health.modelState, "fallback");
  assert.equal(health.validatedBaseAvailable, true);
  assert.equal(adapter.hasValidatedBase(), true);
  assert.equal(adapter.leagueValue(1).leagueValueScore, 182.44);
}

// Browser fetch verifies byte length and SHA-256 before parsing or activation.
(async () => {
  const originalFetch = global.fetch;
  try {
    global.fetch = async (url) => url.includes("manifest")
      ? { ok: true, status: 200, json: async () => JSON.parse(manifestText) }
      : { ok: true, status: 200, text: async () => bundleText };
    const adapter = createAdapter({ players });
    assert.equal((await adapter.start({ bundleUrl: "bundle", manifestUrl: "manifest" })).modelState, "ready");

    global.fetch = async (url) => url.includes("manifest")
      ? { ok: true, status: 200, json: async () => ({ ...manifest, outputs: { bundle: { ...manifest.outputs.bundle, sha256: "0".repeat(64) } } }) }
      : { ok: true, status: 200, text: async () => bundleText };
    assert.equal((await adapter.start({ bundleUrl: "bundle", manifestUrl: "manifest" })).modelState, "fallback");
    assert.match(adapter.health().errors[0], /sha-256/i);
  } finally {
    global.fetch = originalFetch;
  }
  console.log("runtime bundle adapter tests passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
