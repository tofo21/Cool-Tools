# Draft Command Runtime Artifact Contract

Version: 1.0.0

Schema dialect: JSON Schema 2020-12

Canonicalization: `draft-command-canonical-json-v1`

This contract defines the integration boundary among Player Truth, ESPN market, ESPN League Value, Opponent Intent, and the compact Draft Command browser bundle. It does not define, tune, or change any research model or formula.

## Binding separation

| Layer | Owns | Must not modify |
| --- | --- | --- |
| Player Truth | Football outcome distributions and player availability | League Value, ESPN price, opponent behavior, room survival |
| League Value | League scoring, replacement, scarcity, FLEX, and roster-adjusted marginal value | Player Truth projections or ESPN source values |
| ESPN Price | Default rank, continuous ADP, source-supplied ordinal ADP, and live-room rank | Player Truth or League Value |
| Opponent Intent | Per-opponent position and exact-player selection probabilities | Player Truth and Tony-side target valuation |
| Room survival | Probability a target is taken or survives before Tony | Opponent selection probabilities in response to Tony labels |

ESPN default rank and ESPN continuous ADP are separate fields. Neither may be copied into the other. `ordinalAdpRank` must remain `null` unless the frozen source explicitly supplies that ordinal value; the builder never derives it from continuous ADP.

## Universal rules

### Required envelope

Every source artifact requires:

- `schemaVersion`: exact supported contract version;
- `artifactType`, `artifactId`, and `artifactVersion`;
- `generatedAt`, `effectiveAt`, and nullable `expiresAt` as RFC 3339 date-times with timezones;
- `status` using the common vocabulary;
- `integrity.canonicalization` and `integrity.payloadSha256`.

All JSON numbers must be finite. JSON `NaN`, `Infinity`, and `-Infinity` are invalid.

### Missing and null semantics

- Missing means unavailable, not observed, not defensibly produced, or not applicable.
- Missing values are represented by an omitted optional field or an explicitly nullable field set to JSON `null`.
- The builder preserves missing as `null`; it never turns missing into `0`.
- Numeric zero is valid only when the underlying quantity is actually zero. Rank and ADP fields cannot be zero.
- Optional Player Truth research outputs may be omitted. The runtime bundle normalizes omitted optional research outputs to `null` for a stable browser interface.

### Integrity hash

`integrity.payloadSha256` is the lowercase SHA-256 of UTF-8 canonical JSON after removing only `integrity.payloadSha256`. Canonical JSON sorts object keys, uses no insignificant whitespace, preserves array order, and rejects non-finite numbers. The artifact file hash is calculated separately and recorded in the runtime manifest.

### Common status values

| Status | Meaning | Promotion behavior |
| --- | --- | --- |
| `candidate` | Structurally complete but not yet promoted | May pass automated gates |
| `validated` | Producer-side validation passed | May pass automated gates |
| `frozen` | Approved immutable input or output | May be consumed; builder refuses to overwrite a frozen output |
| `fallback` | Deliberately degraded but structurally valid | Bundle is labeled fallback/degraded |
| `rejected` | Unusable artifact | Blocking |

Status never means “loading.” The combined bundle requires `modelState` to be exactly `ready`, `fallback`, or `rejected`.

## 1. Player Truth

Schema: `player_truth.schema.json`

Player Truth contains projected football outcomes. `draftCommandBoardRank` is a canonical-board coverage key, not a Player Truth valuation.

### Required player core

