# Sportsbook Market Source Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Panel layer:** v0.6 sportsbook / Vegas market  
**Status:** Step 10 complete; team-market layer is model-ready with timing controls, player-prop layer remains nested and exploratory

## Purpose

This layer tests whether sportsbook information adds incremental predictive value after consensus projections and fantasy draft markets are already known.

The formal hypothesis remains:

`SPORTSBOOK SIGNAL | CONSENSUS PROJECTION + PUBLIC/PLATFORM ADP`

Sportsbooks are independently incentivized, but a posted season-total line is not automatically an unbiased expected mean. The layer therefore preserves raw market evidence before deriving residuals and separates performance conditional on playing from season-long availability risk.

## Source discipline

The source layer distinguishes three objects:

1. **Team betting environment:** preseason team win totals and posted over/under prices where the source exposes them.
2. **Player season-total markets:** player-specific passing, rushing and receiving lines.
3. **Published calibration evidence:** retrospective category aggregates describing systematic market behavior.

These objects must not be collapsed into one generic `vegas_score`.

## Team win-total series

A single public archive with complete, consistently timestamped, book-specific final lines for all six seasons was not available in a form the reproducible build could retrieve. The canonical v0.6 series therefore preserves one complete 32-team public snapshot per season and carries source family, book, date or bounded window, and odds availability separately.

| Season | Source | Snapshot | Book / definition | Source state |
|---|---|---|---|---|
| 2020 | Boyd's Bets historical results table | Retrospectively preserved 2020 preseason line | Book not specified | `retrospective_preserved_archive_no_odds` |
| 2021 | SportsBettingDime | 2021-09-06 | FanDuel | `preserved_late_preseason_book_table` |
| 2022 | SportsBettingDime | 2022-03-28 | Barstool Sportsbook | `preserved_early_preseason_book_table` |
| 2023 | CBS Sports | 2023-03-29 | Caesars Sportsbook | `preserved_early_preseason_book_table` |
| 2024 | theScore | Post-free-agency opening market; exact publication date not forced | Source article publishes the over price only | `preserved_opening_market_table_partial_odds` |
| 2025 | Boyd's Bets | 2025-08-03 | Multi-book comparison; author-selected midpoint line | `preserved_preseason_multi_book_summary` |

Source URLs:

- https://www.boydsbets.com/nfl-season-win-totals/
- https://www.sportsbettingdime.com/news/nfl/2021-season-win-totals-odds/
- https://www.sportsbettingdime.com/news/nfl/2022-season-win-totals-odds/
- https://www.cbssports.com/nfl/news/2023-nfl-win-totals-oddsmakers-expect-defending-champion-chiefs-to-win-the-most-games-texans-the-fewest/
- https://www.thescore.com/nfl/news/2882262

### Canonical treatment

- one row per team-season;
- `team_win_total` is the source's posted preseason win total;
- over and under American odds are preserved where exposed;
- missing odds stay missing;
- source date is stored only when supported;
- otherwise a bounded snapshot window is retained instead of an invented date;
- source timing and source family must be controlled or sensitivity-tested downstream.

The team win total is a broad team-strength/environment signal. It is **not** an offense-only expectation, so v0.6 does not populate `team_offense_market_score` from it.

### Coverage

The source archive contains exactly **192 team-season observations**, 32 teams in each season from 2020 through 2025.

After team normalization, `team_win_total` is populated for **3,736 of 3,902 player-seasons**. The remaining rows are overwhelmingly free agents, players with unresolved preseason-team labels, or noncanonical aliases rather than missing team-market source rows.

Draft-market player coverage is:

| Season | Draft-market team-win-total coverage |
|---|---:|
| 2020 | 95.57% |
| 2021 | 93.66% |
| 2022 | 91.31% |
| 2023 | 94.83% |
| 2024 | 93.49% |
| 2025 | 96.40% |

## Player season-total archive audit

A public-first audit did not identify a comprehensive, consistently sampled, timestamped player-level NFL season-futures archive covering 2020 through 2025.

The strongest surviving public observations are heterogeneous:

- regional or divisional excerpts;
- editorially selected bets;
- projection-screened extreme disagreements;
- category-level retrospective summaries;
- current APIs centered on game props rather than archived season futures.

A selected table is useful evidence, but it is not representative of the full sportsbook board. Treating it as though every player had an equal probability of appearing would create selection bias.

