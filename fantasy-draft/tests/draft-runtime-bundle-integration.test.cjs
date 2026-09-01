"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const draftRoot = path.resolve(__dirname, "..");
const fixtureRoot = path.join(__dirname, "fixtures", "runtime-contract");
const bundle = JSON.parse(fs.readFileSync(path.join(draftRoot, "data", "candidate", "runtime-contract", "synthetic_runtime_bundle.json"), "utf8"));
const sequence = JSON.parse(fs.readFileSync(path.join(fixtureRoot, "synthetic_draft_sequence.json"), "utf8"));

function clone(value) { return structuredClone(value); }

function createHarness(inputBundle) {
  const runtime = clone(inputBundle);
  const compatible = runtime?.schemaVersion === "1.0.0" && runtime?.compatibility?.applicationId === "draft-command";
  const opponentValid = runtime?.opponentIntent && runtime.opponentIntent.opponents && Array.isArray(runtime.opponentIntent.targetSurvival);
  const playerById = new Map((runtime.playerRecords || []).map((player) => [player.internalPlayerId, player]));
  const marketById = new Map((runtime.marketRecords || []).map((record) => [record.internalPlayerId, record]));
  const leagueById = new Map((runtime.leagueValueRecords || []).map((record) => [record.internalPlayerId, record]));
  const keeperEvents = (runtime.leagueConfiguration?.keepers || []).map((keeper) => ({
    overall: keeper.overallPick,
    teamId: keeper.teamId,
    internalPlayerId: keeper.internalPlayerId,
    source: "keeper",
  }));
  const initialRosters = new Map();
  for (const keeper of keeperEvents) {
    if (!initialRosters.has(keeper.teamId)) initialRosters.set(keeper.teamId, []);
    initialRosters.get(keeper.teamId).push(keeper.internalPlayerId);
  }
  let events = [];
  let observations = [];
  let currentPick = 1;
  let rosters = cloneRosters(initialRosters);
  let targetLabels = new Map();

  function cloneRosters(source) {
    return new Map([...source].map(([teamId, players]) => [teamId, players.slice()]));
  }

  function draftedIds() {
    return new Set([...keeperEvents, ...events].map((event) => event.internalPlayerId).filter(Number.isInteger));
  }

  function availablePlayers() {
    const drafted = draftedIds();
    return (runtime.playerRecords || []).filter((player) => !drafted.has(player.internalPlayerId));
  }

  function sortNullable(left, right, direction) {
    if (left == null && right == null) return 0;
    if (left == null) return 1;
    if (right == null) return -1;
    return (left - right) * direction;
  }

  function decisionBoard({ sort = "leagueValue", direction, position = "ALL", search = "" } = {}) {
    const normalizedSearch = String(search).trim().toLowerCase();
    const filtered = availablePlayers().filter((player) =>
      (position === "ALL" || player.position === position) &&
      (!normalizedSearch || player.name.toLowerCase().includes(normalizedSearch))
    );
    const selectedDirection = direction ?? (sort === "leagueValue" ? -1 : 1);
    return filtered.sort((left, right) => {
      const leftValue = sort === "leagueValue" ? leagueById.get(left.internalPlayerId)?.leagueValueScore : marketById.get(left.internalPlayerId)?.defaultRank;
      const rightValue = sort === "leagueValue" ? leagueById.get(right.internalPlayerId)?.leagueValueScore : marketById.get(right.internalPlayerId)?.defaultRank;
      return sortNullable(leftValue, rightValue, selectedDirection) || left.internalPlayerId - right.internalPlayerId;
    });
  }

  function recordPick({ overall = currentPick, teamId, internalPlayerId = null, externalPlayerId = null, source = "synthetic" }) {
    const observation = { overall, teamId, internalPlayerId, externalPlayerId, source, status: "resolved" };
    if (!playerById.has(internalPlayerId)) {
      observation.internalPlayerId = null;
      observation.status = "unresolved";
      observations.push(observation);
      currentPick = Math.max(currentPick, overall + 1);
      return { ok: true, resolved: false };
    }
    if (draftedIds().has(internalPlayerId)) return { ok: false, code: "DUPLICATE_PLAYER" };
    observations.push(observation);
    events.push({ overall, teamId, internalPlayerId, source });
    if (!rosters.has(teamId)) rosters.set(teamId, []);
    rosters.get(teamId).push(internalPlayerId);
    currentPick = Math.max(currentPick, overall + 1);
    return { ok: true, resolved: true };
  }

  function manualPick(internalPlayerId) {
    return recordPick({ overall: currentPick, teamId: runtime.leagueConfiguration.tonyTeamId, internalPlayerId, source: "manual" });
  }

  function opponentCards() {
    if (!opponentValid) return [];
    return Object.values(runtime.opponentIntent.opponents).map((opponent) => ({
      teamId: opponent.teamId,
      label: opponent.displayLabel,
      nextOverallPick: opponent.nextOverallPick,
      roster: (rosters.get(opponent.teamId) || []).slice(),
      positionProbabilities: clone(opponent.positionProbabilities),
    }));
  }

  function opponentProbabilitySnapshot() {
    if (!opponentValid) return null;
    return JSON.stringify(Object.fromEntries(Object.entries(runtime.opponentIntent.opponents).map(([teamId, opponent]) => [teamId, {
      positionProbabilities: opponent.positionProbabilities,
      topFivePlayerProbabilities: opponent.topFivePlayerProbabilities,
      otherProbability: opponent.otherProbability,
    }])));
  }

  function threatBoard(labels = {}) {
    targetLabels = new Map(Object.entries(labels).map(([id, label]) => [Number(id), label]));
    if (!opponentValid) return [];
    const available = new Set(availablePlayers().map((player) => player.internalPlayerId));
    return runtime.opponentIntent.targetSurvival
      .filter((target) => available.has(target.internalPlayerId))
      .map((target) => ({ ...clone(target), label: targetLabels.get(target.internalPlayerId) || null }));
  }

  function hardReset() {
    events = [];
    observations = [];
    currentPick = 1;
    rosters = cloneRosters(initialRosters);
    targetLabels = new Map();
  }

  function auditExport() {
    return clone({
      modelState: !compatible ? "rejected" : opponentValid ? runtime.modelState : "fallback",
      bundleVersion: runtime.bundleVersion || null,
      sourceArtifacts: runtime.sourceArtifacts || [],
      featureAvailability: {
        ...(runtime.featureAvailability || {}),
        opponentIntent: Boolean(opponentValid),
        roomSurvival: Boolean(opponentValid),
      },
      currentPick,
      events,
      observations,
    });
  }

  function seededRandom(seed) {
    let state = seed >>> 0;
    return () => {
      state = (1664525 * state + 1013904223) >>> 0;
      return state / 0x100000000;
    };
  }

  function simulateOpponentPicks(seed, limit = 9) {
    if (!opponentValid) return [];
    const random = seededRandom(seed);
    const selected = [];
    const opponentEntries = Object.values(runtime.opponentIntent.opponents).sort((a, b) => a.nextOverallPick - b.nextOverallPick);
    for (const opponent of opponentEntries.slice(0, limit)) {
      const available = new Set(availablePlayers().map((player) => player.internalPlayerId));
      const weighted = opponent.topFivePlayerProbabilities.filter((item) => available.has(item.internalPlayerId));
      const total = weighted.reduce((sum, item) => sum + item.probability, 0);
      let chosen = null;
      if (weighted.length && total > 0) {
        let cursor = random() * total;
        for (const item of weighted) {
          cursor -= item.probability;
          if (cursor <= 0) { chosen = item.internalPlayerId; break; }
        }
        chosen ??= weighted.at(-1).internalPlayerId;
      } else {
        chosen = decisionBoard({ sort: "leagueValue" })[0]?.internalPlayerId;
      }
      if (chosen == null) break;
      const result = recordPick({ overall: opponent.nextOverallPick, teamId: opponent.teamId, internalPlayerId: chosen, source: "simulation" });
      assert.equal(result.ok, true);
      selected.push(chosen);
    }
    return selected;
  }

  return {
    compatible,
    modelState: !compatible ? "rejected" : opponentValid ? runtime.modelState : "fallback",
    opponentValid: Boolean(opponentValid),
    availablePlayers,
    decisionBoard,
    recordPick,
    manualPick,
    opponentCards,
    opponentProbabilitySnapshot,
    threatBoard,
    hardReset,
    auditExport,
    simulateOpponentPicks,
    state: () => clone({ events, observations, currentPick, rosters: Object.fromEntries(rosters) }),
  };
}

