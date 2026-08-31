(function attachDraftModel(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.DraftModel = api;
})(typeof window !== "undefined" ? window : globalThis, () => {
  "use strict";

  const CONTRACT_VERSION = "1.0.0";
  const SUPPORTED_SCHEMA_MAJOR = 1;
  const STATUS_LEVELS = new Set(["provisional", "research", "candidate", "production"]);
  const DECISION_TAGS = new Set(["TAKE", "WAIT", "VALUE", "UPSIDE", "POSITION CLIFF", "FADE AT PRICE", "ADVISORY"]);

  function asNumber(value, fallback = null) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function clamp(value, min = 0, max = 1) {
    return Math.max(min, Math.min(max, value));
  }

  function majorVersion(version) {
    const match = String(version || "").match(/^(\d+)\./);
    return match ? Number(match[1]) : null;
  }

  function getPath(object, path) {
    return String(path || "").split(".").filter(Boolean).reduce((value, key) => value == null ? undefined : value[key], object);
  }

  function normalizePackage(packageData) {
    return packageData && typeof packageData === "object" ? packageData : {};
  }

  function validatePackage(packageData, { season, leagueProfileId, knownPlayerIds = [] } = {}) {
    const data = normalizePackage(packageData);
    const errors = [];
    const warnings = [];
    const schemaMajor = majorVersion(data.schemaVersion);
    if (schemaMajor !== SUPPORTED_SCHEMA_MAJOR) errors.push(`Unsupported model schema ${data.schemaVersion || "missing"}; expected ${CONTRACT_VERSION}.`);
    if (asNumber(data.season) !== asNumber(season)) errors.push(`Model season ${data.season || "missing"} does not match ${season}.`);
    if (String(data.leagueProfileId || "") !== String(leagueProfileId || "")) errors.push("Model league profile does not match this draft board.");
    if (!data.metadata || typeof data.metadata !== "object") errors.push("Model metadata is missing.");
    if (!STATUS_LEVELS.has(data.metadata?.status)) warnings.push(`Unknown model status ${data.metadata?.status || "missing"}; treating package as provisional.`);
    if (!Array.isArray(data.players)) errors.push("Model players must be an array.");

    const known = new Set([...knownPlayerIds].map(Number));
    const seen = new Set();
    for (const entry of Array.isArray(data.players) ? data.players : []) {
      const playerId = asNumber(entry?.playerId);
      if (!Number.isInteger(playerId) || playerId <= 0) {
        errors.push("A model player is missing a valid playerId.");
        continue;
      }
      if (seen.has(playerId)) errors.push(`Player ${playerId} appears more than once in the model package.`);
      seen.add(playerId);
      if (known.size && !known.has(playerId)) warnings.push(`Model player ${playerId} is not on the active player board.`);
    }

    const status = STATUS_LEVELS.has(data.metadata?.status) ? data.metadata.status : "provisional";
    const usablePlayers = Array.isArray(data.players) ? data.players.filter((entry) => Number.isInteger(asNumber(entry?.playerId))) : [];
    if (status !== "provisional" && !usablePlayers.length) warnings.push("Research model has no usable player records; provisional calculations remain active.");
    return { ok: errors.length === 0, errors, warnings, status, playerCount: usablePlayers.length };
  }

  function createAdapter({ packageData, players = [], season, leagueProfileId, fallbackVersion = "provisional" }) {
    const knownPlayerIds = players.map((player) => Number(player.id));
    const validation = validatePackage(packageData, { season, leagueProfileId, knownPlayerIds });
    const data = validation.ok ? normalizePackage(packageData) : {};
    const playerIndex = new Map((Array.isArray(data.players) ? data.players : []).map((entry) => [Number(entry.playerId), entry]));
    const coveredKnownPlayers = knownPlayerIds.filter((id) => playerIndex.has(id)).length;
    const coverage = players.length ? coveredKnownPlayers / players.length : 0;
    const declaredStatus = validation.ok ? validation.status : "provisional";
    const metadata = data.metadata || {};
    const expiresAtMs = Date.parse(metadata.expiresAt || "");
    const stale = validation.ok && Number.isFinite(expiresAtMs) && Date.now() > expiresAtMs;
    const mode = validation.ok && !stale && declaredStatus !== "provisional" && coveredKnownPlayers > 0 ? "research" : "fallback";
    const approval = data.decisionPolicy?.approval || {};
    const approvedAtMs = Date.parse(approval.approvedAt || "");
    const decisionPolicyApproved = mode === "research" && declaredStatus === "production" &&
      approval.status === "approved" && approval.calibrated === true &&
      typeof approval.version === "string" && approval.version.trim().length > 0 && Number.isFinite(approvedAtMs);
    const decisionPolicyReason = decisionPolicyApproved
      ? `Calibrated decision policy ${approval.version} approved ${approval.approvedAt}.`
      : !validation.ok
        ? "Model package is invalid or missing."
        : stale
          ? "Model package is expired or stale."
          : declaredStatus !== "production"
            ? `Model status ${declaredStatus} is not approved for calibrated draft calls.`
            : "Calibrated decision-policy approval is missing or incomplete.";
    const policy = {
      takeMaxSurvival: asNumber(data.decisionPolicy?.takeMaxSurvival, 0.24),
      waitMinSurvival: asNumber(data.decisionPolicy?.waitMinSurvival, 0.48),
      valueMinGap: asNumber(data.decisionPolicy?.valueMinGap, 6),
      upsideMinProbability: asNumber(data.decisionPolicy?.upsideMinProbability, 0.24),
      cliffMinDelta: asNumber(data.decisionPolicy?.cliffMinDelta, 4),
      fadeMinReach: asNumber(data.decisionPolicy?.fadeMinReach, 12),
    };

    function entry(playerOrId) {
      const playerId = Number(typeof playerOrId === "object" ? playerOrId?.id : playerOrId);
      return playerIndex.get(playerId) || null;
    }

    function number(playerOrId, path, fallback) {
      const value = asNumber(getPath(entry(playerOrId), path));
      return value == null ? (typeof fallback === "function" ? fallback() : fallback) : value;
    }

    function text(playerOrId, path, fallback) {
      const value = getPath(entry(playerOrId), path);
      return typeof value === "string" && value.trim() ? value : (typeof fallback === "function" ? fallback() : fallback);
    }

    function list(playerOrId, path, fallback = []) {
      const value = getPath(entry(playerOrId), path);
      return Array.isArray(value) ? value.slice() : (typeof fallback === "function" ? fallback() : fallback);
    }

    function market(player, platform, fallback) {
      const marketEntry = getPath(entry(player), `market.${platform}`) || {};
      const price = asNumber(marketEntry.price, asNumber(marketEntry.adp, asNumber(marketEntry.defaultRank, asNumber(marketEntry.order))));
      return {
        price: price == null ? (typeof fallback === "function" ? fallback() : fallback) : price,
        defaultRank: asNumber(marketEntry.defaultRank),
        adp: asNumber(marketEntry.adp),
        order: asNumber(marketEntry.order),
        sigma: asNumber(marketEntry.sigma),
        source: marketEntry.source || null,
      };
    }

    function survivalDetail(player, platform, targetPick, fallback, context = {}) {
      const survivalEntry = getPath(entry(player), `survival.${platform}`) || {};
      const anchors = survivalEntry.anchors;
      let value = null;
      let source = "fallback-heuristic";
      if (anchors && typeof anchors === "object") {
        const exact = asNumber(anchors[String(targetPick)]);
        if (exact != null) {
          value = clamp(exact, 0.01, 0.99);
          source = "model-anchor";
        }
      }
      const center = asNumber(survivalEntry.center);
      const scale = asNumber(survivalEntry.scale);
      if (value == null && center != null && scale != null && scale > 0) {
        const roomAdjustment = asNumber(context.roomAdjustment, 0);
        value = clamp(1 / (1 + Math.exp((Number(targetPick) - center - roomAdjustment) / scale)), 0.01, 0.99);
        source = "model-curve";
      }
      if (value == null) value = clamp(typeof fallback === "function" ? fallback() : asNumber(fallback, 0.5), 0.01, 0.99);
      const calibrationVersion = typeof survivalEntry.calibrationVersion === "string" && survivalEntry.calibrationVersion.trim()
        ? survivalEntry.calibrationVersion.trim()
        : null;
      const calibrated = source !== "fallback-heuristic" && mode === "research" && declaredStatus === "production" && Boolean(calibrationVersion);
      return Object.freeze({
        value,
        source,
        calibrated,
        calibrationVersion,
        qualification: calibrated ? "calibrated" : source === "fallback-heuristic" ? "heuristic" : "uncalibrated-model",
      });
    }

    function survival(player, platform, targetPick, fallback, context = {}) {
      return survivalDetail(player, platform, targetPick, fallback, context).value;
    }

    function tier(player, fallback = {}) {
      const modelEntry = entry(player);
      const tierId = modelEntry?.leagueValue?.tierId || modelEntry?.tier?.id || fallback.id || `${player.pos}-depth`;
      return {
        id: String(tierId),
        label: modelEntry?.leagueValue?.tierLabel || modelEntry?.tier?.label || fallback.label || "Depth",
        rank: asNumber(modelEntry?.leagueValue?.tierRank, asNumber(modelEntry?.tier?.rank, fallback.rank ?? null)),
        value: asNumber(modelEntry?.leagueValue?.tierValue, asNumber(modelEntry?.tier?.value, fallback.value ?? null)),
      };
    }

    function outcome(player, fallback = {}) {
      const modelEntry = entry(player);
      return {
        meanPoints: asNumber(modelEntry?.outcome?.meanPoints, fallback.meanPoints ?? null),
        meanPpg: asNumber(modelEntry?.outcome?.meanPpg, fallback.meanPpg ?? null),
        gamesPlayed: asNumber(modelEntry?.outcome?.gamesPlayed, fallback.gamesPlayed ?? null),
        floorPoints: asNumber(modelEntry?.outcome?.floorPoints, fallback.floorPoints ?? null),
        medianPoints: asNumber(modelEntry?.outcome?.medianPoints, fallback.medianPoints ?? null),
        ceilingPoints: asNumber(modelEntry?.outcome?.ceilingPoints, fallback.ceilingPoints ?? null),
        ceilingProbability: clamp(asNumber(modelEntry?.outcome?.ceilingProbability, fallback.ceilingProbability ?? 0.16)),
        bustProbability: clamp(asNumber(modelEntry?.outcome?.bustProbability, fallback.bustProbability ?? 0.2)),
        eliteProbability: clamp(asNumber(modelEntry?.outcome?.eliteProbability, fallback.eliteProbability ?? 0.1)),
        starterProbability: clamp(asNumber(modelEntry?.outcome?.starterProbability, fallback.starterProbability ?? 0.5)),
      };
    }

    function decisionTag(inputs) {
      if (!decisionPolicyApproved) return "ADVISORY";
      if (DECISION_TAGS.has(inputs?.override)) return inputs.override;
      if (inputs.reach >= policy.fadeMinReach) return "FADE AT PRICE";
      if (inputs.survival <= policy.takeMaxSurvival && inputs.quality) return "TAKE";
      if (inputs.cliff >= policy.cliffMinDelta && inputs.survival < policy.waitMinSurvival) return "POSITION CLIFF";
      if (inputs.valueGap >= policy.valueMinGap) return "VALUE";
      if (inputs.ceilingProbability >= policy.upsideMinProbability && inputs.valueGap >= -3) return "UPSIDE";
      return "WAIT";
    }

    function health() {
      const generatedAt = metadata.generatedAt || null;
      const effectiveAt = metadata.effectiveAt || generatedAt;
      const sourceCount = Array.isArray(metadata.sources) ? metadata.sources.length : 0;
      return {
        contractVersion: CONTRACT_VERSION,
        packageId: data.packageId || "provisional-fallback",
        modelVersion: metadata.modelVersion || fallbackVersion,
        status: declaredStatus,
        mode,
        label: mode === "research" ? (declaredStatus === "production" ? "Research live" : "Research candidate") : stale ? "Research stale" : "Provisional",
        generatedAt,
        effectiveAt,
        coverage,
        coveredPlayers: coveredKnownPlayers,
        totalPlayers: players.length,
        sourceCount,
        valid: validation.ok,
        stale,
        errors: validation.errors.slice(),
        warnings: validation.warnings.slice(),
        decisionPolicyApproved,
        decisionMode: decisionPolicyApproved ? "calibrated" : "advisory",
        decisionPolicyVersion: decisionPolicyApproved ? approval.version : null,
        decisionPolicyReason,
      };
    }

    return Object.freeze({
      contractVersion: CONTRACT_VERSION,
      entry,
      number,
      text,
      list,
      market,
      survival,
      survivalDetail,
      tier,
      outcome,
      decisionTag,
      health,
      policy: Object.freeze(policy),
      validation: Object.freeze({ ...validation, errors: validation.errors.slice(), warnings: validation.warnings.slice() }),
    });
  }

  return Object.freeze({ CONTRACT_VERSION, DECISION_TAGS, createAdapter, validatePackage });
});