| Field | Type/unit | Semantics |
| --- | --- | --- |
| `internalPlayerId` | positive integer | Current stable Draft Command player ID; primary join key |
| `draftCommandBoardRank` | positive integer, ordinal | Player’s rank in the canonical Draft Command input board used only for identity and coverage gates |
| `canonicalPlayerKey` | normalized string | Cross-source canonical identity key; audit aid, never an automatic substitute for `internalPlayerId` |
| `espnPlayerId` | string or `null` | ESPN identity represented as a string; `null` when unresolved or absent |
| `normalizedName` | string | Canonical display name after producer normalization |
| `nflTeam` | 2–3 uppercase letters | NFL team abbreviation |
| `position` | `QB`, `RB`, `WR`, or `TE` | Draft Command fantasy position |
| `identityMatchMethod` | enum | `espn-id`, `canonical-key`, `verified-crosswalk`, `manual-reviewed`, or `unresolved` |
| `identityConfidence` | probability `[0,1]` | Confidence in the identity mapping, not outcome confidence |
| `projectedFullPprPoints` | full-season full-PPR fantasy points | Mean projected total in the model’s expected availability state |
| `projectedPpg` | full-PPR fantasy points per game | Mean projected scoring rate |
| `expectedGames` | games, `[0,17]` | Expected games played, not a probability |
| `availabilityStatus` | enum | `available`, `probable`, `questionable`, `doubtful`, `out`, `ir`, `pup`, `suspended`, or `unknown` |
| `availabilityConfidence` | probability `[0,1]` | Confidence in availability classification |
| `modelConfidence` | probability `[0,1]` | Overall Player Truth confidence |
| `eligibleFeatureFamilies` | unique string array | Feature families admitted by the model contract |
| `quarantinedFeatureFamilies` | unique string array | Feature families excluded from live model use |
| `provenance.modelVersion` | string | Player-level model version |
| `provenance.sourceArtifactIds` | unique string array | Player-level contributing source artifacts |
| `limitations` | unique string array | Player-specific limitations; empty is permitted |

Eligible and quarantined feature families cannot overlap.

### Optional Player Truth research outputs

| Field | Type/unit | Null semantics |
| --- | --- | --- |
| `fullPprPointsP10` | full-season full-PPR points | Distribution output not defensibly available |
| `fullPprPointsP50` | full-season full-PPR points | Distribution output not defensibly available |
| `fullPprPointsP90` | full-season full-PPR points | Distribution output not defensibly available |
| `eliteProbability` | probability `[0,1]` | Elite threshold was not modeled or approved |
| `starterProbability` | probability `[0,1]` | Starter threshold was not modeled or approved |
| `bustProbability` | probability `[0,1]` | Bust threshold was not modeled or approved |

These fields may be omitted or explicitly `null`. When two or more percentile values are present, they must be nondecreasing in P10/P50/P90 order.

## 2. ESPN market

Schema: `espn_market.schema.json`

All record fields are required so source absence is explicit. Nullable fields remain `null` and are never synthesized.

| Field | Type/unit | Semantics |
| --- | --- | --- |
| `internalPlayerId` | positive integer | Stable Draft Command join key |
| `espnPlayerId` | string or `null` | ESPN source identity |
| `espnDefaultRank` | positive integer or `null` | ESPN default draft-room order/rank |
| `espnContinuousAdp` | positive number or `null` | ESPN continuous average overall pick; decimals are preserved |
| `liveRoomRank` | positive integer or `null` | Rank observed in the active room when the source provides it |
| `ordinalAdpRank` | positive integer or `null` | Source-supplied ordinal ADP only |
| `ordinalAdpRankSource` | string or `null` | Required when `ordinalAdpRank` is non-null; otherwise must be null |
| `mappingConfidence` | probability `[0,1]` | Confidence in stable-ID-to-ESPN mapping |
| `captureStatus` | enum | `captured`, `missing-market`, `unmapped`, or `excluded` |

Artifact-level fields include capture time/status, upstream `sourceArtifactId`, upstream `sourceHash`, and declared `rankCoverage`/`adpCoverage`. Coverage is a fraction of `eligiblePlayerCount`; declared coverage must equal values calculated from the records.

## 3. ESPN League Value adapter output

Schema: `espn_league_value.schema.json`

This is the Step 15 output socket. The contract does not supply a formula or weights.

### League configuration

Required fields are `leagueId`, `leagueSettingsVersion`, `settingsHash`, `scoringFormat`, structured `rosterFormat`, `replacementLevelMethodVersion`, `teamCount`, `rounds`, `draftSlot`, `totalPicks`, `tonyTeamId`, and exactly ten keeper slots. The current accepted geometry is 10 teams, 16 rounds, Tony in slot 5, 160 picks, and stable team ID `team-05`. Keeper `overallPick` must match snake geometry.

