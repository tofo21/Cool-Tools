# Football Fundamentals Source Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Panel layer:** v0.7 prior-season football opportunity, role, and efficiency  
**Status:** **STEP 11 COMPLETE** | reproducible build passed | formal predictive weighting not yet assigned

## Purpose

This layer supplies the football-level features required by the Research Contract's opportunity and efficiency stages:

- **Model F:** earlier validated information families + opportunity and role;
- **Model G:** Model F + appropriately controlled efficiency and talent indicators.

The source layer does not assume that an advanced metric is predictive merely because it is granular. Each feature must later earn weight through position-specific, walk-forward out-of-sample testing.

## Temporal contract

Every v0.7 football feature is a **lag-one completed regular-season observation**.

For a target preseason row in season `Y`:

`football_source_season = Y - 1`

Examples:

- 2020 preseason row uses 2019 regular-season football data;
- 2024 preseason row uses 2023 regular-season football data;
- 2025 preseason row uses 2024 regular-season football data.

No target-season regular-season play, snap, usage, efficiency, or outcome is allowed into the preseason feature row. The production build asserts this relationship on all 3,902 rows and reports zero lag-alignment violations.

Rookies and players without prior NFL samples remain missing. They are not assigned zero opportunity or league-average efficiency during ingestion.

## Accepted source families

### 1. nflverse player regular-season summaries

Annual source pattern:

`https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg_{season}.parquet`

Accepted source seasons: 2019-2024.

Primary uses:

- games;
- passing attempts;
- carries;
- targets and receptions;
- rushing and receiving yards;
- receiving air yards and yards after catch;
- first downs;
- target share, air-yard share, WOPR, RACR;
- passing, rushing, and receiving EPA;
- CPOE;
- explosive-play counts;
- realized prior-season PPR points.

### 2. nflverse / Pro Football Reference snap counts

Annual source pattern:

`https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.parquet`

Accepted source seasons: 2019-2024, regular season only.

Primary uses:

- offensive snaps;
- games with offensive snaps;
- average game-level offensive snap percentage;
- weighted offensive snap share across games in which the player logged an offensive snap.

An offense snap is a role and field-presence measure. It is not relabeled as a route.

### 3. nflverse play-by-play

Annual source pattern:

`https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet`

Accepted source seasons: 2019-2024, regular season only.

Only the columns required for opportunity construction are loaded.

Primary uses:

- carries and targets;
- active-game carry share;
- active-game target share;
- active-game air-yard share;
- WOPR calculated as `1.5 × target share + 0.7 × air-yard share`;
- red-zone carries and targets inside the 20 and 10;
- goal-line carries and targets inside the 5;
- end-zone targets;
- targets with 20+ air yards;
- third-down carries and targets;
- two-minute carries and targets.

Quarterback kneels are removed from rushing opportunity.

Active-game shares use team opportunity only from games in the player's observed active-game universe, limiting the distortion created by dividing a partial-season player by a full team season.

### 4. ffverse `ffopportunity`

Annual source pattern:

`https://github.com/ffverse/ffopportunity/releases/download/v1.0.0-data/ep_weekly_{season}.parquet`

Accepted source seasons: 2019-2024, regular-season weeks only.

Primary uses:

- passing expected fantasy points;
- receiving expected fantasy points;
- rushing expected fantasy points;
- total expected fantasy points;
- skill-position expected fantasy points;
- team-share versions of expected fantasy points across active games;
- fantasy points over expectation;
- actual versus expected yards.

The canonical `prev_weighted_opportunity_points` field uses receiving plus rushing expected fantasy points for RB/WR/TE and total expected fantasy points for QB.

### 5. PFR advanced rushing and receiving through nflverse

Canonical source files:

- `advstats_season_rush.parquet`
- `advstats_season_rec.parquet`

Accepted source seasons: 2019-2024.

Primary uses:

- rushing yards before contact per attempt;
- rushing yards after contact per attempt;
- rushing broken tackles and rate;
- receiving aDOT;
- receiving yards before catch and after catch per reception;
- drop percentage;
- receiving broken tackles and rate;
- passer rating when targeted.

### 6. NFL Next Gen Stats through nflverse

Canonical source files:

- `ngs_receiving.parquet`
- `ngs_rushing.parquet`
- `ngs_passing.parquet`

Accepted source seasons: 2019-2024 regular-season summary rows.

Primary uses:

- receiver cushion and separation;
- intended air yards;
- YAC, expected YAC, and YAC over expectation;
- rushing efficiency, stacked-box rate, time to line of scrimmage, and rushing yards over expectation;
- quarterback time to throw, air yards, aggressiveness, expected completion percentage, and CPOE.

NGS applies its own qualifying-volume rules, so coverage is intentionally lower than basic usage and snap coverage.

### 7. DynastyProcess player-ID crosswalk

Used to map PFR identities to stable GSIS identities. Exact stable-ID joins are preferred. A unique normalized name + position fallback is permitted only where a single unambiguous GSIS identity exists for that source season.

