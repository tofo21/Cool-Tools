(function attachOpponentIntent(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.OpponentIntentModel = api;
})(typeof window !== "undefined" ? window : globalThis, () => {
  "use strict";

  const CONTRACT_VERSION = "1.0.0";
  const POSITIONS = Object.freeze(["QB", "RB", "WR", "TE"]);
  const MANDATORY = Object.freeze({ QB: 1, RB: 2, WR: 2, TE: 1 });

  const number = (value, fallback = null) => {
    if (value == null || value === "") return fallback;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));

  function normalize(values) {
    const entries = Object.entries(values).map(([key, value]) => [key, Math.max(0, number(value, 0))]);
    const total = entries.reduce((sum, [, value]) => sum + value, 0);
    if (total <= 0) {
      const equal = entries.length ? 1 / entries.length : 0;
      return Object.fromEntries(entries.map(([key]) => [key, equal]));
    }
    const result = Object.fromEntries(entries.map(([key, value]) => [key, value / total]));
    const last = entries.at(-1)?.[0];
    if (last) result[last] += 1 - Object.values(result).reduce((sum, value) => sum + value, 0);
    return result;
  }

  function sigmoid(value) {
    if (value >= 0) return 1 / (1 + Math.exp(-value));
    const exp = Math.exp(value);
    return exp / (1 + exp);
  }

  function modelScore(model, features) {
    const names = Array.isArray(model?.features) ? model.features : [];
    if (!names.length || names.length !== model.scaler_mean?.length || names.length !== model.scaler_scale?.length || names.length !== model.coef?.length) {
      throw new Error("Opponent Intent model coefficients are malformed.");
    }
    const linear = names.reduce((sum, name, index) => {
      const scale = number(model.scaler_scale[index], 1) || 1;
      const standardized = (number(features[name], 0) - number(model.scaler_mean[index], 0)) / scale;
      return sum + number(model.coef[index], 0) * standardized;
    }, number(model.intercept, 0));
    return sigmoid(linear);
  }

  function validatePackage(packageData, { season = 2026, leagueProfileId, players = [] } = {}) {
    const errors = [];
    const warnings = [];
    const data = packageData && typeof packageData === "object" ? packageData : {};
    if (!String(data.schemaVersion || "").startsWith("1.")) errors.push("Unsupported or missing Opponent Intent schema.");
    if (number(data.season) !== number(season)) errors.push("Opponent Intent season mismatch.");
    if (leagueProfileId && data.leagueProfileId !== leagueProfileId) errors.push("Opponent Intent league profile mismatch.");
    if (!data.positionModel?.dynamicBase || !data.positionModel?.roomBaselines) errors.push("Position model is missing.");
    if (!Array.isArray(data.managers) || data.managers.length !== 9) errors.push("Exactly nine opponent profiles are required.");
    if (new Set((data.managers || []).map((manager) => number(manager.espnTeamId))).size !== (data.managers || []).length) errors.push("ESPN team IDs must be unique.");
    if (new Set((data.managers || []).map((manager) => number(manager.draftSlot))).size !== (data.managers || []).length) errors.push("Draft slots must be unique.");
    if (number(data.policy?.positionManagerResidualWeight, 0) !== 0) errors.push("Unapproved position manager residual weight must be zero.");
    if (number(data.policy?.playerManagerResidualWeight, 0) !== 0) errors.push("Unapproved player manager residual weight must be zero.");
    const known = new Set(players.map((player) => number(player.id)));
    const marketIds = new Set((data.playerMarket || []).map((entry) => number(entry.playerId)));
    if (known.size && ![...known].every((id) => marketIds.has(id))) warnings.push("Some board players lack a packaged ESPN market row; live player fields will be used as fallback.");
    try {
      if (data.positionModel?.dynamicBase) {
        const zero = Object.fromEntries((data.positionModel.dynamicBase.features || []).map((name) => [name, 0]));
        modelScore(data.positionModel.dynamicBase, zero);
      }
    } catch (error) {
      errors.push(error.message);
    }
    return Object.freeze({ ok: errors.length === 0, errors, warnings });
  }

  function hashSeed(text) {
    let value = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      value ^= text.charCodeAt(index);
      value = Math.imul(value, 16777619);
    }
    return value >>> 0;
  }

  function seededRandom(seedText) {
    let value = hashSeed(seedText) || 1;
    return () => {
      value += 0x6D2B79F5;
      let result = value;
      result = Math.imul(result ^ (result >>> 15), result | 1);
      result ^= result + Math.imul(result ^ (result >>> 7), result | 61);
      return ((result ^ (result >>> 14)) >>> 0) / 4294967296;
    };
  }

  function weightedChoice(probabilities, random) {
    const entries = Object.entries(probabilities).filter(([, probability]) => probability > 0);
    if (!entries.length) return null;
    let threshold = random();
    for (const [key, probability] of entries) {
      threshold -= probability;
      if (threshold <= 0) return key;
    }
    return entries.at(-1)[0];
  }

  function createEngine({ packageData, players = [], managers = [], season = 2026, leagueProfileId, teamCount = 10, tonyTeam = 5 } = {}) {
    const validation = validatePackage(packageData, { season, leagueProfileId, players });
    const data = validation.ok ? packageData : null;
    let disabledReason = null;
    const playerById = new Map(players.map((player) => [number(player.id), player]));
    const marketById = new Map((data?.playerMarket || []).map((entry) => [number(entry.playerId), entry]));
    const managerBySlot = new Map((data?.managers || []).map((profile) => [number(profile.draftSlot), profile]));
    const managerMeta = new Map(managers.filter(Boolean).map((manager) => [number(manager.id), manager]));

    function active() {
      return Boolean(data && !disabledReason);
    }

    function health() {
      return Object.freeze({
        mode: active() ? "live" : "fallback",
        status: active() ? data.metadata?.status || "candidate" : "unavailable",
        modelVersion: active() ? data.metadata?.modelVersion : "opponent-intent-unavailable",
        packageId: active() ? data.packageId : null,
        valid: validation.ok && !disabledReason,
        errors: disabledReason ? [...validation.errors, disabledReason] : validation.errors.slice(),
        warnings: validation.warnings.slice(),
        calibratedRounds: active() ? (data.metadata?.calibratedRounds || []).slice() : [],
        managerWeights: active() ? {
          position: number(data.policy.positionManagerResidualWeight, 0),
          player: number(data.policy.playerManagerResidualWeight, 0),
        } : { position: 0, player: 0 },
        promotionStatus: active() ? data.policy?.promotionStatus : "NOT_AVAILABLE",
      });
    }

    function disable(reason = "Opponent Intent disabled safely.") {
      disabledReason = String(reason);
      return health();
    }

    function pickOwner(overall) {
      const round = Math.ceil(overall / teamCount);
      const slot = ((overall - 1) % teamCount) + 1;
      return round % 2 ? slot : teamCount + 1 - slot;
    }

    function market(playerId) {
      const player = playerById.get(number(playerId));
      const packaged = marketById.get(number(playerId)) || {};
      const rank = number(packaged.espnDefaultRank, number(player?.espn));
      const adp = number(packaged.espnAdp, null);
      return {
        playerId: number(playerId),
        playerName: player?.name || `Player ${playerId}`,
        position: player?.pos,
        espnRank: rank,
        espnAdp: adp,
        coverage: packaged.marketCoverage || "live-player-fallback",
      };
    }

    function createLiveState({ events = [], keeperSeeds = [], beforeOverall = Number.POSITIVE_INFINITY } = {}) {
      const occupiedPicks = new Set();
      const draftedPlayerIds = new Set();
      const states = {};
      for (let slot = 1; slot <= teamCount; slot += 1) {
        states[String(slot)] = { rosterCounts: { QB: 0, RB: 0, WR: 0, TE: 0 }, players: [], lastLivePickPosition: null, previousTurnPositions: [] };
      }
      const cutoff = number(beforeOverall, Number.POSITIVE_INFINITY);
      const ordered = [
        ...keeperSeeds.filter(Boolean),
        ...events.filter((event) => event && number(event.overall, 0) < cutoff),
      ].sort((a, b) => number(a.overall, 0) - number(b.overall, 0));
      const recentLivePositions = [];
      for (const event of ordered) {
        const overall = number(event.overall);
        const team = number(event.team, overall ? pickOwner(overall) : null);
        const player = playerById.get(number(event.playerId));
        if (!overall || !team || !player || occupiedPicks.has(overall) || draftedPlayerIds.has(player.id)) continue;
        occupiedPicks.add(overall);
        draftedPlayerIds.add(player.id);
        const managerState = states[String(team)];
        managerState.rosterCounts[player.pos] = (managerState.rosterCounts[player.pos] || 0) + 1;
        managerState.players.push({ playerId: player.id, playerName: player.name, position: player.pos, overallPick: overall, acquisitionType: String(event.source || "").includes("keeper") ? "KEEPER" : "LIVE" });
        if (!String(event.source || "").includes("keeper")) {
          managerState.lastLivePickPosition = player.pos;
          managerState.previousTurnPositions.push(player.pos);
          managerState.previousTurnPositions = managerState.previousTurnPositions.slice(-2);
          recentLivePositions.push(player.pos);
        }
      }
      return {
        managers: states,
        availablePlayerIds: players.map((player) => number(player.id)).filter((id) => !draftedPlayerIds.has(id)),
        draftedPlayerIds: [...draftedPlayerIds],
        occupiedPicks: [...occupiedPicks],
        recentLivePositions: recentLivePositions.slice(-6),
      };
    }

    function cloneLiveState(liveState) {
      return {
        managers: Object.fromEntries(Object.entries(liveState.managers).map(([slot, managerState]) => [slot, {
          rosterCounts: { ...managerState.rosterCounts },
          players: managerState.players.map((player) => ({ ...player })),
          lastLivePickPosition: managerState.lastLivePickPosition || null,
          previousTurnPositions: (managerState.previousTurnPositions || []).slice(),
        }])),
        availablePlayerIds: liveState.availablePlayerIds.slice(),
        draftedPlayerIds: (liveState.draftedPlayerIds || []).slice(),
        occupiedPicks: (liveState.occupiedPicks || []).slice(),
        recentLivePositions: (liveState.recentLivePositions || []).slice(),
      };
    }

    function boardPositions(availableIds) {
      const rows = availableIds.map((id) => market(id)).filter((entry) => POSITIONS.includes(entry.position));
      const rank = rows.slice().sort((a, b) => number(a.espnRank, Infinity) - number(b.espnRank, Infinity) || number(a.espnAdp, Infinity) - number(b.espnAdp, Infinity) || a.playerId - b.playerId);
      const adp = rows.slice().sort((a, b) => number(a.espnAdp, Infinity) - number(b.espnAdp, Infinity) || number(a.espnRank, Infinity) - number(b.espnRank, Infinity) || a.playerId - b.playerId);
      return {
        rank: new Map(rank.map((entry, index) => [entry.playerId, index + 1])),
        adp: new Map(adp.map((entry, index) => [entry.playerId, index + 1])),
      };
    }

    function fallbackPositionDistribution(round, roster, availableByPosition) {
      const baseline = round <= 3
        ? { QB: 0.03, RB: 0.38, WR: 0.52, TE: 0.07 }
        : { QB: 0.14, RB: 0.32, WR: 0.44, TE: 0.10 };
      return normalize(Object.fromEntries(POSITIONS.map((position) => {
        const open = Math.max(0, MANDATORY[position] - number(roster[position], 0));
        const need = 1 + open * 0.55 - Math.max(0, number(roster[position], 0) - MANDATORY[position]) * 0.18;
        return [position, availableByPosition[position] ? baseline[position] * Math.max(0.2, need) : 0];
      })));
    }

    function distribution(team, overallPick, liveState) {
      const slot = number(team);
      const round = Math.ceil(number(overallPick) / teamCount);
      const available = liveState.availablePlayerIds.map(number).filter((id) => playerById.has(id) && POSITIONS.includes(playerById.get(id).pos));
      if (!available.length) throw new Error("No supported players are available for Opponent Intent.");
      const positions = boardPositions(available);
      const availableByPosition = Object.fromEntries(POSITIONS.map((position) => [position, available.filter((id) => playerById.get(id).pos === position).length]));
      const rosterState = liveState.managers[String(slot)] || { rosterCounts: {}, previousTurnPositions: [] };
      const roster = { QB: 0, RB: 0, WR: 0, TE: 0, ...rosterState.rosterCounts };
      const recentCounts = Object.fromEntries(POSITIONS.map((position) => [position, (liveState.recentLivePositions || []).slice(-6).filter((item) => item === position).length]));
      const skillExtras = Math.max(0, roster.RB - 2) + Math.max(0, roster.WR - 2) + Math.max(0, roster.TE - 1);
      const flexOpen = Math.max(0, 2 - skillExtras);
      const top12 = available.slice().sort((a, b) => {
        const aScore = 0.6 * number(positions.rank.get(a), 999) + 0.4 * number(positions.adp.get(a), number(positions.rank.get(a), 999));
        const bScore = 0.6 * number(positions.rank.get(b), 999) + 0.4 * number(positions.adp.get(b), number(positions.rank.get(b), 999));
        return aScore - bScore || a - b;
      }).slice(0, 12);
      const top12Counts = Object.fromEntries(POSITIONS.map((position) => [position, top12.filter((id) => playerById.get(id).pos === position).length]));
      const group = round <= 3 ? "R1_3" : "R4_6";
      const room = data?.positionModel?.roomBaselines?.[group];
      let positionProbabilities;
      if (!active() || !room) {
        positionProbabilities = fallbackPositionDistribution(round, roster, availableByPosition);
      } else {
        const features = {};
        for (const position of POSITIONS) {
          const candidates = available.filter((id) => playerById.get(id).pos === position);
          const best = candidates.reduce((minimum, id) => {
            const rank = number(positions.rank.get(id), 999);
            const adp = number(positions.adp.get(id), rank);
            return Math.min(minimum, 0.6 * rank + 0.4 * adp);
          }, 99);
          features[position] = {
            room_log_prob: Math.log(Math.max(0.0001, number(room[position], 0.0001))),
            roster_count: roster[position],
            open_mandatory: Math.max(0, MANDATORY[position] - roster[position]),
            flex_open_skill: ["RB", "WR", "TE"].includes(position) ? flexOpen : 0,
            last_same: rosterState.lastLivePickPosition === position ? 1 : 0,
            recent_run_count: recentCounts[position],
            best_board_log: -Math.log1p(best),
            top12_share: top12Counts[position] / Math.max(1, top12.length),
            round_norm: Math.min(round, 6) / 6,
            pos_QB: position === "QB" ? 1 : 0,
            pos_RB: position === "RB" ? 1 : 0,
            pos_WR: position === "WR" ? 1 : 0,
            pos_TE: position === "TE" ? 1 : 0,
          };
        }
        positionProbabilities = normalize(Object.fromEntries(POSITIONS.map((position) => [
          position,
          availableByPosition[position] ? modelScore(data.positionModel.dynamicBase, features[position]) : 0,
        ])));
      }

      const playerProbabilities = {};
      const rankWeight = number(data?.playerModel?.rankWeight, 0.6);
      const adpWeight = number(data?.playerModel?.adpWeight, 0.4);
      const decay = number(data?.playerModel?.boardDecayLambda, 0.35);
      for (const position of POSITIONS) {
        const candidates = available.filter((id) => playerById.get(id).pos === position);
        if (!candidates.length) continue;
        const scores = {};
        for (const id of candidates) {
          const rankPosition = number(positions.rank.get(id), 999) - 1;
          const marketEntry = market(id);
          const hasAdp = number(marketEntry.espnAdp) != null;
          const adpPosition = number(positions.adp.get(id), rankPosition + 1) - 1;
          const totalWeight = rankWeight + (hasAdp ? adpWeight : 0);
          const distance = totalWeight > 0 ? ((rankWeight * rankPosition) + (hasAdp ? adpWeight * adpPosition : 0)) / totalWeight : rankPosition;
          scores[String(id)] = Math.exp(-decay * distance);
        }
        const conditional = normalize(scores);
        for (const id of candidates) playerProbabilities[String(id)] = positionProbabilities[position] * conditional[String(id)];
      }

      return {
        round,
        calibratedRound: active() && (data.metadata?.calibratedRounds || []).includes(round),
        roster,
        profile: managerBySlot.get(slot) || null,
        positionProbabilities,
        playerProbabilities: normalize(playerProbabilities),
      };
    }

    function predict(team, overallPick, liveState) {
      try {
        const result = distribution(team, overallPick, liveState);
        const positions = POSITIONS.slice().sort((a, b) => result.positionProbabilities[b] - result.positionProbabilities[a]);
        const playerIds = Object.keys(result.playerProbabilities).sort((a, b) => result.playerProbabilities[b] - result.playerProbabilities[a] || number(a) - number(b));
        const topIds = playerIds.slice(0, 5);
        const profile = result.profile;
        const topPlayers = topIds.map((id) => {
          const player = playerById.get(number(id));
          return { playerId: player.id, playerName: player.name, position: player.pos, probability: result.playerProbabilities[id] };
        });
        const teamName = managerMeta.get(number(team))?.name || profile?.manager || `Team ${team}`;
        const confidence = result.calibratedRound ? (number(profile?.sampleSize, 0) >= 30 ? "MEDIUM" : "LOW") : "LOW";
        const followingPick = nextSelectionForTeam(team, overallPick, liveState.occupiedPicks);
        return {
          schemaVersion: CONTRACT_VERSION,
          modelVersion: active() ? data.metadata.modelVersion : "fallback-context",
          team: number(team),
          espnTeamId: number(profile?.espnTeamId),
          manager: teamName,
          overallPick: number(overallPick),
          round: result.round,
          followingPick,
          picksUntilFollowingTurn: followingPick == null ? null : followingPick - number(overallPick),
          rosterCounts: result.roster,
          openNeeds: Object.fromEntries(POSITIONS.map((position) => [position, Math.max(0, MANDATORY[position] - result.roster[position])])),
          positionProbabilities: result.positionProbabilities,
          topPlayers,
          otherProbability: Math.max(0, 1 - topPlayers.reduce((sum, player) => sum + player.probability, 0)),
          confidence: active() ? confidence : "FALLBACK",
          status: result.calibratedRound ? "CALIBRATED_BASELINE" : active() ? "CONTEXTUAL_UNVALIDATED" : "FALLBACK",
          profileSummary: profile?.profileSummary || "No manager profile is available; room and roster fallback applied.",
          profileEvidence: profile ? {
            sampleSize: profile.sampleSize,
            seasonsRepresented: profile.seasonsRepresented,
            boardStyle: profile.boardStyle,
            alignment: profile.alignment,
            boardModeProbability: profile.boardModeProbability,
            convictionModeProbability: profile.convictionModeProbability,
            behavior: profile.behavior,
            historicalEvidence: profile.historicalEvidence,
          } : null,
          liveContext: {
            recentRoomPositions: (liveState.recentLivePositions || []).slice(),
            previousTurnPositions: (liveState.managers[String(number(team))]?.previousTurnPositions || []).slice(),
            availablePlayers: liveState.availablePlayerIds.length,
          },
          drivers: [
            `Roster before pick: QB ${result.roster.QB} / RB ${result.roster.RB} / WR ${result.roster.WR} / TE ${result.roster.TE}`,
            `Separate ESPN rank and ESPN ADP signals favor ${positions[0]} among available players.`,
            active() ? "Roster need, room context and current board drive the forecast." : "Compact model unavailable; generic room and roster fallback is active.",
            "Manager profile is explanatory only; predictive residual weight is 0.",
          ],
          policyNote: "Opponent Intent does not mutate Player Truth, League Value, tiers, BPA, ESPN rank or ESPN ADP.",
        };
      } catch (error) {
        return { schemaVersion: CONTRACT_VERSION, team: number(team), overallPick: number(overallPick), manager: managerMeta.get(number(team))?.name || `Team ${team}`, status: "UNAVAILABLE", confidence: "UNAVAILABLE", error: error.message, positionProbabilities: {}, topPlayers: [], otherProbability: 1 };
      }
    }

    function nextSelectionForTeam(team, afterPick, occupiedPicks = []) {
      const occupied = new Set(occupiedPicks.map(number));
      for (let pick = Math.max(1, number(afterPick, 0) + 1); pick <= teamCount * 16; pick += 1) {
        if (pickOwner(pick) === number(team) && !occupied.has(pick)) return pick;
      }
      return null;
    }

    function fullBoard({ currentOverallPick, nextTonyPick, liveState }) {
      const rows = [];
      for (let team = 1; team <= teamCount; team += 1) {
        if (team === tonyTeam) continue;
        const nextPick = nextSelectionForTeam(team, number(currentOverallPick) - 1, liveState.occupiedPicks);
        const row = nextPick ? predict(team, nextPick, liveState) : {
          schemaVersion: CONTRACT_VERSION,
          team,
          espnTeamId: number(managerBySlot.get(team)?.espnTeamId),
          manager: managerMeta.get(team)?.name || managerBySlot.get(team)?.manager || `Team ${team}`,
          overallPick: null,
          rosterCounts: liveState.managers[String(team)]?.rosterCounts || { QB: 0, RB: 0, WR: 0, TE: 0 },
          positionProbabilities: {}, topPlayers: [], otherProbability: 1, confidence: "COMPLETE", status: "COMPLETE",
          profileSummary: managerBySlot.get(team)?.profileSummary || "Draft complete.", drivers: [],
        };
        row.picksBeforeTony = nextPick != null && nextTonyPick != null && nextPick < number(nextTonyPick);
        rows.push(row);
      }
      return { schemaVersion: CONTRACT_VERSION, currentOverallPick: number(currentOverallPick), nextTonyPick: number(nextTonyPick), opponentCount: rows.length, opponents: rows };
    }

    function applyPick(liveState, team, overallPick, playerId) {
      const id = number(playerId);
      const index = liveState.availablePlayerIds.indexOf(id);
      const player = playerById.get(id);
      if (index < 0 || !player) throw new Error(`Player ${playerId} is not available.`);
      liveState.availablePlayerIds.splice(index, 1);
      liveState.draftedPlayerIds.push(id);
      liveState.occupiedPicks.push(number(overallPick));
      const managerState = liveState.managers[String(number(team))];
      managerState.rosterCounts[player.pos] = (managerState.rosterCounts[player.pos] || 0) + 1;
      managerState.players.push({ playerId: id, playerName: player.name, position: player.pos, overallPick: number(overallPick), acquisitionType: "SIMULATED" });
      managerState.lastLivePickPosition = player.pos;
      managerState.previousTurnPositions.push(player.pos);
      managerState.previousTurnPositions = managerState.previousTurnPositions.slice(-2);
      liveState.recentLivePositions.push(player.pos);
      liveState.recentLivePositions = liveState.recentLivePositions.slice(-6);
    }

    function simulateTonyWindow({ currentOverallPick, nextTonyPick, liveState, targetPlayerIds = null, tiers = {}, simulations = 300, seed = 20260831 } = {}) {
      const simulationCount = Math.max(1, Math.floor(number(simulations, 300)));
      const start = number(currentOverallPick);
      const end = number(nextTonyPick);
      const occupied = new Set(liveState.occupiedPicks.map(number));
      const picks = [];
      for (let pick = start; pick < end; pick += 1) {
        const team = pickOwner(pick);
        if (team !== tonyTeam && !occupied.has(pick)) picks.push({ overallPick: pick, team });
      }
      const initialAvailable = new Set(liveState.availablePlayerIds.map(number));
      const targets = (targetPlayerIds || liveState.availablePlayerIds).map(number).filter((id) => initialAvailable.has(id));
      const targetSet = new Set(targets);
      const takenCount = new Map(targets.map((id) => [id, 0]));
      const takerCounts = new Map(targets.map((id) => [id, new Map()]));
      const tierEntries = Object.entries(tiers).map(([label, ids]) => [label, new Set((ids || []).map(number))]);
      const tierRemaining = new Map(tierEntries.map(([label]) => [label, 0]));
      const tierAny = new Map(tierEntries.map(([label]) => [label, 0]));

      for (let simulation = 0; simulation < simulationCount; simulation += 1) {
        const random = seededRandom(`${seed}:${simulation}`);
        const state = cloneLiveState(liveState);
        for (const event of picks) {
          const playerProbabilities = distribution(event.team, event.overallPick, state).playerProbabilities;
          const selected = number(weightedChoice(playerProbabilities, random));
          if (!selected) continue;
          applyPick(state, event.team, event.overallPick, selected);
          if (targetSet.has(selected)) {
            takenCount.set(selected, takenCount.get(selected) + 1);
            const managers = takerCounts.get(selected);
            managers.set(event.team, (managers.get(event.team) || 0) + 1);
          }
        }
        const remaining = new Set(state.availablePlayerIds);
        for (const [label, members] of tierEntries) {
          const count = [...members].filter((id) => remaining.has(id)).length;
          tierRemaining.set(label, tierRemaining.get(label) + count);
          if (count > 0) tierAny.set(label, tierAny.get(label) + 1);
        }
      }

      const threats = targets.map((id) => {
        const taken = takenCount.get(id) / simulationCount;
        const managers = [...takerCounts.get(id).entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]);
        const breakdown = managers.map(([team, count]) => ({
          team,
          espnTeamId: number(managerBySlot.get(team)?.espnTeamId),
          manager: managerMeta.get(team)?.name || managerBySlot.get(team)?.manager || `Team ${team}`,
          probability: count / simulationCount,
          conditionalProbabilityGivenTaken: count / Math.max(1, takenCount.get(id)),
        }));
        const player = playerById.get(id);
        return {
          playerId: id,
          playerName: player?.name || `Player ${id}`,
          position: player?.pos || null,
          probabilityTakenBeforeTony: taken,
          probabilitySurviving: 1 - taken,
          mostLikelyTaker: breakdown[0] || null,
          secondMostLikelyTaker: breakdown[1] || null,
          managerThreatBreakdown: breakdown,
          confidence: active() ? "MONTE_CARLO_BASELINE" : "FALLBACK_CONTEXTUAL",
          status: active() && Math.ceil(start / teamCount) <= 6 ? "CALIBRATED_BASELINE" : "CONTEXTUAL_UNVALIDATED",
        };
      });
      return {
        schemaVersion: CONTRACT_VERSION,
        modelVersion: active() ? data.metadata.modelVersion : "fallback-context",
        seed,
        simulations: simulationCount,
        currentOverallPick: start,
        nextTonyPick: end,
        interveningPicks: picks.map((event) => event.overallPick),
        threats,
        tierSurvival: Object.fromEntries(tierEntries.map(([label]) => [label, {
          expectedRemaining: tierRemaining.get(label) / simulationCount,
          probabilityAtLeastOneSurvives: tierAny.get(label) / simulationCount,
        }])),
        policyNote: "Tony target and tier fields select display rows only; they never enter opponent selection probabilities.",
      };
    }

    return Object.freeze({
      contractVersion: CONTRACT_VERSION,
      validatePackage: () => validation,
      health,
      disable,
      pickOwner,
      market,
      createLiveState,
      predict,
      fullBoard,
      simulateTonyWindow,
      applyPick,
    });
  }

  return Object.freeze({ CONTRACT_VERSION, POSITIONS, MANDATORY, normalize, validatePackage, createEngine });
});
