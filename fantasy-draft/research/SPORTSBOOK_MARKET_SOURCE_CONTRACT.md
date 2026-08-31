# Sportsbook Market Source Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Panel layer:** v0.6 sportsbook / Vegas market  
**Status:** Step 10 source architecture frozen; team-market layer is production-ready, player-prop layer remains nested and incomplete

## Purpose

This layer tests whether sportsbook information adds incremental predictive value after consensus projections and fantasy draft markets are already known.

The formal hypothesis remains:

`SPORTSBOOK SIGNAL | CONSENSUS PROJECTION + PUBLIC/PLATFORM ADP`

Sportsbooks are independently incentivized, but a posted season-total line is not automatically an unbiased expected mean. The layer therefore preserves raw market evidence before deriving residuals, and separates a player's performance conditional on playing from his probability of remaining available for the full season.

## Source discipline

The source layer distinguishes three different objects:

1. **Team betting environment:** preseason team win totals and related futures information.
2. **Player season-total markets:** player-specific passing, rushing and receiving lines.
3. **Published calibration evidence:** retrospective category aggregates describing systematic market behavior.

These objects must not be collapsed into a single generic `vegas_score`.

## Team win-total series

Pro-Football-Reference preserves a complete preseason-odds table for every season from 2020 through 2025. The table contains all 32 teams, Super Bowl odds and the preseason win total. The historical odds are attributed by the archive to SportsOddsHistory.com.

### Accepted canonical treatment

- one row per team-season;
- `team_win_total` is the published preseason W/L over-under line;
- Super Bowl odds are preserved separately;
- exact sportsbook is left unspecified when the archive does not identify one;
- the source is labeled `retrospective_preserved_final_preseason_line`;
- an exact snapshot date is retained only when the archive exposes one;
- otherwise the source window is `final_preseason_archive` rather than an invented date.

The team win total is a broad team-strength/environment signal. It is **not** an offense-only expectation, so v0.6 does not populate `team_offense_market_score` from it.

## Player season-total archive audit

A public-first audit did not identify a comprehensive, consistently sampled, timestamped player-level NFL season-futures archive covering 2020-2025.

The strongest surviving public observations are heterogeneous:

- regional or divisional excerpts;
- editorially selected bets;
- projection-screened extreme disagreements;
- category-level retrospective summaries;
- current APIs centered on game props rather than archived season futures.

A selected table is useful evidence, but it is not representative of the full sportsbook board. Treating it as though every player had an equal probability of appearing would create selection bias.

### Accepted v0.6 player observations

| Season | Source | Evidence | Sampling frame | Formal Model-C eligible? |
|---|---|---|---|---|
| 2021 | PFF league betting guide | Public NFC North season-total excerpt | `regional_public_excerpt_nfc_north` | No |
| 2024 | Footballguys | Five editorially selected WR props | `editorial_selected_props` | No |
| 2025 | PFF passing/rushing/receiving analyses | Tables selected for large projection-versus-line differences | `projection_screened_extremes` | No |

These observations are preserved in a long-form archive with player, position, market type, line, source date, book attribution where supported, source state, sampling frame and identity-match audit.

They do **not** populate the primary panel's reserved `vegas_pass_yards`, `vegas_rush_yards`, `vegas_rec_yards`, touchdown or reception fields.

## Why raw lines are not means

Season-long over bets have more failure paths than unders, including injury, benching, role loss, trades and teammate or quarterback injuries. A published 4for4 review of 604 closing player props from 2021-2022 found 369 unders and 235 overs, a 61% under rate overall. Passing-yard props went under 43 times in 58 observations.

This evidence is stored as category-level calibration data. It supports modeling systematic market-category bias, but it does not identify which individual historical player lines belong in the panel.

## Canonical long-form player-prop schema

