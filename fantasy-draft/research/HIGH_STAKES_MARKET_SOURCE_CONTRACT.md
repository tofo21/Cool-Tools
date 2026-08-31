# High-Stakes Market Source Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Panel layer:** v0.5 high-stakes / advanced fantasy draft markets  
**Status:** Step 9 source architecture frozen; historical coverage is intentionally format-aware and incomplete

## Purpose

This layer tests whether high-stakes fantasy draft markets contain incremental predictive information after consensus projections, public ADP, and platform-market signals are already known.

The hypothesis is:

`HIGH-STAKES MARKET | CONSENSUS PROJECTION + PUBLIC ADP + PLATFORM ADP`

High entry fees, experienced participants, or a reputation for sharp drafting do **not** justify an automatic model weight. A high-stakes feature earns production weight only if it improves walk-forward out-of-sample prediction or calibration.

## Core source rule

There is no canonical source-layer field named `high_stakes_adp`.

NFFC, FFPC/FPC, and best-ball markets differ in scoring, roster rules, contest structure, draft incentives, and historical source quality. Combining them into one number at ingestion would destroy the very market differences the research is meant to test.

Preserve each family separately and derive normalized residuals only downstream.

## NFFC direct-source audit

NFFC's current public ADP page is JavaScript-driven and posts directly to:

`https://nfc.shgn.com/adp.data.php`

The current request schema includes team, date range, team count, draft type, sport, position, and league filters. Valid 2026 requests return a full player board with continuous ADP, minimum pick, maximum pick, and pick count.

A targeted historical audit queried preseason windows for every season from 2020 through 2025 using the live page's actual request payload. The backend returned `No ADP Information Available` for all six historical seasons while returning approximately 520 player rows for the analogous 2026 request.

**Decision:** The current NFFC endpoint is accepted for 2026 live/application data, but it is **not** a historical archive for the 2020-2025 training panel.

## NFFC historical observations

Public historical NFFC evidence exists, but the format is heterogeneous:

- articles with specific player ADPs;
- movement tables;
- contest-specific NFFC Primetime or Online Championship analyses;
- generic NFFC tables whose underlying contest mix is not fully specified;
- best-ball-inclusive analyses;
- ordinal boards that do not expose continuous ADP.

Two public Footballguys boards are preserved in v0.5 as historical NFFC observations:

| Season | Snapshot | Evidence | Source state | Production caveat |
|---|---:|---|---|---|
| 2024 | 2024-05-23 | Public NFFC top-50 ordinal board | `preserved_ordinal_early_generic` | Early; generic recent NFFC drafts; no continuous ADP |
| 2025 | 2025-05-30 | Public NFFC ordinal movement board | `preserved_ordinal_early_generic` | Early; generic recent NFFC drafts; no continuous ADP |

These rows may populate `nffc_rank` with provenance fields. They must never be converted into invented decimal ADP values.

Sparse 2020-2023 NFFC article observations remain useful for contextual research and future reconstruction, but v0.5 does not promote them to a canonical player-season predictor because comparable full-board coverage is not available.

## FFPC / FPC preserved season-long series

Footballguys preserves full player-level FFPC/FPC season-long ADP tables for several seasons. These are high-quality market observations but they have a strategically important scoring difference: **tight ends receive 1.5 points per reception**.

Accepted v0.5 full-table observations:

| Season | Snapshot | Market | Source state | Timing note |
|---|---:|---|---|---|
| 2021 | 2021-09-02 | FFPC/FPC normal season-long | `preserved_full_table` | Late preseason / close to kickoff |
| 2022 | 2022-06-25 | FFPC/FPC normal season-long | `preserved_full_table_early` | Materially earlier than target draft window |
| 2023 | 2023-08-01 | FFPC normal season-long | `preserved_full_table` | Roughly five weeks before kickoff |

The raw tables include overall rank, prior-week rank, continuous ADP, earliest pick, and latest pick.

### FFPC scoring caveat