## Opportunity and efficiency remain separate

The ingestion layer preserves raw metrics and their denominators. It does not perform arbitrary source-layer shrinkage.

Examples:

- yards after contact per attempt is stored with rushing attempts;
- separation is stored with NGS targets;
- rushing yards over expectation per attempt is stored with NGS rushing attempts;
- EPA per opportunity is stored alongside the corresponding opportunity count;
- expected fantasy points and fantasy points over expectation remain separate.

Regression toward league/position means, minimum-volume rules, nonlinear transformations, and interactions belong in the walk-forward modeling stage. This keeps the evidence layer auditable and lets the validation process decide how aggressively each metric should be shrunk.

## Route and first-read source gaps

No accepted, comparable public player-level route-run series covering every source season from 2019 through 2024 was identified.

The participation archive identifies offensive personnel on the field and, on some plays, a primary receiver's route. It does not provide a complete all-player route count that can be safely treated as historical routes run.

Therefore these fields remain explicitly null:

- `prev_routes`
- `prev_route_participation`
- `prev_targets_per_route`
- `prev_yards_per_route`

`route_metrics_source_state = PUBLIC_HISTORICAL_ROUTE_SOURCE_GAP_NOT_IMPUTED`

Offensive snaps are retained as a distinct role proxy and are never renamed routes. First-read target share is also retained as a public historical source gap rather than inferred.

## Final coverage

Coverage below is measured among the broad draft-market player universe.

| Target season | Draft-market rows | Prior core stats | Snap share | PBP opportunity | Weighted opportunity | PFR advanced | NGS |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 451 | 79.82% | 80.71% | 80.71% | 80.71% | 79.60% | 44.35% |
| 2021 | 489 | 80.16% | 79.55% | 79.96% | 79.96% | 79.14% | 43.97% |
| 2022 | 472 | 82.20% | 82.42% | 82.42% | 82.42% | 81.57% | 43.64% |
| 2023 | 464 | 82.33% | 82.33% | 82.33% | 82.33% | 81.03% | 43.97% |
| 2024 | 522 | 80.08% | 80.27% | 80.27% | 80.27% | 78.74% | 38.51% |
| 2025 | 445 | 79.55% | 79.78% | 79.78% | 79.78% | 79.33% | 47.42% |

The roughly 20% without prior football samples is expected. It includes rookies, players without prior regular-season action, and fringe preseason-market entries. Missing prior experience is itself information and must remain distinguishable from a true zero.

## Identity and source QA

Final source-row identity performance:

- snap counts: 99.70%-99.89% of relevant rows mapped by season;
- PFR advanced rushing: 99.90%;
- PFR advanced receiving: 99.90%;
- NGS passing/rushing/receiving: 100% of retained rows already carry GSIS identity;
- play-by-play opportunities: 100% of retained player events carry GSIS identity;
- ffopportunity: 100% of retained weekly player-game rows carry GSIS identity.

The canonical panel remains:

- 3,902 player-season rows;
- 268 total fields;
- 0 duplicate season/player IDs;
- 0 lag-alignment violations;
- 0 populated route values;
- 2,905 rows with prior core NFL statistics;
- 2,943 rows with snap-share features;
- 2,947 rows with weighted-opportunity features.

## Modeling acceptance rules

Formal testing must:

1. evaluate opportunity/role features before adding efficiency;
2. compare nested models on identical player-season samples;
3. use walk-forward season splits, never random player-season splits;
4. run position-specific specifications;
5. preserve a rookie/no-prior-NFL-sample indicator rather than zero-filling;
6. retain denominators and impose minimum-volume/shrinkage rules inside training folds only;
7. compare full-season outcome and performance-conditional-on-playing targets;
8. report whether a metric improves MAE/rank correlation, elite/bust calibration, or draft-value residual prediction;
9. reject metrics whose apparent lift is unstable across seasons or driven by tiny samples.

## v0.7 outputs

Canonical production entrypoint:

- `fantasy-draft/research/build_football_fundamentals_v07.py`

Primary outputs:

- `master_player_season_panel_2020_2025_v0_7.csv`
- `football_fundamentals_prior_season_v07.csv`
- `football_fundamentals_coverage_qa_v07.csv`
- `football_fundamentals_match_qa_v07.csv`
- `football_fundamentals_source_manifest_v07.csv`
- `football_fundamentals_field_dictionary_v07.csv`
- `football_fundamentals_source_gaps_v07.csv`
- `football_fundamentals_integrity_v07.json`

Final accepted workflow run: **33353208203**  
Final artifact SHA-256: `fe6872854174169800250ba654695bc29fd7c7695d612d50bb0205efbf2a6d20`

## Step 11 completion decision

**STEP 11 IS COMPLETE.**

The layer now contains broad, leak-safe prior-season opportunity and role measures plus multiple independently sourced efficiency families. It does not yet establish that those variables improve preseason prediction. That determination belongs to the next step: the formal walk-forward signal scorecard.
