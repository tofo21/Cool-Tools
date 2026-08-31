// Replace this generated package when the research pipeline produces a compatible candidate.
// The active schema is documented in ../model/model-package.schema.json.
window.DRAFT_INTELLIGENCE_PACKAGE = {
  schemaVersion: "1.0.0",
  packageId: "draft-command-provisional-2026-08-27",
  season: 2026,
  leagueProfileId: "espn-keeper-10-ppr-2flex-2026",
  metadata: {
    status: "provisional",
    modelVersion: "fallback-2026.08.27",
    generatedAt: "2026-08-27T00:00:00Z",
    effectiveAt: "2026-08-27T00:00:00Z",
    description: "Existing ECR, platform-room rank and roster heuristic fallback while the research model is under construction.",
    sources: [
      { id: "espn-sourcebook-2020-2026", layer: "platform" },
      { id: "sleeper-sourcebook-2020-2026", layer: "platform" },
      { id: "juiceboxone-ppr-2026-08-27", layer: "room-market" },
    ],
  },
  decisionPolicy: {
    takeMaxSurvival: 0.24,
    waitMinSurvival: 0.48,
    valueMinGap: 6,
    upsideMinProbability: 0.24,
    cliffMinDelta: 4,
    fadeMinReach: 12,
  },
  players: [],
};
