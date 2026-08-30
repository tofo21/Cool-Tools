# Consensus Projection Source Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Panel layer:** v0.4 historical preseason consensus projections  
**Status:** Verified for 2021-2025; 2020 frozen as an explicit source gap and not imputed

## Purpose

This layer provides an independent preseason statistical projection baseline for the historical player-season panel. It supports the first rung of the predictive-validation ladder:

- **Model A:** consensus statistical preseason projections only
- **Model B:** Model A + ECR/public/platform draft-market signals
- Later models add sharp markets, betting markets, opportunity/efficiency, injury, team context, and other signal families.

ECR and ADP are not substitutes for this layer. The projection layer estimates expected football production; ECR and ADP represent analyst/draft-market prices.

## Accepted source family

The primary 2022-2025 source family is the preserved annual **ElBoberto Custom Auction Value Generator** workbook. The workbook author states that the spreadsheet takes **FantasyPros consensus projections** and transforms them using league settings. The workbooks contain hidden position-specific `*_Raw` tabs and an Intro statement identifying FantasyPros projections as the consensus source.

For 2021, the accepted bridge is a contemporaneous **Roto Street Journal ElBoberto-derived workbook**. Its August 2021 accompanying article states that the downloadable tool uses aggregate FantasyPros projections and that its projection data were updated 2021-08-27. Because the distribution channel differs from the direct 2022-2025 ElBoberto releases, 2021 carries its own provenance state rather than being silently treated as identical provenance.

Accepted final pre-kickoff versions:

| Season | Workbook/source | Snapshot | NFL kickoff | State |
|---|---|---:|---:|---|
| 2020 | No accepted same-family snapshot recovered | — | 2020-09-10 | **SOURCE_GAP_FROZEN_NOT_IMPUTED** |
| 2021 | Roto Street / ElBoberto-derived FantasyPros consensus workbook | 2021-08-27 | 2021-09-09 | Verified pre-kickoff bridge |
| 2022 | `2022_FantasyFootball_1.5_elboberto.xlsm` | 2022-09-06 | 2022-09-08 | Verified pre-kickoff |
| 2023 | `2023_FantasyFootball_1.03_elboberto.xlsm` | 2023-09-05 | 2023-09-07 | Verified pre-kickoff |
| 2024 | `2024_FantasyFootball_1.05_elboberto.xlsm` | 2024-08-29 | 2024-09-05 | Verified pre-kickoff |
| 2025 | `2025_FantasyFootball_1.06_elboberto.xlsm` | 2025-09-03 | 2025-09-04 | Verified pre-kickoff |

The build stores source URL, workbook version, declared snapshot date, workbook modified timestamp when available, SHA-256 digest, source state, and distribution note for provenance.

## Raw fields preserved

The accepted workbooks expose component projections rather than only a rank or fantasy-point total. The panel preserves available fields including:

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

**2020 is intentionally blank in this signal family. Step 8 considers that gap closed methodologically, not awaiting imputation.**

Do not:

- fill 2020 from current FantasyPros pages;
- substitute ECR for projections;
- use the accessible 2020 Roto Street derivative in the primary series because it explicitly blends FantasyPros (75%) with FantasyPoints (25%);
- mix another consensus methodology into the primary series without an explicit source-family flag and sensitivity analysis;
- backfill missing players from post-kickoff data;
- infer component stats from rank/ADP.

Missing values remain missing.

## 2020 recovery decision

The exact deleted 2020 ElBoberto Reddit thread remains accessible enough to establish that the workbook used raw statistical inputs and the familiar hidden raw-tab architecture. However, its original post body and download links are gone.

A targeted archival recovery was executed against the exact `www.reddit.com`, `old.reddit.com`, and `reddit.com` thread URL variants. Wayback CDX returned **zero preserved captures** for the first two variants and no recoverable workbook link. Web search also did not recover a direct 2020 ElBoberto workbook.

A 2020 Roto Street ElBoberto-derived workbook is accessible, but its accompanying article explicitly states that its projections combine FantasyPros and FantasyPoints. It therefore does not satisfy the primary signal's source-family contract and is rejected from Model A.

Result: **2020 = SOURCE_GAP_FROZEN_NOT_IMPUTED.** It may be used later only as a separately flagged sensitivity source, never as if it were the canonical FantasyPros-consensus series.

## Historical leakage controls

A source is accepted only when it can be established as preseason for the target season. Direct FantasyPros `year=` historical page queries were tested and rejected because the site could silently serve current-season data. That route is not approved.

The accepted 2021-2025 workbooks are pre-kickoff releases. The build checks workbook metadata when present and rejects a workbook whose modified date is on or after that season's NFL kickoff.

## Coverage after canonical matching

Final v0.4 coverage among the broad draft-market universe:

| Season | Draft-market projection coverage | FantasyPros ECR top-300 coverage | Status |
|---|---:|---:|---|
| 2020 | 0.00% | 0.00% | Frozen source gap |
| 2021 | 91.21% | 98.27% | PASS |
| 2022 | 90.89% | 97.18% | PASS |
| 2023 | 94.83% | 97.83% | PASS |
| 2024 | 90.61% | 99.64% | PASS |
| 2025 | 95.28% | 99.65% | PASS |

The lower broad-universe percentage is expected because the preserved projection sources do not attempt to project every fringe player. The ECR-top-300 coverage is the more relevant QA measure for draft-model validation.

## Reproducible build

Canonical Step 8 attachment code:

- `fantasy-draft/research/attach_preserved_consensus_v04.py`

Supporting recovery / predecessor code remains in the repository for auditability, but v0.4 is the canonical output.

Primary outputs:

- `master_player_season_panel_2020_2025_v0_4.csv`
- `consensus_projection_source_snapshot_v04.csv`
- `consensus_projection_source_manifest_v04.csv`
- `consensus_projection_match_qa_v04.csv`
- `consensus_projection_coverage_qa_v04.csv`
- `consensus_projection_manual_review_v04.csv`

Targeted 2020 archive audit outputs:

- `recover_2020_elboberto_attempts.csv`
- `recover_2020_elboberto_links.csv`
- `recover_2020_elboberto_errors.txt`

## Step 8 completion rule

**Step 8 is complete.** The canonical historical consensus-projection series is 2021-2025, with 2020 explicitly missing by source contract.

Formal predictive validation should:

1. use 2021-2025 for the primary Model A / Model B walk-forward analysis;
2. report 2022-2025 as a same-direct-distribution sensitivity analysis because those seasons use the direct annual ElBoberto releases;
3. exclude the 2020 consensus projection feature from primary estimation rather than impute it;
4. optionally test the known 2020 blended derivative only as a separately labeled robustness check.