function pickOwner(overall, teamCount = 10) {
  const round = Math.ceil(overall / teamCount);
  const slot = ((overall - 1) % teamCount) + 1;
  return round % 2 ? slot : teamCount + 1 - slot;
}

// D. Bundle supports the later Draft Command integration interface.
{
  const harness = createHarness(bundle);
  assert.equal(harness.compatible, true);
  assert.equal(harness.modelState, "ready");
  assert.ok(harness.decisionBoard().length > 0, "Decision Board populates");

  const leagueDesc = harness.decisionBoard({ sort: "leagueValue", direction: -1 });
  const leagueAsc = harness.decisionBoard({ sort: "leagueValue", direction: 1 });
  assert.equal(leagueDesc[0].internalPlayerId, leagueAsc.at(-1).internalPlayerId, "League Value sort reverses on underlying numbers");
  const espnOrder = harness.decisionBoard({ sort: "espnPrice", direction: 1 });
  assert.notDeepEqual(leagueDesc.map((player) => player.internalPlayerId), espnOrder.map((player) => player.internalPlayerId), "ESPN Price remains an independent sort");

  const qbs = harness.decisionBoard({ position: "QB" });
  assert.ok(qbs.length > 0 && qbs.every((player) => player.position === "QB"));
  const search = harness.decisionBoard({ search: "Player 03" });
  assert.equal(search.length, 1);
  assert.equal(search[0].internalPlayerId, 1003);

  const before = harness.availablePlayers().length;
  assert.equal(harness.recordPick({ overall: 1, teamId: "team-01", internalPlayerId: 1001 }).ok, true);
  assert.equal(harness.availablePlayers().length, before - 1, "sequential depletion updates availability");
  assert.equal(harness.decisionBoard().some((player) => player.internalPlayerId === 1001), false, "drafted players are excluded");
  assert.equal(harness.recordPick({ overall: 2, teamId: "team-02", internalPlayerId: 1001 }).code, "DUPLICATE_PLAYER");
  assert.ok(harness.opponentCards().find((card) => card.teamId === "team-01").roster.includes(1001), "opponent card roster updates");

  const probabilityBefore = harness.opponentProbabilitySnapshot();
  const threats = harness.threatBoard({ 1002: "BPA", 1003: "Tony tier" });
  assert.ok(threats.length > 0);
  assert.equal(harness.opponentProbabilitySnapshot(), probabilityBefore, "Tony target labels cannot change opponent probabilities");

  const manualTarget = harness.decisionBoard()[0].internalPlayerId;
  assert.equal(harness.manualPick(manualTarget).ok, true);
  assert.ok(harness.state().rosters["team-05"].includes(manualTarget), "Manual pick updates Tony's roster");
  const auditBeforeMutation = harness.auditExport();
  auditBeforeMutation.events.length = 0;
  assert.ok(harness.state().events.length > 0, "audit export remains read-only");
  assert.ok(harness.auditExport().sourceArtifacts.every((item) => item.fileSha256 && item.payloadSha256), "audit carries status and provenance");

  harness.hardReset();
  assert.equal(harness.state().events.length, 0);
  assert.equal(harness.state().observations.length, 0);
  assert.equal(harness.state().currentPick, 1);
  assert.equal(harness.state().rosters["team-05"].length, 1, "Hard Reset preserves configured keeper input but clears live state");
}

