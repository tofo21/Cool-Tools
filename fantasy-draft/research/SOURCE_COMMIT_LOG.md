# Fantasy Draft Research Source Commit Log

This file records source-interpretation decisions that materially affect the historical player-season panel schema or downstream model treatment. It supplements, but does not replace, the canonical research contract and sourcebooks.

## v0.2 | ESPN + Sleeper historical platform layers | 2026-08-30

### ESPN

1. **Treat ESPN official/default rank and realized ESPN ADP as separate features.** Their disagreement is a potentially useful behavioral signal and should not be collapsed during ingestion.
2. **Store the preserved 2020-2025 ESPN ADP archive as `espn_adp_rank` (ordinal), not `espn_adp` (continuous average pick).** Do not manufacture decimal ADP from ordinal archive values. Leave `espn_adp` null unless a defensible continuous source is acquired.
3. **Store ranking and ADP snapshot dates separately.** The official ranking artifact and the historical ADP archive often come from different preseason dates. Use `espn_rank_snapshot_date` and `espn_adp_snapshot_date`; retain `espn_snapshot_date` only for backwards compatibility with the official ranking snapshot.
4. **Compute `espn_rank_adp_gap = espn_adp_rank - espn_rank` only when both values exist.** This is a derived divergence feature, not a new independent source.
5. **Canonical rank source:** official ESPN PPR draft-kit PDFs. **Canonical ADP source:** FantasyPros historical ESPN-specific PPR ADP column. Public GitHub CSV copies are retrieval mirrors only and their currentized team metadata must not be used.

### Sleeper

1. **Sleeper's default redraft board is ADP-driven.** Do not count a separate Sleeper 'rank' and Sleeper ADP as two independent market votes.
2. **For 2021-2025, store the preserved FantasyPros Sleeper-specific historical PPR value as `sleeper_adp_order` (ordinal).** Do not convert the ordinal archive into fictitious continuous ADP.
3. **For 2020 only, use FantasyData historical PPR ADP as a medium-confidence reconstruction.** Populate continuous `sleeper_adp`, derive `sleeper_adp_order`, and mark `sleeper_source_state = reconstructed`. This must remain distinguishable from the preserved 2021-2025 Sleeper-specific archive.
4. **Sensitivity rule:** analyses that require strict identical-source comparability across all seasons should either exclude the 2020 Sleeper feature or run it as a separate sensitivity specification.

### General provenance / QA

1. Preserve both **canonical source URL** and **retrieval mirror URL** when the historical data is downloaded from a public archival copy.
2. Never use currentized team fields from historical mirror CSVs for player-season identity or preseason team assignment.
3. Missing platform values remain null. Coverage limits are source coverage, not values to impute during ingestion.
4. Validate each season against known sourcebook anchors (official ESPN top-five ordering and ESPN/Sleeper ADP leaders) before accepting the build.

### Implemented panel fields

- `espn_rank`
- `espn_rank_snapshot_date`
- `espn_adp_rank`
- `espn_adp_snapshot_date`
- `espn_rank_adp_gap`
- `espn_rank_source_url`
- `espn_adp_source_url`
- `espn_adp_retrieval_url`
- `sleeper_adp`
- `sleeper_adp_order`
- `sleeper_snapshot_date`
- `sleeper_source_state`
- `sleeper_source_url`
- `sleeper_retrieval_url`
- `sleeper_source_note`

### Build

Reproducible pipeline entrypoint: `fantasy-draft/research/attach_platform_layers_v02c.py` via `.github/workflows/build-fantasy-research-panel.yml`.

---

## v0.4 | Historical consensus statistical projections / Step 8 | 2026-08-30

### Core interpretation

1. **Consensus statistical projections are a Player Truth baseline, not a draft-market signal.** Do not substitute ECR, ADP, ESPN rank, or Sleeper order for missing statistical projections.
2. **Canonical projected fantasy points are recomputed from projected football components.** The workbook's standard-scoring FPTS field is retained for provenance but is not the full-PPR modeling target.
3. **Use the same standardized full-PPR scoring formula for projected and realized outcomes.** This prevents scoring-system differences from masquerading as projection error.

### Accepted source family

1. **2022-2025:** direct final pre-kickoff annual ElBoberto workbooks using FantasyPros consensus projections.
2. **2021:** accepted as a separately flagged bridge using the contemporaneous Roto Street Journal ElBoberto-derived workbook. Its accompanying article states aggregate FantasyPros projections updated 2021-08-27.
3. **2021 provenance must remain distinguishable** with `fantasypros_consensus_via_2021_rotostreet_elboberto_workbook`; do not relabel it as a direct annual ElBoberto release.
4. **2020 is frozen as `SOURCE_GAP_FROZEN_NOT_IMPUTED`.** The original Reddit post body/download is deleted; targeted Wayback recovery found no preserved thread captures; the accessible Roto Street derivative explicitly blends FantasyPros (75%) and FantasyPoints (25%) and is therefore rejected from the primary series.

