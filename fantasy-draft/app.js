(() => {
  "use strict";

  const TONY_TEAM = 5;
  const TEAM_COUNT = 10;
  const ROUNDS = 16;
  const TOTAL_PICKS = TEAM_COUNT * ROUNDS;
  const TONY_PICKS = [5, 16, 25, 36, 45, 56, 65, 76, 85, 96, 105, 116, 125, 136, 145, 156];
  const TARGETS = { QB: 2, RB: 5, WR: 7, TE: 2 };
  const STORE_KEY = "draft-command-2026-v2";
  const LEGACY_STORE_KEY = "draft-command-2026-v1";
  const SNAPSHOT_KEY = "draft-command-2026-snapshots-v2";
  const SCHEMA_VERSION = 2;

  const MANAGERS = [
    null,
    { id: 1, name: "Justin Gerkin", short: "Gerkin" },
    { id: 2, name: "Dan Merrick", short: "Dan" },
    { id: 3, name: "Matt Castleman", short: "Castleman" },
    { id: 4, name: "Matt Hull", short: "Hull" },
    { id: 5, name: "Tony Fontana", short: "Tony" },
    { id: 6, name: "Matt Runge", short: "Runge" },
    { id: 7, name: "Jon Merrick", short: "Jon" },
    { id: 8, name: "Matt Sloka", short: "Sloka" },
    { id: 9, name: "Kyle Cavanaugh", short: "Kyle" },
    { id: 10, name: "Brenden Lautenbach", short: "Brenden" },
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
    platform: "espn",
    position: "ALL",
    search: "",
    visible: 20,
    rosterTeam: TONY_TEAM,
    editingOverall: null,
  };

  const PLAYER_BY_ID = new Map(window.PLAYER_DATA.map((player) => [player.id, player]));
  let renderCache = {};

  const els = Object.fromEntries([
    "roundPick", "overallPick", "clockOwner", "draftProgress", "nextTonyText", "pickMap",
    "decisionWindow", "workspaceTitle", "bestOverallCard", "bestValueCard", "bestFitCard",
    "decisionStrip", "playerSearch", "playerTable", "boardCount", "loadMore", "rosterCount",
    "rosterNeeds", "rosterList", "rosterManager", "rosterManagerName", "historyList", "undoPick",
    "cliffPanel", "platformHeader", "toast", "saveStatus", "keeperList", "resetDraft",
    "exportDraft", "importDraft", "importDraftFile", "recoverDraft", "pickDialog", "dialogTitle",
    "dialogCopy", "replacementSearch", "replacementList", "removePick", "rewindPick",
  ].map((id) => [id, document.getElementById(id)]));

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
  const KEEPER_OVERALLS = new Set(KEEPERS.map((keeper) => keeper.overall));
  const KEEPER_PLAYER_IDS = new Set(KEEPERS.map((keeper) => keeper.playerId));

  function playerById(id) {
    return PLAYER_BY_ID.get(Number(id));
  }

  function canonicalizeEvents(events) {
    const usedOveralls = new Set();
    const usedPlayers = new Set(KEEPER_PLAYER_IDS);
    return (Array.isArray(events) ? events : []).map((event) => ({
      overall: Number(event.overall),
      team: Number(event.team),
      playerId: Number(event.playerId),
      source: event.source || "manual",
      timestamp: event.timestamp || new Date().toISOString(),
    })).filter((event) => {
      if (!Number.isInteger(event.overall) || event.overall < 1 || event.overall > TOTAL_PICKS) return false;
      if (KEEPER_OVERALLS.has(event.overall) || KEEPER_PLAYER_IDS.has(event.playerId)) return false;
      if (!playerById(event.playerId) || pickOwner(event.overall) !== event.team) return false;
      if (usedOveralls.has(event.overall) || usedPlayers.has(event.playerId)) return false;
      usedOveralls.add(event.overall);
      usedPlayers.add(event.playerId);
      return true;
    }).sort((a, b) => a.overall - b.overall);
  }

  function statePayload() {
    return {
      schemaVersion: SCHEMA_VERSION,
      league: "Tony 2026 ESPN keeper league",
      savedAt: new Date().toISOString(),
      platform: state.platform,
      rosterTeam: state.rosterTeam,
      events: state.events,
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

  function updateSaveStatus(savedAt) {
    if (!els.saveStatus) return;
    const time = new Date(savedAt);
    els.saveStatus.textContent = Number.isNaN(time.getTime()) ? "Recovery ready" : `Saved ${time.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  }

  function saveState({ snapshot = true } = {}) {
    const payload = statePayload();
    localStorage.setItem(STORE_KEY, JSON.stringify(payload));
    if (snapshot) {
      const snapshots = readSnapshots();
      const fingerprint = JSON.stringify(payload.events);
      const lastFingerprint = snapshots.length ? JSON.stringify(snapshots[snapshots.length - 1].events || []) : null;
      if (fingerprint !== lastFingerprint) {
        snapshots.push(payload);
        localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(snapshots.slice(-12)));
      }
    }
    updateSaveStatus(payload.savedAt);
  }

  function applyPayload(payload) {
    state.events = canonicalizeEvents(payload?.events || payload?.picks || []);
    state.platform = payload?.platform === "sleeper" ? "sleeper" : "espn";
    const rosterTeam = Number(payload?.rosterTeam);
    state.rosterTeam = rosterTeam >= 1 && rosterTeam <= TEAM_COUNT ? rosterTeam : TONY_TEAM;
  }

  function migrateLegacyEvents(picks) {
    const events = [];
    const usedPlayers = new Set(KEEPER_PLAYER_IDS);
    let overall = 1;
    for (const oldPick of Array.isArray(picks) ? picks : []) {
      const playerId = Number(oldPick.playerId);
      if (!playerById(playerId) || usedPlayers.has(playerId)) continue;
      while (overall <= TOTAL_PICKS && KEEPER_OVERALLS.has(overall)) overall += 1;
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
        const legacy = JSON.parse(localStorage.getItem(LEGACY_STORE_KEY));
        if (legacy) saved = legacy;
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
    saveState({ snapshot: false });
  }

  function allEvents() {
    if (!renderCache.allEvents) renderCache.allEvents = [...KEEPERS, ...state.events].sort((a, b) => a.overall - b.overall);
    return renderCache.allEvents;
  }

  function eventAt(overall) {
    if (!renderCache.eventsByOverall) renderCache.eventsByOverall = new Map(allEvents().map((event) => [event.overall, event]));
    return renderCache.eventsByOverall.get(overall) || null;
  }

  function currentPick() {
    if (renderCache.currentPick) return renderCache.currentPick;
    for (let overall = 1; overall <= TOTAL_PICKS; overall += 1) {
      if (!eventAt(overall)) {
        renderCache.currentPick = overall;
        return overall;
      }
    }
    renderCache.currentPick = TOTAL_PICKS + 1;
    return renderCache.currentPick;
  }

  function nextTonyPick(from = currentPick()) {
    return TONY_PICKS.find((pick) => pick >= from && !KEEPER_OVERALLS.has(pick) && !eventAt(pick)) || null;
  }

  function followingTonyPick(from) {
    return TONY_PICKS.find((pick) => pick > from && !KEEPER_OVERALLS.has(pick) && !eventAt(pick)) || null;
  }

  function draftedIds() {
    return new Set(allEvents().map((event) => event.playerId));
  }

  function price(player) { return player[state.platform] ?? player.market ?? player.adp; }
  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
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

  function leagueScore(player) {
    const base = 102 - player.ecr * 0.48;
    const priceSignal = ((player.market || player.adp) - player.ecr) * 0.08;
    return base + positionAdjustment(player) + needBonus(player) + priceSignal;
  }

  function availablePlayers() {
    if (!renderCache.available) {
      const drafted = draftedIds();
      renderCache.available = window.PLAYER_DATA.filter((player) => !drafted.has(player.id));
    }
    return renderCache.available;
  }

  function leagueRank(player) {
    if (!renderCache.leagueRanks) {
      renderCache.leagueRanks = new Map(availablePlayers().slice().sort((a, b) => leagueScore(b) - leagueScore(a)).map((item, index) => [item.id, index + 1]));
    }
    return renderCache.leagueRanks.get(player.id) || 0;
  }

  function survival(player, targetPick) {
    const sigma = clamp(3.2 + price(player) * 0.045, 3.5, 10.5);
    return clamp(1 / (1 + Math.exp((targetPick - price(player)) / sigma)), 0.01, 0.99);
  }

  function samePositionNext(player) {
    const same = availablePlayers().filter((item) => item.pos === player.pos && item.id !== player.id).sort((a, b) => leagueScore(b) - leagueScore(a));
    return same[0] || null;
  }

  function cliffDelta(player) {
    const next = samePositionNext(player);
    return next ? Math.max(0, leagueScore(player) - leagueScore(next)) : 12;
  }

  function recommendationPool() {
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const onClock = currentPick() <= TOTAL_PICKS && pickOwner(currentPick()) === TONY_TEAM;
    return availablePlayers().map((player) => {
      const arrive = onClock ? 1 : survival(player, target);
      const gap = price(player) - player.ecr;
      const score = leagueScore(player);
      return { player, arrive, gap, score, projected: score * (0.58 + arrive * 0.42) };
    });
  }

  function recommendations() {
    const pool = recommendationPool();
    const overall = pool.slice().sort((a, b) => b.projected - a.projected)[0];
    const value = pool.slice().sort((a, b) => ((b.gap * 1.8) + b.score * .12 + b.arrive * 8) - ((a.gap * 1.8) + a.score * .12 + a.arrive * 8))[0];
    const fit = pool.slice().sort((a, b) => ((b.score + needBonus(b.player) * 1.8 + cliffDelta(b.player)) * (0.65 + b.arrive * .35)) - ((a.score + needBonus(a.player) * 1.8 + cliffDelta(a.player)) * (0.65 + a.arrive * .35)))[0];
    return { overall, value, fit };
  }

  function verdict(player) {
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const after = followingTonyPick(target) || TOTAL_PICKS;
    const survive = survival(player, after);
    const rankAtPick = price(player) - target;
    if (survive < .24 && leagueScore(player) > 38) return { label: "TAKE", cls: "take" };
    if (survive >= .48 && rankAtPick > -8) return { label: "WAIT", cls: "wait" };
    return { label: "PASS", cls: "pass" };
  }

  function renderStatus() {
    const pick = currentPick();
    if (pick > TOTAL_PICKS) {
      els.roundPick.textContent = "DONE";
      els.overallPick.textContent = "160 selections resolved";
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
    return `<div class="rec-label"><span>${label}</span><span class="pos-pill pos-${player.pos}">${player.pos}</span></div>
      <div class="rec-name">${player.name}</div>
      <div class="rec-meta">${player.team} · ECR ${player.ecr} · ${state.platform.toUpperCase()} ${price(player)}</div>
      <p class="rec-reason">${detail(player, arrive, gap)}</p>`;
  }

  function renderRecommendations() {
    const { overall, value, fit } = recommendations();
    if (!overall) {
      els.bestOverallCard.innerHTML = "";
      els.bestValueCard.innerHTML = "";
      els.bestFitCard.innerHTML = "";
      els.decisionStrip.innerHTML = "";
      return;
    }
    els.bestOverallCard.innerHTML = recCard(overall, "Best player", (p, arrive) => `${Math.round(arrive * 100)}% chance to reach Tony's next turn · league-adjusted score ${leagueScore(p).toFixed(1)}.`);
    els.bestValueCard.innerHTML = recCard(value, "Best value", (p, arrive, gap) => `${gap >= 0 ? "+" : ""}${gap} slots versus ECR · ${Math.round(arrive * 100)}% projected availability.`);
    els.bestFitCard.innerHTML = recCard(fit, "Best fit", (p) => `${needBonus(p) > 2 ? "Fills a priority roster need" : "Supports the 2-FLEX build"} · ${cliffDelta(p).toFixed(1)}-point positional cliff.`);
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const nextTurn = followingTonyPick(target);
    const after = nextTurn || TOTAL_PICKS;
    const v = verdict(overall.player);
    const survive = survival(overall.player, after);
    els.decisionStrip.innerHTML = `<div class="decision-call">${v.label}</div>
      <div class="decision-copy"><strong>${overall.player.name} at ${pickLabel(target)}</strong><span>${v.label === "TAKE" ? "The next viable window is unlikely to stay open." : "The model sees enough depth to preserve optionality."} ${samePositionNext(overall.player)?.name || "No comparable fallback"} is the next ${overall.player.pos}.</span></div>
      <div class="decision-metric"><strong>${Math.round(survive * 100)}%</strong><small>survival to ${nextTurn ? pickLabel(after) : "end"}</small></div>`;
  }

  function renderPickMap() {
    const next = nextTonyPick();
    els.pickMap.innerHTML = TONY_PICKS.map((pick) => {
      const isKeeper = KEEPER_OVERALLS.has(pick);
      const classes = [pick < currentPick() || eventAt(pick) ? "done" : "", pick === next ? "next" : "", isKeeper ? "keeper" : ""].filter(Boolean).join(" ");
      return `<span class="pick-token ${classes}" title="${isKeeper ? "Jaxson Dart keeper cost" : `Tony pick ${pickLabel(pick)}`}">${isKeeper ? "K16" : pick}</span>`;
    }).join("");
  }

  function boardRows() {
    const query = state.search.trim().toLowerCase();
    return availablePlayers().filter((player) => state.position === "ALL" || player.pos === state.position).filter((player) => !query || `${player.name} ${player.team}`.toLowerCase().includes(query)).sort((a, b) => {
      const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
      const aScore = leagueScore(a) * (0.72 + survival(a, target) * .28);
      const bScore = leagueScore(b) * (0.72 + survival(b, target) * .28);
      return bScore - aScore;
    });
  }

  function renderBoard() {
    const rows = boardRows();
    const target = nextTonyPick() || Math.min(currentPick(), TOTAL_PICKS);
    const nextTurn = followingTonyPick(target);
    const after = nextTurn || TOTAL_PICKS;
    els.boardCount.textContent = `${rows.length} available`;
    els.platformHeader.textContent = `${state.platform === "espn" ? "ESPN" : "Sleeper"} price`;
    els.playerTable.innerHTML = rows.slice(0, state.visible).map((player, index) => {
      const rank = leagueRank(player);
      const gap = price(player) - player.ecr;
      const prob = survival(player, after);
      const call = verdict(player);
      return `<tr>
        <td><div class="player-cell"><span class="rank-num">${index + 1}</span><span class="pos-pill pos-${player.pos}">${player.pos}</span><div><span class="player-name">${player.name}</span><span class="player-meta">${player.team} · BYE ${player.bye}</span></div></div></td>
        <td><span class="metric-main">#${rank}</span><span class="metric-sub">ECR ${player.ecr} · score ${leagueScore(player).toFixed(1)}</span></td>
        <td><span class="metric-main ${gap >= 4 ? "value-positive" : gap <= -4 ? "value-negative" : ""}">#${price(player)}</span><span class="metric-sub">${gap >= 0 ? "+" : ""}${gap} vs ECR</span></td>
        <td><div class="survival"><div class="survival-head"><span>${nextTurn ? pickLabel(after) : "END"}</span><span>${Math.round(prob * 100)}%</span></div><div class="survival-bar"><span style="width:${Math.round(prob * 100)}%"></span></div></div></td>
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
    els.rosterList.innerHTML = roster.length ? roster.map(({ event, player }) => `<div class="roster-row"><div><span>${player.name}</span><small>${player.team} · ${pickLabel(event.overall)}${event.source === "keeper" ? " · KEEPER" : ""}</small></div><span class="pos-pill pos-${player.pos}">${player.pos}</span></div>`).join("") : `<div class="empty-state">${manager(state.rosterTeam).short}'s players will appear here as live picks are entered.</div>`;
  }

  function renderHistory() {
    const recent = state.events.slice().sort((a, b) => b.overall - a.overall).slice(0, 10);
    els.undoPick.disabled = !state.events.length;
    els.historyList.innerHTML = recent.length ? recent.map((event) => {
      const player = playerById(event.playerId);
      return `<div class="history-row"><div class="history-main"><span>${player?.name || "Unknown"}</span><small>${pickLabel(event.overall)} · ${manager(event.team).name}</small></div><div class="history-actions"><span class="pos-pill pos-${player?.pos || "QB"}">${player?.pos || "?"}</span><button class="history-edit" data-edit-pick="${event.overall}" type="button">Edit</button></div></div>`;
    }).join("") : `<div class="empty-state">All 10 keepers are loaded. Enter the first live selection from the board.</div>`;
  }

  function renderKeepers() {
    els.keeperList.innerHTML = KEEPERS.map((keeper) => {
      const player = playerById(keeper.playerId);
      return `<div class="keeper-row"><div><strong>${manager(keeper.team).name}</strong><small>${player?.name || "Unknown"}</small></div><span class="keeper-round">R${keeper.round}</span></div>`;
    }).join("");
  }

  function renderCliffs() {
    const positions = ["RB", "WR", "TE", "QB"];
    const items = positions.map((pos) => availablePlayers().filter((p) => p.pos === pos).sort((a, b) => leagueScore(b) - leagueScore(a))[0]).filter(Boolean);
    els.cliffPanel.innerHTML = `<p class="eyebrow">Scarcity monitor</p><h2>Position cliffs</h2>${items.map((player) => {
      const next = samePositionNext(player);
      const delta = cliffDelta(player);
      return `<div class="cliff-player"><strong><span>${player.pos}: ${player.name}</span><span class="cliff-severity">${delta >= 4 ? "STEEP" : delta >= 2 ? "WATCH" : "DEPTH"}</span></strong><p>${next ? `${next.name} is next; ${delta.toFixed(1)} score points down.` : "No comparable option remains."}</p></div>`;
    }).join("")}`;
  }

  function render() {
    renderCache = {};
    renderStatus();
    renderPickMap();
    renderRecommendations();
    renderBoard();
    renderRoster();
    renderHistory();
    renderCliffs();
    document.querySelectorAll(".platform-btn").forEach((button) => button.classList.toggle("active", button.dataset.platform === state.platform));
  }

  function draftPlayer(id) {
    const overall = currentPick();
    if (overall > TOTAL_PICKS) return;
    const player = playerById(id);
    if (!player || draftedIds().has(player.id)) return;
    const team = pickOwner(overall);
    state.events.push({ overall, team, playerId: player.id, source: "manual", timestamp: new Date().toISOString() });
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
    if (!event) return;
    const player = playerById(event.playerId);
    state.editingOverall = event.overall;
    els.dialogTitle.textContent = `${pickLabel(event.overall)} · ${manager(event.team).name}`;
    els.dialogCopy.textContent = `Current selection: ${player.name}. Choose an available replacement, remove only this event, or rewind the live draft from this point.`;
    els.replacementSearch.value = "";
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
    const event = editEvent(state.editingOverall);
    const player = playerById(playerId);
    if (!event || !player) return;
    const blocked = draftedIds();
    blocked.delete(event.playerId);
    if (blocked.has(player.id)) return;
    const oldPlayer = playerById(event.playerId);
    event.playerId = player.id;
    event.timestamp = new Date().toISOString();
    event.source = "manual-correction";
    saveState();
    els.pickDialog.close();
    render();
    showToast(`${pickLabel(event.overall)} corrected: ${oldPlayer.name} → ${player.name}`);
  }

  function removeEditingPick() {
    const event = editEvent(state.editingOverall);
    if (!event || !window.confirm(`Remove ${playerById(event.playerId).name} from ${pickLabel(event.overall)}? Later picks will stay in place until this slot is corrected.`)) return;
    state.events = state.events.filter((item) => item.overall !== event.overall);
    saveState();
    els.pickDialog.close();
    render();
    showToast(`Removed pick ${pickLabel(event.overall)}`);
  }

  function rewindEditingPick() {
    const event = editEvent(state.editingOverall);
    if (!event) return;
    const affected = state.events.filter((item) => item.overall >= event.overall).length;
    if (!window.confirm(`Rewind to ${pickLabel(event.overall)}? This clears ${affected} live selection${affected === 1 ? "" : "s"} from that pick forward. Keepers remain loaded.`)) return;
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

  async function importDraft(file) {
    if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      if (Number(payload.schemaVersion) !== SCHEMA_VERSION || !Array.isArray(payload.events)) throw new Error("Unsupported backup format");
      const imported = canonicalizeEvents(payload.events);
      if (imported.length !== payload.events.length) throw new Error("Backup contains invalid or conflicting picks");
      if (!window.confirm(`Replace the current live draft with this backup containing ${imported.length} entered picks? The 10 configured keepers remain fixed.`)) return;
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
    const currentFingerprint = JSON.stringify(state.events);
    const prior = readSnapshots().slice().reverse().find((snapshot) => JSON.stringify(snapshot.events || []) !== currentFingerprint);
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
    if (!removed) return;
    state.events = state.events.filter((event) => event.overall !== removed.overall);
    saveState();
    render();
    showToast(`Undid pick ${pickLabel(removed.overall)}`);
  });
  els.resetDraft.addEventListener("click", () => {
    if (!state.events.length || window.confirm("Reset every live selection? The manager list and 10 keepers will remain loaded, and the prior state will stay available as a recovery snapshot.")) {
      state.events = [];
      saveState();
      render();
      showToast("Live picks reset; keepers preserved");
    }
  });
  els.exportDraft.addEventListener("click", exportDraft);
  els.importDraft.addEventListener("click", () => els.importDraftFile.click());
  els.importDraftFile.addEventListener("change", (event) => importDraft(event.target.files?.[0]));
  els.recoverDraft.addEventListener("click", recoverPriorSnapshot);
  els.removePick.addEventListener("click", removeEditingPick);
  els.rewindPick.addEventListener("click", rewindEditingPick);

  els.rosterManager.innerHTML = MANAGERS.slice(1).map((item) => `<option value="${item.id}">${item.id}. ${item.name}</option>`).join("");
  loadState();
  renderKeepers();
  render();
})();
