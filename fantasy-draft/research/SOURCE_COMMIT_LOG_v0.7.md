# Fantasy Draft Research Source Commit Log v0.7

This file records source-interpretation decisions that materially affect the historical player-season panel or downstream model treatment.

## v0.2 | ESPN and Sleeper platform layers

### ESPN

- Preserve official/default PPR rank and realized ESPN ADP separately.
- Historical ordinal ADP remains ordinal; do not manufacture decimal average-pick precision.
- Store rank and ADP snapshot dates separately.
- Compute rank-versus-ADP gaps only from comparable fields.
- Preserve raw values and retrieval provenance.

### Sleeper

- Sleeper default redraft order is generally ADP-driven.
- Do not count default order and ADP as two independent market votes.
- 2021-2025 uses the preserved Sleeper-specific ordinal archive.
- 2020 is a separately flagged FantasyData reconstruction.
- Missing platform values remain missing.

## v0.4 | Consensus projections

- Consensus statistical projections are the Player Truth baseline.
- ECR and ADP do not substitute for missing component projections.
- Canonical full-PPR projected points are recomputed from projected football statistics.
- 2021 uses the Roto Street / ElBoberto FantasyPros-consensus bridge.
- 2022-2025 uses direct annual ElBoberto releases.
- 2020 is `SOURCE_GAP_FROZEN_NOT_IMPUTED`.
- Primary Model A / Model B testing uses 2021-2025.
- Same-direct-source sensitivity uses 2022-2025.

Canonical panel: `master_player_season_panel_2020_2025_v0_4.csv`

## v0.5 | High-stakes markets

- Do not create a universal `high_stakes_adp` field.
- FFPC/FPC, NFFC, and best ball remain separate market families.
- High stakes is a hypothesis, not an automatic predictive credential.
- 2021-2023 FFPC/FPC data remains explicitly TE-premium.
- 2024-2025 NFFC observations remain ordinal and early.
- Compare high-stakes models on identical rows.
- Run position-specific and TE-adjusted/non-TE sensitivities.
- NFFC gaps are not filled with FFPC values.

Final source matching:

| Season | Source | Matched |
|---|---|---:|
| 2021 | FFPC/FPC | 214 / 214 |
| 2022 | FFPC/FPC | 157 / 159 |
| 2023 | FFPC | 160 / 160 |
| 2024 | NFFC | 50 / 50 |
| 2025 | NFFC | 211 / 211 |

Canonical panel: `master_player_season_panel_2020_2025_v0_5.csv`

## v0.6 | Sportsbook and Vegas markets

### Core rules

- Sportsbook information is an independent hypothesis, not revealed truth.
- Team environment, player props, and category calibration stay separate.
- Season-long availability risk is separated from performance conditional on playing.
- Regional, editorial, and projection-screened prop tables remain selection-biased observations.
- Source date, source family, book definition, and odds availability remain explicit.

### Team win totals

The archive contains 192 observations, exactly 32 teams for each season from 2020 through 2025.

Accepted snapshots:

- 2020 Boyd's Bets retrospective archive;
- 2021 FanDuel via SportsBettingDime, dated 2021-09-06;
- 2022 Barstool via SportsBettingDime, dated 2022-03-28;
- 2023 Caesars via CBS Sports, dated 2023-03-29;
- 2024 theScore post-free-agency opening market;
- 2025 Boyd's Bets multi-book summary, dated 2025-08-03.

Team win totals populate 3,736 of 3,902 player-season rows. Generic win totals do not become offense-only scores.

### Player props

The final long-form archive contains 68 selected observations:

- 2021 PFF regional excerpt: 11;
- 2024 Footballguys editorial set: 5;
- 2025 PFF projection-screened set: 52.

All match canonical identity, but all remain `primary_model_eligible = false`. The primary player-level `vegas_*` fields remain blank.

Canonical panel: `master_player_season_panel_2020_2025_v0_6.csv`

## v0.7 | Football fundamentals / Step 11

### Temporal rule

- Every football feature is lagged exactly one completed regular season.
- Target season `Y` uses source season `Y - 1`.
- No target-season regular-season usage or efficiency enters a preseason row.
- Rookies and players without a prior NFL sample remain missing rather than zero-filled.

### Accepted source families

- nflverse player regular-season summaries, 2019-2024;
- nflverse/PFR snap counts, 2019-2024 regular seasons;
- nflverse play-by-play, 2019-2024 regular seasons;
- ffverse `ffopportunity` expected fantasy points, 2019-2024;
- PFR advanced rushing and receiving through nflverse;
- NFL Next Gen Stats passing, rushing, and receiving through nflverse;
- DynastyProcess stable-ID crosswalk.

### Opportunity and role

The layer adds:

- games, pass attempts, carries, targets, receptions, and touches;
- offensive snaps and weighted snap share;
- active-game carry, target, and air-yard shares;
- WOPR;
- red-zone, goal-line, end-zone, deep, third-down, and two-minute opportunity;
- expected fantasy points and team share;
- opportunity-per-snap and expected-points-per-opportunity measures.

Quarterback kneels are excluded from rushing opportunity.

### Efficiency

The layer preserves:

- EPA and CPOE;
- volume-normalized basic efficiency;
- PFR contact, broken-tackle, aDOT, drop, and YAC metrics;
- NGS separation, expected YAC, rushing yards over expectation, stacked-box, time-to-throw, aggressiveness, and expected-completion metrics;
- ffopportunity fantasy points and yards over expectation.

Raw efficiency and its denominator remain separate. Shrinkage, minimum-volume filters, and transformations occur inside model-training folds rather than in ingestion.

### Route and first-read gaps

- No accepted comparable public all-player route-run series spans 2019-2024.
- `prev_routes`, `prev_route_participation`, `prev_targets_per_route`, and `prev_yards_per_route` remain null.
- Offensive snaps are not relabeled as routes.
- First-read target share remains an explicit public historical source gap.

### Final v0.7 integrity

- 3,902 player-season rows;
- 268 fields;
- 132 new football fields;
- 0 duplicate season/player IDs;
- 0 lag-alignment violations;
- 2,905 rows with prior core NFL statistics;
- 2,943 rows with snap share;
- 2,947 rows with weighted opportunity;
- 0 populated route values.

Draft-market coverage for core/snap/opportunity families is approximately 80% by season. PFR advanced coverage is approximately 79%-82%. NGS coverage is approximately 39%-47%, reflecting qualifying-player thresholds.

Canonical panel: `master_player_season_panel_2020_2025_v0_7.csv`

Canonical production entrypoint: `fantasy-draft/research/build_football_fundamentals_v07.py`

Final workflow run: `33353208203`

Artifact SHA-256: `fe6872854174169800250ba654695bc29fd7c7695d612d50bb0205efbf2a6d20`

## Current status

Steps 8, 9, 10, and 11 are complete.

Next: the formal walk-forward signal scorecard, beginning with consensus, fantasy markets, team win totals, opportunity/role, and position-specific shrunk efficiency. Sparse high-stakes and player-prop families remain nested-sample studies.