FFPC ADP is not directly comparable to standard-PPR ADP, especially for tight ends. Do not treat an FFPC-versus-ESPN or FFPC-versus-Sleeper gap as pure information disagreement without controlling for position and scoring.

Preferred downstream treatments include:

- position-specific models;
- TE-specific scoring adjustment;
- residualizing FFPC ADP against same-season public/platform ADP by position;
- excluding TE rows in a standard-PPR sensitivity analysis;
- retaining snapshot timing as a feature or sample restriction.

## Best-ball treatment

Best-ball is a separate market family.

Best-ball roster construction, stacking incentives, zero weekly lineup decisions, tournament structure, and portfolio-style drafting can materially change player prices. FFPC best-ball, Underdog, DraftKings, Drafters, and similar markets must not be mixed into managed redraft ADP at the source layer.

When historical best-ball observations are added later, store them under distinct market-family and league-type keys.

## Canonical v0.5 schema

Long-form observation archive:

- `season`
- `market_family`
- `contest`
- `scoring_format`
- `te_premium`
- `league_type`
- `snapshot_date`
- `source_state`
- `source_url`
- `player_name`
- `position`
- `source_team`
- `adp`
- `rank`
- `prior_rank`
- `min_pick`
- `max_pick`
- `pick_count`
- `notes`

Player-season panel fields remain family-specific:

### FFPC
- `ffpc_adp`
- `ffpc_rank`
- `ffpc_prior_rank`
- `ffpc_min_pick`
- `ffpc_max_pick`
- `ffpc_snapshot_date`
- `ffpc_source_state`
- `ffpc_source_url`
- `ffpc_contest`
- `ffpc_scoring_format`

### NFFC
- `nffc_adp`
- `nffc_rank`
- `nffc_prior_rank`
- `nffc_min_pick`
- `nffc_max_pick`
- `nffc_snapshot_date`
- `nffc_source_state`
- `nffc_source_url`
- `nffc_contest`
- `nffc_scoring_format`

Missing fields remain missing. Do not fill NFFC gaps with FFPC values or vice versa.

## Model-D acceptance rule

The Research Contract's Model D is not a request to force a high-stakes feature into every 2020-2025 row.

Formal high-stakes testing should use nested/comparable samples:

1. Start with observations whose source family and format are explicitly known.
2. Compare Model D with the immediately simpler model on the **same rows** so coverage differences do not masquerade as predictive improvement.
3. Run position-specific specifications.
4. For FFPC, run at least one non-TE or TE-adjusted sensitivity test.
5. For NFFC ordinal-only observations, use rank/residual features appropriate to ordinal data rather than fabricated continuous ADP.
6. Report the number of seasons and player-seasons supporting every result.
7. Do not grant the feature production weight from a one-season or tiny sample unless the evidence is independently corroborated.

## Timing and leakage rules

Every high-stakes observation must carry its source date or source window.

An early May/June board and a late-August board can both be valid but answer different questions. Never overwrite an earlier snapshot with a later value while discarding its date. Never use a post-kickoff observation as a preseason predictor.

## v0.5 outputs

Canonical build code:

- `fantasy-draft/research/build_high_stakes_market_v05.py`

Primary outputs:

- `master_player_season_panel_2020_2025_v0_5.csv`
- `high_stakes_market_observations_v05.csv`
- `high_stakes_source_manifest_v05.csv`
- `high_stakes_match_qa_v05.csv`
- `high_stakes_coverage_qa_v05.csv`
- raw preserved table extracts by season/source

## Step 9 completion rule

Step 9 is complete when:

1. the direct NFFC historical-retention audit is recorded;
2. the strongest defensible public full/ordinal historical observations are preserved with format metadata;
3. FFPC and NFFC remain separate source families;
4. the v0.5 panel attaches only source-supported values with auditable player matching;
5. no synthetic unified `high_stakes_adp` is created;
6. QA and source manifests pass the reproducible build.

The expected outcome is allowed to be that historical high-stakes evidence is too heterogeneous for one universal 2020-2025 production feature. That is a research finding, not a data-cleaning failure.
