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