### Final accepted snapshots

- 2021: Roto Street / ElBoberto-derived FantasyPros consensus, 2021-08-27
- 2022: ElBoberto v1.5, 2022-09-06
- 2023: ElBoberto v1.03, 2023-09-05
- 2024: ElBoberto v1.05, 2024-08-29
- 2025: ElBoberto v1.06, 2025-09-03

All accepted snapshots are pre-kickoff and pass the build validation.

### Final coverage

| Season | Draft-market projection coverage | ECR Top-300 coverage | State |
|---|---:|---:|---|
| 2020 | 0.00% | 0.00% | Frozen source gap |
| 2021 | 91.21% | 98.27% | PASS |
| 2022 | 90.89% | 97.18% | PASS |
| 2023 | 94.83% | 97.83% | PASS |
| 2024 | 90.61% | 99.64% | PASS |
| 2025 | 95.28% | 99.65% | PASS |

### Validation policy

1. Primary Model A / Model B historical validation uses **2021-2025**.
2. Run a **2022-2025 same-direct-distribution sensitivity test** because those seasons use the direct annual ElBoberto releases.
3. Do not impute the 2020 consensus projection feature.
4. The known 2020 75/25 blended derivative may be tested later only as a separately labeled robustness specification.
5. Direct FantasyPros historical `year=` page queries remain disallowed because testing showed that they can silently return current-season content.

### Implemented panel fields

- `consensus_proj_points`
- `consensus_proj_pass_attempts`
- `consensus_proj_pass_completions`
- `consensus_proj_pass_yards`
- `consensus_proj_pass_tds`
- `consensus_proj_pass_ints`
- `consensus_proj_rush_attempts`
- `consensus_proj_rush_yards`
- `consensus_proj_rush_tds`
- `consensus_proj_receptions`
- `consensus_proj_rec_yards`
- `consensus_proj_rec_tds`
- `consensus_proj_fumbles_lost`
- `consensus_proj_source_points_standard`
- consensus source URL/version/date/hash/state provenance fields

### Build

Canonical Step 8 entrypoint: `fantasy-draft/research/attach_preserved_consensus_v04.py` via `.github/workflows/build-fantasy-research-panel.yml`.

Canonical Step 8 panel: `master_player_season_panel_2020_2025_v0_4.csv`.

**Step 8 status: COMPLETE.**

---

## v0.5 | High-stakes / advanced fantasy draft markets / Step 9 | 2026-08-30

### Core interpretation

1. **Do not create a synthetic universal `high_stakes_adp` field at ingestion.** NFFC, FFPC/FPC, and best-ball markets have different scoring, roster structures, contest incentives, and historical source quality.
2. **High stakes is a hypothesis, not a credential.** NFFC/FFPC receives no special production weight until incremental predictive value is demonstrated out of sample after consensus/public/platform markets are controlled.
3. **Preserve source-family meaning before normalization.** Residuals and scoring/position adjustments belong downstream.

### NFFC direct historical audit

1. The current NFFC page loads data from `/adp.data.php` using team/date/team-count/draft-type/sport/position/league filters.
2. Valid 2026 requests return a full board with continuous ADP, minimum pick, maximum pick, and pick count.
3. The same valid request structure returned `No ADP Information Available` for preseason windows in every historical season 2020-2025.
4. Therefore the current NFFC backend is a **2026 live/application source**, not a historical archive for the training panel.

### Accepted FFPC/FPC full-table observations

- 2021-09-02: normal season-long FFPC/FPC, full public table, `preserved_full_table`
- 2022-06-25: normal season-long FFPC/FPC, full public table, `preserved_full_table_early`
- 2023-08-01: normal season-long FFPC, full public table, `preserved_full_table`

All three explicitly use **1.5 PPR for tight ends**. Do not treat their ADP gap versus standard-PPR markets as a pure information signal without position/scoring adjustment.

### Accepted NFFC ordinal observations

- 2024-05-23: public top-50 recent-NFFC ordinal board, `preserved_ordinal_early_generic`
- 2025-05-30: public NFFC ordinal movement board, `preserved_ordinal_early_generic`

These sources do not expose defensible continuous ADP. Store the published ordinal rank only. Do not manufacture decimal precision.

