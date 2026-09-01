# Step 14 to Step 15 / Runtime Integration Handoff

Step 14 branch: `codex/step14-player-truth-2026`

## Immutable Step 14 input

- Runtime artifact: `fantasy-draft/data/candidate/player-truth/player_truth_step14.json`
- Contract: `fantasy-draft/contracts/player_truth.schema.json`
- Contract version: `1.0.0`
- Player Truth artifact version: `step14-2026.1`
- Player Truth file SHA-256: `f6488e648af2549f1b7fa50eb485aa8f29784280144796e5e6d581a13b477bd3`
- Universal P50: frozen consensus `standardized_full_ppr_points`
- Join key for all downstream artifacts: integer `internalPlayerId`

Step 15 must not modify, impute, rescale, or replace any Player Truth outcome. It must not use a player name, ESPN rank, ADP, ECR, auction value, or market price as an outcome join or projection substitute.

## Exact thin Step 15 adapter output

Emit:

`fantasy-draft/data/candidate/league-value/espn_league_value_step15.json`

Validate it against:

`fantasy-draft/contracts/espn_league_value.schema.json`

The adapter must:

1. consume only the committed Step 14 Player Truth artifact plus the separately approved 2026 league-settings/keeper inputs required by the Step 15 formula;
2. emit one League Value record per supported Player Truth `internalPlayerId`, with full coverage for all 159 Player Truth rows at board rank 160 or better;
3. preserve `projectedFullPprPoints`, `projectedPpg`, and `expectedGames` as separate upstream heads and leave Player Truth unchanged;
4. declare an independently reviewed formula version, generator, source artifact IDs, source commits, settings version/hash, replacement-level method, scoring format, roster geometry, and exactly ten keeper slots;
5. emit the required numeric fields `projectedLeaguePoints`, `replacementValueByPosition`, `marginalValue`, `flexAdjustedValue`, `leagueValueScore`, `leagueValueRank`, and `positionalRank`;
6. preserve an unavailable dynamic `rosterFitAdjustment` as `null`, not zero;
7. order `leagueValueRank` by descending numeric `leagueValueScore` with ascending stable ID as the tie break, and calculate positional ranks by the same rule within position;
8. sign the JSON using `draft-command-canonical-json-v1` and retain candidate/validated status until the normal promotion gate completes.

The contract requires current league geometry to be provided explicitly. The runtime harness expects 10 teams, 16 rounds, 160 total picks, Tony at draft slot 5 with stable team ID `team-05`, and valid snake-draft keeper geometry. The Step 15 formula and weights are not supplied by the runtime contract and must not be invented.

## Explicit identity and coverage handling

- Keenan Allen, Draft Command ID 143, has a resolved identity but no approved consensus projection. He is absent from Player Truth and must remain absent from League Value. Do not synthesize a projection or an orphan League Value row. The generic `--approve-top160-identity-gap` flag is not applicable to an absent Player Truth row.
- Jaydon Blue, Draft Command ID 190, has a consensus projection but no Step 13B GSIS/ESPN crosswalk. Retain internal ID 190; do not invent an ESPN or GSIS ID. The harness will surface this lower-board unresolved identity as a warning.
- Kayshon Boutte retains current Draft Command team HOU while the frozen consensus source-team provenance remains NE. Do not overwrite either value.
- Josh Jacobs remains at 256.850 full-PPR points and `COMMISSIONER_EXEMPT`; Step 15 must not create a return date or games adjustment.

## Full runtime validation

Once the real ESPN market, Step 15 League Value, and Opponent Intent artifacts are present, choose one RFC 3339 timestamp and reuse it for both commands:

```bash
export DRAFT_RUNTIME_AS_OF="YYYY-MM-DDTHH:MM:SSZ"

python3 fantasy-draft/research/validate_draft_runtime_bundle.py \
  --player-truth fantasy-draft/data/candidate/player-truth/player_truth_step14.json \
  --espn-market fantasy-draft/data/candidate/espn-market/espn_market_frozen.json \
  --league-value fantasy-draft/data/candidate/league-value/espn_league_value_step15.json \
  --opponent-intent fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json \
  --as-of "$DRAFT_RUNTIME_AS_OF" \
  --report fantasy-draft/reports/DRAFT_RUNTIME_REAL_ARTIFACT_VALIDATION.md \
  --json

python3 fantasy-draft/research/build_draft_runtime_bundle.py \
  --player-truth fantasy-draft/data/candidate/player-truth/player_truth_step14.json \
  --espn-market fantasy-draft/data/candidate/espn-market/espn_market_frozen.json \
  --league-value fantasy-draft/data/candidate/league-value/espn_league_value_step15.json \
  --opponent-intent fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json \
  --output-dir fantasy-draft/data/candidate/runtime-contract \
  --bundle-filename draft_runtime_bundle.json \
  --manifest-filename draft_runtime_bundle_manifest.json \
  --report-filename draft_runtime_bundle_validation.md \
  --as-of "$DRAFT_RUNTIME_AS_OF" \
  --json
```

Do not use missing-artifact flags for final acceptance. Do not change Draft Command application, UI, synchronization, extension, Opponent Intent, or deployment code during the thin Step 15 adapter work.
