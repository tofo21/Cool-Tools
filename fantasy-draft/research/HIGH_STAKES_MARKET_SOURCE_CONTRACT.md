# High-Stakes Market Source Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Panel layer:** v0.5 high-stakes / advanced fantasy draft markets  
**Status:** **STEP 9 COMPLETE** | source architecture frozen | historical coverage intentionally format-aware and incomplete

## Purpose

This layer tests whether high-stakes fantasy draft markets contain incremental predictive information after consensus projections, public ADP, and platform-market signals are already known.

The hypothesis remains:

`HIGH-STAKES MARKET | CONSENSUS PROJECTION + PUBLIC ADP + PLATFORM ADP`

High entry fees, experienced participants, or a reputation for sharp drafting do **not** justify an automatic model weight. A high-stakes feature earns production weight only if it improves walk-forward out-of-sample prediction or calibration.

## Core source rule

There is no canonical source-layer field named `high_stakes_adp`.

NFFC, FFPC/FPC, and best-ball markets differ in scoring, roster rules, contest structure, draft incentives, source timing, and historical source quality. Combining them into one number at ingestion would destroy the market differences the research is meant to test.

Preserve each family separately and derive normalized residuals only downstream.

## NFFC direct-source audit

NFFC's current public ADP page is JavaScript-driven and posts directly to:

`https://nfc.shgn.com/adp.data.php`

The live request schema includes team, date range, team count, draft type, sport, position, and league filters. Valid 2026 requests return a full player board with continuous ADP, minimum pick, maximum pick, and pick count.

A targeted historical audit queried preseason windows for every season from 2020 through 2025 using the live page's actual request payload. The backend returned `No ADP Information Available` for all six historical seasons while returning approximately 520 player rows for the analogous 2026 request.

**Decision:** the current NFFC endpoint is accepted for 2026 live/application data, but it is **not** a historical archive for the 2020-2025 training panel.

## NFFC historical observations

Public historical NFFC evidence exists, but the format is heterogeneous:

- articles with specific player ADPs;
- movement tables;
- contest-specific Primetime or Online Championship analysis;
- generic NFFC tables whose contest mix is not fully specified;
- best-ball-inclusive analysis;
- ordinal boards that do not expose continuous ADP.

Two public Footballguys boards are preserved in v0.5 as canonical historical NFFC observations:

| Season | Snapshot | Evidence | Source state | Production caveat |
|---|---:|---|---|---|
| 2024 | 2024-05-23 | Public NFFC top-50 ordinal board | `preserved_ordinal_early_generic` | Early; generic recent NFFC drafts; no continuous ADP |
| 2025 | 2025-05-30 | Public NFFC ordinal movement board | `preserved_ordinal_early_generic` | Early; generic recent NFFC drafts; no continuous ADP |

These rows populate `nffc_rank` with provenance fields. They are never converted into invented decimal ADP values.

Sparse 2020-2023 NFFC article observations remain useful for contextual research and future reconstruction, but v0.5 does not promote them to a canonical player-season predictor because comparable full-board coverage is not available.

## FFPC / FPC preserved season-long series

Footballguys preserves full player-level FFPC/FPC season-long ADP tables for several seasons. These are useful high-information market observations but have a strategically important scoring difference: **tight ends receive 1.5 points per reception**.

Accepted v0.5 full-table observations:

| Season | Snapshot | Market | Source state | Timing note |
|---|---:|---|---|---|
| 2021 | 2021-09-02 | FFPC/FPC normal season-long | `preserved_full_table` | Late preseason / close to kickoff |
| 2022 | 2022-06-25 | FFPC/FPC normal season-long | `preserved_full_table_early` | Materially earlier than target draft window |
| 2023 | 2023-08-01 | FFPC normal season-long | `preserved_full_table` | Roughly five weeks before kickoff |

The raw tables preserve overall rank, prior-week rank, continuous ADP, earliest pick, and latest pick when supplied.

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

Best-ball roster construction, stacking incentives, zero weekly lineup decisions, tournament structure, and portfolio-style drafting can materially change player prices. FFPC best ball, Underdog, DraftKings, Drafters, and best-ball-inclusive NFFC aggregates must not be mixed into managed-redraft ADP at the source layer.

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

Player-season panel fields remain family-specific.

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

