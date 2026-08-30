(() => {
  "use strict";

  const EVENT_NAME = "draft-command-espn-state";
  const picks = new Map();
  const meta = { teamCount: null, rounds: null };
  let lastFingerprint = "";
  let lastEmit = 0;
  let lastDetection = "waiting";

  const numberFrom = (...values) => {
    for (const value of values) {
      const parsed = Number(value);
      if (Number.isInteger(parsed) && parsed > 0) return parsed;
    }
    return null;
  };

  function nameFrom(value) {
    if (!value || typeof value !== "object") return "";
    const direct = value.fullName || value.displayName || value.playerName || value.athleteName || value.name;
    if (typeof direct === "string" && direct.trim().split(/\s+/).length >= 2) return direct.trim();
    const first = value.firstName || value.first_name;
    const last = value.lastName || value.last_name;
    return first && last ? `${first} ${last}` : "";
  }

  function playerObjectFrom(value) {
    const candidates = [value.player, value.athlete, value.proPlayer, value.selectedPlayer, value.draftedPlayer, value.playerCard];
    return candidates.find((candidate) => candidate && typeof candidate === "object") || value;
  }

  function candidateFrom(value, path) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const markerKeys = ["pickNumber", "overallPick", "overallPickNumber", "selectionNumber", "draftPickNumber", "pick_no"];
    const hasMarker = markerKeys.some((key) => Object.prototype.hasOwnProperty.call(value, key));
    const draftPath = /draft|pick|selection/i.test(path);
    if (!hasMarker && !draftPath) return null;

    const player = playerObjectFrom(value);
    const playerName = nameFrom(player) || nameFrom(value);
    const overall = numberFrom(value.pickNumber, value.overallPick, value.overallPickNumber, value.selectionNumber, value.draftPickNumber, value.pick_no);
    if (!overall || !playerName || overall > 500) return null;

    const externalId = player.id || player.playerId || player.player_id || player.athleteId || value.playerId || value.athleteId || null;
    return {
      overall,
      playerName,
      externalId,
      position: player.position?.abbrev || player.position?.name || player.positionAbbrev || player.position || value.position || null,
      nflTeam: player.proTeam?.abbrev || player.team?.abbrev || player.proTeamAbbrev || player.teamAbbrev || value.proTeamAbbrev || null,
    };
  }

  function scanObject(root, path = "root", limit = 30000) {
    const seen = new WeakSet();
    const queue = [{ value: root, path }];
    let queueIndex = 0;
    let scanned = 0;
    let found = 0;
    while (queueIndex < queue.length && scanned < limit) {
      const current = queue[queueIndex];
      queueIndex += 1;
      const value = current.value;
      if (!value || typeof value !== "object" || seen.has(value)) continue;
      if (value.nodeType || value === window || value === document) continue;
      seen.add(value);
      scanned += 1;

      const candidate = candidateFrom(value, current.path);
      if (candidate) {
        const existing = picks.get(candidate.overall);
        if (!existing || existing.playerName !== candidate.playerName) picks.set(candidate.overall, candidate);
        found += 1;
      }

      const possibleTeams = numberFrom(value.teamCount, value.teams, value.numberOfTeams, value.leagueSize, value.settings?.teams);
      const possibleRounds = numberFrom(value.rounds, value.numberOfRounds, value.settings?.rounds);
      if (possibleTeams && possibleTeams <= 32) meta.teamCount = possibleTeams;
      if (possibleRounds && possibleRounds <= 40) meta.rounds = possibleRounds;

      for (const [key, child] of Object.entries(value)) {
        if (!child || typeof child !== "object") continue;
        if (/^_?ownerDocument$|^parent(Node|Element)?$|^window$|^document$/.test(key)) continue;
        queue.push({ value: child, path: `${current.path}.${key}` });
      }
    }
    return { found, scanned };
  }

  function emit(force = false) {
    const ordered = [...picks.values()].sort((a, b) => a.overall - b.overall);
    const fingerprint = JSON.stringify(ordered.map((pick) => [pick.overall, pick.playerName]));
    if (!force && fingerprint === lastFingerprint && Date.now() - lastEmit < 4000) return;
    lastFingerprint = fingerprint;
    lastEmit = Date.now();
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: {
      source: "espn",
      syncKey: `espn:${location.pathname}${location.search}`,
      teamCount: meta.teamCount,
      rounds: meta.rounds,
      picks: ordered,
      authoritative: false,
      completeThrough: ordered.reduce((max, pick) => Math.max(max, pick.overall), 0),
      timestamp: new Date().toISOString(),
      detectedBy: lastDetection,
      espnUrl: location.href,
    } }));
  }

  function inspectPayload(payload, detectedBy) {
    try {
      const result = scanObject(payload, detectedBy);
      if (result.found) lastDetection = detectedBy;
      emit(result.found > 0);
    } catch (_) { /* ESPN responses may contain unsupported objects */ }
  }

  const originalFetch = window.fetch;
  if (originalFetch) {
    window.fetch = async function draftCommandFetch(...args) {
      const response = await originalFetch.apply(this, args);
      response.clone().json().then((payload) => inspectPayload(payload, "fetch")).catch(() => {});
      return response;
    };
  }

  const originalOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function draftCommandOpen(method, url, ...rest) {
    this.__draftCommandUrl = String(url || "");
    this.addEventListener("load", () => {
      if (!/draft|pick|fantasy/i.test(this.__draftCommandUrl || "")) return;
      try { inspectPayload(JSON.parse(this.responseText), "xhr"); } catch (_) { /* non-JSON response */ }
    }, { once: true });
    return originalOpen.call(this, method, url, ...rest);
  };

  const OriginalWebSocket = window.WebSocket;
  if (OriginalWebSocket) {
    window.WebSocket = function DraftCommandWebSocket(...args) {
      const socket = new OriginalWebSocket(...args);
      socket.addEventListener("message", (event) => {
        if (typeof event.data !== "string" || !/[{[]/.test(event.data)) return;
        try { inspectPayload(JSON.parse(event.data), "websocket"); } catch (_) { /* non-JSON frame */ }
      });
      return socket;
    };
    window.WebSocket.prototype = OriginalWebSocket.prototype;
    for (const key of ["CONNECTING", "OPEN", "CLOSING", "CLOSED"]) {
      Object.defineProperty(window.WebSocket, key, { value: OriginalWebSocket[key] });
    }
  }

  function scanReact() {
    const roots = [document.getElementById("root"), document.querySelector("[id*='draft']"), document.body].filter(Boolean);
    const elements = document.querySelectorAll("*");
    for (let index = 0; index < Math.min(elements.length, 1600); index += 1) {
      const element = elements[index];
      const key = Object.keys(element).find((name) => name.startsWith("__reactFiber$") || name.startsWith("__reactInternalInstance$") || name.startsWith("_reactRootContainer"));
      if (key) roots.push(element[key]);
    }
    let found = 0;
    for (const root of roots.slice(0, 20)) found += scanObject(root, "react", 12000).found;
    if (found) lastDetection = "react";
    emit(found > 0);
  }

  setInterval(scanReact, 2000);
  setInterval(() => emit(true), 5000);
  window.addEventListener("load", () => setTimeout(scanReact, 500));
  emit(true);
})();
