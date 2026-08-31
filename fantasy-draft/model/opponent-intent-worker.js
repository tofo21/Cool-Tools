"use strict";

// Heavy sequential simulation stays off the ingestion/render thread.
self.window = self;
importScripts("../data/players.js", "../data/opponent-intent-package.js", "./opponent-intent.js");

const managers = [
  null,
  { id: 1, espnTeamId: 10, name: "Justin Gerkin" },
  { id: 2, espnTeamId: 1, name: "Dan Merrick" },
  { id: 3, espnTeamId: 8, name: "Matt Castleman" },
  { id: 4, espnTeamId: 4, name: "Matt Hull" },
  { id: 5, espnTeamId: 9, name: "Tony Fontana" },
  { id: 6, espnTeamId: 7, name: "Matt Runge" },
  { id: 7, espnTeamId: 2, name: "Jon Merrick" },
  { id: 8, espnTeamId: 5, name: "Matt Sloka" },
  { id: 9, espnTeamId: 11, name: "Kyle Cavanaugh" },
  { id: 10, espnTeamId: 12, name: "Brenden Lautenbach" },
];

const engine = self.OpponentIntentModel.createEngine({
  packageData: self.OPPONENT_INTENT_PACKAGE,
  players: self.PLAYER_DATA,
  managers,
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  teamCount: 10,
  tonyTeam: 5,
});

self.addEventListener("message", (event) => {
  const message = event.data || {};
  if (message.type !== "simulate-opponent-window") return;
  try {
    const threat = engine.simulateTonyWindow(message.options || {});
    self.postMessage({ type: "opponent-intent-result", generation: message.generation, threat });
  } catch (error) {
    self.postMessage({ type: "opponent-intent-error", generation: message.generation, error: error.message || String(error) });
  }
});