### Required League Value record

| Field | Type/unit | Semantics |
| --- | --- | --- |
| `internalPlayerId` | positive integer | Stable Draft Command join key |
| `projectedLeaguePoints` | league fantasy points | Projection after applying the league’s scoring settings |
| `replacementValueByPosition` | league fantasy points | Replacement baseline for the player’s position |
| `marginalValue` | league fantasy points above/below replacement | VORP or equivalent marginal value |
| `flexAdjustedValue` | formula-defined numeric units | Value after FLEX opportunity adjustment |
| `leagueValueScore` | numeric score, higher is better | Underlying numeric sort field used by the Decision Board |
| `leagueValueRank` | positive integer, ordinal | Exact descending order of `leagueValueScore`, stable-ID ascending as tie break |
| `positionalRank` | positive integer, ordinal | Exact score order within position |
| `rosterFitAdjustment` | formula-defined numeric units or `null` | `null` means no dynamic roster-fit value was produced; it does not mean zero |
| `confidence` | probability `[0,1]` | Confidence in the League Value output |
| `status` | common artifact status | Record-level usability |
| `provenance.formulaVersion` | string | Must equal top-level `formula.formulaVersion` |
| `provenance.sourceArtifactIds` | unique string array | Inputs used for this record |

`leagueValueScore` is the sorting source. Formatted labels or display text are never sort inputs.

## 4. Opponent Intent

Schema: `opponent_intent.schema.json`

`opponents` is an object keyed by stable IDs such as `team-01`. The object key must equal the nested `teamId`. Display labels are optional; synthetic labels follow `M01`–`M09`.

### Required opponent entry

| Field | Type/unit | Semantics |
| --- | --- | --- |
| `teamId` | stable team ID | Primary opponent key |
| `displayLabel` | `Mnn` string or `null` | Non-identifying display label |
| `nextOverallPick` | positive integer | Opponent’s next pick in the current room state |
| `currentRoster` | stable-ID roster array | Current drafted/keeper players and assigned slots |
| `openRosterPositions` | nonnegative counts | Open QB/RB/WR/TE/FLEX/bench counts |
| `positionProbabilities` | four probabilities | Probability of the opponent’s next pick being each position; total must be 1 |
| `topFivePlayerProbabilities` | exactly five player/probability records | Five named-player probabilities for the opponent’s next pick |
| `otherProbability` | probability `[0,1]` | Remaining exact-player probability; top five plus other must total 1 |
| `confidence` | probability `[0,1]` | Confidence in this opponent prediction |
| `predictionStatus` | enum | `calibrated`, `contextual`, `unvalidated`, or `fallback` |
| `explanatoryDrivers` | unique string array | Human-readable drivers, not model inputs |
| `limitations` | unique string array | Opponent-specific limitations |

### Room survival and tier outputs

`targetSurvival` requires stable player ID, probability taken before Tony, complementary probability survives, most-likely taker, and nullable second-most-likely taker. Taken plus survives must equal 1 within `1e-9`. Taker fields use stable team IDs.

`tierSurvival` contains `tierId`, `probabilityAtLeastOneSurvives` in `[0,1]`, and nonnegative `expectedSurvivors` measured in players.

The artifact also requires deterministic `simulation.seed`, positive `simulation.count`, prediction/model source versions, and limitations. Tony’s tiers, BPA, or League Value may choose which stable player IDs appear on a Threat Board, but those labels cannot feed back into opponent selection probabilities.

## 5. Combined runtime bundle

Schema: `draft_runtime_bundle.schema.json`

The bundle is a compact public-safe browser payload:

- bundle/version/generation metadata and a definite status;
- source commits, artifact IDs, artifact versions, schemas, statuses, file hashes, and payload hashes;
- coverage overall, by position, and by board range;
- confidence policy and explicit `nullMeansMissing: true`;
- league geometry, roster format, and keeper slots;
- normalized Player Truth records;
- independent market and League Value arrays joined by stable ID;
- compact Opponent Intent data or `null`;
- feature flags, limitations, fallback policy, and application compatibility.

