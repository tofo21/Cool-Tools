(function attachRuntimeBundleAdapter(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.DraftRuntimeBundle = api;
})(typeof window !== "undefined" ? window : globalThis, () => {
  "use strict";

  const SUPPORTED_SCHEMA_MAJOR = 1;
  const REQUIRED_CAPABILITIES = new Set([
    "definite-model-state",
    "numeric-league-value-sort",
    "separate-espn-rank-adp",
    "stable-id-only-joins",
  ]);

  function schemaMajor(version) {
    const match = String(version || "").match(/^(\d+)\./);
    return match ? Number(match[1]) : null;
  }

  function finiteTree(value, path = "$") {
    const errors = [];
    if (typeof value === "number" && !Number.isFinite(value)) errors.push(`${path} contains a non-finite number.`);
    if (Array.isArray(value)) value.forEach((item, index) => errors.push(...finiteTree(item, `${path}[${index}]`)));
    if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [key, child] of Object.entries(value)) errors.push(...finiteTree(child, `${path}.${key}`));
    }
    return errors;
  }

  function uniqueIndex(records, label) {
    const index = new Map();
    const errors = [];
    for (const record of Array.isArray(records) ? records : []) {
      const playerId = Number(record?.internalPlayerId);
      if (!Number.isInteger(playerId) || playerId <= 0) {
        errors.push(`${label} contains an invalid internalPlayerId.`);
      } else if (index.has(playerId)) {
        errors.push(`${label} contains duplicate internalPlayerId ${playerId}.`);
      } else {
        index.set(playerId, Object.freeze({ ...record }));
      }
    }
    return { index, errors };
  }

  function validateBundle(bundle, knownPlayerIds = []) {
    const data = bundle && typeof bundle === "object" ? bundle : {};
    const errors = finiteTree(data);
    const warnings = [];
    if (schemaMajor(data.schemaVersion) !== SUPPORTED_SCHEMA_MAJOR) errors.push(`Unsupported runtime schema ${data.schemaVersion || "missing"}.`);
    if (data.artifactType !== "draft-runtime-bundle") errors.push("Runtime artifactType is invalid.");
    if (!new Set(["ready", "fallback", "rejected"]).has(data.modelState)) errors.push("Runtime modelState must be ready, fallback, or rejected.");
    if (data.compatibility?.applicationId !== "draft-command") errors.push("Runtime application compatibility is invalid.");
    const capabilities = new Set(data.compatibility?.requiredCapabilities || []);
    for (const capability of REQUIRED_CAPABILITIES) if (!capabilities.has(capability)) errors.push(`Runtime capability ${capability} is missing.`);
    if (data.compatibility?.persistencePolicy !== "bundle-fetch-only-no-localStorage") errors.push("Runtime persistence policy is incompatible.");

    const players = uniqueIndex(data.playerRecords, "playerRecords");
    const market = uniqueIndex(data.marketRecords, "marketRecords");
    const leagueValue = uniqueIndex(data.leagueValueRecords, "leagueValueRecords");
    errors.push(...players.errors, ...market.errors, ...leagueValue.errors);
    const approvedRecords = Array.isArray(data.approvedExceptions) ? data.approvedExceptions : [];
    const approved = new Map();
    for (const exception of approvedRecords) {
      const playerId = Number(exception?.internalPlayerId);
      if (!Number.isInteger(playerId) || approved.has(playerId)) errors.push("approvedExceptions contains an invalid or duplicate internalPlayerId.");
      else approved.set(playerId, Object.freeze({ ...exception }));
    }
    for (const playerId of leagueValue.index.keys()) if (!players.index.has(playerId)) errors.push(`League Value player ${playerId} has no Player Truth record.`);
    for (const playerId of market.index.keys()) {
      if (!players.index.has(playerId) && approved.get(playerId)?.exceptionType !== "resolved-identity-missing-projection") {
        errors.push(`Market player ${playerId} has no Player Truth record or approved exception.`);
      }
    }
    for (const [playerId, exception] of approved) {
      const record = market.index.get(playerId);
      if (players.index.has(playerId) || exception.exceptionType !== "resolved-identity-missing-projection" || !record
        || record.espnPlayerId == null || record.captureStatus !== "captured" || Number(record.mappingConfidence) < 0.8) {
        errors.push(`Approved missing-projection exception ${playerId} is not a resolved market-only identity.`);
      }
    }
    const known = new Set(knownPlayerIds.map(Number));
    for (const playerId of new Set([...players.index.keys(), ...market.index.keys(), ...leagueValue.index.keys()])) {
      if (known.size && !known.has(playerId)) errors.push(`Runtime player ${playerId} is not on the stable Draft Command board.`);
    }
    if (data.modelState === "ready") {
      if (players.index.size !== 199) errors.push(`Ready runtime requires 199 Player Truth rows; received ${players.index.size}.`);
      if (market.index.size !== 200) errors.push(`Ready runtime requires 200 ESPN market rows, including explicit null records; received ${market.index.size}.`);
      if (leagueValue.index.size !== 199) errors.push(`Ready runtime requires 199 League Value rows; received ${leagueValue.index.size}.`);
      if (data.leagueConfiguration?.keepers?.length !== 10) errors.push("Ready runtime requires exactly ten keeper slots.");
      if (!data.featureAvailability?.playerTruth || !data.featureAvailability?.leagueValue
        || !data.featureAvailability?.espnRank || !data.featureAvailability?.espnAdp) errors.push("Ready runtime is missing required valuation or ESPN market features.");
    }
    if (approved.size) warnings.push(`${approved.size} approved missing-projection exception is active.`);
    return { ok: errors.length === 0, errors, warnings, indexes: { players: players.index, market: market.index, leagueValue: leagueValue.index }, approved };
  }

  async function sha256Hex(text) {
    if (!globalThis.crypto?.subtle || typeof TextEncoder !== "function") throw new Error("Browser SHA-256 verification is unavailable.");
    const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function createAdapter({ players = [] } = {}) {
    const knownPlayerIds = players.map((player) => Number(player.id));
    let current = null;
    let currentManifest = null;
    let indexes = { players: new Map(), market: new Map(), leagueValue: new Map() };
    let approved = new Map();
    let modelState = "fallback";
    let validatedBaseAvailable = false;
    let errors = ["Validated runtime bundle has not loaded; provisional fallback is active."];
    let warnings = [];
    const listeners = new Set();

    function notify() {
      for (const listener of listeners) {
        try { listener(health()); } catch (_) { /* UI listeners are isolated. */ }
      }
    }

    function setFailure(reason, { rejected = false } = {}) {
      current = null;
      currentManifest = null;
      indexes = { players: new Map(), market: new Map(), leagueValue: new Map() };
      approved = new Map();
      modelState = rejected ? "rejected" : "fallback";
      validatedBaseAvailable = false;
      errors = [String(reason || "Runtime bundle unavailable.")];
      warnings = [];
      notify();
      return health();
    }

    function load(bundle, { manifest = null } = {}) {
      const validation = validateBundle(bundle, knownPlayerIds);
      if (!validation.ok) {
        const unsupported = validation.errors.some((message) => /Unsupported runtime schema|application compatibility/i.test(message));
        return setFailure(validation.errors[0], { rejected: unsupported });
      }
      current = Object.freeze(bundle);
      currentManifest = manifest ? Object.freeze(manifest) : null;
      indexes = validation.indexes;
      approved = validation.approved;
      modelState = bundle.modelState;
      validatedBaseAvailable = indexes.players.size === 199 && indexes.market.size === 200 && indexes.leagueValue.size === 199
        && Boolean(bundle.featureAvailability?.playerTruth && bundle.featureAvailability?.leagueValue
          && bundle.featureAvailability?.espnRank && bundle.featureAvailability?.espnAdp);
      errors = [];
      warnings = validation.warnings;
      notify();
      return health();
    }

    async function start({
      bundleUrl = "./data/candidate/runtime-contract/draft_runtime_bundle.json",
      manifestUrl = "./data/candidate/runtime-contract/draft_runtime_bundle_manifest.json",
      timeoutMs = 3500,
    } = {}) {
      if (typeof fetch !== "function") return setFailure("Runtime fetch is unavailable; provisional fallback is active.");
      let timeout = null;
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      try {
        timeout = setTimeout(() => controller?.abort(), timeoutMs);
        const options = { cache: "no-store", ...(controller ? { signal: controller.signal } : {}) };
        const [bundleResponse, manifestResponse] = await Promise.all([fetch(bundleUrl, options), fetch(manifestUrl, options)]);
        if (!bundleResponse.ok || !manifestResponse.ok) throw new Error(`Runtime fetch failed (${bundleResponse.status}/${manifestResponse.status}).`);
        const [bundleText, manifest] = await Promise.all([bundleResponse.text(), manifestResponse.json()]);
        const expected = manifest?.outputs?.bundle;
        if (!expected?.sha256 || !Number.isInteger(expected.bytes)) throw new Error("Runtime manifest is incomplete.");
        if (new TextEncoder().encode(bundleText).length !== expected.bytes) throw new Error("Runtime bundle byte count does not match the manifest.");
        if (await sha256Hex(bundleText) !== expected.sha256) throw new Error("Runtime bundle SHA-256 does not match the manifest.");
        return load(JSON.parse(bundleText), { manifest });
      } catch (error) {
        return setFailure(error?.name === "AbortError" ? "Runtime bundle load timed out; provisional fallback is active." : error?.message);
      } finally {
        if (timeout != null) clearTimeout(timeout);
      }
    }

    function health() {
      const coverage = current?.coverage?.overall;
      const coveredPlayers = Number(coverage?.playerTruth || indexes.players.size || 0);
      const totalPlayers = Number(coverage?.eligible || players.length || 0);
      return Object.freeze({
        modelState,
        mode: modelState === "ready" ? "research" : modelState,
        label: modelState === "ready" ? "Validated League Value" : modelState === "rejected" ? "Model rejected" : validatedBaseAvailable ? "Validated base · degraded" : "Provisional fallback",
        packageId: current?.bundleVersion || "provisional-fallback",
        modelVersion: current?.bundleVersion || "fallback-2026.08.27",
        status: current?.status || modelState,
        valid: validatedBaseAvailable,
        validatedBaseAvailable,
        stale: false,
        generatedAt: current?.generatedAt || null,
        effectiveAt: current?.generatedAt || null,
        coverage: totalPlayers ? coveredPlayers / totalPlayers : 0,
        coveredPlayers,
        totalPlayers,
        sourceCount: current?.sourceArtifacts?.length || 0,
        errors: errors.slice(),
        warnings: warnings.slice(),
        decisionPolicyApproved: false,
        decisionMode: "advisory",
        decisionPolicyVersion: null,
        decisionPolicyReason: modelState === "ready"
          ? "Validated base artifacts are live; roster fit and Opponent Intent remain separate advisory layers."
          : errors[0] || "Validated runtime unavailable.",
        featureAvailability: current?.featureAvailability ? { ...current.featureAvailability } : { playerTruth: false, leagueValue: false, espnRank: false, espnAdp: false, opponentIntent: false, roomSurvival: false, manualDraft: true },
      });
    }

    function auditMetadata() {
      return {
        modelState,
        bundleVersion: current?.bundleVersion || null,
        generatedAt: current?.generatedAt || null,
        sourceCommits: current?.sourceCommits?.slice() || [],
        sourceArtifacts: current?.sourceArtifacts?.map((artifact) => ({ ...artifact })) || [],
        approvedExceptions: current?.approvedExceptions?.map((exception) => ({ ...exception })) || [],
        manifestBundleSha256: currentManifest?.outputs?.bundle?.sha256 || null,
        persistencePolicy: current?.compatibility?.persistencePolicy || "bundle-not-loaded",
      };
    }

    return Object.freeze({
      load,
      start,
      health,
      hasValidatedBase: () => validatedBaseAvailable,
      playerTruth: (playerId) => indexes.players.get(Number(playerId)) || null,
      market: (playerId) => indexes.market.get(Number(playerId)) || null,
      leagueValue: (playerId) => indexes.leagueValue.get(Number(playerId)) || null,
      approvedException: (playerId) => approved.get(Number(playerId)) || null,
      bundle: () => current,
      auditMetadata,
      onChange(listener) { listeners.add(listener); return () => listeners.delete(listener); },
      reject: (reason) => setFailure(reason, { rejected: true }),
      fallback: (reason) => setFailure(reason),
    });
  }

  return Object.freeze({ SUPPORTED_SCHEMA_MAJOR, REQUIRED_CAPABILITIES, createAdapter, validateBundle });
});
