(function attachDraftReplay(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.DraftReplay = api;
})(typeof window !== "undefined" ? window : globalThis, () => {
  "use strict";

  const CONTRACT_VERSION = "1.0.0";
  const DEFAULT_TARGETS = Object.freeze({ QB: 2, RB: 5, WR: 7, TE: 2 });
  const DEFAULT_PROFILE = Object.freeze({
    id: "espn-keeper-10-ppr-2flex-2026",
    name: "Tony 2026 ESPN keeper league",
    teamCount: 10,
    rounds: 16,
    tonyTeam: 5,
    targets: DEFAULT_TARGETS,
    keepers: [
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
    ],
  });

  const number = (value, fallback = null) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));
  const round = (value, places = 3) => Number.isFinite(value) ? Number(value.toFixed(places)) : null;
  const normalizeName = (name) => String(name || "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/\b(jr|sr|ii|iii|iv)\b/g, "").replace(/[^a-z0-9]/g, "");
  const ALIASES = new Map([
    ["gabe davis", "gabriel davis"],
    ["hollywood brown", "marquise brown"],
    ["tank dell", "nathaniel dell"],
  ].map(([alias, canonical]) => [normalizeName(alias), normalizeName(canonical)]));

  function pickOwner(overall, teamCount = 10) {
    const pick = Number(overall);
    const roundNumber = Math.ceil(pick / teamCount);
    const slot = ((pick - 1) % teamCount) + 1;
    return roundNumber % 2 ? slot : teamCount + 1 - slot;
  }

  function keeperOverall(roundNumber, team, teamCount = 10) {
    return ((roundNumber - 1) * teamCount) + (roundNumber % 2 ? team : teamCount + 1 - team);
  }

  function pickLabel(overall, teamCount = 10) {
    const roundNumber = Math.ceil(overall / teamCount);
    return `${roundNumber}.${String(((overall - 1) % teamCount) + 1).padStart(2, "0")}`;
  }

  function createProfile(overrides = {}) {
    const teamCount = number(overrides.teamCount, DEFAULT_PROFILE.teamCount);
    const profile = {
      ...DEFAULT_PROFILE,
      ...overrides,
      teamCount,
      rounds: number(overrides.rounds, DEFAULT_PROFILE.rounds),
      tonyTeam: number(overrides.tonyTeam, DEFAULT_PROFILE.tonyTeam),
      targets: { ...DEFAULT_TARGETS, ...(overrides.targets || {}) },
      keepers: (overrides.keepers || DEFAULT_PROFILE.keepers).map((keeper) => ({ ...keeper })),
    };
    profile.totalPicks = profile.teamCount * profile.rounds;
    profile.keepers = profile.keepers.map((keeper) => ({
      ...keeper,
      overall: number(keeper.overall, keeperOverall(keeper.round, keeper.team, profile.teamCount)),
      source: "keeper",
    }));
    profile.tonyPicks = Array.from({ length: profile.rounds }, (_, index) => {
      const roundNumber = index + 1;
      return ((roundNumber - 1) * profile.teamCount) + (roundNumber % 2 ? profile.tonyTeam : profile.teamCount + 1 - profile.tonyTeam);
    });
    return profile;
  }

  function rawPlayerName(raw) {
    return raw?.playerName || raw?.name || raw?.player?.fullName || raw?.player?.name || raw?.metadata?.name ||
      [raw?.metadata?.first_name || raw?.firstName, raw?.metadata?.last_name || raw?.lastName].filter(Boolean).join(" ");
  }

  function rawOverall(raw) {
    return number(raw?.overall, number(raw?.pick_no, number(raw?.pickNumber, number(raw?.overallPickNumber, number(raw?.overall_pick_number)))));
  }

  function calibration(records) {
    const bins = Array.from({ length: 5 }, (_, index) => ({
      min: index * 0.2,
      max: (index + 1) * 0.2,
      count: 0,
      predictedTotal: 0,
      observedTotal: 0,
    }));
    let brierTotal = 0;
    for (const record of records) {
      const probability = clamp(number(record.probability, 0.5));
      const observed = record.observed ? 1 : 0;
      const bin = bins[Math.min(4, Math.floor(probability * 5))];
      bin.count += 1;
      bin.predictedTotal += probability;
      bin.observedTotal += observed;
      brierTotal += (probability - observed) ** 2;
    }
    let ece = 0;
    const summarized = bins.map((bin) => {
      const predicted = bin.count ? bin.predictedTotal / bin.count : null;
      const observed = bin.count ? bin.observedTotal / bin.count : null;
      if (bin.count) ece += (bin.count / records.length) * Math.abs(predicted - observed);
      return {
        range: `${Math.round(bin.min * 100)}–${Math.round(bin.max * 100)}%`,
        count: bin.count,
        predicted: round(predicted),
        observed: round(observed),
      };
    });
    return {
      count: records.length,
      brier: records.length ? round(brierTotal / records.length, 4) : null,
      ece: records.length ? round(ece, 4) : null,
      bins: summarized,
    };
  }

  function createEngine({ players = [], model, profile: profileOverrides = {} } = {}) {
    if (!model || typeof model.market !== "function") throw new Error("A DraftModel adapter is required.");
    const profile = createProfile(profileOverrides);
    const playerById = new Map(players.map((player) => [Number(player.id), player]));
    const playerByName = new Map(players.map((player) => [normalizeName(player.name), player]));
    const keeperOveralls = new Set(profile.keepers.map((keeper) => keeper.overall));
    const keeperPlayerIds = new Set(profile.keepers.map((keeper) => keeper.playerId));

    function resolvePlayer(raw) {
      // playerId is Draft Command's canonical ID. Platform IDs are intentionally
      // resolved by name so a numeric external ID cannot alias the wrong player.
      const directId = number(raw?.playerId);
      if (directId != null && playerById.has(directId)) return playerById.get(directId);
      const normalized = normalizeName(rawPlayerName(raw));
      return playerByName.get(normalized) || playerByName.get(ALIASES.get(normalized)) || null;
    }

    function normalizeLog(input) {
      const envelope = Array.isArray(input) ? { events: input } : (input || {});
      const rawEvents = envelope.events || envelope.picks || envelope.draftPicks || envelope.draft_picks;
      const issues = [];
      const events = [];
      const seenOveralls = new Set();
      const seenPlayers = new Set(keeperPlayerIds);
      const inferredSource = envelope.platform || envelope.source || (rawEvents?.[0]?.pick_no != null ? "sleeper" : "espn");
      const platform = String(inferredSource).toLowerCase().includes("sleeper") ? "sleeper" : "espn";

      if (!Array.isArray(rawEvents)) {
        return { ok: false, platform, events: [], issues: [{ code: "INVALID_LOG", message: "Expected an events or picks array." }], completeThrough: 0 };
      }
      const reportedTeams = number(envelope.teamCount, number(envelope.settings?.teams));
      const reportedRounds = number(envelope.rounds, number(envelope.settings?.rounds));
      if (reportedTeams != null && reportedTeams !== profile.teamCount) issues.push({ code: "TEAM_COUNT", message: `Log reports ${reportedTeams} teams; replay profile requires ${profile.teamCount}.` });
      if (reportedRounds != null && reportedRounds !== profile.rounds) issues.push({ code: "ROUND_COUNT", message: `Log reports ${reportedRounds} rounds; replay profile requires ${profile.rounds}.` });

      for (const raw of rawEvents.slice().sort((a, b) => (rawOverall(a) || 0) - (rawOverall(b) || 0))) {
        const overall = rawOverall(raw);
        const name = rawPlayerName(raw) || "Unknown player";
        if (!Number.isInteger(overall) || overall < 1 || overall > profile.totalPicks) {
          issues.push({ code: "INVALID_PICK", overall, playerName: name, message: "Pick number is outside this draft profile." });
          continue;
        }
        if (seenOveralls.has(overall)) {
          issues.push({ code: "DUPLICATE_PICK", overall, playerName: name, message: "Duplicate overall pick ignored." });
          continue;
        }
        const player = resolvePlayer(raw);
        if (!player) {
          issues.push({ code: "UNRESOLVED_PLAYER", overall, playerName: name, message: "Player is not on the active board." });
          continue;
        }
        const configuredKeeper = profile.keepers.find((keeper) => keeper.overall === overall);
        if (configuredKeeper) {
          if (configuredKeeper.playerId !== player.id) issues.push({ code: "KEEPER_CONFLICT", overall, playerName: name, message: "Pick conflicts with the configured keeper slot." });
          continue;
        }
        if (seenPlayers.has(player.id)) {
          issues.push({ code: "DUPLICATE_PLAYER", overall, playerName: player.name, message: "Player was already drafted or reserved as a keeper." });
          continue;
        }
        const expectedTeam = pickOwner(overall, profile.teamCount);
        const reportedTeam = number(raw.team, number(raw.teamId, number(raw.draft_slot, number(raw.roster_id))));
        if (reportedTeam != null && reportedTeam !== expectedTeam) issues.push({ code: "OWNER_REPAIRED", overall, playerName: player.name, message: `Owner ${reportedTeam} replaced with snake-order team ${expectedTeam}.` });
        events.push({
          overall,
          team: expectedTeam,
          playerId: player.id,
          playerName: player.name,
          source: raw.source || platform,
          timestamp: raw.timestamp || raw.pickedAt || null,
        });
        seenOveralls.add(overall);
        seenPlayers.add(player.id);
      }
      const declaredComplete = number(envelope.completeThrough, number(envelope.complete_through));
      const completeThrough = declaredComplete == null ? Math.max(0, ...events.map((event) => event.overall)) : Math.min(profile.totalPicks, declaredComplete);
      return { ok: events.length > 0, platform, events, issues, completeThrough, profile: { id: profile.id, teamCount: profile.teamCount, rounds: profile.rounds, tonyTeam: profile.tonyTeam } };
    }

    function createDecisionContext(eventsBefore, platform, decisionOverall) {
      const allBefore = [...profile.keepers, ...eventsBefore];
      const drafted = new Set(allBefore.map((event) => event.playerId));
      const available = players.filter((player) => !drafted.has(player.id));
      const roster = allBefore.filter((event) => event.team === profile.tonyTeam).map((event) => playerById.get(event.playerId)).filter(Boolean);
      const counts = roster.reduce((result, player) => {
        result[player.pos] = (result[player.pos] || 0) + 1;
        return result;
      }, { QB: 0, RB: 0, WR: 0, TE: 0 });
      const openTonyPicks = profile.tonyPicks.filter((pick) => !keeperOveralls.has(pick));
      const nextTony = openTonyPicks.find((pick) => pick > decisionOverall) || profile.totalPicks;
      const draftRound = Math.ceil(decisionOverall / profile.teamCount);
      const price = (player) => model.market(player, platform, player[platform] ?? player.market ?? player.adp).price;
      const positionAdjustment = (player) => player.pos === "WR" ? 3.2 : player.pos === "RB" ? 2.2 : player.pos === "TE" ? (player.ecr <= 45 ? 3.4 : 0.4) : player.pos === "QB" ? (player.ecr <= 30 ? -2.5 : -5.5) : 0;
      const fallbackBase = (player) => 102 - player.ecr * 0.48 + positionAdjustment(player) + ((player.market || player.adp) - player.ecr) * 0.08;
      const leagueBase = (player) => model.number(player, "leagueValue.score", () => fallbackBase(player));
      const needBonus = (player) => {
        const target = profile.targets[player.pos] || 0;
        const deficit = Math.max(0, target - (counts[player.pos] || 0));
        let bonus = deficit * 0.65;
        if (player.pos === "QB" && counts.QB === 0 && draftRound >= 7) bonus += 4.5;
        if (player.pos === "TE" && counts.TE === 0 && draftRound >= 6) bonus += 3;
        if (["RB", "WR"].includes(player.pos) && counts[player.pos] < 2) bonus += 2.5;
        if ((counts[player.pos] || 0) >= target) bonus -= 7;
        return bonus;
      };
      const leagueScore = (player) => leagueBase(player) + needBonus(player);
      const fairPick = (player) => model.number(player, "leagueValue.fairPick", player.ecr);
      const valueGap = (player) => price(player) - fairPick(player);
      const fallbackOutcome = (player) => {
        const strength = clamp(1 - ((player.ecr || 200) - 1) / 200);
        return {
          ceilingProbability: clamp(0.10 + strength * 0.21, 0.1, 0.31),
          bustProbability: clamp(0.29 - strength * 0.15 + ((player.landmine || 5.5) - 5.5) * 0.02, 0.1, 0.36),
          eliteProbability: clamp(0.04 + strength * 0.19, 0.04, 0.23),
          starterProbability: clamp(0.34 + strength * 0.48, 0.34, 0.82),
        };
      };
      const outcome = (player) => model.outcome(player, fallbackOutcome(player));
      const survival = (player, target = nextTony) => model.survival(player, platform, target, () => {
        const sigma = clamp(3.2 + price(player) * 0.045, 3.5, 10.5);
        return clamp(1 / (1 + Math.exp((target - price(player)) / sigma)), 0.01, 0.99);
      });
      const ordered = available.slice().sort((a, b) => leagueScore(b) - leagueScore(a));
      const ranks = new Map(ordered.map((player, index) => [player.id, index + 1]));
      const tier = (player) => model.tier(player, { id: `${player.pos}-${Math.max(1, Math.ceil((ranks.get(player.id) || player.ecr || 1) / 8))}`, label: `${player.pos} depth` });
      const cliff = (player) => {
        const next = ordered.find((candidate) => candidate.pos === player.pos && candidate.id !== player.id);
        return next ? Math.max(0, leagueScore(player) - leagueScore(next)) : 12;
      };
      const pool = available.map((player) => {
        const score = leagueScore(player);
        const gap = valueGap(player);
        const surviveNext = survival(player);
        const playerOutcome = outcome(player);
        const fitImpact = needBonus(player) + model.number(player, "leagueValue.rosterFitBase", 0);
        const cliffValue = cliff(player);
        const vorpLost = model.number(player, "decision.expectedVorpLostByWaiting", () => cliffValue * (1 - surviveNext));
        const championshipEquity = model.number(player, "leagueValue.championshipEquityBase", 0);
        return {
          player,
          price: price(player),
          baseScore: leagueBase(player),
          score,
          gap,
          surviveNext,
          tier: tier(player),
          cliff: cliffValue,
          fitImpact,
          outcome: playerOutcome,
          pickNow: score + gap * 0.72 + fitImpact * 0.9 + (1 - surviveNext) * 9 + vorpLost * 1.1 + championshipEquity * 100 - playerOutcome.bustProbability * 3,
        };
      });
      const by = (scorer) => pool.slice().sort((a, b) => scorer(b) - scorer(a))[0] || null;
      const recommendations = {
        bestPlayer: by((entry) => entry.baseScore),
        bestValue: by((entry) => entry.gap * 1.8 + entry.score * 0.12 + 8),
        bestFit: by((entry) => entry.score + entry.fitImpact * 1.8 + entry.cliff),
        bestCeiling: by((entry) => entry.outcome.ceilingProbability * 60 + entry.outcome.eliteProbability * 35 + entry.score * 0.2 - entry.outcome.bustProbability * 12),
        safestWait: by((entry) => entry.surviveNext * 52 + entry.score * 0.2 - entry.cliff * (1 - entry.surviveNext) * 2.2),
        bestPickNow: by((entry) => entry.pickNow),
        platformPrice: by((entry) => -entry.price),
      };
      const verdict = (entry) => model.decisionTag({
        override: model.text(entry.player, "decision.override", null),
        reach: fairPick(entry.player) - decisionOverall,
        survival: entry.surviveNext,
        quality: (ranks.get(entry.player.id) || 999) <= Math.max(36, decisionOverall + 18),
        cliff: entry.cliff,
        valueGap: entry.gap,
        ceilingProbability: entry.outcome.ceilingProbability,
      });
      return { available, pool, recommendations, nextTony, verdict, counts };
    }

    function run(input) {
      const normalized = normalizeLog(input);
      if (!normalized.ok) return { ok: false, contractVersion: CONTRACT_VERSION, normalized, summary: null, decisions: [] };
      const events = normalized.events;
      const eventsByPlayer = new Map(events.map((event) => [event.playerId, event]));
      const eventOveralls = new Set(events.map((event) => event.overall));
      const eventsBefore = [];
      const decisions = [];
      const individualRecords = [];
      const tierRecords = [];
      const strategyRows = new Map([
        ["recorded", { id: "recorded", label: "Recorded actual", choices: 0, score: 0, gap: 0, agreements: 0 }],
        ["bpa", { id: "bpa", label: "Static best player", choices: 0, score: 0, gap: 0, agreements: 0 }],
        ["platform", { id: "platform", label: `${normalized.platform.toUpperCase()} room price`, choices: 0, score: 0, gap: 0, agreements: 0 }],
        ["model", { id: "model", label: "Best Pick Now", choices: 0, score: 0, gap: 0, agreements: 0 }],
      ]);
      let counterfactualCorrect = 0;
      let counterfactualCount = 0;

      for (const event of events) {
        if (event.team === profile.tonyTeam && !keeperOveralls.has(event.overall)) {
          const context = createDecisionContext(eventsBefore, normalized.platform, event.overall);
          const actualPlayer = playerById.get(event.playerId);
          const actualEntry = context.pool.find((entry) => entry.player.id === event.playerId) || null;
          const recommended = context.recommendations.bestPickNow;
          const actualCall = recommended ? context.verdict(recommended) : null;
          const completeWindow = context.nextTony > event.overall && normalized.completeThrough >= context.nextTony &&
            Array.from({ length: Math.max(0, context.nextTony - event.overall - 1) }, (_, index) => event.overall + index + 1)
              .every((overall) => keeperOveralls.has(overall) || eventOveralls.has(overall));
          const candidateRows = context.pool.slice().sort((a, b) => b.pickNow - a.pickNow).slice(0, 20).filter((entry) => entry.player.id !== event.playerId);

          if (completeWindow) {
            for (const entry of candidateRows) {
              const selected = eventsByPlayer.get(entry.player.id);
              individualRecords.push({
                decisionOverall: event.overall,
                targetOverall: context.nextTony,
                playerId: entry.player.id,
                probability: entry.surviveNext,
                observed: !selected || selected.overall >= context.nextTony,
              });
            }
            const tiers = new Map();
            for (const entry of candidateRows) {
              if (!tiers.has(entry.tier.id)) tiers.set(entry.tier.id, []);
              tiers.get(entry.tier.id).push(entry);
            }
            for (const [tierId, members] of tiers) {
              if (members.length < 2) continue;
              const probability = 1 - members.reduce((product, member) => product * (1 - member.surviveNext), 1);
              const observed = members.some((member) => {
                const selected = eventsByPlayer.get(member.player.id);
                return !selected || selected.overall >= context.nextTony;
              });
              tierRecords.push({ decisionOverall: event.overall, targetOverall: context.nextTony, tierId, probability, observed });
            }
          }

          let counterfactual = { status: "pending", correct: null };
          if (recommended && recommended.player.id === event.playerId) {
            counterfactual = { status: "taken", correct: actualCall === "TAKE" || actualCall === "VALUE" || actualCall === "UPSIDE" || actualCall === "POSITION CLIFF" };
          } else if (recommended && completeWindow) {
            const selected = eventsByPlayer.get(recommended.player.id);
            const survived = !selected || selected.overall >= context.nextTony;
            const waitCall = actualCall === "WAIT" || actualCall === "FADE AT PRICE";
            const correct = waitCall ? survived : !survived;
            counterfactual = { status: survived ? "survived" : "lost", correct };
            counterfactualCorrect += correct ? 1 : 0;
            counterfactualCount += 1;
          }

          const choices = {
            recorded: actualEntry,
            bpa: context.recommendations.bestPlayer,
            platform: context.recommendations.platformPrice,
            model: recommended,
          };
          for (const [strategyId, choice] of Object.entries(choices)) {
            if (!choice) continue;
            const row = strategyRows.get(strategyId);
            row.choices += 1;
            row.score += choice.score;
            row.gap += choice.gap;
            if (choice.player.id === event.playerId) row.agreements += 1;
          }

          decisions.push({
            overall: event.overall,
            pick: pickLabel(event.overall, profile.teamCount),
            nextTonyOverall: context.nextTony,
            nextTonyPick: pickLabel(context.nextTony, profile.teamCount),
            actual: actualEntry ? { playerId: actualPlayer.id, name: actualPlayer.name, pos: actualPlayer.pos, score: round(actualEntry.score), valueGap: round(actualEntry.gap) } : { playerId: actualPlayer.id, name: actualPlayer.name, pos: actualPlayer.pos, score: null, valueGap: null },
            recommendation: recommended ? { playerId: recommended.player.id, name: recommended.player.name, pos: recommended.player.pos, score: round(recommended.score), valueGap: round(recommended.gap), survival: round(recommended.surviveNext), tag: actualCall } : null,
            agreed: recommended?.player.id === event.playerId,
            counterfactual,
            calibrationReady: completeWindow,
          });
        }
        eventsBefore.push(event);
      }

      const strategies = [...strategyRows.values()].map((row) => ({
        id: row.id,
        label: row.label,
        choices: row.choices,
        meanDraftScore: row.choices ? round(row.score / row.choices) : null,
        meanValueGap: row.choices ? round(row.gap / row.choices) : null,
        actualAgreement: row.choices ? round(row.agreements / row.choices) : null,
      }));
      const individual = calibration(individualRecords);
      const tiers = calibration(tierRecords);
      return {
        ok: true,
        contractVersion: CONTRACT_VERSION,
        generatedAt: new Date().toISOString(),
        normalized,
        modelHealth: model.health(),
        summary: {
          decisions: decisions.length,
          completeThrough: normalized.completeThrough,
          completeThroughLabel: normalized.completeThrough ? pickLabel(normalized.completeThrough, profile.teamCount) : "—",
          individualCalibration: individual,
          tierCalibration: tiers,
          recommendationAgreement: decisions.length ? round(decisions.filter((decision) => decision.agreed).length / decisions.length) : null,
          counterfactualAccuracy: counterfactualCount ? round(counterfactualCorrect / counterfactualCount) : null,
          counterfactualCount,
          issueCount: normalized.issues.length,
        },
        strategies,
        decisions,
        calibrationRecords: { individual: individualRecords, tiers: tierRecords },
      };
    }

    function sampleLog(platform = "espn") {
      const sorted = players.filter((player) => !keeperPlayerIds.has(player.id)).slice().sort((a, b) => {
        const aPrice = number(playerById.get(a.id)?.[platform], number(a.market, a.ecr));
        const bPrice = number(playerById.get(b.id)?.[platform], number(b.market, b.ecr));
        return aPrice - bPrice || a.ecr - b.ecr;
      });
      const events = [];
      let cursor = 0;
      for (let overall = 1; overall <= profile.totalPicks; overall += 1) {
        if (keeperOveralls.has(overall)) continue;
        const player = sorted[cursor++];
        if (!player) break;
        events.push({
          overall,
          team: pickOwner(overall, profile.teamCount),
          playerId: player.id,
          playerName: player.name,
          source: "deterministic-fixture",
        });
      }
      return {
        schemaVersion: CONTRACT_VERSION,
        name: `${platform.toUpperCase()} deterministic full-draft fixture`,
        platform,
        teamCount: profile.teamCount,
        rounds: profile.rounds,
        completeThrough: profile.totalPicks,
        events,
      };
    }

    return Object.freeze({ profile, normalizeLog, run, sampleLog });
  }

  return Object.freeze({ CONTRACT_VERSION, DEFAULT_PROFILE, calibration, createEngine, createProfile, keeperOverall, normalizeName, pickLabel, pickOwner });
});