// Missing/corrupt optional intelligence degrades without blocking the board.
{
  const absent = clone(bundle);
  absent.opponentIntent = null;
  absent.featureAvailability.opponentIntent = false;
  absent.featureAvailability.roomSurvival = false;
  const missingHarness = createHarness(absent);
  assert.equal(missingHarness.modelState, "fallback");
  assert.equal(missingHarness.opponentCards().length, 0);
  assert.equal(missingHarness.threatBoard().length, 0);
  assert.ok(missingHarness.decisionBoard().length > 0);

  const corrupt = clone(bundle);
  corrupt.opponentIntent = { modelArtifactVersion: "broken" };
  const corruptHarness = createHarness(corrupt);
  assert.equal(corruptHarness.modelState, "fallback");
  assert.ok(corruptHarness.decisionBoard().length > 0);

  const incompatible = clone(bundle);
  incompatible.schemaVersion = "9.0.0";
  const rejected = createHarness(incompatible);
  assert.equal(rejected.modelState, "rejected");
  assert.notEqual(rejected.modelState, "loading");
}

// Sequential unresolved observations do not prevent later picks.
{
  const harness = createHarness(bundle);
  for (const pick of sequence.picks) harness.recordPick(pick);
  const state = harness.state();
  assert.equal(state.currentPick, 11);
  assert.equal(state.observations.length, 10);
  assert.equal(state.observations.find((item) => item.overall === 2).status, "unresolved");
  assert.equal(state.events.length, 9);
  assert.equal(new Set(state.events.map((event) => event.internalPlayerId)).size, state.events.length);
  assert.ok(state.events.some((event) => event.overall === 10), "later pick survives an unresolved earlier identity");
}

