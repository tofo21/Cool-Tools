(() => {
  "use strict";

  const STORE_KEY = "draft-command-live-sync-v1";
  const POLL_MS = 3000;
  const els = Object.fromEntries([
    "syncState", "syncIssues", "syncFoot", "espnSyncMessage", "espnCheckBridge",
    "sleeperDraftId", "sleeperConnect", "sleeperSyncNow", "sleeperSyncMessage",
  ].map((id) => [id, document.getElementById(id)]));

  const state = {
    source: "manual",
    sleeperDraftId: "",
    sleeperConnected: false,
    sleeperStatus: null,
    sleeperTimer: null,
    sleeperBusy: false,
    sleeperFailures: 0,
    espnLastSeen: 0,
    espnDetails: null,
    espnPaused: false,
    espnResetPending: false,
  };

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE_KEY));
      if (["manual", "espn", "sleeper"].includes(saved?.source)) state.source = saved.source;
      if (saved?.sleeperDraftId) state.sleeperDraftId = String(saved.sleeperDraftId);
    } catch (_) { /* ignore malformed sync settings */ }
  }

  function saveState() {
    localStorage.setItem(STORE_KEY, JSON.stringify({ source: state.source, sleeperDraftId: state.sleeperDraftId }));
  }

  function extractDraftId(value) {
    const matches = String(value || "").match(/\d{10,}/g);
    return matches?.at(-1) || "";
  }

  function timeLabel(timestamp = Date.now()) {
    return new Date(timestamp).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
  }

  function setStatus(kind, label) {
    els.syncState.className = `sync-state sync-${kind}`;
    els.syncState.querySelector("span").textContent = label;
  }

  function showIssues(result) {
    const issues = [...(result?.unresolved || []), ...(result?.conflicts || [])];
    els.syncIssues.hidden = !issues.length;
    els.syncIssues.innerHTML = issues.length ? `<strong>${issues.length} pick${issues.length === 1 ? "" : "s"} need attention</strong>${issues.slice(0, 6).map((issue) => `<span>${issue.overall ? `#${issue.overall} · ` : ""}${issue.playerName || "Unknown"}: ${issue.reason}</span>`).join("")}${issues.length > 6 ? `<small>+${issues.length - 6} more</small>` : ""}` : "";
  }

  function renderSource() {
    document.querySelectorAll("[data-sync-source]").forEach((button) => button.classList.toggle("active", button.dataset.syncSource === state.source));
    document.querySelectorAll("[data-sync-view]").forEach((view) => { view.hidden = view.dataset.syncView !== state.source; });
    if (state.source === "manual") {
      setStatus("idle", "Manual");
      els.syncFoot.textContent = state.espnResetPending
        ? "Clearing the ESPN bridge cache…"
        : state.espnPaused
          ? "ESPN cache cleared and paused. Open the next draft room, then select ESPN."
          : "No automatic source connected.";
    } else if (state.source === "espn") {
      renderEspnStatus();
    } else {
      renderSleeperStatus();
    }
  }

  function postBridgeCommand(type) {
    const identity = window.DraftCommandLive.syncIdentity();
    window.postMessage({ source: "draft-command-app", type, timestamp: Date.now(), ...identity }, window.location.origin);
  }

  function resumeEspnBridge() {
    window.DraftCommandLive.resumeSourceIngestion({ source: "espn-bridge", bridgeVersion: state.espnDetails?.bridgeVersion || null });
    state.espnPaused = false;
    state.espnResetPending = false;
    state.espnLastSeen = 0;
    state.espnDetails = null;
    postBridgeCommand("ESPN_BRIDGE_RESUME");
    setTimeout(requestEspnStatus, 200);
  }

  function clearEspnBridge(resetDetail = {}) {
    stopSleeperPolling();
    state.source = "manual";
    if (resetDetail?.sessionId) {
      state.sleeperDraftId = "";
      state.sleeperStatus = null;
      state.sleeperFailures = 0;
      els.sleeperDraftId.value = "";
    }
    state.espnPaused = true;
    state.espnResetPending = true;
    state.espnLastSeen = 0;
    state.espnDetails = null;
    saveState();
    renderSource();
    window.DraftCommandLive.recordSyncDiagnostic("bridge-clear-requested", { bridgeVersion: state.espnDetails?.bridgeVersion || null, resetAt: resetDetail?.resetAt || null });
    const identity = window.DraftCommandLive.syncIdentity();
    window.postMessage({ source: "draft-command-app", type: "ESPN_BRIDGE_HARD_RESET", timestamp: Date.now(), ...identity, ...resetDetail }, window.location.origin);
  }

  function selectSource(source) {
    state.source = source;
    if (source !== "sleeper") stopSleeperPolling();
    if (source === "espn" || source === "sleeper") document.querySelector(`[data-platform="${source}"]`)?.click();
    saveState();
    renderSource();
    if (source === "espn") resumeEspnBridge();
    if (source === "sleeper" && state.sleeperDraftId) connectSleeper();
  }

  function renderEspnStatus() {
    if (state.espnPaused) {
      setStatus("waiting", "ESPN paused");
      els.espnSyncMessage.textContent = "Bridge paused for this new draft session. Open the intended ESPN room, then click Check / resume ESPN.";
      els.syncFoot.textContent = "No cached ESPN picks can enter the board while paused.";
      return;
    }
    const age = Date.now() - state.espnLastSeen;
    if (state.espnLastSeen && age < 12000) {
      setStatus("live", "ESPN live");
      const pickCount = Number(state.espnDetails?.pickCount || 0);
      els.espnSyncMessage.textContent = `Bridge connected${pickCount ? ` · ${pickCount} ESPN picks detected` : " · waiting for the draft room"}.`;
      els.syncFoot.textContent = `ESPN bridge ${state.espnDetails?.bridgeVersion || "version unknown"} checked ${timeLabel(state.espnLastSeen)}.`;
    } else {
      setStatus("waiting", "ESPN waiting");
      els.espnSyncMessage.textContent = "Bridge not detected yet. Install it, then keep the ESPN draft room and Draft Command open in the same browser.";
      els.syncFoot.textContent = "Waiting for the local ESPN bridge.";
    }
  }

  function requestEspnStatus() {
    if (state.source !== "espn") return;
    if (state.espnPaused) {
      resumeEspnBridge();
      return;
    }
    postBridgeCommand("ESPN_BRIDGE_PING");
    setTimeout(() => { if (state.source === "espn") renderEspnStatus(); }, 800);
  }

  function handleEspnMessage(message) {
    if (message?.source !== "draft-command-espn-bridge") return;

    const identity = window.DraftCommandLive.syncIdentity();
    if (message.details?.generation != null && Number(message.details.generation) !== identity.generation) {
      window.DraftCommandLive.recordSyncDiagnostic("bridge-stale-rejected", { receivedGeneration: Number(message.details.generation), bridgeVersion: message.details?.bridgeVersion || null });
      return;
    }
    if (message.details?.sessionId && message.details.sessionId !== identity.sessionId) {
      window.DraftCommandLive.recordSyncDiagnostic("bridge-stale-rejected", { receivedSessionId: message.details.sessionId, bridgeVersion: message.details?.bridgeVersion || null });
      return;
    }
    if (message.details?.staleRejected) window.DraftCommandLive.recordSyncDiagnostic("bridge-stale-rejected", { bridgeVersion: message.details?.bridgeVersion || null, reason: "extension-storage-generation-mismatch" });

    if (message.type === "ESPN_BRIDGE_CLEARED") {
      state.espnPaused = true;
      state.espnResetPending = false;
      state.espnLastSeen = 0;
      state.espnDetails = message.details || null;
      window.DraftCommandLive.recordSyncDiagnostic("bridge-cleared-paused", { bridgeVersion: message.details?.bridgeVersion || null });
      renderSource();
      return;
    }

    if (message.type === "ESPN_BRIDGE_RESUMED") {
      state.espnPaused = false;
      state.espnResetPending = false;
      state.espnLastSeen = Date.now();
      state.espnDetails = message.details || null;
      window.DraftCommandLive.recordSyncDiagnostic("bridge-resumed", { bridgeVersion: message.details?.bridgeVersion || null });
      if (state.source === "espn") renderEspnStatus();
      return;
    }

    state.espnLastSeen = Date.now();
    state.espnDetails = message.details || state.espnDetails;
    state.espnPaused = Boolean(message.details?.paused);
    if (message.type === "ESPN_PICKS" && state.source === "espn" && !state.espnPaused && message.snapshot) {
      const result = window.DraftCommandLive.ingestSnapshot({
        ...message.snapshot,
        source: "espn",
        syncKey: message.snapshot.syncKey || "espn:draft-room",
        authoritative: Boolean(message.snapshot.authoritative),
        sessionId: message.details?.sessionId,
        generation: message.details?.generation,
        bridgeVersion: message.details?.bridgeVersion,
      });
      showIssues(result);
      if (!result.ok) {
        setStatus("error", "ESPN blocked");
        els.espnSyncMessage.textContent = result.message;
      }
    }
    if (state.source === "espn") renderEspnStatus();
  }

  function renderSleeperStatus() {
    if (state.sleeperStatus?.kind === "error") {
      setStatus("error", "Sleeper blocked");
      els.sleeperSyncMessage.textContent = state.sleeperStatus.message;
    } else if (state.sleeperConnected) {
      setStatus("live", "Sleeper live");
      els.sleeperSyncMessage.textContent = `Connected to draft ${state.sleeperDraftId}${state.sleeperStatus?.draftStatus ? ` · ${state.sleeperStatus.draftStatus.replace(/_/g, " ")}` : ""}.`;
    } else if (state.sleeperBusy) {
      setStatus("waiting", "Connecting");
      els.sleeperSyncMessage.textContent = "Checking the Sleeper draft and league format…";
    } else {
      setStatus("waiting", "Sleeper waiting");
      els.sleeperSyncMessage.textContent = "Enter a Sleeper draft URL or ID. The format must match this 10-team, 16-round board.";
    }
  }

  function stopSleeperPolling() {
    clearInterval(state.sleeperTimer);
    state.sleeperTimer = null;
    state.sleeperConnected = false;
  }

  function startSleeperPolling() {
    clearInterval(state.sleeperTimer);
    state.sleeperTimer = setInterval(() => {
      if (!document.hidden && state.source === "sleeper") syncSleeper(false);
    }, POLL_MS);
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Sleeper returned HTTP ${response.status}`);
    return response.json();
  }

  function sleeperSnapshot(draft, picks) {
    const normalizedPicks = picks.map((pick) => ({
      overall: Number(pick.pick_no),
      playerName: pick.metadata?.first_name && pick.metadata?.last_name ? `${pick.metadata.first_name} ${pick.metadata.last_name}` : pick.metadata?.name || pick.player_name,
      firstName: pick.metadata?.first_name,
      lastName: pick.metadata?.last_name,
      position: pick.metadata?.position,
      nflTeam: pick.metadata?.team,
      externalId: pick.player_id,
      rosterId: pick.roster_id,
      draftSlot: pick.draft_slot,
    }));
    return {
      source: "sleeper",
      syncKey: `sleeper:${draft.draft_id}`,
      teamCount: Number(draft.settings?.teams),
      rounds: Number(draft.settings?.rounds),
      picks: normalizedPicks,
      authoritative: true,
      completeThrough: normalizedPicks.reduce((max, pick) => Math.max(max, pick.overall || 0), 0),
      timestamp: new Date().toISOString(),
    };
  }

  async function syncSleeper(userInitiated = false) {
    if (state.sleeperBusy || !state.sleeperDraftId) return;
    state.sleeperBusy = true;
    if (state.source === "sleeper") renderSleeperStatus();
    try {
      const [draft, picks] = await Promise.all([
        fetchJson(`https://api.sleeper.app/v1/draft/${state.sleeperDraftId}`),
        fetchJson(`https://api.sleeper.app/v1/draft/${state.sleeperDraftId}/picks`),
      ]);
      const snapshot = sleeperSnapshot(draft, picks);
      const result = window.DraftCommandLive.ingestSnapshot(snapshot);
      showIssues(result);
      if (!result.ok) {
        stopSleeperPolling();
        state.sleeperStatus = { kind: "error", message: result.message, draftStatus: draft.status };
      } else {
        state.sleeperConnected = true;
        state.sleeperFailures = 0;
        state.sleeperStatus = { kind: "live", draftStatus: draft.status };
        els.syncFoot.textContent = `Sleeper checked ${timeLabel()} · ${picks.length} source picks · ${result.added} added · ${result.matched} matched.`;
        if (!state.sleeperTimer) startSleeperPolling();
      }
    } catch (error) {
      state.sleeperFailures += 1;
      state.sleeperStatus = { kind: "error", message: error.message || "Could not reach Sleeper." };
      if (state.sleeperFailures >= 3) stopSleeperPolling();
      if (userInitiated) showIssues({ unresolved: [{ playerName: "Connection", reason: state.sleeperStatus.message }] });
    } finally {
      state.sleeperBusy = false;
      if (state.source === "sleeper") renderSleeperStatus();
    }
  }

  function connectSleeper() {
    const draftId = extractDraftId(els.sleeperDraftId.value || state.sleeperDraftId);
    if (!draftId) {
      state.sleeperStatus = { kind: "error", message: "Paste a valid Sleeper draft URL or numeric draft ID." };
      renderSleeperStatus();
      return;
    }
    stopSleeperPolling();
    window.DraftCommandLive.resumeSourceIngestion({ source: "sleeper" });
    state.sleeperDraftId = draftId;
    state.sleeperStatus = null;
    state.sleeperFailures = 0;
    els.sleeperDraftId.value = draftId;
    saveState();
    syncSleeper(true);
  }

  document.addEventListener("click", (event) => {
    const sourceButton = event.target.closest("[data-sync-source]");
    if (sourceButton) selectSource(sourceButton.dataset.syncSource);
  });
  els.espnCheckBridge.addEventListener("click", requestEspnStatus);
  els.sleeperConnect.addEventListener("click", connectSleeper);
  els.sleeperSyncNow.addEventListener("click", () => {
    if (!state.sleeperDraftId) connectSleeper();
    else syncSleeper(true);
  });
  els.sleeperDraftId.addEventListener("keydown", (event) => { if (event.key === "Enter") connectSleeper(); });
  window.addEventListener("message", (event) => {
    if (event.source === window && event.origin === window.location.origin) handleEspnMessage(event.data);
  });
  window.addEventListener("draft-command-hard-reset", (event) => clearEspnBridge(event.detail || {}));
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.source === "sleeper" && state.sleeperDraftId) syncSleeper(false);
  });
  setInterval(() => { if (state.source === "espn") renderEspnStatus(); }, 5000);

  window.DraftCommandSync = Object.freeze({
    clearEspnCache: clearEspnBridge,
    resumeEspn: () => selectSource("espn"),
    state: () => ({
      source: state.source,
      espnPaused: state.espnPaused,
      espnResetPending: state.espnResetPending,
      espnLastSeen: state.espnLastSeen,
    }),
  });

  loadState();
  els.sleeperDraftId.value = state.sleeperDraftId;
  renderSource();
  if (state.source === "espn") resumeEspnBridge();
  if (state.source === "sleeper" && state.sleeperDraftId) connectSleeper();
})();
