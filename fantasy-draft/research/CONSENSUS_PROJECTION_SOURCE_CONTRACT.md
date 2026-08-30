# Consensus Projection Source Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Panel layer:** v0.3 historical preseason consensus projections  
**Status:** Verified for 2022-2025; 2020-2021 intentionally unresolved and not imputed

## Purpose

This layer provides an independent preseason statistical projection baseline for the historical player-season panel. It is designed to support the first rung of the predictive-validation ladder:

- **Model A:** consensus statistical preseason projections only
- **Model B:** Model A + ECR/public/platform draft-market signals
- Later models add sharp markets, betting markets, opportunity/efficiency, injury, team context, and other signal families.

ECR and ADP are not substitutes for this layer. The projection layer estimates expected football production; ECR and ADP represent analyst/draft-market prices.

## Source family

The accepted 2022-2025 source family is the preserved annual **ElBoberto Custom Auction Value Generator** workbook. The workbook author states that the spreadsheet takes **FantasyPros consensus projections** and transforms them using league settings. The workbooks themselves contain hidden position-specific `*_Raw` tabs and an Intro statement identifying FantasyPros projections as the consensus source.

Accepted final pre-kickoff versions:

| Season | Workbook | Snapshot | NFL kickoff | State |
|---|---|---:|---:|---|
| 2022 | `2022_FantasyFootball_1.5_elboberto.xlsm` | 2022-09-06 | 2022-09-08 | Verified pre-kickoff |
| 2023 | `2023_FantasyFootball_1.03_elboberto.xlsm` | 2023-09-05 | 2023-09-07 | Verified pre-kickoff |
| 2024 | `2024_FantasyFootball_1.05_elboberto.xlsm` | 2024-08-29 | 2024-09-05 | Verified pre-kickoff |
| 2025 | `2025_FantasyFootball_1.06_elboberto.xlsm` | 2025-09-03 | 2025-09-04 | Verified pre-kickoff |

The build stores source URL, workbook version, declared snapshot date, workbook modified timestamp when available, SHA-256 digest, and source state for provenance.

## Raw fields preserved

The source workbooks expose component projections rather than only a rank or fantasy-point total. The panel preserves available fields including:

- pass attempts
- pass completions
- passing yards
- passing TDs
- passing interceptions
- rushing attempts
- rushing yards
- rushing TDs
- receptions
- receiving yards
- receiving TDs
- fumbles lost
- workbook-provided standard-scoring fantasy points

## Canonical projected fantasy points

The workbook `MISC FPTS` field is preserved as `consensus_proj_source_points_standard`, but it is **not** used as the canonical full-PPR projection.

`consensus_proj_points` is recalculated from the component projections using the same standardized full-PPR scoring convention as the realized outcome panel:

- passing yards: 0.04 per yard
- passing TD: 4
- interception: -2
- rushing yards: 0.10 per yard
- rushing TD: 6
- reception: 1
- receiving yards: 0.10 per yard
- receiving TD: 6
- fumble lost: -2

This preserves apples-to-apples comparison between preseason projection and realized fantasy outcome.

## Identity matching

Source rows attach to the canonical player-season panel by normalized player name + position. Exact matches are preferred. Fuzzy matches are allowed only at a high threshold with a separation requirement from the second-best candidate. Match method and score are retained in QA output.

Source team metadata is retained for QA but does not overwrite canonical historical identity or team information.

## Missing-data policy

**2020 and 2021 are intentionally blank in this signal family until a defensible same-family preseason source is recovered.**

Do not:

- fill 2020-2021 from current FantasyPros pages;
- substitute ECR for projections;
- mix a different consensus methodology into the primary series without an explicit source-family flag and sensitivity analysis;
- backfill missing players from post-kickoff data;
- infer component stats from rank/ADP.

Missing values remain missing.

## Historical leakage controls

A source is accepted only when it can be established as preseason for the target season. Direct FantasyPros `year=` historical page queries were tested and rejected because the site could silently serve current-season data. That route is not approved.

The accepted preserved workbooks are final pre-kickoff releases. The build also checks workbook metadata when present and rejects a workbook whose modified date is on or after that season's NFL kickoff.

## Coverage after canonical matching

Final v0.3 coverage among the broad draft-market universe:

| Season | Draft-market projection coverage | FantasyPros ECR top-300 coverage |
|---|---:|---:|
| 2020 | 0.00% | 0.00% |
| 2021 | 0.00% | 0.00% |
| 2022 | 90.89% | 97.18% |
| 2023 | 94.83% | 97.83% |
| 2024 | 90.61% | 99.64% |
| 2025 | 95.28% | 99.65% |

The lower broad-universe percentage is expected because the preserved projection sources do not attempt to project every fringe player. The high ECR-top-300 coverage is the more relevant QA measure for draft-model validation.

## Reproducible build

Primary attachment code:

- `fantasy-draft/research/attach_preserved_consensus_v03.py`
- `fantasy-draft/research/attach_preserved_consensus_v03b.py`

Primary outputs:

- `master_player_season_panel_2020_2025_v0_3.csv`
- `consensus_projection_source_snapshot_v03.csv`
- `consensus_projection_source_manifest_v03.csv`
- `consensus_projection_match_qa_v03.csv`
- `consensus_projection_coverage_qa_v03.csv`
- `consensus_projection_manual_review_v03.csv`

## Open source gap

The immediate unresolved task is to recover a defensible final-preseason **2020 and 2021 FantasyPros-consensus projection snapshot** from the same or demonstrably equivalent source family. Until then, the formal walk-forward Model A / Model B evaluation should either:

1. begin with 2022-2025, or
2. wait for 2020-2021 recovery before reporting the full 2020-2025 result.

Do not silently use a different source family to make the panel look complete.