Missing fields remain missing. NFFC gaps are never filled with FFPC values or vice versa.

## Identity and parser QA

The final build includes two audited compatibility fixes only:

1. legacy Footballguys tables whose visual header was encoded in the first `<td>` row are promoted to semantic column headers without altering source values;
2. `Ken Walker III` is resolved to canonical `Kenneth Walker III` for player identity matching while the raw source name remains preserved in the long-form observation archive.

A non-player Footballguys paywall/footer row exposed by the HTML table renderer is excluded from standardized player observations while the raw table remains preserved.

Final source-to-panel match QA:

| Season | Market | Source player rows | Matched | Match rate | Note |
|---|---|---:|---:|---:|---|
| 2021 | FFPC/FPC | 214 | 214 | 100.00% | PASS |
| 2022 | FFPC/FPC | 159 | 157 | 98.74% | Two legitimate early-snapshot rows absent from final-preseason panel: Rob Gronkowski and Tim Patrick |
| 2023 | FFPC | 160 | 160 | 100.00% | PASS |
| 2024 | NFFC | 50 | 50 | 100.00% | PASS |
| 2025 | NFFC | 211 | 211 | 100.00% | PASS |

The two unmatched 2022 observations are retained in the source archive. They are not forced into the canonical player-season panel because the June high-stakes snapshot predates final-preseason player-pool changes.

## Draft-market coverage in v0.5

Coverage measures the canonical panel's broad draft-market universe, not source-table completeness:

| Season | Draft-market rows | FFPC coverage | NFFC coverage |
|---|---:|---:|---:|
| 2020 | 451 | 0.00% | 0.00% |
| 2021 | 489 | 43.76% | 0.00% |
| 2022 | 472 | 33.26% | 0.00% |
| 2023 | 464 | 34.48% | 0.00% |
| 2024 | 522 | 0.00% | 9.58% |
| 2025 | 445 | 0.00% | 47.42% |

This intentionally sparse, format-specific coverage is why Model D must be a nested-sample test rather than a universal column added to every row.

## Model-D acceptance rule

The Research Contract's Model D is not a request to force a high-stakes feature into every 2020-2025 row.

Formal high-stakes testing must:

1. use observations whose source family and format are explicitly known;
2. compare Model C and Model D on the **same rows** so coverage differences cannot masquerade as predictive improvement;
3. run position-specific specifications;
4. for FFPC, run at least one non-TE or TE-adjusted sensitivity test;
5. for NFFC ordinal-only observations, use rank/residual features appropriate to ordinal data rather than fabricated continuous ADP;
6. report the number of seasons and player-seasons supporting every result;
7. avoid granting production weight from a one-season or tiny sample unless independently corroborated.

## Timing and leakage rules

Every high-stakes observation carries its source date or source window.

An early May/June board and a late-August board can both be valid but answer different questions. Never overwrite an earlier snapshot with a later value while discarding its date. Never use a post-kickoff observation as a preseason predictor.

## Reproducible build

Canonical Step 9 build code:

- `fantasy-draft/research/build_high_stakes_market_v05.py` — source definitions, standardization, matching, provenance, coverage, outputs
- `fantasy-draft/research/build_high_stakes_market_v05b.py` — audited legacy-table compatibility, parser-debris filter, and nickname matching wrapper used by the production workflow

Canonical workflow:

- `.github/workflows/build-fantasy-research-panel.yml`

Primary outputs:

- `master_player_season_panel_2020_2025_v0_5.csv`
- `high_stakes_market_observations_v05.csv`
- `high_stakes_source_manifest_v05.csv`
- `high_stakes_match_qa_v05.csv`
- `high_stakes_coverage_qa_v05.csv`
- raw preserved table extracts by season/source

Final accepted workflow run: **33345876155**  
Final artifact SHA-256: `6def8fa01c6df0c5a8d192cae430f7052806a16b368fb8914c3cf627599e7373`

## Step 9 completion decision

**STEP 9 IS COMPLETE.**

The principal research finding is not that there is one universal historical sharp-market ADP. The defensible finding is the opposite: historical high-stakes evidence is useful but heterogeneous enough that source family, scoring format, contest type, and timestamp must remain explicit.

The next research lane is the sportsbook / team betting environment layer. High-stakes predictive weight will be decided later through the contracted walk-forward Model D test, not by source reputation.
