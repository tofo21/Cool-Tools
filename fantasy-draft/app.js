(() => {
  "use strict";

  const TONY_TEAM = 5;
  const TEAM_COUNT = 10;
  const ROUNDS = 16;
  const TOTAL_PICKS = TEAM_COUNT * ROUNDS;
  const TONY_PICKS = [5, 16, 25, 36, 45, 56, 65, 76, 85, 96, 105, 116, 125, 136, 145, 156];
  const TARGETS = { QB: 2, RB: 5, WR: 7, TE: 2 };
  const STORE_KEY = "draft-command-2026-v1";

  const state = {
    picks: [],
    platform: "espn",
    position: "ALL",
    search: "",
    visible: 20,
  };

  const els = Object.fromEntries([
    "roundPick", "overallPick", "clockOwner", "draftProgress", "nextTonyText", "pickMap",
    "decisionWindow", "workspaceTitle", "bestOverallCard", "bestValueCard", "bestFitCard",
    "decisionStrip", "playerSearch", "playerTable", "boardCount", "loadMore", "rosterCount",
    "rosterNeeds", "rosterList", "historyList", "undoPick", "cliffPanel", "platformHeader", "toast",
  ].map((id) => [id, document.getElementById(id)]));

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE_KEY));
      if (saved && Array.isArray(saved.picks)) state.picks = saved.picks;
      if (saved?.platform === "sleeper") state.platform = "sleeper";
    } catch (_) { /* ignore malformed local state */ }
  }

  function saveState() {
    localStorage.setItem(STORE_KEY, JSON.stringify({ picks: state.picks, platform: state.platform }));
  }

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

  function currentPick() { return Math.min(state.picks.length + 1, TOTAL_PICKS); }
  function nextTonyPick(from = currentPick()) { return TONY_PICKS.find((pick) => pick >= from) || null; }
  function followingTonyPick(from) { return TONY_PICKS.find((pick) => pick > from) || TOTAL_PICKS; }
  function draftedIds() { return new Set(state.picks.map((pick) => pick.playerId)); }
  function playerById(id) { return window.PLAYER_DATA.find((player) => player.id === Number(id)); }
  function price(player) { return player[state.platform] ?? player.market ?? player.adp; }
  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }

  function tonyRoster() {
    return state.picks.filter((pick) => pick.team === TONY_TEAM).map((pick) => playerById(pick.playerId)).filter(Boolean);
  }

  function rosterCounts() {
    return tonyRoster().reduce((counts, player) => {
      counts[player.pos] = (counts[player.pos] || 0) + 1;
      return counts;
    }, { QB: 0, RB: 0, WR: 0, TE: 0 });
  }

  function needBonus(player) {
    const counts = rosterCounts();
    const target = TARGETS[player.pos];
    const deficit = Math.max(0, target - counts[player.pos]);
    const round = Math.ceil((nextTonyPick() || currentPick()) / TEAM_COUNT);
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

  function leagueRank(player) {
    const available = availablePlayers().slice().sort((a, b) => leagueScore(b) - leagueScore(a));
    return available.findIndex((item) => item.id === player.id) + 1;
  }

  function survival(player, targetPick) {
    const sigma = clamp(3.2 + price(player) * 0.045, 3.5, 10.5);
    return clamp(1 / (1 + Math.exp((targetPick - price(player)) / sigma)), 0.01, 0.99);
  }

  function availablePlayers() {
    const drafted = draftedIds();
    return window.PLAYER_DATA.filter((player) => !drafted.has(player.id));
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
    const target = nextTonyPick() || currentPick();
    const onClock = pickOwner(currentPick()) === TONY_TEAM;
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
    const target = nextTonyPick() || currentPick();
    const after = followingTonyPick(target);
    const survive = survival(player, after);
    const rankAtPick = price(player) - target;
    if (survive < .24 && leagueScore(player) > 38) return { label: "TAKE", cls: "take" };
    if (survive >= .48 && rankAtPick > -8) return { label: "WAIT", cls: "wait" };
    return { label: "PASS", cls: "pass" };
  }

  function renderStatus() {
    const pick = currentPick();
    const owner = pickOwner(pick);
    const next = nextTonyPick(pick);
    els.roundPick.textContent = pickLabel(pick);
    els.overallPick.textContent = `Overall ${pick}`;
    els.clockOwner.textContent = owner === TONY_TEAM ? "Tony is on the clock" : `Team ${owner} is on the clock`;
    els.clockOwner.style.color = owner === TONY_TEAM ? "var(--green)" : "var(--text)";
    els.draftProgress.style.width = `${(state.picks.length / TOTAL_PICKS) * 100}%`;
    els.nextTonyText.textContent = next === pick ? `Make the pick — next turn is ${pickLabel(followingTonyPick(pick))}` : next ? `Tony picks in ${next - pick} selections at ${pickLabel(next)}` : "Tony's draft is complete";

    const target = next || pick;
    const after = followingTonyPick(target);
    els.decisionWindow.textContent = `${pickLabel(target)} → ${pickLabel(after)}`;
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
    if (!overall) return;
    els.bestOverallCard.innerHTML = recCard(overall, "Best player", (p, arrive) => `${Math.round(arrive * 100)}% chance to reach Tony's next turn · league-adjusted score ${leagueScore(p).toFixed(1)}.`);
    els.bestValueCard.innerHTML = recCard(value, "Best value", (p, arrive, gap) => `${gap >= 0 ? "+" : ""}${gap} slots versus ECR · ${Math.round(arrive * 100)}% projected availability.`);
    els.bestFitCard.innerHTML = recCard(fit, "Best fit", (p) => `${needBonus(p) > 2 ? "Fills a priority roster need" : "Supports the 2-FLEX build"} · ${cliffDelta(p).toFixed(1)}-point positional cliff.`);

    const target = nextTonyPick() || currentPick();
    const after = followingTonyPick(target);
    const v = verdict(overall.player);
    const survive = survival(overall.player, after);
    els.decisionStrip.innerHTML = `<div class="decision-call">${v.label}</div>
      <div class="decision-copy"><strong>${overall.player.name} at ${pickLabel(target)}</strong><span>${v.label === "TAKE" ? "The next viable window is unlikely to stay open." : "The model sees enough depth to preserve optionality."} ${samePositionNext(overall.player)?.name || "No comparable fallback"} is the next ${overall.player.pos}.</span></div>
      <div class="decision-metric"><strong>${Math.round(survive * 100)}%</strong><small>survival to ${pickLabel(after)}</small></div>`;
  }

  function renderPickMap() {
    const next = nextTonyPick();
    els.pickMap.innerHTML = TONY_PICKS.map((pick) => `<span class="pick-token ${pick < currentPick() ? "done" : pick === next ? "next" : ""}">${pick}</span>`).join("");
  }

  function boardRows() {
    const query = state.search.trim().toLowerCase();
    return availablePlayers().filter((player) => state.position === "ALL" || player.pos === state.position).filter((player) => !query || `${player.name} ${player.team}`.toLowerCase().includes(query)).sort((a, b) => {
      const target = nextTonyPick() || currentPick();
      const aScore = leagueScore(a) * (0.72 + survival(a, target) * .28);
      const bScore = leagueScore(b) * (0.72 + survival(b, target) * .28);
      return bScore - aScore;
    });
  }

  function renderBoard() {
    const rows = boardRows();
    const target = nextTonyPick() || currentPick();
    const after = followingTonyPick(target);
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
        <td><div class="survival"><div class="survival-head"><span>${pickLabel(after)}</span><span>${Math.round(prob * 100)}%</span></div><div class="survival-bar"><span style="width:${Math.round(prob * 100)}%"></span></div></div></td>
        <td><span class="call-badge call-${call.cls}">${call.label}</span></td>
        <td><button class="draft-btn" data-draft-id="${player.id}" type="button">Draft</button></td>
      </tr>`;
    }).join("");
    els.loadMore.hidden = rows.length <= state.visible;
  }

  function renderRoster() {
    const roster = tonyRoster();
    const counts = rosterCounts();
    els.rosterCount.textContent = `${roster.length} / 16`;
    els.rosterNeeds.innerHTML = Object.keys(TARGETS).map((pos) => `<div class="need-box"><strong>${counts[pos]}</strong><small>${pos} / ${TARGETS[pos]}</small></div>`).join("");
    els.rosterList.innerHTML = roster.length ? roster.map((player) => `<div class="roster-row"><div><span>${player.name}</span><small>${player.team}</small></div><span class="pos-pill pos-${player.pos}">${player.pos}</span></div>`).join("") : `<div class="empty-state">Tony's players will appear here as the live picks are entered.</div>`;
  }

  function renderHistory() {
    const recent = state.picks.slice(-10).reverse();
    els.undoPick.disabled = !state.picks.length;
    els.historyList.innerHTML = recent.length ? recent.map((pick) => {
      const player = playerById(pick.playerId);
      return `<div class="history-row"><div><span>${player?.name || "Unknown"}</span><small>${pickLabel(pick.overall)} · ${pick.team === TONY_TEAM ? "TONY" : `TEAM ${pick.team}`}</small></div><span class="pos-pill pos-${player?.pos || "QB"}">${player?.pos || "?"}</span></div>`;
    }).join("") : `<div class="empty-state">Enter picks from the board to start the live draft log.</div>`;
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
    if (state.picks.length >= TOTAL_PICKS) return;
    const player = playerById(id);
    if (!player || draftedIds().has(player.id)) return;
    const overall = currentPick();
    const team = pickOwner(overall);
    state.picks.push({ overall, team, playerId: player.id });
    state.visible = 20;
    saveState();
    render();
    showToast(`${player.name} drafted at ${pickLabel(overall)} by ${team === TONY_TEAM ? "Tony" : `Team ${team}`}`);
  }

  let toastTimer;
  function showToast(message) {
    els.toast.textContent = message;
    els.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2200);
  }

  document.addEventListener("click", (event) => {
    const draft = event.target.closest("[data-draft-id]");
    if (draft) draftPlayer(draft.dataset.draftId);
    const platform = event.target.closest("[data-platform]");
    if (platform) {
      state.platform = platform.dataset.platform;
      saveState();
      render();
    }
    const filter = event.target.closest("[data-pos]");
    if (filter) {
      state.position = filter.dataset.pos;
      state.visible = 20;
      document.querySelectorAll(".filter-btn").forEach((button) => button.classList.toggle("active", button === filter));
      renderBoard();
    }
  });

  els.playerSearch.addEventListener("input", (event) => {
    state.search = event.target.value;
    state.visible = 20;
    renderBoard();
  });
  els.loadMore.addEventListener("click", () => { state.visible += 20; renderBoard(); });
  els.undoPick.addEventListener("click", () => {
    const removed = state.picks.pop();
    if (!removed) return;
    saveState();
    render();
    showToast(`Undid pick ${pickLabel(removed.overall)}`);
  });
  document.getElementById("resetDraft").addEventListener("click", () => {
    if (!state.picks.length || window.confirm("Reset all entered picks and Tony's roster?")) {
      state.picks = [];
      saveState();
      render();
      showToast("Draft reset");
    }
  });

  loadState();
  render();
})();