### Best-ball rule

Best-ball observations remain a separate market family. Do not merge FFPC best ball, Underdog, DraftKings, Drafters, or best-ball-inclusive NFFC aggregates into managed redraft ADP at the source layer.

### Model-D validation rule

1. Compare Model C and Model D on the **same player-season rows** to prevent source coverage from masquerading as predictive lift.
2. Run position-specific specifications.
3. Run an FFPC non-TE or TE-adjusted sensitivity analysis.
4. Treat early snapshots as early information, not final preseason prices.
5. Report season count and player-season sample size for every high-stakes result.
6. Never impute missing NFFC from FFPC or vice versa.

### Implemented v0.5 fields

Separate FFPC and NFFC fields are added for ADP/rank/prior rank/min/max/date/source state/source URL/contest/scoring format where the source actually exposes those values.

Long-form audit output: `high_stakes_market_observations_v05.csv`.

### Build

Canonical Step 9 entrypoint: `fantasy-draft/research/build_high_stakes_market_v05.py` via `.github/workflows/build-fantasy-research-panel.yml`.

Canonical Step 9 panel: `master_player_season_panel_2020_2025_v0_5.csv`.

**Step 9 status: COMPLETE when the v0.5 reproducible build and QA pass.**

---

## v0.6 | Sportsbook / Vegas market / Step 10 | 2026-08-30

### Core interpretation

1. **Sportsbook information is a hypothesis, not revealed truth.** Raw player season-total lines are not automatically unbiased expected means.
2. **Keep team environment, player props and published calibration evidence separate.** Do not create one generic `vegas_score` at ingestion.
3. **Separate availability from conditional performance.** Season-long overs have asymmetric failure paths through injury, benching, role loss and related availability shocks.
4. **Selection bias is source metadata.** Regional excerpts, editorial picks and projection-screened disagreements cannot be treated as representative full boards.

### Team win-total layer

1. Pro-Football-Reference preserves a complete 32-team preseason-odds table for every season from 2020 through 2025.
2. The archive attributes historical odds to SportsOddsHistory.com and exposes a preseason W/L over-under line plus Super Bowl odds.
3. Store `team_win_total` and the futures price separately.
4. Preserve an exact snapshot date only where the archive exposes one; otherwise use `final_preseason_archive` as the bounded source window.
5. Do not populate `team_offense_market_score` from a generic team win total. It is a broad team-strength/environment measure, not an offense-only forecast.

### Player-prop public archive audit

No comprehensive, consistently sampled, timestamped public NFL season-futures player-prop archive was verified across 2020-2025.

Accepted long-form observations are intentionally marked non-production:

- 2021 PFF NFC North public excerpt: `regional_public_excerpt_nfc_north`
- 2024 Footballguys selected WR props: `editorial_selected_props`
- 2025 PFF passing/rushing/receiving comparison tables: `projection_screened_extremes`

All carry `primary_model_eligible = false`.

### Calibration evidence

The 4for4 retrospective study of 604 closing 2021-2022 season-long props is retained at category level. It reported 369 unders and 235 overs overall. These category counts inform later bias correction and study design but do not create player-level features.

### Formal Model-C rule

1. Do not populate the primary `vegas_*` fields from selected or excerpted observations.
2. A future player-prop source must provide broad, consistently sampled preseason coverage with player, market, line, book/consensus definition and timestamp or bounded window.
3. Compare Model B and Model C on identical rows.
4. Preserve odds and remove vig only downstream.
5. Build category-aware Vegas-versus-consensus residuals rather than using raw lines as universal expectations.
6. Require a verified sample/schema before recommending a paid vendor; weekly game-prop coverage is not evidence of historical season-futures coverage.

### Implemented v0.6 fields

Team market:

- `team_win_total`
- `team_win_total_super_bowl_odds`
- snapshot/source/window/provider/book provenance fields

Player observation metadata:

- `sportsbook_player_prop_observation_count`
- `sportsbook_player_prop_source_count`
- `sportsbook_player_prop_sampling_frames`
- `sportsbook_player_prop_primary_model_eligible`

Long-form outputs preserve the raw selected lines and identity-match audit without promoting them into the primary feature columns.

### Build

Canonical Step 10 entrypoint: `fantasy-draft/research/build_sportsbook_market_v06.py` via `.github/workflows/build-fantasy-research-panel.yml`.

Canonical Step 10 panel: `master_player_season_panel_2020_2025_v0_6.csv`.

**Step 10 status: COMPLETE when all 192 team-season rows, player-observation match QA, source-discipline assertions and the reproducible v0.6 build pass.**