- `season`
- `player_name`
- `position`
- `market_type`
- `raw_market_label`
- `line`
- `over_odds_american`
- `under_odds_american`
- `recommendation_side`
- `recommendation_odds_american`
- `projection`
- `projection_line_differential`
- `book`
- `source_date`
- `source_provider`
- `source_url`
- `retrieval_url`
- `source_state`
- `sampling_frame`
- `primary_model_eligible`
- identity-match fields
- `notes`

Missing odds remain missing. Page-level multi-book attribution must not be converted into a fictitious row-level book.

## Team-market panel fields

- `team_win_total`
- `team_win_total_super_bowl_odds`
- `team_win_total_snapshot_date`
- `team_win_total_snapshot_window`
- `team_win_total_source_state`
- `team_win_total_source_url`
- `team_win_total_retrieval_url`
- `team_win_total_source_provider`
- `team_win_total_underlying_provider`
- `team_win_total_book`

## Player-observation metadata fields

The panel may record that selected public observations exist without treating their lines as unbiased features:

- `sportsbook_player_prop_observation_count`
- `sportsbook_player_prop_source_count`
- `sportsbook_player_prop_sampling_frames`
- `sportsbook_player_prop_primary_model_eligible`

For v0.6, `sportsbook_player_prop_primary_model_eligible` is false for every preserved player observation.

## Formal Model-C acceptance rule

The Research Contract's Model C is not satisfied by sprinkling selected prop lines into the panel.

A player-level sportsbook feature becomes eligible for formal testing only when the source provides a sufficiently broad and consistently sampled preseason board with:

1. player identity;
2. market type;
3. line;
4. book or defensible consensus definition;
5. timestamp or bounded preseason window;
6. odds where available;
7. enough seasons/player-seasons to support walk-forward or appropriately nested validation.

When such a source is acquired, Model C must be compared with Model B on identical rows. Derived sportsbook features should include category-aware residuals versus consensus projections and may require separate availability and conditional-performance models.

## Paid-source rule

Do not recommend or ingest a paid historical-odds vendor merely because it advertises player props. Require a sample export or schema confirmation showing that it actually includes historical **NFL season-long futures/player totals**, not only weekly game props, and that the required dates, books, lines and odds are available for the requested seasons.

## Leakage and provenance rules

1. Every feature must have been knowable before the season or target draft date.
2. Retrospective archive pages may preserve preseason values, but the source state must say that the page is a later preservation of an earlier market.
3. Never infer an exact historical snapshot date from a current page timestamp.
4. Never backfill a missing player line using an analyst projection.
5. Never infer an offense-only score from a generic team win total.
6. Never treat a projection-screened or editorially selected list as a representative sportsbook board.
7. Preserve raw source values before any vig removal, category correction or residual construction.

## v0.6 outputs

Canonical build code:

- `fantasy-draft/research/build_sportsbook_market_v06.py`

Primary outputs:

- `master_player_season_panel_2020_2025_v0_6.csv`
- `sportsbook_team_market_observations_v06.csv`
- `sportsbook_player_prop_observations_v06.csv`
- `sportsbook_category_calibration_v06.csv`
- `sportsbook_source_manifest_v06.csv`
- `sportsbook_match_qa_v06.csv`
- `sportsbook_coverage_qa_v06.csv`
- raw preserved source tables

## Step 10 completion rule

Step 10 is complete when:

1. all 32 team win totals are attached for every season from 2020 through 2025;
2. source date/window and provenance are retained without invented precision;
3. the strongest defensible public player-prop observations are archived with sampling-frame flags;
4. player identity matching exceeds 95%;
5. selected observations do not contaminate the primary `vegas_*` fields;
6. `team_offense_market_score` remains null unless an offense-specific market is acquired;
7. the public player-prop archive gap is explicitly recorded;
8. the reproducible v0.6 build and QA pass.

The expected conclusion is permitted to be asymmetric: the team betting environment can be ready for modeling while the historical player-prop feature remains blocked for formal production weighting. That is the truthful result of the source audit, not a failure to finish the step.