### Accepted v0.6 player observations

| Season | Source | Rows | Sampling frame | Formal Model-C eligible? |
|---|---|---:|---|---|
| 2021 | PFF league betting guide | 11 | `regional_public_excerpt_nfc_north` | No |
| 2024 | Footballguys WR season props | 5 | `editorial_selected_props` | No |
| 2025 | PFF passing/rushing/receiving analyses | 52 | `projection_screened_extremes` | No |

The long-form player archive therefore contains **68 observations across 58 unique player-seasons**. All 68 match the canonical panel identity layer.

These observations preserve player, position, market type, line, source date, book attribution where supported, source state, sampling frame, published or projection-implied side, and identity-match audit.

They do **not** populate the primary panel's reserved `vegas_pass_yards`, `vegas_rush_yards`, `vegas_rec_yards`, touchdown, reception or snapshot fields.

## Why raw lines are not means

Season-long over bets have more failure paths than unders, including injury, benching, role loss, trades and teammate or quarterback injuries. A published 4for4 review of 604 closing player props from 2021-2022 found 369 unders and 235 overs, a 61% under rate overall. Passing-yard props went under 43 times in 58 observations.

Source:

- https://www.4for4.com/2023/preseason/key-winning-season-long-player-props

The v0.6 artifact stores 30 category-calibration rows: the ten market categories for 2021, the same ten for 2022, and ten combined 2021-2022 summaries. This evidence informs future bias correction but is not joined to players as a predictor.

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

The panel records that selected public observations exist without treating their lines as unbiased features:

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
7. enough seasons and player-seasons to support walk-forward or appropriately nested validation.

When such a source is acquired, Model C must be compared with Model B on identical rows. Derived sportsbook features should include category-aware residuals versus consensus projections and may require separate availability and conditional-performance models.

The team-win-total feature is eligible for historical environment testing now, provided model specifications retain season, snapshot timing and source-family controls. The player-level prop feature is not yet eligible for universal production weighting.

## Paid-source rule

Do not recommend or ingest a paid historical-odds vendor merely because it advertises player props. Require a sample export or schema confirmation showing that it actually includes historical **NFL season-long futures/player totals**, not only weekly game props, and that dates, books, lines and odds are available for the required seasons.

## Leakage and provenance rules

1. Every feature must have been knowable before the season or target draft date.
2. Retrospective archive pages may preserve preseason values, but the source state must say that the page is a later preservation of an earlier market.
3. Never infer an exact historical snapshot date from a current page timestamp.
4. Never backfill a missing player line using an analyst projection.
5. Never infer an offense-only score from a generic team win total.
6. Never treat a projection-screened or editorially selected list as a representative sportsbook board.
7. Preserve raw source values before vig removal, category correction or residual construction.
8. A mixed-source cross-season series must retain source family and snapshot timing rather than presenting itself as one homogeneous closing-line feed.

## v0.6 outputs

Canonical build code:

- `fantasy-draft/research/build_sportsbook_market_v06.py` - base schema, matching, QA and output logic
- `fantasy-draft/research/build_sportsbook_market_v06b.py` - curated complete team-market snapshots
- `fantasy-draft/research/build_sportsbook_market_v06c.py` - curated 2025 PFF player-prop tables and final production entrypoint

Primary outputs:

- `master_player_season_panel_2020_2025_v0_6.csv`
- `sportsbook_team_market_observations_v06.csv`
- `sportsbook_player_prop_observations_v06.csv`
- `sportsbook_category_calibration_v06.csv`
- `sportsbook_source_manifest_v06.csv`
- `sportsbook_match_qa_v06.csv`
- `sportsbook_coverage_qa_v06.csv`

## Step 10 completion rule

Step 10 is complete because:

1. all 32 team win totals are preserved for every season from 2020 through 2025;
2. source date or bounded window and provenance are retained without invented precision;
3. the strongest defensible public player-prop observations are archived with sampling-frame flags;
4. player identity matching is 68 of 68;
5. selected observations do not contaminate the primary `vegas_*` fields;
6. `team_offense_market_score` remains null;
7. the public player-prop archive gap is explicitly recorded;
8. the reproducible v0.6 build and QA pass with zero duplicate season/player IDs.

The final conclusion is asymmetric: the team betting environment is ready for controlled historical testing, while historical player props remain a nested exploratory lane. That is the truthful result of the source audit.