// Fixed seed is reproducible; simulated players deplete and rosters update.
{
  const first = createHarness(bundle);
  const second = createHarness(bundle);
  const firstPicks = first.simulateOpponentPicks(bundle.opponentIntent.simulation.seed);
  const secondPicks = second.simulateOpponentPicks(bundle.opponentIntent.simulation.seed);
  assert.deepEqual(firstPicks, secondPicks);
  assert.equal(new Set(firstPicks).size, firstPicks.length);
  assert.equal(first.availablePlayers().some((player) => firstPicks.includes(player.internalPlayerId)), false);
  assert.ok(first.opponentCards().some((card) => card.roster.length > 1));
}

// Exact 10-team, 16-round snake geometry and ten keeper slots are representable.
{
  assert.equal(bundle.leagueConfiguration.teamCount, 10);
  assert.equal(bundle.leagueConfiguration.rounds, 16);
  assert.equal(bundle.leagueConfiguration.draftSlot, 5);
  assert.equal(bundle.leagueConfiguration.tonyFirstPick, 5);
  assert.equal(bundle.leagueConfiguration.totalPicks, 160);
  assert.equal(bundle.leagueConfiguration.keepers.length, 10);
  const ownerCounts = new Map();
  for (let overall = 1; overall <= 160; overall += 1) ownerCounts.set(pickOwner(overall), (ownerCounts.get(pickOwner(overall)) || 0) + 1);
  assert.deepEqual([...ownerCounts.values()], Array(10).fill(16));
}

// E. Bundle design is fetch-only and does not add browser persistence requirements.
{
  for (const relative of [
    "research/runtime_contract_lib.py",
    "research/build_draft_runtime_bundle.py",
    "research/validate_draft_runtime_bundle.py",
  ]) {
    const source = fs.readFileSync(path.join(draftRoot, relative), "utf8");
    assert.doesNotMatch(source, /(?:window\.)?(?:localStorage|sessionStorage)\s*\.|(?:getItem|setItem|removeItem)\s*\(/);
  }
  assert.equal(bundle.compatibility.persistencePolicy, "bundle-fetch-only-no-localStorage");
  for (const forbidden of ["cookies", "credentials", "authenticatedResponses", "rawManagerPickHistories", "trainingLedgers", "simulationLedgers"]) {
    assert.equal(Object.hasOwn(bundle, forbidden), false);
  }
}

console.log("draft runtime bundle-integration tests passed");
