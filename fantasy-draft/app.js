(() => {
  "use strict";

  const TONY_TEAM = 5;
  const TEAM_COUNT = 10;
  const ROUNDS = 16;
  const TOTAL_PICKS = TEAM_COUNT * ROUNDS;
  const TONY_PICKS = [5, 16, 25, 36, 45, 56, 65, 76, 85, 96, 105, 116, 125, 136, 145, 156];
  const TARGETS = { QB: 2, RB: 5, WR: 7, TE: 2 };
  const STORE_KEY = "draft-command-2026-v3";
  const LEGACY_STORE_KEYS = ["draft-command-2026-v2", "draft-command-2026-v1"];
  const SNAPSHOT_KEY = "draft-command-2026-snapshots-v3";
  const LEGACY_SNAPSHOT_KEYS = ["draft-command-2026-snapshots-v2"];
  const SYNC_SETTINGS_KEY = "draft-command-live-sync-v1";
  const SCHEMA_VERSION = 3;
  const AUDIT_SCHEMA_VERSION = "draft-command-audit-v2";
  const APP_RELEASE = "F5D-2026.09.01-final-integration-candidate";
  const MAX_AUDIT_RECORDS = 2500;
  const MAX_RECOVERY_SNAPSHOTS = 12;
  const MODEL_LEAGUE_PROFILE_ID = "espn-keeper-10-ppr-2flex-2026";
  const OPPONENT_SIMULATIONS = window.__DRAFT_COMMAND_TEST__ ? 8 : 300;

  const MANAGERS = [
    null,
    { id: 1, espnTeamId: 10, name: "Justin Gerkin", short: "Gerkin" },
    { id: 2, espnTeamId: 1, name: "Dan Merrick", short: "Dan" },
    { id: 3, espnTeamId: 8, name: "Matt Castleman", short: "Castleman" },
    { id: 4, espnTeamId: 4, name: "Matt Hull", short: "Hull" },
    { id: 5, espnTeamId: 9, name: "Tony Fontana", short: "Tony" },
    { id: 6, espnTeamId: 7, name: "Matt Runge", short: "Runge" },
    { id: 7, espnTeamId: 2, name: "Jon Merrick", short: "Jon" },
    { id: 8, espnTeamId: 5, name: "Matt Sloka", short: "Sloka" },
    { id: 9, espnTeamId: 11, name: "Kyle Cavanaugh", short: "Kyle" },
    { id: 10, espnTeamId: 12, name: "Brenden Lautenbach", short: "Brenden" },
  ];

  const KEEPER_CONFIG = [
    { team: 1, playerId: 68, round: 6 },
    { team: 2, playerId: 24, round: 6 },
    { team: 3, playerId: 45, round: 10 },
    { team: 4, playerId: 50, round: 9 },
    { team: 5, playerId: 90, round: 16 },
    { team: 6, playerId: 30, round: 7 },
    { team: 7, playerId: 47, round: 12 },
    { team: 8, playerId: 52, round: 14 },
    { team: 9, playerId: 26, round: 9 },
    { team: 10, playerId: 33, round: 9 },
  ];

  const state = {
    events: [],
    sourceObservations: [],
    keeperMode: false,
    keeperSeeds: [],
    seedReconciliations: [],
    sessionId: null,
    generation: 1,
    sourceIngestionPaused: false,
    platform: "espn",
    position: "ALL",
    search: "",
    boardSort: { key: "espnPrice", direction: "asc" },
    opponentSort: { key: "nextPick", direction: "asc" },
    visible: 20,
    rosterTeam: TONY_TEAM,
    editingOverall: null,
    resolvingObservationOverall: null,
    resolvingMissingOverall: null,
    auditLog: [],
  };

  const PLAYER_BY_ID = new Map(window.PLAYER_DATA.map((player) => [player.id, player]));
  const normalizePlayerName = (name) => String(name || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\b(jr|sr|ii|iii|iv)\b/g, "")
    .replace(/[^a-z0-9]/g, "");
  const PLAYER_BY_NAME = new Map(window.PLAYER_DATA.map((player) => [normalizePlayerName(player.name), player]));
  const PLAYER_NAME_ALIASES = new Map([
    ["gabe davis", "gabriel davis"],
    ["hollywood brown", "marquise brown"],
    ["tank dell", "nathaniel dell"],
  ].map(([alias, canonical]) => [normalizePlayerName(alias), normalizePlayerName(canonical)]));
  let renderCache = {};
  let persistenceWarning = null;

  const els = Object.fromEntries([
    "roundPick", "overallPick", "clockOwner", "draftProgress", "nextTonyText", "pickMap",
    "decisionWindow", "workspaceTitle", "bestOverallCard", "bestValueCard", "bestFitCard",
    "decisionStrip", "playerSearch", "playerTable", "boardCount", "loadMore", "rosterCount",
    "rosterNeeds", "rosterList", "rosterManager", "rosterManagerName", "historyList", "undoPick",
    "cliffPanel", "platformHeader", "platformHeaderLabel", "platformSortButton", "platformSortIndicator", "leagueValueHeader", "leagueSortButton", "leagueSortIndicator", "toast", "saveStatus", "keeperList", "resetDraft",
    "exportDraft", "importDraft", "importDraftFile", "recoverDraft", "pickDialog", "dialogTitle",
    "dialogCopy", "replacementSearch", "replacementList", "removePick", "rewindPick",
    "modelStatusBadge", "modelVersion", "modelFreshness", "modelCoverage", "modelStatusCopy",
    "modelSourceNote", "snapshotNote", "decisionLenses", "roomRankNote", "boardOrderNote",
    "exportAuditLog", "nextPickHeader", "callHeader", "keeperToggle", "keeperModeNote",
    "draftAlerts", "onClockManagerCard", "opponentIntentStatus", "opponentBoard",
    "opponentBoardStatus", "threatBoard", "threatBoardStatus", "tierSurvival",
    "espnAdpHeader", "takenBeforeTonyHeader", "opponentThreatHeader",
  ].map((id) => [id, document.getElementById(id)]));

  const MODEL = window.DraftModel.createAdapter({
    packageData: window.DRAFT_INTELLIGENCE_PACKAGE,
    players: window.PLAYER_DATA,
    season: 2026,
    leagueProfileId: MODEL_LEAGUE_PROFILE_ID,
    fallbackVersion: "fallback-2026.08.27",
  });

  const RUNTIME = window.DraftRuntimeBundle?.createAdapter({ players: window.PLAYER_DATA }) || null;
  if (RUNTIME && window.DRAFT_RUNTIME_BUNDLE) {
    RUNTIME.load(window.DRAFT_RUNTIME_BUNDLE, { manifest: window.DRAFT_RUNTIME_MANIFEST || null });
  }

  function runtimeReady() { return Boolean(RUNTIME?.hasValidatedBase()); }
  function modelHealth() { return RUNTIME?.health() || MODEL.health(); }

  const OPPONENT_INTENT = window.OpponentIntentModel?.createEngine({
    packageData: window.OPPONENT_INTENT_PACKAGE,
    players: window.PLAYER_DATA,
    managers: MANAGERS,
    season: 2026,
    leagueProfileId: MODEL_LEAGUE_PROFILE_ID,
    teamCount: TEAM_COUNT,
    tonyTeam: TONY_TEAM,
  }) || null;
  let opponentContext = { signature: null, status: "loading", board: null, threat: null, liveState: null, window: null, error: null };
  let opponentSimulationTimer = null;
  let opponentSimulationGeneration = 0;
  let opponentWorker = null;

  function pickLabel(overall) {
    const round = Math.ceil(overall / TEAM_COUNT);
    const inRound = ((overall - 1) % TEAM_COUNT) + 1;
    return `${round}.${String(inRound).padStart(2, "0")}`;
  }

  function pickOwner(overall) {
    const round = Math.ceil(overall / TEAM_COUNT);
    const slot = ((overall - 1) % TEAM_COUNT) + 1;
    return round % 2 ? slot : TEAM_COUNT + 1 - slot;
  }

  function keeperOverall(round, team) {
    return ((round - 1) * TEAM_COUNT) + (round % 2 ? team : TEAM_COUNT + 1 - team);
  }

  const KEEPERS = KEEPER_CONFIG.map((keeper) => ({
    ...keeper,
    overall: keeperOverall(keeper.round, keeper.team),
    source: "keeper",
    timestamp: null,
  }));
  function createSessionId() {
    try { return crypto.randomUUID(); } catch (_) { return `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
  }

  function playerById(id) {
    return PLAYER_BY_ID.get(Number(id));
  }

  function canonicalizeEvents(events) {
    const usedOveralls = new Set();
    const usedPlayers = new Set();
    return (Array.isArray(events) ? events : []).map((event) => ({
      overall: Number(event.overall),
      team: Number(event.team),
      playerId: Number(event.playerId),
      source: event.source || "manual",
      status: event.status || (String(event.source || "").includes("sync") ? "source-confirmed" : "modeled"),
      timestamp: event.timestamp || new Date().toISOString(),
      syncKey: event.syncKey || null,
      externalId: event.externalId == null ? null : String(event.externalId),
      externalName: event.externalName || null,
      manager: event.manager || manager(Number(event.team))?.name || null,
      rosterAssignment: Number(event.rosterAssignment || event.team),
      status: event.status || (event.source === "keeper-seed" ? "keeper-seed" : event.source === "manual" ? "manual" : "source-confirmed"),
    })).filter((event) => {
      if (!Number.isInteger(event.overall) || event.overall < 1 || event.overall > TOTAL_PICKS) return false;
      if (!playerById(event.playerId) || pickOwner(event.overall) !== event.team) return false;
      if (usedOveralls.has(event.overall) || usedPlayers.has(event.playerId)) return false;
      usedOveralls.add(event.overall);
      usedPlayers.add(event.playerId);
      return true;
    }).sort((a, b) => a.overall - b.overall);
  }

  function canonicalizeKeeperSeeds(seeds, active = state.keeperMode) {
    if (!active) return [];
    const configured = new Map(KEEPERS.map((keeper) => [`${keeper.overall}:${keeper.playerId}`, keeper]));
    const usedOveralls = new Set();
    const usedPlayers = new Set();
    return (Array.isArray(seeds) ? seeds : []).map((seed) => ({
      overall: Number(seed.overall),
      team: Number(seed.team),
      playerId: Number(seed.playerId),
      round: Number(seed.round),
      source: "keeper-seed",
      status: seed.status || "seeded",
      timestamp: seed.timestamp || null,
    })).filter((seed) => {
      if (!configured.has(`${seed.overall}:${seed.playerId}`) || seed.team !== pickOwner(seed.overall)) return false;
      if (usedOveralls.has(seed.overall) || usedPlayers.has(seed.playerId)) return false;
      usedOveralls.add(seed.overall);
      usedPlayers.add(seed.playerId);
      return true;
    }).sort((a, b) => a.overall - b.overall);
  }

  function canonicalizeObservations(observations) {
    const byKey = new Map();
    for (const raw of Array.isArray(observations) ? observations : []) {
      const overall = Number(raw?.overall);
      if (!Number.isInteger(overall) || overall < 1 || overall > TOTAL_PICKS) continue;
      const source = raw.source === "sleeper-sync" ? "sleeper-sync" : raw.source === "manual" ? "manual" : "espn-sync";
      const syncKey = String(raw.syncKey || source);
      const observation = {
        observationId: raw.observationId || `${state.sessionId || "session"}:${syncKey}:${overall}`,
        overall,
        round: Math.ceil(overall / TEAM_COUNT),
        roundPick: ((overall - 1) % TEAM_COUNT) + 1,
        team: pickOwner(overall),
        manager: raw.manager || manager(pickOwner(overall))?.name || null,
        sourceTeam: raw.sourceTeam || raw.espnTeam || null,
        sourceManager: raw.sourceManager || raw.espnManager || null,
        source,
        syncKey,
        sourceUrl: raw.sourceUrl || raw.espnUrl || null,
        futureKeeperHint: raw.futureKeeperHint === true,
        externalId: raw.externalId == null ? null : String(raw.externalId),
        externalName: raw.externalName || raw.playerName || null,
        rawPlayerName: raw.rawPlayerName || raw.externalName || raw.playerName || null,
        playerId: playerById(raw.playerId) ? Number(raw.playerId) : null,
        manualPlayerId: playerById(raw.manualPlayerId) ? Number(raw.manualPlayerId) : null,
        status: raw.status || (raw.playerId ? "resolved" : "unresolved"),
        reasonCode: raw.reasonCode || null,
        reason: raw.reason || null,
        resolutionStatus: raw.resolutionStatus || raw.status || (raw.playerId ? "resolved" : "unresolved"),
        unresolvedReasonCode: raw.unresolvedReasonCode || raw.reasonCode || null,
        firstObservedAt: raw.firstObservedAt || raw.timestamp || new Date().toISOString(),
        lastObservedAt: raw.lastObservedAt || raw.timestamp || new Date().toISOString(),
        generation: Number(raw.generation || state.generation || 1),
      };
      byKey.set(`${syncKey}:${overall}`, observation);
    }
    return [...byKey.values()].sort((a, b) => a.overall - b.overall);
  }

  function canonicalizeAuditLog(records) {
    return (Array.isArray(records) ? records : []).filter((record) => record && typeof record === "object" && record.recordedAt)
      .map((record) => structuredClone(record)).slice(-MAX_AUDIT_RECORDS);
  }

  function statePayload() {
    return {
      schemaVersion: SCHEMA_VERSION,
      league: "Tony 2026 ESPN keeper league",
      savedAt: new Date().toISOString(),
      platform: state.platform,
      rosterTeam: state.rosterTeam,
      events: state.events,
      modeledEvents: state.events,
      sourceObservations: state.sourceObservations,
      keeperMode: state.keeperMode,
      keeperSeeds: state.keeperSeeds,
      seedReconciliations: state.seedReconciliations,
      sessionId: state.sessionId,
      generation: state.generation,
      sourceIngestionPaused: state.sourceIngestionPaused,
      // Detailed audits remain in memory for export and are deterministically
      // rebuilt from canonical events after refresh. This keeps browser storage
      // bounded through a complete 160-pick draft.
      auditLog: [],
      auditRebuildRequired: state.auditLog.length > 0,
    };
  }

  function readSnapshots() {
    try {
      const snapshots = JSON.parse(localStorage.getItem(SNAPSHOT_KEY));
      return Array.isArray(snapshots) ? snapshots : [];
    } catch (_) {
      return [];
    }
  }

  function isStorageQuotaError(error) {
    return error?.name === "QuotaExceededError" || error?.name === "NS_ERROR_DOM_QUOTA_REACHED" || error?.code === 22 || error?.code === 1014;
  }

  function recoverySnapshotPayload(payload) {
    const { auditLog: _auditLog, ...snapshot } = payload;
    return { ...snapshot, recoverySnapshot: true };
  }

  function clearRecoveryStorage() {
    for (const key of [SNAPSHOT_KEY, ...LEGACY_SNAPSHOT_KEYS]) {
      try { localStorage.removeItem(key); } catch (_) { /* active in-memory draft remains usable */ }
    }
  }

  function writeActiveState(payload) {
    const serialized = JSON.stringify(payload);
    try {
      localStorage.setItem(STORE_KEY, serialized);
      persistenceWarning = null;
      return true;
    } catch (error) {
      if (!isStorageQuotaError(error)) {
        persistenceWarning = "Live in memory · export backup";
        return false;
      }
    }

    clearRecoveryStorage();
    try {
      localStorage.setItem(STORE_KEY, serialized);
      persistenceWarning = "Saved · old recovery history cleared";
      return true;
    } catch (error) {
      if (!isStorageQuotaError(error)) {
        persistenceWarning = "Live in memory · export backup";
        return false;
      }
    }

    // Preserve the active board and source cursor even if the detailed audit trail
    // outgrows browser storage. The in-memory audit remains exportable, and it is
    // deterministically rebuilt from persisted events after a refresh.
    const compactPayload = { ...payload, auditLog: [], auditRebuildRequired: true };
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(compactPayload));
      persistenceWarning = "Saved · audit retained in memory";
      return true;
    } catch (_) {
      persistenceWarning = "Live in memory · export backup";
      return false;
    }
  }

  function writeRecoverySnapshots(snapshots) {
    const candidates = [
      snapshots.slice(-MAX_RECOVERY_SNAPSHOTS),
      snapshots.slice(-4),
      snapshots.slice(-1),
    ];
    for (const candidate of candidates) {
      try {
        localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(candidate));
        return true;
      } catch (error) {
        if (!isStorageQuotaError(error)) return false;
      }
    }
    try { localStorage.removeItem(SNAPSHOT_KEY); } catch (_) { /* active state is still authoritative */ }
    persistenceWarning = persistenceWarning || "Saved · recovery history unavailable";
    return false;
  }

  function updateSaveStatus(savedAt) {
    if (!els.saveStatus) return;
    if (persistenceWarning) {
      els.saveStatus.textContent = persistenceWarning;
      els.saveStatus.title = "The active draft remains usable. Export a backup and audit log when practical.";
      return;
    }
    const time = new Date(savedAt);
    els.saveStatus.textContent = Number.isNaN(time.getTime()) ? "Recovery ready" : `Saved ${time.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
    els.saveStatus.title = "";
  }

  function saveState({ snapshot = true } = {}) {
    const payload = statePayload();
    writeActiveState(payload);
    if (snapshot) {
      const storedSnapshots = readSnapshots();
      const snapshots = storedSnapshots.map(recoverySnapshotPayload);
      const fingerprint = JSON.stringify([payload.events, payload.sourceObservations, payload.keeperSeeds]);
      const last = snapshots.at(-1);
      const lastFingerprint = last ? JSON.stringify([last.events || [], last.sourceObservations || [], last.keeperSeeds || []]) : null;
      if (fingerprint !== lastFingerprint) {
        snapshots.push(recoverySnapshotPayload(payload));
      }
      const needsCompaction = storedSnapshots.some((stored) => Array.isArray(stored?.auditLog) && stored.auditLog.length);
      if (fingerprint !== lastFingerprint || needsCompaction) writeRecoverySnapshots(snapshots);
    }
    updateSaveStatus(payload.savedAt);
  }

  function applyPayload(payload) {
    state.events = canonicalizeEvents(payload?.modeledEvents || payload?.events || payload?.picks || []);
    state.sessionId = typeof payload?.sessionId === "string" && payload.sessionId ? payload.sessionId : createSessionId();
    state.generation = Math.max(1, Number(payload?.generation) || 1);
    state.sourceIngestionPaused = payload?.sourceIngestionPaused === true;
    state.keeperMode = payload?.schemaVersion >= 3 && payload?.keeperMode === true;
    state.keeperSeeds = canonicalizeKeeperSeeds(payload?.keeperSeeds || (state.keeperMode ? KEEPERS : []), state.keeperMode);
    state.seedReconciliations = (Array.isArray(payload?.seedReconciliations) ? payload.seedReconciliations : []).filter((item) => item && item.action).map((item) => ({ ...item }));
    state.sourceObservations = canonicalizeObservations(payload?.sourceObservations || state.events.map((event) => ({
      ...event,
      externalName: playerById(event.playerId)?.name,
      status: "resolved",
    })));
    state.auditLog = canonicalizeAuditLog(payload?.auditLog);
    state.platform = payload?.platform === "sleeper" ? "sleeper" : "espn";
    const rosterTeam = Number(payload?.rosterTeam);
    state.rosterTeam = rosterTeam >= 1 && rosterTeam <= TEAM_COUNT ? rosterTeam : TONY_TEAM;
    if (!state.auditLog.length && state.events.length) state.auditLog = rebuildAuditLog(state.events);
  }

  function migrateLegacyEvents(picks) {
    const events = [];
    const usedPlayers = new Set();
    let overall = 1;
    for (const oldPick of Array.isArray(picks) ? picks : []) {
      const playerId = Number(oldPick.playerId);
      if (!playerById(playerId) || usedPlayers.has(playerId)) continue;
      if (overall > TOTAL_PICKS) break;
      events.push({ overall, team: pickOwner(overall), playerId, source: "legacy-migration", timestamp: new Date().toISOString() });
      usedPlayers.add(playerId);
      overall += 1;
    }
    return events;
  }

  function loadState() {
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(STORE_KEY));
    } catch (_) { /* try recovery history below */ }
    if (!saved) {
      try {
        for (const key of LEGACY_STORE_KEYS) {
          const legacy = JSON.parse(localStorage.getItem(key));
          if (legacy) { saved = legacy; break; }
        }
      } catch (_) { /* ignore malformed legacy state */ }
    }
    if (!saved) saved = readSnapshots().at(-1) || null;
    if (saved) {
      if (!saved.schemaVersion && Array.isArray(saved.picks)) {
        applyPayload({ ...saved, events: migrateLegacyEvents(saved.picks), picks: undefined });
      } else {
        applyPayload(saved);
      }
    }
    if (!state.sessionId) state.sessionId = createSessionId();
    saveState({ snapshot: false });
  }

  function allEvents() {
    if (!renderCache.allEvents) renderCache.allEvents = [...state.keeperSeeds, ...state.events].sort((a, b) => a.overall - b.overall);
    return renderCache.allEvents;
  }

  function eventAt(overall) {
    if (!renderCache.eventsByOverall) renderCache.eventsByOverall = new Map(allEvents().map((event) => [event.overall, event]));
    return renderCache.eventsByOverall.get(overall) || null;
  }

  function currentPick() {
    if (renderCache.currentPick) return renderCache.currentPick;
    for (let overall = 1; overall <= TOTAL_PICKS; overall += 1) {
      const observed = state.sourceObservations.some((observation) => observation.overall === overall);
      const seeded = state.keeperSeeds.some((seed) => seed.overall === overall);
      if (!observed && !seeded) {
        renderCache.currentPick = overall;
        return overall;
      }
    }
    renderCache.currentPick = TOTAL_PICKS + 1;
    return renderCache.currentPick;
  }

  function nextTonyPick(from = currentPick()) {
    return TONY_PICKS.find((pick) => pick >= from && !eventAt(pick)) || null;
  }

  function followingTonyPick(from) {
    return TONY_PICKS.find((pick) => pick > from && !eventAt(pick)) || null;
  }

  function draftedIds() {
    return new Set(allEvents().map((event) => event.playerId));
  }

  function resolveExternalPlayer(rawPick) {
    const externalName = rawPick.playerName || rawPick.name || [rawPick.firstName, rawPick.lastName].filter(Boolean).join(" ");
    const normalized = normalizePlayerName(externalName);
    return PLAYER_BY_NAME.get(normalized) || PLAYER_BY_NAME.get(PLAYER_NAME_ALIASES.get(normalized)) || null;
  }

  function sourceLabel(event) {
    if (event.source === "keeper-seed" || event.source === "keeper") return "KEEPER SEED";
    if (event.source === "espn-sync") return "ESPN SYNC";
    if (event.source === "sleeper-sync") return "SLEEPER SYNC";
    if (event.source === "manual-correction") return "CORRECTED";
    return "MANUAL";
  }

  function isManualEvent(event) {
    return Boolean(event && ["manual", "manual-recovery", "manual-resolution", "manual-correction"].includes(event.source));
  }

  function missingPickMessage(overall) {
    const round = Math.ceil(overall / TEAM_COUNT);
    const roundPick = ((overall - 1) % TEAM_COUNT) + 1;
    return `Need pick for ${manager(pickOwner(overall)).name} — Round ${round}, Pick ${roundPick}`;
  }

  function snapshotDiagnostics(snapshot, result) {
    const observed = state.sourceObservations.map((item) => item.overall);
    const progressionObserved = state.sourceObservations.filter((item) => !item.futureKeeperHint).map((item) => item.overall);
    const maxObserved = progressionObserved.length ? Math.max(...progressionObserved) : 0;
    const maxSourceObserved = observed.length ? Math.max(...observed) : 0;
    const observedSet = new Set(observed);
    const gaps = [];
    for (let overall = 1; overall <= maxObserved; overall += 1) {
      if (!observedSet.has(overall) && !state.keeperSeeds.some((seed) => seed.overall === overall)) gaps.push(overall);
    }
    return {
      appRelease: APP_RELEASE,
      snapshotTimestamp: snapshot?.timestamp || new Date().toISOString(),
      sourceUrl: snapshot?.sourceUrl || snapshot?.espnUrl || null,
      sessionId: state.sessionId,
      generation: state.generation,
      syncKey: result.syncKey,
      bridgeVersion: snapshot?.bridgeVersion || null,
      rawSourcePickCount: snapshot?.picks?.length || 0,
      sourceObservedOveralls: observed,
      sourceObservedCount: observed.length,
      modeledEventCount: state.events.length,
      activeKeeperSeedCount: state.keeperSeeds.length,
      maxObserved,
      maxSourceObserved,
      displayedNextPick: currentPick(),
      resolvedCount: state.sourceObservations.filter((item) => item.status === "resolved").length,
      unresolvedCount: state.sourceObservations.filter((item) => item.status !== "resolved").length,
      unresolvedOveralls: state.sourceObservations.filter((item) => item.status !== "resolved").map((item) => item.overall),
      unresolvedReasonCodes: [...new Set(state.sourceObservations.filter((item) => item.status !== "resolved").map((item) => item.reasonCode || "RESOLUTION_FAILED"))],
      missingSourceSlots: gaps,
      seedReconciliationEvents: result.reconciliation,
      cursorIntegrityWarning: currentPick() <= maxObserved ? `Displayed cursor ${currentPick()} is behind source-observed pick ${maxObserved}.` : null,
    };
  }

  function recordSystemAudit(action, details = {}) {
    appendAuditRecord(action, null, state.events, { source: details.source || "system", details: { appRelease: APP_RELEASE, sessionId: state.sessionId, generation: state.generation, ...details } });
    saveState({ snapshot: false });
  }

  function rejectSnapshot(result, action, details = {}) {
    recordSystemAudit(action, { source: result.source, syncKey: result.syncKey, ...details });
    return result;
  }

  function ingestSnapshot(snapshot) {
    const source = snapshot?.source === "sleeper" ? "sleeper-sync" : "espn-sync";
    const syncKey = String(snapshot?.syncKey || source);
    const teamCount = Number(snapshot?.teamCount || TEAM_COUNT);
    const rounds = Number(snapshot?.rounds || ROUNDS);
    const result = { ok: true, added: 0, updated: 0, removed: 0, matched: 0, observed: 0, unresolved: [], conflicts: [], reconciliation: [], source, syncKey };

    if (teamCount !== TEAM_COUNT || rounds !== ROUNDS) {
      return rejectSnapshot({ ...result, ok: false, code: "FORMAT_MISMATCH", message: `This board is configured for ${TEAM_COUNT} teams and ${ROUNDS} rounds; the connected draft reports ${teamCount} teams and ${rounds} rounds.` }, "source-rejected-format", { teamCount, rounds });
    }
    if (!Array.isArray(snapshot?.picks)) return rejectSnapshot({ ...result, ok: false, code: "INVALID_SNAPSHOT", message: "The connected source did not provide a valid pick list." }, "source-rejected-invalid");
    if (source === "espn-sync" && snapshot?.generation != null && Number(snapshot.generation) !== state.generation) {
      return rejectSnapshot({ ...result, ok: false, code: "STALE_GENERATION", message: "A stale ESPN bridge snapshot was rejected after reset." }, "bridge-stale-rejected", { receivedGeneration: Number(snapshot.generation), bridgeVersion: snapshot?.bridgeVersion || null });
    }
    if (source === "espn-sync" && snapshot?.sessionId && snapshot.sessionId !== state.sessionId) {
      return rejectSnapshot({ ...result, ok: false, code: "STALE_SESSION", message: "An ESPN snapshot from the prior draft session was rejected." }, "bridge-stale-rejected", { receivedSessionId: snapshot.sessionId, bridgeVersion: snapshot?.bridgeVersion || null });
    }
    if (state.sourceIngestionPaused) {
      return rejectSnapshot({ ...result, ok: false, code: "SOURCE_PAUSED", message: "Source ingestion is paused after Hard Reset Draft. Reconnect explicitly to continue." }, "source-rejected-paused", { bridgeVersion: snapshot?.bridgeVersion || null });
    }

    const previousEvents = state.events.map((event) => ({ ...event }));
    const incomingOveralls = new Set();
    const working = state.events.map((event) => ({ ...event }));
    const workingSeeds = state.keeperSeeds.map((seed) => ({ ...seed }));
    const incomingPlayerIds = new Set();
    const byOverall = new Map(working.map((event) => [event.overall, event]));
    const playerOverall = new Map([...workingSeeds, ...working].map((event) => [event.playerId, event.overall]));
    const observationByKey = new Map(state.sourceObservations.map((observation) => [`${observation.syncKey}:${observation.overall}`, { ...observation }]));
    const sortedPicks = snapshot.picks.slice().sort((a, b) => Number(a.overall) - Number(b.overall));

    for (const rawPick of sortedPicks) {
      const overall = Number(rawPick.overall);
      const externalName = rawPick.playerName || rawPick.name || [rawPick.firstName, rawPick.lastName].filter(Boolean).join(" ") || "Unknown player";
      if (!Number.isInteger(overall) || overall < 1 || overall > TOTAL_PICKS) {
        result.unresolved.push({ overall: rawPick.overall, playerName: externalName, reason: "invalid pick number", code: "INVALID_PICK" });
        continue;
      }
      if (incomingOveralls.has(overall)) {
        result.conflicts.push({ overall, playerName: externalName, reason: "duplicate pick number in source", code: "DUPLICATE_SOURCE_PICK" });
        continue;
      }
      incomingOveralls.add(overall);

      const key = `${syncKey}:${overall}`;
      const prior = observationByKey.get(key);
      const externalId = rawPick.externalId == null ? null : String(rawPick.externalId);
      const sameIdentity = prior && prior.externalName === externalName && prior.externalId === externalId;
      const manuallyMapped = sameIdentity ? playerById(prior.manualPlayerId) : null;
      const player = manuallyMapped || resolveExternalPlayer(rawPick);
      const observedAt = snapshot.timestamp || new Date().toISOString();
      const observation = {
        observationId: prior?.observationId || `${state.sessionId}:${syncKey}:${overall}`,
        overall,
        round: Math.ceil(overall / TEAM_COUNT),
        roundPick: ((overall - 1) % TEAM_COUNT) + 1,
        team: pickOwner(overall),
        manager: manager(pickOwner(overall)).name,
        sourceTeam: rawPick.teamName || rawPick.espnTeam || rawPick.team || null,
        sourceManager: rawPick.managerName || rawPick.espnManager || rawPick.manager || null,
        source,
        syncKey,
        sourceUrl: snapshot.sourceUrl || snapshot.espnUrl || null,
        futureKeeperHint: rawPick.isKeeper === true || KEEPERS.some((keeper) => keeper.overall === overall && keeper.playerId === player?.id),
        externalId,
        externalName,
        rawPlayerName: externalName,
        playerId: player?.id || null,
        manualPlayerId: manuallyMapped?.id || null,
        status: player ? "resolved" : "unresolved",
        reasonCode: player ? null : "PLAYER_NOT_ON_BOARD",
        reason: player ? null : "player is not on the current board",
        resolutionStatus: player ? "resolved" : "unresolved",
        unresolvedReasonCode: player ? null : "PLAYER_NOT_ON_BOARD",
        firstObservedAt: prior?.firstObservedAt || observedAt,
        lastObservedAt: observedAt,
        generation: state.generation,
      };
      observationByKey.set(key, observation);
      if (!prior) result.observed += 1;
      if (!prior || !sameIdentity) {
        appendAuditRecord("source-observed", { overall, team: pickOwner(overall), playerId: player?.id || null, externalName, source, syncKey, timestamp: observedAt }, working.filter((event) => event.overall < overall), {
          platform: source === "sleeper-sync" ? "sleeper" : "espn",
          details: { observationId: observation.observationId, resolutionStatus: observation.status },
        });
      }

      if (!player) {
        const seedAtIndex = workingSeeds.findIndex((seed) => seed.overall === overall);
        if (seedAtIndex >= 0) {
          const [seedAt] = workingSeeds.splice(seedAtIndex, 1);
          playerOverall.delete(seedAt.playerId);
          result.reconciliation.push({ action: "seed-overridden-unresolved", overall, seededPlayerId: seedAt.playerId, externalName });
        }
        const existing = byOverall.get(overall);
        if (existing?.syncKey === syncKey) {
          working.splice(working.indexOf(existing), 1);
          byOverall.delete(overall);
          playerOverall.delete(existing.playerId);
          result.removed += 1;
        }
        result.unresolved.push({ overall, playerName: externalName, reason: "player is not on the current board — map this observation manually", code: "PLAYER_NOT_ON_BOARD", message: missingPickMessage(overall) });
        continue;
      }

      if (incomingPlayerIds.has(player.id)) {
        observation.status = "conflict";
        observation.resolutionStatus = "conflict";
        observation.reasonCode = "DUPLICATE_SOURCE_PLAYER";
        observation.unresolvedReasonCode = "DUPLICATE_SOURCE_PLAYER";
        observation.reason = "player appears twice in the source snapshot";
        const seedAtIndex = workingSeeds.findIndex((seed) => seed.overall === overall);
        if (seedAtIndex >= 0) {
          const [seedAt] = workingSeeds.splice(seedAtIndex, 1);
          playerOverall.delete(seedAt.playerId);
          result.reconciliation.push({ action: "seed-overridden-duplicate", overall, seededPlayerId: seedAt.playerId, sourcePlayerId: player.id });
        }
        const existing = byOverall.get(overall);
        if (existing?.syncKey === syncKey) {
          working.splice(working.indexOf(existing), 1);
          byOverall.delete(overall);
          playerOverall.delete(existing.playerId);
          result.removed += 1;
        }
        result.conflicts.push({ overall, playerName: externalName, reason: observation.reason, code: observation.reasonCode, message: missingPickMessage(overall) });
        continue;
      }
      incomingPlayerIds.add(player.id);

      const seedAtIndex = workingSeeds.findIndex((seed) => seed.overall === overall);
      const seedAt = workingSeeds[seedAtIndex];
      if (seedAt?.playerId === player.id) {
        workingSeeds.splice(seedAtIndex, 1);
        playerOverall.delete(player.id);
        const existing = byOverall.get(overall);
        if (existing && existing.playerId !== player.id) {
          working.splice(working.indexOf(existing), 1);
          playerOverall.delete(existing.playerId);
          byOverall.delete(overall);
        }
        const confirmedEvent = existing?.playerId === player.id ? existing : {
          overall,
          team: pickOwner(overall),
          playerId: player.id,
          source,
          syncKey,
          externalId,
          externalName,
          timestamp: observedAt,
        };
        confirmedEvent.source = source;
        confirmedEvent.status = "source-confirmed";
        confirmedEvent.syncKey = syncKey;
        confirmedEvent.externalId = externalId;
        confirmedEvent.externalName = externalName;
        confirmedEvent.timestamp = observedAt;
        if (!working.includes(confirmedEvent)) working.push(confirmedEvent);
        byOverall.set(overall, confirmedEvent);
        playerOverall.set(player.id, overall);
        result.matched += 1;
        result.reconciliation.push({ action: "seed-confirmed", overall, playerId: player.id });
        continue;
      }
      if (seedAt) {
        workingSeeds.splice(seedAtIndex, 1);
        playerOverall.delete(seedAt.playerId);
        result.reconciliation.push({ action: "seed-overridden", overall, seededPlayerId: seedAt.playerId, sourcePlayerId: player.id });
      }
      const seedForPlayerIndex = workingSeeds.findIndex((seed) => seed.playerId === player.id);
      if (seedForPlayerIndex >= 0) {
        const moved = workingSeeds[seedForPlayerIndex];
        workingSeeds.splice(seedForPlayerIndex, 1);
        playerOverall.delete(player.id);
        result.reconciliation.push({ action: "seed-moved", fromOverall: moved.overall, toOverall: overall, playerId: player.id });
      }

      const existing = byOverall.get(overall);
      if (existing) {
        if (existing.playerId === player.id) {
          if (existing.source !== source || existing.syncKey !== syncKey) {
            const priorSource = existing.source;
            existing.source = source;
            existing.status = "source-confirmed";
            existing.syncKey = syncKey;
            existing.externalId = externalId;
            existing.externalName = externalName;
            existing.timestamp = observedAt;
            result.updated += 1;
            result.reconciliation.push({ action: "manual-recovery-source-confirmed", overall, playerId: player.id, priorSource });
          }
          result.matched += 1;
          continue;
        }
        const usedAt = playerOverall.get(player.id);
        if (usedAt && usedAt !== overall) {
          const duplicate = byOverall.get(usedAt);
          if (duplicate) {
            working.splice(working.indexOf(duplicate), 1);
            byOverall.delete(usedAt);
            result.reconciliation.push({ action: "source-player-moved", fromOverall: usedAt, toOverall: overall, playerId: player.id });
          }
        }
        playerOverall.delete(existing.playerId);
        existing.playerId = player.id;
        existing.source = source;
        existing.status = "source-confirmed";
        existing.syncKey = syncKey;
        existing.externalId = externalId;
        existing.externalName = externalName;
        existing.timestamp = observedAt;
        playerOverall.set(player.id, overall);
        result.updated += 1;
        continue;
      }

      const usedAt = playerOverall.get(player.id);
      if (usedAt) {
        const duplicate = byOverall.get(usedAt);
        if (duplicate) {
          working.splice(working.indexOf(duplicate), 1);
          byOverall.delete(usedAt);
          result.reconciliation.push({ action: "source-player-moved", fromOverall: usedAt, toOverall: overall, playerId: player.id });
        }
      }
      const draftEvent = { overall, team: pickOwner(overall), playerId: player.id, source, status: "source-confirmed", syncKey, externalId, externalName, timestamp: observedAt };
      working.push(draftEvent);
      byOverall.set(overall, draftEvent);
      playerOverall.set(player.id, overall);
      result.added += 1;
    }

    if (snapshot.authoritative) {
      const completeThrough = Number(snapshot.completeThrough ?? Math.max(0, ...incomingOveralls));
      for (let index = working.length - 1; index >= 0; index -= 1) {
        const event = working[index];
        if (event.syncKey === syncKey && event.overall <= completeThrough && !incomingOveralls.has(event.overall)) {
          working.splice(index, 1);
          result.removed += 1;
        }
      }
      for (const [key, observation] of observationByKey) {
        if (observation.syncKey === syncKey && observation.overall <= completeThrough && !incomingOveralls.has(observation.overall)) observationByKey.delete(key);
      }
    }

    const finalEvents = canonicalizeEvents(working);
    const previousByOverall = new Map(previousEvents.map((event) => [event.overall, event]));
    const finalByOverall = new Map(finalEvents.map((event) => [event.overall, event]));
    state.events = finalEvents;
    state.keeperSeeds = canonicalizeKeeperSeeds(workingSeeds, state.keeperMode);
    state.sourceObservations = canonicalizeObservations([...observationByKey.values()]);
    const reconciledAt = snapshot.timestamp || new Date().toISOString();
    state.seedReconciliations = [...state.seedReconciliations, ...result.reconciliation.map((item) => ({ ...item, syncKey, timestamp: reconciledAt }))].slice(-100);
    renderCache = {};
    for (const event of finalEvents) {
      const previous = previousByOverall.get(event.overall);
      if (!previous || previous.playerId !== event.playerId || previous.source !== event.source || previous.syncKey !== event.syncKey) appendAuditRecord(previous ? "pick-updated" : "pick-recorded", event, finalEvents.filter((item) => item.overall < event.overall), {
        platform: source === "sleeper-sync" ? "sleeper" : "espn",
        details: previous ? { previousPlayerId: previous.playerId, previousSource: previous.source, syncKey } : { syncKey },
      });
    }
    for (const event of previousEvents) {
      if (!finalByOverall.has(event.overall)) appendAuditRecord("pick-removed", event, previousEvents.filter((item) => item.overall < event.overall), { details: { syncKey, reason: "source-reconciliation" } });
    }
    for (const reconciliation of result.reconciliation) {
      appendAuditRecord(`keeper-${reconciliation.action}`, null, state.events, { source, details: { syncKey, ...reconciliation } });
    }
    appendAuditRecord("source-snapshot", null, state.events, { source, platform: source === "sleeper-sync" ? "sleeper" : "espn", details: snapshotDiagnostics(snapshot, result) });
    state.visible = 20;
    saveState();
    render();
    if (result.observed || result.added || result.updated) showToast(`${result.observed} new source observation${result.observed === 1 ? "" : "s"}`);
    return result;
  }

  function fallbackPrice(player, platform = state.platform) { return player[platform] ?? player.market ?? player.adp; }
  function price(player, platform = state.platform) {
    if (runtimeReady() && platform === "espn") return RUNTIME.market(player.id)?.defaultRank ?? null;
    return MODEL.market(player, platform, () => fallbackPrice(player, platform)).price;
  }
  function roomOrder(player, platform = state.platform) {
    const raw = price(player, platform);
    if (raw == null || raw === "") return Number.POSITIVE_INFINITY;
    const value = Number(raw);
    return Number.isFinite(value) ? value : Number.POSITIVE_INFINITY;
  }
  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
  function fixed(value, digits = 1) { return Number.isFinite(value) ? Number(value).toFixed(digits) : "—"; }
  function manager(team) { return MANAGERS[Number(team)]; }

  function teamRoster(team) {
    renderCache.teamRosters ||= new Map();
    const teamId = Number(team);
    if (!renderCache.teamRosters.has(teamId)) {
      renderCache.teamRosters.set(teamId, allEvents().filter((event) => event.team === teamId).map((event) => ({ event, player: playerById(event.playerId) })).filter((entry) => entry.player));
    }
    return renderCache.teamRosters.get(teamId);
  }

  function rosterCounts(team = TONY_TEAM) {
    renderCache.rosterCounts ||= new Map();
    const teamId = Number(team);
    if (!renderCache.rosterCounts.has(teamId)) {
      renderCache.rosterCounts.set(teamId, teamRoster(teamId).reduce((counts, entry) => {
        counts[entry.player.pos] = (counts[entry.player.pos] || 0) + 1;
        return counts;
      }, { QB: 0, RB: 0, WR: 0, TE: 0 }));
    }
    return renderCache.rosterCounts.get(teamId);
  }

  function needBonus(player) {
    const counts = rosterCounts(TONY_TEAM);
    const target = TARGETS[player.pos];
    const deficit = Math.max(0, target - counts[player.pos]);
    const round = Math.ceil((nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS)) / TEAM_COUNT);
    let bonus = deficit * 0.65;
    if (player.pos === "QB" && counts.QB === 0 && round >= 7) bonus += 4.5;
    if (player.pos === "TE" && counts.TE === 0 && round >= 6) bonus += 3;
    if ((player.pos === "RB" || player.pos === "WR") && counts[player.pos] < 2) bonus += 2.5;
    if (counts[player.pos] >= target) bonus -= 7;
    return bonus;
  }

  function positionAdjustment(player) {
    if (player.pos === "WR") return 3.2;
    if (player.pos === "RB") return 2.2;
    if (player.pos === "TE") return player.ecr <= 45 ? 3.4 : 0.4;
    if (player.pos === "QB") return player.ecr <= 30 ? -2.5 : -5.5;
    return 0;
  }

  function fallbackLeagueBase(player) {
    const base = 102 - player.ecr * 0.48;
    const priceSignal = ((player.market || player.adp) - player.ecr) * 0.08;
    return base + positionAdjustment(player) + priceSignal;
  }

  function leagueBase(player) {
    if (runtimeReady()) return RUNTIME.leagueValue(player.id)?.leagueValueScore ?? null;
    return MODEL.number(player, "leagueValue.score", () => fallbackLeagueBase(player));
  }

  function leagueScore(player) {
    return leagueBase(player);
  }

  function fairPick(player) {
    if (runtimeReady()) return RUNTIME.leagueValue(player.id)?.leagueValueRank ?? null;
    return MODEL.number(player, "leagueValue.fairPick", player.ecr);
  }

  function valueGap(player) {
    const marketRank = price(player);
    const valueRank = fairPick(player);
    return Number.isFinite(marketRank) && Number.isFinite(valueRank) ? marketRank - valueRank : null;
  }

  function outcome(player) {
    if (runtimeReady()) {
      const record = RUNTIME.playerTruth(player.id);
      const values = record?.outcome || {};
      return {
        ceilingProbability: values.ceilingProbability ?? null,
        bustProbability: values.bustProbability ?? null,
        eliteProbability: values.eliteProbability ?? null,
        starterProbability: values.starterProbability ?? null,
        p10: values.p10 ?? null,
        p50: values.p50 ?? null,
        p90: values.p90 ?? null,
        projectedFullPprPoints: values.projectedFullPprPoints ?? null,
        projectedPpg: values.projectedPpg ?? null,
        expectedGames: values.expectedGames ?? null,
      };
    }
    const strength = clamp(1 - ((player.ecr || 200) - 1) / 200, 0, 1);
    return MODEL.outcome(player, {
      ceilingProbability: clamp(0.10 + strength * 0.21, 0.1, 0.31),
      bustProbability: clamp(0.29 - strength * 0.15 + ((player.landmine || 5.5) - 5.5) * 0.02, 0.1, 0.36),
      eliteProbability: clamp(0.04 + strength * 0.19, 0.04, 0.23),
      starterProbability: clamp(0.34 + strength * 0.48, 0.34, 0.82),
    });
  }

  function confidence(player) {
    if (runtimeReady()) return RUNTIME.leagueValue(player.id)?.confidence ?? RUNTIME.playerTruth(player.id)?.modelConfidence ?? null;
    return MODEL.number(player, "decision.confidence", 0.45);
  }

  function availablePlayers() {
    if (!renderCache.available) {
      const drafted = draftedIds();
      renderCache.available = window.PLAYER_DATA.filter((player) => !drafted.has(player.id));
    }
    return renderCache.available;
  }

  function opponentKeeperSeeds() {
    return KEEPERS.filter((keeper) => !state.events.some((event) => event.overall === keeper.overall || event.playerId === keeper.playerId))
      .map((keeper) => ({ ...keeper, source: "keeper-template" }));
  }

  function opponentLiveState(beforeOverall = currentPick()) {
    if (!OPPONENT_INTENT) return null;
    return OPPONENT_INTENT.createLiveState({
      events: state.events,
      keeperSeeds: opponentKeeperSeeds(),
      beforeOverall,
    });
  }

  function opponentThreatWindow() {
    const current = currentPick();
    if (current > TOTAL_PICKS) return { start: TOTAL_PICKS + 1, nextTony: null, onClock: false };
    const onClock = pickOwner(current) === TONY_TEAM;
    const nextTony = onClock ? followingTonyPick(current) : nextTonyPick(current);
    return {
      start: onClock ? current + 1 : current,
      nextTony,
      onClock,
    };
  }

  function opponentSignature() {
    return JSON.stringify([
      state.generation,
      state.events.map((event) => [event.overall, event.playerId, event.source]),
      state.keeperMode,
      state.keeperSeeds.map((seed) => [seed.overall, seed.playerId]),
    ]);
  }

  function threatMap() {
    if (!renderCache.threatMap) renderCache.threatMap = new Map((opponentContext.threat?.threats || []).map((threat) => [Number(threat.playerId), threat]));
    return renderCache.threatMap;
  }

  function threatFor(player) {
    return threatMap().get(Number(player?.id)) || null;
  }

  function opponentTargetPlayers(limit = 12) {
    const recs = recommendations();
    const preferred = [recs.bestPickNow, recs.bestValue, recs.bestPlayer, recs.bestFit, recs.bestCeiling, recs.safestWait]
      .map((entry) => entry?.player).filter(Boolean);
    const leaders = availablePlayers().filter((player) => Number.isFinite(leagueScore(player))).slice().sort((a, b) => leagueScore(b) - leagueScore(a) || a.id - b.id);
    const seen = new Set();
    return [...preferred, ...leaders].filter((player) => {
      if (seen.has(player.id)) return false;
      seen.add(player.id);
      return true;
    }).slice(0, limit);
  }

  function opponentTierTargets() {
    const leaders = availablePlayers().filter((player) => Number.isFinite(leagueScore(player))).slice().sort((a, b) => leagueScore(b) - leagueScore(a) || a.id - b.id).slice(0, 5);
    return { "Current League Value top five": leaders.map((player) => player.id) };
  }

  function finishOpponentSimulation(generation, threat, error = null) {
    if (generation !== opponentSimulationGeneration) return;
    opponentContext = error
      ? { ...opponentContext, status: "fallback", threat: null, error: error.message || String(error) || "Opponent simulation failed safely." }
      : { ...opponentContext, status: "ready", threat, error: null };
    renderCache = {};
    renderOpponentIntent();
    renderBoard();
  }

  function postOpponentWorker(generation, options) {
    if (typeof window.Worker !== "function") return false;
    try {
      if (!opponentWorker) {
        opponentWorker = new window.Worker("./model/opponent-intent-worker.js");
        opponentWorker.addEventListener("message", (event) => {
          const message = event.data || {};
          if (message.type === "opponent-intent-result") finishOpponentSimulation(message.generation, message.threat);
          if (message.type === "opponent-intent-error") finishOpponentSimulation(message.generation, null, new Error(message.error || "Opponent worker failed safely."));
        });
        opponentWorker.addEventListener("error", (error) => finishOpponentSimulation(opponentSimulationGeneration, null, error));
      }
      opponentWorker.postMessage({ type: "simulate-opponent-window", generation, options });
      return true;
    } catch (_) {
      opponentWorker?.terminate?.();
      opponentWorker = null;
      return false;
    }
  }

  function scheduleOpponentIntent() {
    if (!OPPONENT_INTENT) {
      opponentContext = { signature: "missing", status: "unavailable", board: null, threat: null, liveState: null, window: null, error: "Opponent Intent runtime did not load." };
      renderOpponentIntent();
      return;
    }
    const signature = opponentSignature();
    if (opponentContext.signature === signature) return;
    const generation = ++opponentSimulationGeneration;
    if (opponentSimulationTimer != null) clearTimeout(opponentSimulationTimer);
    try {
      const liveState = opponentLiveState();
      const windowState = opponentThreatWindow();
      const boardTarget = nextTonyPick(currentPick());
      const board = OPPONENT_INTENT.fullBoard({ currentOverallPick: currentPick(), nextTonyPick: boardTarget, liveState });
      opponentContext = { signature, status: windowState.nextTony ? "calculating" : "complete", board, threat: null, liveState, window: windowState, error: null };
      renderCache = {};
      renderOpponentIntent();
      renderBoard();
      if (!windowState.nextTony || !liveState.availablePlayerIds.length) return;
      const simulationOptions = {
        currentOverallPick: windowState.start,
        nextTonyPick: windowState.nextTony,
        liveState,
        targetPlayerIds: liveState.availablePlayerIds,
        tiers: opponentTierTargets(),
        simulations: OPPONENT_SIMULATIONS,
        seed: 20260831,
      };
      if (postOpponentWorker(generation, simulationOptions)) return;
      opponentSimulationTimer = setTimeout(() => {
        if (generation !== opponentSimulationGeneration) return;
        try {
          finishOpponentSimulation(generation, OPPONENT_INTENT.simulateTonyWindow(simulationOptions));
        } catch (error) {
          finishOpponentSimulation(generation, null, error);
        }
      }, 0);
    } catch (error) {
      opponentContext = { signature, status: "fallback", board: null, threat: null, liveState: null, window: null, error: error.message || "Opponent Intent failed safely." };
      renderOpponentIntent();
    }
  }

  function leagueRank(player) {
    if (runtimeReady()) return RUNTIME.leagueValue(player.id)?.leagueValueRank ?? null;
    if (!renderCache.leagueRanks) {
      renderCache.leagueRanks = new Map(availablePlayers().slice().sort((a, b) => leagueScore(b) - leagueScore(a)).map((item, index) => [item.id, index + 1]));
    }
    return renderCache.leagueRanks.get(player.id) || 0;
  }

  function survival(player, targetPick) {
    return survivalDetail(player, targetPick).value;
  }

  function survivalDetail(player, targetPick) {
    if (runtimeReady()) {
      const threat = threatFor(player);
      if (!threat) return {
        value: null,
        source: opponentContext.status === "calculating" ? "opponent-intent-pending" : "opponent-intent-unavailable",
        calibrated: false,
        calibrationVersion: null,
        qualification: opponentContext.status === "calculating" ? "pending" : "missing",
        targetPick,
      };
      return {
        value: threat.probabilitySurviving,
        source: "dynamic-opponent-intent",
        calibrated: false,
        calibrationVersion: null,
        qualification: threat.status === "CALIBRATED_BASELINE" ? "calibrated-baseline-advisory" : "contextual-unvalidated",
        targetPick: opponentContext.window?.nextTony ?? targetPick,
      };
    }
    return MODEL.survivalDetail(player, state.platform, targetPick, () => {
      const sigma = clamp(3.2 + price(player) * 0.045, 3.5, 10.5);
      return clamp(1 / (1 + Math.exp((targetPick - price(player)) / sigma)), 0.01, 0.99);
    });
  }

  function availabilitySignal(value) {
    if (!Number.isFinite(value)) return "MISSING";
    if (value >= 0.68) return "HIGH";
    if (value >= 0.34) return "MEDIUM";
    return "LOW";
  }

  function availabilityDisplay(detail, { compact = false } = {}) {
    if (!Number.isFinite(detail?.value)) return compact ? "—" : "Availability not modeled";
    if (detail.calibrated) return compact ? `${Math.round(detail.value * 100)}%` : `${Math.round(detail.value * 100)}% calibrated`;
    const signal = availabilitySignal(detail.value);
    if (detail.qualification === "heuristic") return compact ? `${signal} · UNCAL.` : `${signal} uncalibrated availability signal`;
    return compact ? `${Math.round(detail.value * 100)}% · UNCAL.` : `${Math.round(detail.value * 100)}% uncalibrated model estimate`;
  }

  function tierInfo(player) {
    if (runtimeReady()) {
      const rank = leagueRank(player);
      if (!Number.isFinite(rank)) return { id: "LV-missing", label: "No validated tier", rank: null };
      const tier = Math.max(1, Math.ceil(rank / 8));
      return { id: `LV-${tier}`, label: `LV tier ${tier}`, rank: tier };
    }
    const fallbackTier = Math.max(1, Math.ceil((leagueRank(player) || player.ecr || 1) / 8));
    return MODEL.tier(player, { id: `${player.pos}-${fallbackTier}`, label: `${player.pos} tier ${fallbackTier}`, rank: fallbackTier });
  }

  function samePositionNext(player) {
    const same = availablePlayers()
      .filter((item) => item.pos === player.pos && item.id !== player.id && Number.isFinite(leagueScore(item)))
      .sort((a, b) => leagueScore(b) - leagueScore(a));
    return same[0] || null;
  }

  function cliffDelta(player) {
    if (!Number.isFinite(leagueScore(player))) return null;
    const next = samePositionNext(player);
    return next ? Math.max(0, leagueScore(player) - leagueScore(next)) : 12;
  }

  function recommendationPool() {
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const onClock = currentPick() <= TOTAL_PICKS && pickOwner(currentPick()) === TONY_TEAM;
    const nextTurn = followingTonyPick(target) || TOTAL_PICKS;
    return availablePlayers().filter((player) => Number.isFinite(leagueBase(player))).map((player) => {
      const arrive = onClock ? 1 : survival(player, target);
      const surviveNext = survival(player, nextTurn);
      const gap = valueGap(player);
      const score = leagueScore(player);
      const baseScore = leagueBase(player);
      const playerOutcome = outcome(player);
      const cliff = cliffDelta(player);
      const fitImpact = needBonus(player) + (runtimeReady() ? 0 : MODEL.number(player, "leagueValue.rosterFitBase", 0));
      const championshipEquity = runtimeReady() ? 0 : MODEL.number(player, "leagueValue.championshipEquityBase", 0);
      const vorpLost = runtimeReady() || !Number.isFinite(surviveNext) ? 0 : MODEL.number(player, "decision.expectedVorpLostByWaiting", () => cliff * (1 - surviveNext));
      const projected = Number.isFinite(arrive) ? score * (0.58 + arrive * 0.42) : score;
      const pickNow = score
        + (Number.isFinite(gap) ? gap * 0.72 : 0)
        + fitImpact * 0.9
        + (Number.isFinite(surviveNext) ? (1 - surviveNext) * 9 : 0)
        + vorpLost * 1.1
        + championshipEquity * 100
        - (Number.isFinite(playerOutcome.bustProbability) ? playerOutcome.bustProbability * 3 : 0);
      return {
        player,
        arrive,
        surviveNext,
        gap,
        score,
        baseScore,
        projected,
        fitImpact,
        cliff,
        vorpLost,
        championshipEquity,
        outcome: playerOutcome,
        confidence: confidence(player),
        pickNow,
      };
    });
  }

  function recommendations() {
    const pool = recommendationPool();
    const by = (scorer) => pool.slice().sort((a, b) => scorer(b) - scorer(a))[0];
    const bestPlayer = by((entry) => entry.baseScore);
    const bestValue = by((entry) => (Number.isFinite(entry.gap) ? entry.gap * 1.8 : 0) + entry.score * .12 + (Number.isFinite(entry.arrive) ? entry.arrive * 8 : 0));
    const bestFit = by((entry) => (entry.score + entry.fitImpact * 1.8 + entry.cliff) * (Number.isFinite(entry.arrive) ? 0.65 + entry.arrive * .35 : 1));
    const bestCeiling = by((entry) => entry.score * .2
      + (Number.isFinite(entry.outcome.ceilingProbability) ? entry.outcome.ceilingProbability * 60 : 0)
      + (Number.isFinite(entry.outcome.eliteProbability) ? entry.outcome.eliteProbability * 35 : 0)
      - (Number.isFinite(entry.outcome.bustProbability) ? entry.outcome.bustProbability * 12 : 0));
    const safestWait = by((entry) => entry.score * .2 + (Number.isFinite(entry.surviveNext) ? entry.surviveNext * 52 : 0) - entry.vorpLost * 2.2);
    const projectedTarget = by((entry) => entry.projected);
    const bestPickNow = by((entry) => entry.pickNow);
    return { bestPlayer, bestValue, bestFit, bestCeiling, safestWait, projectedTarget, bestPickNow };
  }

  function verdict(player) {
    if (runtimeReady()) {
      const label = Number.isFinite(leagueBase(player)) ? "ADVISORY" : "NO LEAGUE VALUE";
      return { label, cls: label.toLowerCase().replace(/\s+/g, "-") };
    }
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const after = followingTonyPick(target) || TOTAL_PICKS;
    const survive = survival(player, after);
    const label = MODEL.decisionTag({
      override: MODEL.text(player, "decision.override", null),
      reach: fairPick(player) - target,
      survival: survive,
      quality: leagueRank(player) <= Math.max(36, target + 18),
      cliff: cliffDelta(player),
      valueGap: valueGap(player),
      ceilingProbability: outcome(player).ceilingProbability,
    });
    return { label, cls: label.toLowerCase().replace(/\s+/g, "-") };
  }

  function modelAuditSnapshot() {
    const health = modelHealth();
    return {
      packageId: health.packageId,
      modelVersion: health.modelVersion,
      status: health.status,
      mode: health.mode,
      valid: health.valid,
      stale: health.stale,
      coverage: health.coverage,
      decisionMode: health.decisionMode,
      decisionPolicyApproved: health.decisionPolicyApproved,
      decisionPolicyVersion: health.decisionPolicyVersion,
      decisionPolicyReason: health.decisionPolicyReason,
      runtime: RUNTIME?.auditMetadata() || null,
    };
  }

  function marketAuditSnapshot(platform = state.platform) {
    return {
      platform,
      snapshotDate: window.PLAYER_DATA_META?.snapshotDate || null,
      displayDate: window.PLAYER_DATA_META?.displayDate || null,
      source: window.PLAYER_DATA_META?.source || null,
      playerCount: window.PLAYER_DATA.length,
    };
  }

  function rosterAuditSnapshot(eventsBefore) {
    const events = [...state.keeperSeeds, ...canonicalizeEvents(eventsBefore)].sort((a, b) => a.overall - b.overall);
    return {
      phase: "immediately-before-event",
      teams: MANAGERS.slice(1).map((item) => ({
        team: item.id,
        manager: item.name,
        players: events.filter((event) => event.team === item.id).map((event) => {
          const player = playerById(event.playerId);
          return {
            overall: event.overall,
            pick: pickLabel(event.overall),
            playerId: event.playerId,
            name: player?.name || event.externalName || "Unknown",
            position: player?.pos || null,
            source: event.source,
          };
        }),
      })),
    };
  }

  function withEventState(eventsBefore, platform, callback) {
    const originalEvents = state.events;
    const originalPlatform = state.platform;
    const originalCache = renderCache;
    state.events = canonicalizeEvents(eventsBefore);
    state.platform = platform === "sleeper" ? "sleeper" : "espn";
    renderCache = {};
    try {
      return callback();
    } finally {
      state.events = originalEvents;
      state.platform = originalPlatform;
      renderCache = originalCache;
    }
  }

  function recommendationComponent(entry, targetPick) {
    if (!entry) return null;
    const nextTurn = followingTonyPick(targetPick) || TOTAL_PICKS;
    const availability = survivalDetail(entry.player, nextTurn);
    return {
      playerId: entry.player.id,
      name: entry.player.name,
      position: entry.player.pos,
      team: entry.player.team,
      leagueScore: Number.isFinite(entry.score) ? Number(entry.score.toFixed(4)) : null,
      leagueBase: Number.isFinite(entry.baseScore) ? Number(entry.baseScore.toFixed(4)) : null,
      roomPrice: price(entry.player),
      fairPick: fairPick(entry.player),
      valueGap: Number.isFinite(entry.gap) ? Number(entry.gap.toFixed(4)) : null,
      fitImpact: Number.isFinite(entry.fitImpact) ? Number(entry.fitImpact.toFixed(4)) : null,
      cliffDelta: Number.isFinite(entry.cliff) ? Number(entry.cliff.toFixed(4)) : null,
      confidence: entry.confidence,
      outcome: { ...entry.outcome },
      nextPickAvailability: {
        value: availability.value,
        signal: availabilitySignal(availability.value),
        source: availability.source,
        calibrated: availability.calibrated,
        calibrationVersion: availability.calibrationVersion,
        qualification: availability.qualification,
      },
    };
  }

  function recommendationAuditSnapshot(eventsBefore, platform, decisionOverall) {
    return withEventState(eventsBefore, platform, () => {
      const recs = recommendations();
      const targetPick = decisionOverall || currentPick();
      const primary = recs.bestPickNow;
      const call = primary ? verdict(primary.player) : null;
      return {
        capturedAt: new Date().toISOString(),
        decisionOverall: targetPick,
        decisionPick: pickLabel(targetPick),
        advisoryState: {
          label: call?.label || "ADVISORY",
          calibrated: modelHealth().decisionPolicyApproved,
          reason: modelHealth().decisionPolicyReason,
        },
        components: {
          bestPlayer: recommendationComponent(recs.bestPlayer, targetPick),
          bestValue: recommendationComponent(recs.bestValue, targetPick),
          bestFit: recommendationComponent(recs.bestFit, targetPick),
          bestCeiling: recommendationComponent(recs.bestCeiling, targetPick),
          safestWait: recommendationComponent(recs.safestWait, targetPick),
          projectedTarget: recommendationComponent(recs.projectedTarget, targetPick),
          bestPickNow: recommendationComponent(recs.bestPickNow, targetPick),
        },
      };
    });
  }

  function appendAuditRecord(action, event, eventsBefore, details = {}) {
    const recordedAt = new Date().toISOString();
    const eventCopy = event ? { ...event, pick: pickLabel(event.overall), playerName: playerById(event.playerId)?.name || event.externalName || null } : null;
    const record = {
      auditId: `${recordedAt}:${action}:${event?.overall || "draft"}:${state.auditLog.length + 1}`,
      recordedAt,
      action,
      source: event?.source || details.source || "manual",
      event: eventCopy,
      model: modelAuditSnapshot(),
      marketSnapshot: marketAuditSnapshot(details.platform || state.platform),
      rosterState: rosterAuditSnapshot(eventsBefore),
      recommendationBeforeTonyPick: event?.team === TONY_TEAM && ["source-observed", "pick-recorded", "pick-updated", "restored-event"].includes(action)
        ? recommendationAuditSnapshot(eventsBefore, details.platform || state.platform, event.overall)
        : null,
      details: details.details || null,
    };
    state.auditLog.push(record);
    state.auditLog = state.auditLog.slice(-MAX_AUDIT_RECORDS);
    return record;
  }

  function rebuildAuditLog(events) {
    const originalAudit = state.auditLog;
    state.auditLog = [];
    const ordered = canonicalizeEvents(events);
    for (const event of ordered) appendAuditRecord("restored-event", event, ordered.filter((item) => item.overall < event.overall));
    const rebuilt = state.auditLog.slice();
    state.auditLog = originalAudit;
    return rebuilt;
  }

  function auditExportPayload() {
    return {
      schemaVersion: AUDIT_SCHEMA_VERSION,
      exportedAt: new Date().toISOString(),
      league: "Tony 2026 ESPN keeper league",
      platform: state.platform,
      currentPick: currentPick(),
      appRelease: APP_RELEASE,
      sessionId: state.sessionId,
      generation: state.generation,
      model: modelAuditSnapshot(),
      marketSnapshot: marketAuditSnapshot(),
      managers: MANAGERS.slice(1),
      keeperMode: state.keeperMode,
      configuredKeepers: KEEPERS,
      activeKeeperSeeds: state.keeperSeeds.map((seed) => ({ ...seed })),
      seedReconciliations: state.seedReconciliations.map((item) => ({ ...item })),
      sourceObservations: state.sourceObservations.map((observation) => ({ ...observation })),
      draftEvents: state.events.map((event) => ({ ...event })),
      modeledEvents: state.events.map((event) => ({ ...event })),
      sourceIngestionPaused: state.sourceIngestionPaused,
      auditTrail: state.auditLog.map((record) => structuredClone(record)),
    };
  }

  function renderStatus() {
    const pick = currentPick();
    if (pick > TOTAL_PICKS) {
      els.roundPick.textContent = "DONE";
      els.overallPick.textContent = "160 source selections observed";
      els.clockOwner.textContent = "Draft complete";
      els.clockOwner.style.color = "var(--green)";
      els.draftProgress.style.width = "100%";
      els.nextTonyText.textContent = "Export a final backup for the league record.";
      els.decisionWindow.textContent = "Complete";
      els.workspaceTitle.textContent = "Final draft board";
      return;
    }
    const owner = pickOwner(pick);
    const next = nextTonyPick(pick);
    els.roundPick.textContent = pickLabel(pick);
    els.overallPick.textContent = `Overall ${pick}`;
    els.clockOwner.textContent = owner === TONY_TEAM ? "Tony is on the clock" : `${manager(owner).name} is on the clock`;
    els.clockOwner.style.color = owner === TONY_TEAM ? "var(--green)" : "var(--text)";
    els.draftProgress.style.width = `${((pick - 1) / TOTAL_PICKS) * 100}%`;
    const afterCurrent = followingTonyPick(pick);
    els.nextTonyText.textContent = next === pick ? `Make the pick — next open turn is ${afterCurrent ? pickLabel(afterCurrent) : "the end"}` : next ? `Tony picks in ${next - pick} selections at ${pickLabel(next)}` : "Tony's remaining round cost is already occupied by his keeper";
    const target = next || pick;
    const after = followingTonyPick(target);
    els.decisionWindow.textContent = `${pickLabel(target)} → ${after ? pickLabel(after) : "END"}`;
    els.workspaceTitle.textContent = owner === TONY_TEAM ? `Tony is live at ${pickLabel(pick)}` : `Projected targets for Tony at ${pickLabel(target)}`;
  }

  function recCard(entry, label, detail) {
    const { player, arrive, gap } = entry;
    const tier = tierInfo(player);
    const roomPrice = price(player);
    return `<div class="rec-label"><span>${label}</span><span class="pos-pill pos-${player.pos}">${player.pos}</span></div>
      <div class="rec-name">${player.name}</div>
      <div class="rec-meta">${player.team} · ${tier.label} · ${state.platform.toUpperCase()} ${roomPrice ?? "—"}</div>
      <p class="rec-reason">${detail(player, arrive, gap)}</p>`;
  }

  function renderRecommendations() {
    const recs = recommendations();
    const onClock = currentPick() <= TOTAL_PICKS && pickOwner(currentPick()) === TONY_TEAM;
    const primary = onClock ? recs.bestPickNow : recs.projectedTarget;
    if (!primary) {
      els.bestOverallCard.innerHTML = "";
      els.bestValueCard.innerHTML = "";
      els.bestFitCard.innerHTML = "";
      els.decisionStrip.innerHTML = "";
      els.decisionLenses.innerHTML = "";
      return;
    }
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const nextTurn = followingTonyPick(target);
    const after = nextTurn || TOTAL_PICKS;
    els.bestOverallCard.innerHTML = recCard(primary, onClock ? "Best pick now" : "Projected target", (p) => `${availabilityDisplay(survivalDetail(p, target))} to Tony's next modeled window · validated League Value ${fixed(leagueScore(p))}.`);
    els.bestValueCard.innerHTML = recCard(recs.bestValue, "Best value", (p, arrive, gap) => `${Number.isFinite(gap) ? `${gap >= 0 ? "+" : ""}${fixed(gap)} slots versus League Value rank` : "ESPN or League Value rank unavailable"} · ${availabilityDisplay(survivalDetail(p, target))}.`);
    els.bestFitCard.innerHTML = recCard(recs.bestFit, "Best fit", (p) => `${needBonus(p) > 2 ? "Fills a priority roster need" : "Supports the 2-FLEX build"} · ${fixed(cliffDelta(p))}-point immutable-value drop watch.`);
    els.decisionLenses.innerHTML = [
      { label: "Best player", entry: recs.bestPlayer, metric: `LV ${recs.bestPlayer.baseScore.toFixed(1)}` },
      { label: "Best ceiling", entry: recs.bestCeiling, metric: Number.isFinite(recs.bestCeiling.outcome.ceilingProbability) ? `${Math.round(recs.bestCeiling.outcome.ceilingProbability * 100)}% upside` : "Upside not modeled" },
      { label: "Safest wait", entry: recs.safestWait, metric: availabilityDisplay(survivalDetail(recs.safestWait.player, after), { compact: true }) },
    ].map(({ label, entry, metric }) => `<div class="lens-card"><span>${label}</span><strong>${entry.player.name}</strong><small>${metric}</small></div>`).join("");
    const v = verdict(primary.player);
    const availability = survivalDetail(primary.player, after);
    const health = modelHealth();
    const reason = runtimeReady() ? null : MODEL.list(primary.player, "decision.reasons")[0];
    const advisoryCopy = runtimeReady()
      ? "Validated base League Value with live roster fit kept separate. Opponent probabilities remain advisory; TAKE, WAIT, and POSITION CLIFF calls are disabled."
      : "Directional fallback ranking only. TAKE, WAIT, and POSITION CLIFF calls are disabled until a validated runtime package is available.";
    els.decisionStrip.classList.toggle("uncalibrated", !health.decisionPolicyApproved);
    els.decisionStrip.innerHTML = health.decisionPolicyApproved
      ? `<div class="decision-call">${v.label}</div>
        <div class="decision-copy"><strong>${primary.player.name} at ${pickLabel(target)}</strong><span>${reason || (v.label === "TAKE" || v.label === "POSITION CLIFF" ? "The next viable window is unlikely to stay open." : "The calibrated policy sees enough depth to preserve optionality.")} ${samePositionNext(primary.player)?.name || "No comparable fallback"} is the next ${primary.player.pos}.</span></div>
        <div class="decision-metric"><strong>${availabilityDisplay(availability, { compact: true })}</strong><small>survival to ${nextTurn ? pickLabel(after) : "end"}</small></div>`
      : `<div class="decision-call">ADVISORY</div>
        <div class="decision-copy"><strong>${runtimeReady() ? "VALIDATED BASE" : "UNCALIBRATED FALLBACK"} · ${primary.player.name} at ${pickLabel(target)}</strong><span>${advisoryCopy}</span></div>
        <div class="decision-metric"><strong>${availabilityDisplay(availability, { compact: true })}</strong><small>availability signal to ${nextTurn ? pickLabel(after) : "end"}</small></div>`;
  }

  function renderPickMap() {
    const next = nextTonyPick();
    els.pickMap.innerHTML = TONY_PICKS.map((pick) => {
      const isKeeper = state.keeperSeeds.some((seed) => seed.overall === pick);
      const classes = [pick < currentPick() || eventAt(pick) ? "done" : "", pick === next ? "next" : "", isKeeper ? "keeper" : ""].filter(Boolean).join(" ");
      return `<span class="pick-token ${classes}" title="${isKeeper ? "Jaxson Dart keeper cost" : `Tony pick ${pickLabel(pick)}`}">${isKeeper ? "K16" : pick}</span>`;
    }).join("");
  }

  const BOARD_SORT_DEFAULTS = Object.freeze({
    name: "asc", position: "asc", leagueValue: "desc", espnPrice: "asc", espnAdp: "asc",
    survival: "desc", taken: "desc", threat: "desc",
  });

  function espnAdp(player) {
    if (runtimeReady()) return RUNTIME.market(player.id)?.continuousAdp ?? null;
    return OPPONENT_INTENT?.market(player.id)?.espnAdp ?? null;
  }

  function boardMetric(player, key, platform, after) {
    const threat = threatFor(player);
    if (key === "name") return player.name.toLowerCase();
    if (key === "position") return player.pos;
    if (key === "leagueValue") return leagueScore(player);
    if (key === "espnPrice") return roomOrder(player, platform);
    if (key === "espnAdp") return espnAdp(player);
    if (key === "survival") return survivalDetail(player, after).value;
    if (key === "taken") return threat?.probabilityTakenBeforeTony ?? null;
    if (key === "threat") return threat?.mostLikelyTaker?.probability ?? null;
    return player.id;
  }

  function compareMetrics(left, right, direction) {
    const leftMissing = left == null || (typeof left === "number" && !Number.isFinite(left));
    const rightMissing = right == null || (typeof right === "number" && !Number.isFinite(right));
    if (leftMissing || rightMissing) return leftMissing === rightMissing ? 0 : leftMissing ? 1 : -1;
    const result = typeof left === "string" ? left.localeCompare(right) : left - right;
    return direction === "desc" ? -result : result;
  }

  function boardRows(platform = state.platform, sort = state.boardSort) {
    const query = state.search.trim().toLowerCase();
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const after = followingTonyPick(target) || TOTAL_PICKS;
    return availablePlayers()
      .filter((player) => state.position === "ALL" || player.pos === state.position)
      .filter((player) => !query || `${player.name} ${player.team}`.toLowerCase().includes(query))
      .sort((a, b) => compareMetrics(boardMetric(a, sort.key, platform, after), boardMetric(b, sort.key, platform, after), sort.direction)
        || compareMetrics(price(a, platform), price(b, platform), "asc")
        || compareMetrics(leagueScore(a), leagueScore(b), "desc") || a.id - b.id);
  }

  function sortLabel(key, platformName) {
    return ({
      name: "player name", position: "position", leagueValue: "League Value", espnPrice: `${platformName} default room rank`,
      espnAdp: "ESPN ADP", survival: "next-pick survival", taken: "probability taken before Tony", threat: "strongest opponent threat",
    })[key] || key;
  }

  function updateSortHeaders() {
    document.querySelectorAll("[data-board-sort]").forEach((button) => {
      const active = button.dataset.boardSort === state.boardSort.key;
      button.classList.toggle("active", active);
      button.dataset.direction = active ? state.boardSort.direction : "";
      button.setAttribute?.("aria-pressed", String(active));
    });
    document.querySelectorAll("[data-opponent-sort]").forEach((button) => {
      const active = button.dataset.opponentSort === state.opponentSort.key;
      button.classList.toggle("active", active);
      button.dataset.direction = active ? state.opponentSort.direction : "";
      button.setAttribute?.("aria-pressed", String(active));
    });
  }

  function setBoardSort(key) {
    if (!(key in BOARD_SORT_DEFAULTS)) return false;
    state.boardSort = state.boardSort.key === key
      ? { key, direction: state.boardSort.direction === "asc" ? "desc" : "asc" }
      : { key, direction: BOARD_SORT_DEFAULTS[key] };
    state.visible = 20;
    renderBoard();
    return true;
  }

  function setOpponentSort(key) {
    const defaults = { manager: "asc", nextPick: "asc", position: "desc", threat: "desc", confidence: "desc" };
    if (!(key in defaults)) return;
    state.opponentSort = state.opponentSort.key === key
      ? { key, direction: state.opponentSort.direction === "asc" ? "desc" : "asc" }
      : { key, direction: defaults[key] };
    renderOpponentBoard();
  }

  function renderBoard() {
    const rows = boardRows();
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const nextTurn = followingTonyPick(target);
    const after = nextTurn || TOTAL_PICKS;
    const platformName = state.platform === "espn" ? "ESPN" : "Sleeper";
    const health = modelHealth();
    els.boardCount.textContent = `${rows.length} available`;
    els.platformHeader.textContent = `${platformName} price`;
    els.roomRankNote.textContent = `${platformName} controls the room-price column; League Value remains independent.`;
    els.boardOrderNote.textContent = `Sorted by ${sortLabel(state.boardSort.key, platformName)} · ${state.boardSort.direction === "asc" ? "low to high / A–Z" : "high to low / Z–A"}`;
    els.nextPickHeader.textContent = health.decisionPolicyApproved ? "Survives next pick" : "Next-pick signal";
    els.callHeader.textContent = health.decisionPolicyApproved ? "Call" : "Status";
    updateSortHeaders();
    els.playerTable.innerHTML = rows.slice(0, state.visible).map((player, index) => {
      const rank = leagueRank(player);
      const gap = valueGap(player);
      const availability = survivalDetail(player, after);
      const call = verdict(player);
      const tier = tierInfo(player);
      const signal = availabilitySignal(availability.value);
      const barWidth = !Number.isFinite(availability.value) ? 0 : availability.calibrated ? Math.round(availability.value * 100) : signal === "HIGH" ? 100 : signal === "MEDIUM" ? 66 : 33;
      const threat = threatFor(player);
      const taken = threat ? `${Math.round(threat.probabilityTakenBeforeTony * 100)}%` : opponentContext.status === "calculating" ? "…" : "—";
      const taker = threat?.mostLikelyTaker;
      const score = leagueScore(player);
      const roomPrice = price(player);
      const leagueValueCell = Number.isFinite(score)
        ? `<span class="metric-main">#${rank}</span><span class="metric-sub">${tier.label} · score ${fixed(score)}</span>`
        : `<span class="metric-main">—</span><span class="metric-sub">No validated Player Truth / League Value</span>`;
      const marketCell = Number.isFinite(roomPrice)
        ? `<span class="metric-main ${Number.isFinite(gap) && gap >= 4 ? "value-positive" : Number.isFinite(gap) && gap <= -4 ? "value-negative" : ""}">#${roomPrice}</span><span class="metric-sub">${Number.isFinite(gap) ? `${gap >= 0 ? "+" : ""}${fixed(gap)} vs LV rank` : "League Value rank unavailable"}</span>`
        : `<span class="metric-main">—</span><span class="metric-sub">ESPN market unavailable</span>`;
      return `<tr data-player-id="${player.id}">
        <td><div class="player-cell"><span class="rank-num">${index + 1}</span><div><span class="player-name">${player.name}</span><span class="player-meta">${player.team} · BYE ${player.bye}</span></div></div></td>
        <td><span class="pos-pill pos-${player.pos}">${player.pos}</span></td>
        <td>${leagueValueCell}</td>
        <td>${marketCell}</td>
        <td><span class="metric-main">${espnAdp(player) == null ? "—" : espnAdp(player).toFixed(1)}</span><span class="metric-sub">separate ESPN signal</span></td>
        <td><div class="survival"><div class="survival-head"><span>${nextTurn ? pickLabel(after) : "END"}</span><span>${availabilityDisplay(availability, { compact: true })}</span></div><div class="survival-bar ${availability.calibrated ? "" : "uncalibrated"}"><span style="width:${barWidth}%"></span></div></div></td>
        <td><span class="metric-main">${taken}</span><span class="metric-sub">${opponentContext.window?.nextTony ? `before ${pickLabel(opponentContext.window.nextTony)}` : "window complete"}</span></td>
        <td><span class="metric-main">${taker ? taker.manager : "—"}</span><span class="metric-sub">${taker ? `${Math.round(taker.probability * 100)}% direct threat` : opponentContext.status === "calculating" ? "recalculating" : "no simulated threat"}</span></td>
        <td><span class="call-badge call-${call.cls}">${call.label}</span></td>
        <td><button class="draft-btn" data-draft-id="${player.id}" type="button" ${currentPick() > TOTAL_PICKS ? "disabled" : ""}>Draft</button></td>
      </tr>`;
    }).join("");
    els.loadMore.hidden = rows.length <= state.visible;
  }

  function renderRoster() {
    const roster = teamRoster(state.rosterTeam);
    const counts = rosterCounts(state.rosterTeam);
    els.rosterManager.value = String(state.rosterTeam);
    els.rosterManagerName.textContent = manager(state.rosterTeam).name;
    els.rosterCount.textContent = `${roster.length} / 16`;
    els.rosterNeeds.innerHTML = Object.keys(TARGETS).map((pos) => `<div class="need-box"><strong>${counts[pos]}</strong><small>${pos} / ${TARGETS[pos]}</small></div>`).join("");
    els.rosterList.innerHTML = roster.length ? roster.map(({ event, player }) => `<div class="roster-row"><div><span>${player.name}</span><small>${player.team} · ${pickLabel(event.overall)} · ${sourceLabel(event)}</small></div><span class="pos-pill pos-${player.pos}">${player.pos}</span></div>`).join("") : `<div class="empty-state">${manager(state.rosterTeam).short}'s players will appear here as live picks are entered.</div>`;
  }

  function renderHistory() {
    const recent = state.events.slice().sort((a, b) => b.overall - a.overall).slice(0, 10);
    const latest = state.events.slice().sort((a, b) => b.overall - a.overall)[0];
    els.undoPick.disabled = !isManualEvent(latest);
    els.undoPick.title = isManualEvent(latest) ? "Undo the latest manual event" : "ESPN source events are authoritative; use Hard Reset Draft for a new session.";
    els.historyList.innerHTML = recent.length ? recent.map((event) => {
      const player = playerById(event.playerId);
      return `<div class="history-row"><div class="history-main"><span>${player?.name || "Unknown"}</span><small>${pickLabel(event.overall)} · ${manager(event.team).name} · ${sourceLabel(event)}</small></div><div class="history-actions"><span class="pos-pill pos-${player?.pos || "QB"}">${player?.pos || "?"}</span>${isManualEvent(event) ? `<button class="history-edit" data-edit-pick="${event.overall}" type="button">Edit manual</button>` : ""}</div></div>`;
    }).join("") : `<div class="empty-state">No modeled picks yet. Enter manually or connect ESPN; keeper seeds are ${state.keeperMode ? "loaded" : "off"}.</div>`;
  }

  function renderKeepers() {
    els.keeperToggle.textContent = state.keeperMode ? `Remove ESPN keepers · ${KEEPERS.length} loaded` : "Load ESPN keepers";
    els.keeperToggle.classList.toggle("active", state.keeperMode);
    els.keeperModeNote.textContent = state.keeperMode
      ? "Seeds are active. ESPN observations remain authoritative and can confirm, move, or override them."
      : "Off by default. Use only when the live ESPN room has keeper slots configured the same way.";
    els.keeperList.innerHTML = KEEPERS.map((keeper) => {
      const player = playerById(keeper.playerId);
      const seed = state.keeperSeeds.find((item) => item.overall === keeper.overall);
      const confirmed = state.events.some((event) => event.overall === keeper.overall && event.playerId === keeper.playerId && event.status === "source-confirmed");
      const reconciliation = state.seedReconciliations.slice().reverse().find((item) => item.playerId === keeper.playerId || item.seededPlayerId === keeper.playerId || item.overall === keeper.overall || item.fromOverall === keeper.overall);
      const label = !state.keeperMode ? "OFF" : seed ? `R${keeper.round}` : confirmed ? "CONFIRMED" : reconciliation?.action.includes("moved") ? "MOVED" : reconciliation?.action.includes("override") ? "OVERRIDDEN" : "RESOLVED";
      return `<div class="keeper-row ${state.keeperMode && (seed || confirmed) ? "active" : "inactive"}"><div><strong>${manager(keeper.team).name}</strong><small>${player?.name || "Unknown"} · ${pickLabel(keeper.overall)}</small></div><span class="keeper-round">${label}</span></div>`;
    }).join("");
  }

  function draftIssues() {
    const issues = [];
    const observed = new Set(state.sourceObservations.map((observation) => observation.overall));
    const progression = state.sourceObservations.filter((observation) => !observation.futureKeeperHint).map((observation) => observation.overall);
    const maxObserved = progression.length ? Math.max(...progression) : 0;
    for (let overall = 1; overall <= maxObserved; overall += 1) {
      if (!observed.has(overall) && !state.keeperSeeds.some((seed) => seed.overall === overall)) {
        issues.push({ overall, code: "SOURCE_PICK_MISSING", detail: "ESPN never reported this slot; later selections were observed.", resolvable: "missing", integrity: true });
      }
    }
    for (const observation of state.sourceObservations.filter((item) => item.status !== "resolved")) {
      const seedAction = state.seedReconciliations.slice().reverse().find((item) => item.overall === observation.overall || item.toOverall === observation.overall);
      const seedDetail = seedAction ? ` Keeper seed was ${seedAction.action.replaceAll("-", " ")}.` : "";
      issues.push({ overall: observation.overall, code: observation.reasonCode || "RESOLUTION_FAILED", detail: `${observation.rawPlayerName || observation.externalName || "Unknown player"} was reported by ESPN but the internal player board lacks a match.${seedDetail}`, resolvable: true });
    }
    return issues.sort((a, b) => a.overall - b.overall);
  }

  function renderDraftAlerts() {
    const issues = draftIssues();
    els.draftAlerts.hidden = !issues.length;
    const integrity = issues.some((issue) => issue.integrity);
    els.draftAlerts.innerHTML = issues.length ? `<div><strong>${integrity ? "Integrity warning · " : ""}${issues.length} source pick${issues.length === 1 ? "" : "s"} need attention</strong><span>The source clock continues from observations; unresolved players are not added to a roster until mapped.</span></div>${issues.slice(0, 8).map((issue) => `<div class="draft-alert-row"><span><strong>${missingPickMessage(issue.overall)}</strong><small>${issue.code.replaceAll("_", " ")} · ${issue.detail}</small></span>${issue.resolvable ? `<button type="button" ${issue.resolvable === "missing" ? `data-resolve-missing="${issue.overall}"` : `data-resolve-observation="${issue.overall}"`}>${issue.resolvable === "missing" ? "Assign manually" : "Map player"}</button>` : ""}</div>`).join("")}` : "";
  }

  function renderCliffs() {
    const positions = ["RB", "WR", "TE", "QB"];
    const items = positions.map((pos) => availablePlayers().filter((p) => p.pos === pos && Number.isFinite(leagueScore(p))).sort((a, b) => leagueScore(b) - leagueScore(a))[0]).filter(Boolean);
    const approved = modelHealth().decisionPolicyApproved;
    els.cliffPanel.innerHTML = `<p class="eyebrow">Scarcity monitor</p><h2>Position cliffs</h2>${approved ? "" : '<p class="cliff-advisory">ADVISORY · score gaps only</p>'}${items.map((player) => {
      const next = samePositionNext(player);
      const delta = cliffDelta(player);
      return `<div class="cliff-player"><strong><span>${player.pos}: ${player.name}</span><span class="cliff-severity">${delta >= 4 ? "STEEP" : delta >= 2 ? "WATCH" : "DEPTH"}</span></strong><p>${next ? `${next.name} is next; ${delta.toFixed(1)} score points down.` : "No comparable option remains."}</p></div>`;
    }).join("")}`;
  }

  function percent(value, digits = 0) {
    return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(digits)}%` : "—";
  }

  function likelyPosition(row) {
    return Object.entries(row?.positionProbabilities || {}).sort((a, b) => b[1] - a[1])[0] || ["—", 0];
  }

  function managerThreatScore(team) {
    return opponentTargetPlayers().reduce((sum, player) => {
      const breakdown = threatFor(player)?.managerThreatBreakdown || [];
      return sum + (breakdown.find((entry) => entry.team === Number(team))?.probability || 0);
    }, 0);
  }

  function renderOnClockManagerCard() {
    const health = OPPONENT_INTENT?.health();
    const rows = opponentContext.board?.opponents || [];
    const current = currentPick();
    const currentTeam = current <= TOTAL_PICKS ? pickOwner(current) : null;
    const row = currentTeam && currentTeam !== TONY_TEAM
      ? rows.find((item) => item.team === currentTeam)
      : rows.filter((item) => item.overallPick != null && item.overallPick > current).sort((a, b) => a.overallPick - b.overallPick)[0];
    const status = opponentContext.status === "calculating" ? "Recalculating" : health?.mode === "live" ? "Baseline live" : "Fallback";
    els.opponentIntentStatus.textContent = status;
    els.opponentIntentStatus.className = `intent-status intent-${health?.mode === "live" ? "live" : "fallback"}`;
    if (!row) {
      els.onClockManagerCard.innerHTML = `<div class="empty-state">${current > TOTAL_PICKS ? "Draft complete." : "Tony is on the clock; no later opponent selection remains."}</div>`;
      return;
    }
    const [position, probability] = likelyPosition(row);
    const roster = row.rosterCounts || {};
    const needs = row.openNeeds || {};
    const topPlayers = row.topPlayers || [];
    els.onClockManagerCard.innerHTML = `
      <div class="intent-manager-head"><div><strong>${row.manager}</strong><small>ESPN team ${row.espnTeamId ?? "—"} · ${row.overallPick ? pickLabel(row.overallPick) : "complete"}</small></div><span class="pos-pill pos-${position}">${position}</span></div>
      <div class="intent-primary"><strong>${percent(probability)}</strong><span>most likely position</span></div>
      <div class="intent-roster"><span>Roster</span><strong>QB ${roster.QB || 0} · RB ${roster.RB || 0} · WR ${roster.WR || 0} · TE ${roster.TE || 0}</strong><small>Open: QB ${needs.QB || 0} · RB ${needs.RB || 0} · WR ${needs.WR || 0} · TE ${needs.TE || 0}</small></div>
      <div class="position-distribution">${Object.entries(row.positionProbabilities || {}).map(([pos, value]) => `<div><span>${pos}</span><i><b style="width:${Math.round(value * 100)}%"></b></i><strong>${percent(value)}</strong></div>`).join("")}</div>
      <div class="intent-player-list">${topPlayers.map((player, index) => `<div><span>${index + 1}. ${player.playerName}</span><strong>${percent(player.probability, 1)}</strong></div>`).join("")}<div><span>Other</span><strong>${percent(row.otherProbability, 1)}</strong></div></div>
      <p class="intent-summary">${row.profileSummary || row.error || "Room and roster context only."}</p>
      <p class="intent-meta">${row.confidence} · ${String(row.status || "fallback").replaceAll("_", " ")} · ${row.profileEvidence?.sampleSize || 0} historical R1–6 picks · ${row.picksUntilFollowingTurn ?? "—"} picks to following turn · manager residual 0</p>`;
  }

  function opponentRowMetric(row, key) {
    const [position, probability] = likelyPosition(row);
    if (key === "manager") return row.manager.toLowerCase();
    if (key === "nextPick") return row.overallPick;
    if (key === "position") return probability;
    if (key === "threat") return managerThreatScore(row.team);
    if (key === "confidence") return ({ MEDIUM: 3, LOW: 2, FALLBACK: 1, UNAVAILABLE: 0, COMPLETE: 0 })[row.confidence] || 0;
    return position;
  }

  function renderOpponentBoard() {
    const rows = (opponentContext.board?.opponents || []).slice();
    els.opponentBoardStatus.textContent = opponentContext.status === "calculating" ? "Threats calculating" : opponentContext.status === "ready" ? "Live" : opponentContext.status === "complete" ? "Complete" : "Fallback";
    if (!rows.length) {
      els.opponentBoard.innerHTML = `<tr><td colspan="6"><div class="empty-state">${opponentContext.error || "Opponent model unavailable; the draft board remains fully usable."}</div></td></tr>`;
      return;
    }
    rows.sort((a, b) => compareMetrics(opponentRowMetric(a, state.opponentSort.key), opponentRowMetric(b, state.opponentSort.key), state.opponentSort.direction)
      || (a.overallPick ?? Infinity) - (b.overallPick ?? Infinity) || a.team - b.team);
    els.opponentBoard.innerHTML = rows.map((row) => {
      const [position, probability] = likelyPosition(row);
      const top = row.topPlayers?.[0];
      const topFive = (row.topPlayers || []).map((player) => `${player.playerName} ${percent(player.probability, 1)}`).join(" · ");
      const threat = managerThreatScore(row.team);
      const roster = row.rosterCounts || {};
      return `<tr class="${row.picksBeforeTony ? "before-tony" : ""}">
        <td><span class="metric-main">${row.manager}</span><span class="metric-sub">ESPN ${row.espnTeamId ?? "—"} · QB ${roster.QB || 0} RB ${roster.RB || 0} WR ${roster.WR || 0} TE ${roster.TE || 0}</span></td>
        <td><span class="metric-main">${row.overallPick ? pickLabel(row.overallPick) : "—"}</span><span class="metric-sub">${row.picksBeforeTony ? "BEFORE TONY" : "later"}</span></td>
        <td><span class="metric-main"><span class="pos-pill pos-${position}">${position}</span> ${percent(probability)}</span><span class="metric-sub">${Object.entries(row.positionProbabilities || {}).map(([pos, value]) => `${pos} ${percent(value)}`).join(" · ")}</span></td>
        <td><span class="metric-main">${top?.playerName || "—"}</span><span class="metric-sub top-five-summary" title="${topFive}">${topFive || row.status}</span></td>
        <td><span class="metric-main">${opponentContext.threat ? threat.toFixed(2) : opponentContext.status === "calculating" ? "…" : "—"}</span><span class="metric-sub">expected displayed-target picks</span></td>
        <td><span class="intent-confidence confidence-${String(row.confidence || "fallback").toLowerCase()}">${row.confidence}</span><span class="metric-sub">${String(row.status || "fallback").replaceAll("_", " ")}</span></td>
      </tr>`;
    }).join("");
    updateSortHeaders();
  }

  function renderThreatBoard() {
    const threat = opponentContext.threat;
    els.threatBoardStatus.textContent = opponentContext.status === "calculating" ? "Recalculating" : opponentContext.status === "ready" ? `${threat.simulations} seeded runs` : opponentContext.status === "complete" ? "Complete" : "Fallback";
    if (!threat) {
      els.tierSurvival.innerHTML = "";
      els.threatBoard.innerHTML = `<div class="empty-state">${opponentContext.status === "calculating" ? "Sequential depletion simulation is running; ESPN ingestion remains active." : opponentContext.error || "No Tony window remains."}</div>`;
      return;
    }
    const targets = opponentTargetPlayers();
    const mapped = targets.map((player) => ({ player, threat: threatFor(player) })).filter((entry) => entry.threat);
    const tier = threat.tierSurvival?.["Current League Value top five"];
    els.tierSurvival.innerHTML = tier ? `<span>League Value top-five tier</span><strong>${tier.expectedRemaining.toFixed(1)} expected to survive · ${percent(tier.probabilityAtLeastOneSurvives)} chance at least one remains</strong>` : "";
    els.threatBoard.innerHTML = mapped.map(({ player, threat: row }) => {
      const top = row.mostLikelyTaker;
      const second = row.secondMostLikelyTaker;
      const breakdown = row.managerThreatBreakdown.slice(0, 4).map((entry) => `${entry.manager} ${percent(entry.probability)}`).join(" · ");
      return `<article class="threat-card">
        <div><span class="pos-pill pos-${player.pos}">${player.pos}</span><strong>${player.name}</strong></div>
        <div class="threat-prob"><strong>${percent(row.probabilityTakenBeforeTony)}</strong><span>taken</span><strong>${percent(row.probabilitySurviving)}</strong><span>survives</span></div>
        <p>${top ? `${top.manager} is the leading threat (${percent(top.probability)}).` : "No modeled opponent selected him in this window."}${second ? ` Next: ${second.manager} (${percent(second.probability)}).` : ""}</p>
        <small>${breakdown || "No manager-specific threat in seeded runs"} · ${row.status.replaceAll("_", " ")}</small>
      </article>`;
    }).join("") || `<div class="empty-state">No available Tony targets remain.</div>`;
  }

  function renderOpponentIntent() {
    renderOnClockManagerCard();
    renderOpponentBoard();
    renderThreatBoard();
  }

  function freshnessLabel(timestamp) {
    if (!timestamp) return "Unknown";
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return "Unknown";
    const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86400000));
    return days === 0 ? "Today" : `${days}d old`;
  }

  function renderModelHealth() {
    const health = modelHealth();
    const percent = Math.round(health.coverage * 100);
    els.modelStatusBadge.textContent = health.label;
    els.modelStatusBadge.className = `model-badge model-${health.mode}`;
    els.modelVersion.textContent = health.modelVersion;
    els.modelFreshness.textContent = freshnessLabel(health.effectiveAt);
    els.modelCoverage.textContent = `${percent}%`;
    els.modelStatusCopy.textContent = runtimeReady()
      ? `${health.coveredPlayers} of ${health.totalPlayers} board players have validated Player Truth and immutable League Value; decision calls remain advisory.`
      : health.stale
        ? "The loaded research package has expired, so recommendations reverted to the provisional fallback."
        : `ADVISORY / UNCALIBRATED · ${health.modelState === "rejected" ? "Runtime rejected safely" : "Provisional fallback active"}: ${health.errors?.[0] || "validated runtime unavailable"}`;
    const roomSnapshot = window.PLAYER_DATA_META?.displayDate || "current snapshot";
    els.snapshotNote.textContent = `${health.modelVersion} · room board ${roomSnapshot}`;
    const modelNote = runtimeReady()
      ? `<strong>Model:</strong> ${health.modelVersion} · ${percent}% Player Truth / League Value coverage · ${health.sourceCount} signed source artifacts. Missing fields remain missing and are never imputed.`
      : `<strong>Model:</strong> ${health.modelState === "rejected" ? "Validated runtime rejected" : "Provisional fallback active"}. Manual drafting and synchronization remain available.`;
    els.modelSourceNote.innerHTML = `${modelNote}<br><strong>Projection semantics:</strong> Step 14 P50 is the frozen consensus baseline. Step 13B signals did not numerically adjust it; unavailable P10/P90 and event probabilities remain blank.<br><strong>Layer separation:</strong> Immutable League Value, live roster fit, frozen ESPN rank/ADP, and dynamic Opponent Intent remain separate. Opponent outputs are advisory; TAKE/WAIT and POSITION CLIFF calls are suppressed.<br><strong>Draft-room order:</strong> ESPN and Sleeper PPR defaults from ${window.PLAYER_DATA_META?.source || "the platform source layer"}, ${roomSnapshot}. The selected platform controls the player-list order; League Value remains independent.`;
  }

  function render() {
    renderCache = {};
    renderStatus();
    renderPickMap();
    renderRecommendations();
    renderBoard();
    renderRoster();
    renderHistory();
    renderKeepers();
    renderDraftAlerts();
    renderCliffs();
    renderModelHealth();
    renderOpponentIntent();
    scheduleOpponentIntent();
    document.querySelectorAll(".platform-btn").forEach((button) => button.classList.toggle("active", button.dataset.platform === state.platform));
  }

  function draftPlayer(id) {
    const overall = currentPick();
    if (overall > TOTAL_PICKS) return;
    const player = playerById(id);
    if (!player || draftedIds().has(player.id)) return;
    const team = pickOwner(overall);
    const timestamp = new Date().toISOString();
    const event = { overall, team, playerId: player.id, source: "manual", status: "manual", syncKey: "manual", timestamp };
    state.sourceObservations.push({
      observationId: `${state.sessionId}:manual:${overall}`,
      overall, team, playerId: player.id, manualPlayerId: player.id, externalName: player.name,
      externalId: null, source: "manual", syncKey: "manual", status: "resolved", reasonCode: null,
      firstObservedAt: timestamp, lastObservedAt: timestamp, generation: state.generation,
    });
    state.sourceObservations = canonicalizeObservations(state.sourceObservations);
    appendAuditRecord("pick-recorded", event, state.events);
    state.events.push(event);
    state.events.sort((a, b) => a.overall - b.overall);
    state.visible = 20;
    saveState();
    render();
    showToast(`${player.name} drafted at ${pickLabel(overall)} by ${manager(team).name}`);
  }

  function editEvent(overall) {
    return state.events.find((event) => event.overall === Number(overall)) || null;
  }

  function openEditDialog(overall) {
    const event = editEvent(overall);
    if (!isManualEvent(event)) return;
    const player = playerById(event.playerId);
    state.editingOverall = event.overall;
    state.resolvingObservationOverall = null;
    state.resolvingMissingOverall = null;
    els.removePick.hidden = false;
    els.rewindPick.hidden = true;
    els.dialogTitle.textContent = `${pickLabel(event.overall)} · ${manager(event.team).name}`;
    els.dialogCopy.textContent = `Current manual selection: ${player.name}. Choose an available replacement or remove only this manual event.`;
    els.replacementSearch.value = "";
    renderReplacementList();
    els.pickDialog.showModal();
    requestAnimationFrame(() => els.replacementSearch.focus());
  }

  function openObservationDialog(overall) {
    const observation = state.sourceObservations.find((item) => item.overall === Number(overall) && item.status !== "resolved");
    if (!observation) return;
    state.editingOverall = null;
    state.resolvingObservationOverall = observation.overall;
    state.resolvingMissingOverall = null;
    els.dialogTitle.textContent = `${pickLabel(observation.overall)} · ${manager(observation.team).name}`;
    els.dialogCopy.textContent = `${observation.externalName || "Unknown source player"} was observed by ${sourceLabel(observation)} but was not found on the board. Choose the correct player to map this source observation.`;
    els.replacementSearch.value = "";
    els.removePick.hidden = true;
    els.rewindPick.hidden = true;
    renderReplacementList();
    els.pickDialog.showModal();
    requestAnimationFrame(() => els.replacementSearch.focus());
  }

  function openMissingDialog(overall) {
    const pick = Number(overall);
    if (!Number.isInteger(pick) || pick < 1 || pick > TOTAL_PICKS || state.sourceObservations.some((item) => item.overall === pick)) return;
    state.editingOverall = null;
    state.resolvingObservationOverall = null;
    state.resolvingMissingOverall = pick;
    els.dialogTitle.textContent = `${pickLabel(pick)} · ${manager(pickOwner(pick)).name}`;
    els.dialogCopy.textContent = "ESPN never reported this slot. Choose the player selected here to create a clearly labeled manual recovery event at the original missing pick.";
    els.replacementSearch.value = "";
    els.removePick.hidden = true;
    els.rewindPick.hidden = true;
    renderReplacementList();
    els.pickDialog.showModal();
    requestAnimationFrame(() => els.replacementSearch.focus());
  }

  function replacementCandidates() {
    const current = editEvent(state.editingOverall);
    const blocked = draftedIds();
    if (current) blocked.delete(current.playerId);
    const query = els.replacementSearch.value.trim().toLowerCase();
    return window.PLAYER_DATA.filter((player) => !blocked.has(player.id)).filter((player) => !query || `${player.name} ${player.team} ${player.pos}`.toLowerCase().includes(query)).slice(0, 30);
  }

  function renderReplacementList() {
    els.replacementList.innerHTML = replacementCandidates().map((player) => `<button class="replacement-option" data-replace-id="${player.id}" type="button"><span class="pos-pill pos-${player.pos}">${player.pos}</span><strong>${player.name}</strong><small>${player.team} · ECR ${player.ecr}</small></button>`).join("") || `<div class="empty-state">No available players match that search.</div>`;
  }

  function replacePick(playerId) {
    if (state.resolvingMissingOverall != null) {
      resolveMissingPick(state.resolvingMissingOverall, playerId);
      return;
    }
    if (state.resolvingObservationOverall != null) {
      resolveObservation(state.resolvingObservationOverall, playerId);
      return;
    }
    const event = editEvent(state.editingOverall);
    const player = playerById(playerId);
    if (!event || !player) return;
    const blocked = draftedIds();
    blocked.delete(event.playerId);
    if (blocked.has(player.id)) return;
    const oldEvent = { ...event };
    const oldPlayer = playerById(event.playerId);
    event.playerId = player.id;
    event.timestamp = new Date().toISOString();
    event.source = "manual-correction";
    event.syncKey = null;
    event.externalId = null;
    event.externalName = null;
    const observation = state.sourceObservations.find((item) => item.overall === event.overall && (item.manualPlayerId || item.source === "manual"));
    if (observation) {
      observation.playerId = player.id;
      observation.manualPlayerId = player.id;
      observation.status = "resolved";
      observation.resolutionStatus = "manually-resolved";
      observation.lastObservedAt = event.timestamp;
      if (observation.source === "manual") {
        observation.externalName = player.name;
        observation.rawPlayerName = player.name;
      }
    }
    appendAuditRecord("pick-updated", event, state.events.filter((item) => item.overall < event.overall), {
      details: { previousPlayerId: oldEvent.playerId, previousPlayerName: oldPlayer.name, reason: "manual-correction" },
    });
    saveState();
    els.pickDialog.close();
    render();
    showToast(`${pickLabel(event.overall)} corrected: ${oldPlayer.name} → ${player.name}`);
  }

  function resolveObservation(overall, playerId) {
    const observation = state.sourceObservations.find((item) => item.overall === Number(overall) && item.status !== "resolved");
    const player = playerById(playerId);
    if (!observation || !player || draftedIds().has(player.id)) return false;
    const seedAt = state.keeperSeeds.find((seed) => seed.overall === observation.overall);
    const seedForPlayer = state.keeperSeeds.find((seed) => seed.playerId === player.id);
    state.keeperSeeds = state.keeperSeeds.filter((seed) => seed !== seedAt && seed !== seedForPlayer);
    state.events = state.events.filter((event) => event.overall !== observation.overall && event.playerId !== player.id);
    const event = {
      overall: observation.overall,
      team: pickOwner(observation.overall),
      playerId: player.id,
      source: "manual-resolution",
      status: "manual-resolution",
      syncKey: observation.syncKey,
      externalId: observation.externalId,
      externalName: observation.externalName,
      timestamp: new Date().toISOString(),
    };
    observation.playerId = player.id;
    observation.manualPlayerId = player.id;
    observation.status = "resolved";
    observation.resolutionStatus = "manually-resolved";
    observation.reasonCode = null;
    observation.unresolvedReasonCode = null;
    observation.reason = null;
    observation.lastObservedAt = event.timestamp;
    state.events.push(event);
    state.events = canonicalizeEvents(state.events);
    appendAuditRecord("pick-recorded", event, state.events.filter((item) => item.overall < event.overall), {
      details: { reason: "manual-observation-resolution", observationId: observation.observationId },
    });
    state.editingOverall = null;
    state.resolvingObservationOverall = null;
    els.removePick.hidden = false;
    els.rewindPick.hidden = false;
    els.pickDialog.close();
    renderCache = {};
    saveState();
    render();
    showToast(`${observation.externalName || "Source player"} mapped to ${player.name}`);
    return true;
  }

  function resolveMissingPick(overall, playerId) {
    const pick = Number(overall);
    const player = playerById(playerId);
    if (!Number.isInteger(pick) || !player || draftedIds().has(player.id) || state.sourceObservations.some((item) => item.overall === pick)) return false;
    const timestamp = new Date().toISOString();
    const team = pickOwner(pick);
    const observation = {
      observationId: `${state.sessionId}:manual-missing:${pick}`,
      overall: pick,
      round: Math.ceil(pick / TEAM_COUNT),
      roundPick: ((pick - 1) % TEAM_COUNT) + 1,
      team,
      manager: manager(team).name,
      source: "manual",
      syncKey: "manual-missing-recovery",
      sourceUrl: null,
      externalId: null,
      externalName: player.name,
      rawPlayerName: player.name,
      playerId: player.id,
      manualPlayerId: player.id,
      status: "resolved",
      resolutionStatus: "resolved",
      reasonCode: "SOURCE_PICK_MANUALLY_RECOVERED",
      unresolvedReasonCode: null,
      firstObservedAt: timestamp,
      lastObservedAt: timestamp,
      generation: state.generation,
    };
    const event = { overall: pick, team, playerId: player.id, source: "manual-recovery", status: "manual-recovery", syncKey: observation.syncKey, timestamp };
    state.sourceObservations.push(observation);
    state.sourceObservations = canonicalizeObservations(state.sourceObservations);
    state.events.push(event);
    state.events = canonicalizeEvents(state.events);
    appendAuditRecord("pick-recorded", event, state.events.filter((item) => item.overall < pick), {
      details: { reason: "missing-source-slot-manual-recovery", observationId: observation.observationId },
    });
    state.resolvingMissingOverall = null;
    els.removePick.hidden = false;
    els.rewindPick.hidden = false;
    els.pickDialog.close();
    renderCache = {};
    saveState();
    render();
    showToast(`${missingPickMessage(pick)} manually resolved with ${player.name}`);
    return true;
  }

  function removeEditingPick() {
    const event = editEvent(state.editingOverall);
    if (!event || !window.confirm(`Remove ${playerById(event.playerId).name} from ${pickLabel(event.overall)}? Later picks will stay in place until this slot is corrected.`)) return;
    const beforeEvents = state.events.map((item) => ({ ...item }));
    appendAuditRecord("pick-removed", event, beforeEvents, { details: { reason: "manual-removal" } });
    state.events = state.events.filter((item) => item.overall !== event.overall);
    removeManualObservation(event);
    saveState();
    els.pickDialog.close();
    render();
    showToast(`Removed pick ${pickLabel(event.overall)}`);
  }

  function removeManualObservation(event) {
    const observation = state.sourceObservations.find((item) => item.overall === event.overall && (item.manualPlayerId === event.playerId || item.source === "manual"));
    if (!observation) return;
    if (observation.source === "manual") {
      state.sourceObservations = state.sourceObservations.filter((item) => item !== observation);
      return;
    }
    observation.playerId = null;
    observation.manualPlayerId = null;
    observation.status = "unresolved";
    observation.resolutionStatus = "unresolved";
    observation.reasonCode = observation.unresolvedReasonCode || "PLAYER_NOT_ON_BOARD";
    observation.unresolvedReasonCode = observation.reasonCode;
    observation.reason = "manual mapping removed; player is not on the current board";
    observation.lastObservedAt = new Date().toISOString();
  }

  function rewindEditingPick() {
    const event = editEvent(state.editingOverall);
    if (!event) return;
    const affected = state.events.filter((item) => item.overall >= event.overall).length;
    if (!window.confirm(`Rewind modeled events to ${pickLabel(event.overall)}? This clears ${affected} roster event${affected === 1 ? "" : "s"}; source observations remain authoritative and may restore them.`)) return;
    const beforeEvents = state.events.map((item) => ({ ...item }));
    for (const removed of beforeEvents.filter((item) => item.overall >= event.overall)) {
      appendAuditRecord("pick-removed", removed, beforeEvents, { details: { reason: "rewind", rewindTo: event.overall } });
    }
    state.events = state.events.filter((item) => item.overall < event.overall);
    saveState();
    els.pickDialog.close();
    render();
    showToast(`Rewound draft to ${pickLabel(event.overall)}`);
  }

  function exportDraft() {
    const payload = statePayload();
    payload.managers = MANAGERS.slice(1);
    payload.keepers = KEEPERS;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `draft-command-backup-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast("Draft backup exported");
  }

  function exportAuditLog() {
    const payload = auditExportPayload();
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `draft-command-audit-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast("Decision and event log exported");
  }

  async function importDraft(file) {
    if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      if (Number(payload.schemaVersion) !== SCHEMA_VERSION || !Array.isArray(payload.events)) throw new Error("Unsupported backup format");
      const imported = canonicalizeEvents(payload.events);
      if (imported.length !== payload.events.length) throw new Error("Backup contains invalid or conflicting picks");
      if (!window.confirm(`Replace the current live draft with this backup containing ${imported.length} modeled events? Keeper-seed mode will match the backup.`)) return;
      applyPayload(payload);
      saveState();
      render();
      showToast("Draft backup restored");
    } catch (error) {
      showToast(error.message || "Could not import this backup");
    } finally {
      els.importDraftFile.value = "";
    }
  }

  function recoverPriorSnapshot() {
    const currentFingerprint = JSON.stringify([state.events, state.sourceObservations, state.keeperSeeds]);
    const prior = readSnapshots().slice().reverse().find((snapshot) => JSON.stringify([snapshot.events || [], snapshot.sourceObservations || [], snapshot.keeperSeeds || []]) !== currentFingerprint);
    if (!prior) {
      showToast("No earlier recovery snapshot is available");
      return;
    }
    const count = Array.isArray(prior.events) ? prior.events.length : 0;
    if (!window.confirm(`Recover the prior automatic snapshot with ${count} entered picks?`)) return;
    applyPayload(prior);
    saveState();
    render();
    showToast("Prior recovery snapshot restored");
  }

  function setKeeperMode(enabled, { force = false } = {}) {
    const desired = Boolean(enabled);
    if (desired === state.keeperMode) return true;
    if (state.sourceObservations.length && !force) {
      const message = `Changing keeper mode will perform Hard Reset Draft and clear the active draft before ${desired ? "loading" : "removing"} keeper seeds. Continue?`;
      if (!window.confirm(message)) return false;
      hardReset({ confirmed: true });
    }
    state.keeperMode = desired;
    state.keeperSeeds = desired ? canonicalizeKeeperSeeds(KEEPERS.map((keeper) => ({ ...keeper, source: "keeper-seed", status: "seeded" })), true) : [];
    appendAuditRecord(desired ? "keeper-seeds-loaded" : "keeper-seeds-removed", null, state.events, {
      details: { configured: KEEPERS.length, active: state.keeperSeeds.length },
    });
    renderCache = {};
    saveState();
    render();
    showToast(desired ? `${state.keeperSeeds.length} ESPN keeper seeds loaded` : "ESPN keeper seeds removed");
    return true;
  }

  function hardReset({ confirmed = false } = {}) {
    if (!confirmed) {
      const message = "WARNING: Do not Hard Reset after the real draft begins unless you intentionally want to restart the entire draft record. This clears the active draft, ESPN synchronization history, manual picks, active keeper seeds and audit events. League settings, managers, rankings, model data and the stored keeper template remain. Continue?";
      if (!window.confirm(message)) return false;
    }
    state.sourceIngestionPaused = true;
    const nextGeneration = state.generation + 1;
    const nextSessionId = createSessionId();
    state.events = [];
    state.sourceObservations = [];
    state.keeperMode = false;
    state.keeperSeeds = [];
    state.seedReconciliations = [];
    state.auditLog = [];
    state.editingOverall = null;
    state.resolvingObservationOverall = null;
    state.resolvingMissingOverall = null;
    state.visible = 20;
    state.sessionId = nextSessionId;
    state.generation = nextGeneration;
    opponentSimulationGeneration += 1;
    if (opponentSimulationTimer != null) clearTimeout(opponentSimulationTimer);
    opponentSimulationTimer = null;
    opponentWorker?.terminate?.();
    opponentWorker = null;
    opponentContext = { signature: null, status: "loading", board: null, threat: null, liveState: null, window: null, error: null };
    for (const key of [STORE_KEY, ...LEGACY_STORE_KEYS, SNAPSHOT_KEY, ...LEGACY_SNAPSHOT_KEYS, SYNC_SETTINGS_KEY]) localStorage.removeItem(key);
    renderCache = {};
    saveState({ snapshot: false });
    render();
    window.dispatchEvent(new CustomEvent("draft-command-hard-reset", {
      detail: { resetAt: new Date().toISOString(), sessionId: nextSessionId, generation: nextGeneration, appRelease: APP_RELEASE },
    }));
    showToast("Draft hard reset complete · ESPN paused · keeper seeds off");
    return true;
  }

  function resumeSourceIngestion(details = {}) {
    state.sourceIngestionPaused = false;
    recordSystemAudit("bridge-reconnected", { source: details.source || "espn-bridge", bridgeVersion: details.bridgeVersion || null });
    return true;
  }

  let toastTimer;
  function showToast(message) {
    els.toast.textContent = message;
    els.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2600);
  }

  document.addEventListener("click", (event) => {
    const draft = event.target.closest("[data-draft-id]");
    if (draft) draftPlayer(draft.dataset.draftId);
    const platform = event.target.closest("[data-platform]");
    if (platform) {
      state.platform = platform.dataset.platform;
      saveState({ snapshot: false });
      render();
    }
    const filter = event.target.closest("[data-pos]");
    if (filter) {
      state.position = filter.dataset.pos;
      state.visible = 20;
      document.querySelectorAll(".filter-btn").forEach((button) => button.classList.toggle("active", button === filter));
      renderBoard();
    }
    const edit = event.target.closest("[data-edit-pick]");
    if (edit) openEditDialog(edit.dataset.editPick);
    const replacement = event.target.closest("[data-replace-id]");
    if (replacement) replacePick(replacement.dataset.replaceId);
    const unresolved = event.target.closest("[data-resolve-observation]");
    if (unresolved) openObservationDialog(unresolved.dataset.resolveObservation);
    const missing = event.target.closest("[data-resolve-missing]");
    if (missing) openMissingDialog(missing.dataset.resolveMissing);
    const boardSort = event.target.closest("[data-board-sort]");
    if (boardSort) setBoardSort(boardSort.dataset.boardSort);
    const opponentSort = event.target.closest("[data-opponent-sort]");
    if (opponentSort) setOpponentSort(opponentSort.dataset.opponentSort);
  });

  els.playerSearch.addEventListener("input", (event) => {
    state.search = event.target.value;
    state.visible = 20;
    renderBoard();
  });
  els.replacementSearch.addEventListener("input", renderReplacementList);
  els.loadMore.addEventListener("click", () => { state.visible += 20; renderBoard(); });
  els.rosterManager.addEventListener("change", (event) => {
    state.rosterTeam = Number(event.target.value);
    saveState({ snapshot: false });
    renderRoster();
  });
  els.undoPick.addEventListener("click", () => {
    const removed = state.events.slice().sort((a, b) => b.overall - a.overall)[0];
    if (!isManualEvent(removed)) return;
    appendAuditRecord("pick-removed", removed, state.events, { details: { reason: "undo" } });
    state.events = state.events.filter((event) => event.overall !== removed.overall);
    removeManualObservation(removed);
    saveState();
    render();
    showToast(`Undid pick ${pickLabel(removed.overall)}`);
  });
  els.resetDraft.addEventListener("click", () => {
    hardReset();
  });
  els.keeperToggle.addEventListener("click", () => setKeeperMode(!state.keeperMode));
  els.exportDraft.addEventListener("click", exportDraft);
  els.exportAuditLog.addEventListener("click", exportAuditLog);
  els.importDraft.addEventListener("click", () => els.importDraftFile.click());
  els.importDraftFile.addEventListener("change", (event) => importDraft(event.target.files?.[0]));
  els.recoverDraft.addEventListener("click", recoverPriorSnapshot);
  els.removePick.addEventListener("click", removeEditingPick);
  els.rewindPick.addEventListener("click", rewindEditingPick);

  window.DraftCommandLive = Object.freeze({
    ingestSnapshot,
    resolvePlayer: (rawPick) => resolveExternalPlayer(rawPick),
    profile: Object.freeze({ teamCount: TEAM_COUNT, rounds: ROUNDS, platform: "espn", league: "Tony 2026 ESPN keeper league" }),
    state: () => ({
      events: state.events.map((event) => ({ ...event })),
      modeledEvents: state.events.map((event) => ({ ...event })),
      sourceObservations: state.sourceObservations.map((observation) => ({ ...observation })),
      keeperMode: state.keeperMode,
      keeperSeeds: state.keeperSeeds.map((seed) => ({ ...seed })),
      seedReconciliations: state.seedReconciliations.map((item) => ({ ...item })),
      auditLog: state.auditLog.map((record) => structuredClone(record)),
      currentPick: currentPick(), sessionId: state.sessionId, generation: state.generation, sourceIngestionPaused: state.sourceIngestionPaused,
    }),
    syncIdentity: () => ({ sessionId: state.sessionId, generation: state.generation, appRelease: APP_RELEASE }),
    setKeeperMode,
    resolveObservation,
    resolveMissingPick,
    hardReset,
    resumeSourceIngestion,
    recordSyncDiagnostic: (action, details = {}) => recordSystemAudit(action, { source: "espn-bridge", ...details }),
    issues: () => structuredClone(draftIssues()),
    configuredKeepers: () => KEEPERS.map((keeper) => ({ ...keeper })),
    recordManualPick: draftPlayer,
    auditExport: () => structuredClone(auditExportPayload()),
    modelHealth: () => modelHealth(),
    runtimeAudit: () => structuredClone(RUNTIME?.auditMetadata() || null),
    playerIntelligence: (playerId) => ({
      playerTruth: structuredClone(RUNTIME?.playerTruth(playerId) || null),
      market: structuredClone(RUNTIME?.market(playerId) || null),
      leagueValue: structuredClone(RUNTIME?.leagueValue(playerId) || null),
      approvedException: structuredClone(RUNTIME?.approvedException(playerId) || null),
    }),
    opponentModelHealth: () => OPPONENT_INTENT?.health() || { mode: "fallback", valid: false, errors: ["runtime missing"] },
    opponentBoard: () => structuredClone(opponentContext.board || OPPONENT_INTENT?.fullBoard({ currentOverallPick: currentPick(), nextTonyPick: nextTonyPick(currentPick()), liveState: opponentLiveState() }) || { opponents: [] }),
    opponentWindow: (options = {}) => {
      if (!OPPONENT_INTENT) return null;
      const windowState = opponentThreatWindow();
      if (!windowState.nextTony) return null;
      return OPPONENT_INTENT.simulateTonyWindow({
        currentOverallPick: windowState.start,
        nextTonyPick: windowState.nextTony,
        liveState: opponentLiveState(),
        targetPlayerIds: options.targetPlayerIds || availablePlayers().map((player) => player.id),
        tiers: options.tiers || {},
        simulations: options.simulations || 100,
        seed: options.seed || 20260831,
      });
    },
    recommendations: () => recommendations(),
    setBoardSort,
    setPositionFilter: (position) => {
      state.position = ["ALL", "QB", "RB", "WR", "TE"].includes(position) ? position : "ALL";
      state.visible = 20;
      renderBoard();
    },
    setPlayerSearch: (search) => {
      state.search = String(search || "");
      state.visible = 20;
      renderBoard();
    },
    boardSort: () => ({ ...state.boardSort }),
    decisionBoard: (sort = state.boardSort, platform = state.platform) => boardRows(platform, sort).map((player) => {
      const threat = threatFor(player);
      return {
        id: player.id, name: player.name, position: player.pos, leagueValue: leagueScore(player), roomRank: price(player, platform),
        espnAdp: espnAdp(player), probabilityTakenBeforeTony: threat?.probabilityTakenBeforeTony ?? null,
        opponentThreat: threat?.mostLikelyTaker?.probability ?? null,
      };
    }),
    boardOrder: (platform = state.platform, sort = state.boardSort) => boardRows(platform, sort).map((player) => ({
      id: player.id,
      name: player.name,
      pos: player.pos,
      roomRank: price(player, platform),
      leagueRank: leagueRank(player),
      leagueScore: leagueScore(player),
    })),
  });

  els.rosterManager.innerHTML = MANAGERS.slice(1).map((item) => `<option value="${item.id}">${item.id}. ${item.name}</option>`).join("");
  RUNTIME?.onChange(() => {
    renderCache = {};
    render();
  });
  loadState();
  renderKeepers();
  render();
  if (RUNTIME && !window.DRAFT_RUNTIME_BUNDLE) RUNTIME.start();
})();