The bundle deliberately does not duplicate market or League Value values inside Player Truth records. Browser consumers create stable-ID indexes after loading.

The bundle must not contain raw historical drafts, training ledgers, raw manager pick histories, authenticated ESPN responses, cookies, credentials, local identity crosswalks, simulation ledgers, unnecessary research panels, or private fields. `additionalProperties: false` is used on source contracts and security-sensitive runtime records to make accidental publication visible.

## Identity, coverage, and promotion gates

1. Primary joins use `internalPlayerId` only.
2. Names and `canonicalPlayerKey` are audit evidence, not silent primary joins.
3. Internal IDs, non-null ESPN IDs, canonical keys, and relevant ranks must be unique.
4. Every mapped Player Truth record must have exactly one League Value record.
5. Cross-artifact ESPN IDs for the same internal ID must agree when both are non-null.
6. Every keeper must resolve in Player Truth and League Value.
7. An identity gap at board rank 160 or better is blocking unless the exact internal ID is explicitly approved on the validation command. The approval is reported and does not manufacture a mapping.
8. Lower-board gaps remain in the coverage report but need not block.
9. An individual nonblocking mismatch is excluded from only the affected join; later players continue.
10. If an unknown stable player appears in an Opponent Intent top-five list, that named entry is removed and its unchanged probability mass is added to `otherProbability`. Unknown roster and target-survival entries are removed. No remaining opponent probability is renormalized or otherwise changed.

The known future ESPN benchmark is 199/200 Draft Command identities matched, 10/10 keepers resolved, zero unresolved raw ESPN top-160 players, and zero unresolved raw ranked top-250 players. Jaydon Blue was the sole Draft Command-only miss and was absent from ESPN’s 500-player payload. This is an acceptance benchmark for incoming real artifacts, not synthetic data.

## Compatibility and fallback policy

| Condition | Gate | Required interface behavior |
| --- | --- | --- |
| Player Truth missing, rejected, corrupt, stale, or incompatible | Blocking for candidate bundle | Use clearly labeled provisional/fallback valuation outside the rejected bundle |
| League Value missing, rejected, corrupt, stale, or incompatible | Blocking for candidate bundle | Use clearly labeled provisional/fallback valuation; do not pretend display rank is League Value |
| ESPN market absent | Blocking by default; permitted only with explicit degraded flag | Preserve Player Truth and Manual board; market sort/features are unavailable |
| Opponent Intent absent | Blocking by default; permitted only with explicit degraded flag | Hide or downgrade opponent cards, threat predictions, and room survival; board remains usable |
| Unsupported schema major/version | Blocking | Reject bundle cleanly and preserve draft tracking |
| Stale artifact | Blocking | Report exact expiry; do not silently promote |
| Payload hash mismatch | Blocking | Reject affected artifact as corrupt |
| Incomplete player coverage | Top-160/keepers blocking; lower board reported | Exclude affected joins only where allowed |
| Missing optional research field | Nonblocking | Preserve as `null`; display as unavailable |
| Unresolved player identity | Rank/keeper-dependent | Report stable ID and affected layer; never name-join silently |
| Non-normalized probabilities | Blocking | Reject Opponent Intent artifact |
| Duplicate internal/ESPN player ID | Blocking | Reject affected artifact |
| ESPN rank or ADP absent for individual | Nonblocking | Keep separate field `null`; preserve other market and Player Truth values |
| Runtime bundle incompatible with app release | Blocking at load | Reject bundle and retain current draft state/manual tracking |

The application integration branch must replace any indefinite “Loading model” state with a bounded transition to `ready`, `fallback`, or `rejected`.

## Validator implementation boundary

`runtime_contract_lib.py` is dependency-free and validates the exact JSON Schema subset used here: local `$ref`, `type`, `const`, `enum`, `oneOf`, required/properties/pattern properties/additional properties, object/array cardinality, array uniqueness, string patterns and lengths, finite numeric bounds, and RFC 3339 date-times. Cross-artifact identity, rank, probability, geometry, staleness, and hash rules are semantic gates layered on top of schema validation.
