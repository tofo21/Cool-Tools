# Fantasy Draft Research Source Commit Log v0.8

This file records source and modeling decisions that materially affect the historical panel or downstream production model.

## Prior canonical decisions

### Platform markets

- ESPN official/default rank and ESPN ADP remain separate.
- Historical ordinal values are never converted into invented continuous ADP.
- Sleeper default order is ADP-driven and counted once.
- Platform data can be important for draft price even when it adds little to Player Truth.

### Consensus projections

- Consensus component projections are the Player Truth baseline.
- Full-PPR projected points are recomputed from football components.
- 2021-2025 is the primary projection-validation window.
- 2020 remains an explicit source gap, not imputed.

### High stakes

- There is no universal `high_stakes_adp` field.
- FFPC, NFFC, and best ball remain separate families.
- TE premium and snapshot timing remain explicit.

### Sportsbook

- Team environment, player props, and calibration evidence remain separate.
- Team win total is not an offense-only projection.
- Selected player-prop articles do not populate universal Vegas fields.

### Football fundamentals

- Every feature is lagged exactly one completed regular season.
- Opportunity and efficiency remain separate.
- Efficiency retains denominators and is shrunk only inside model training.
- Rookies/no-prior-sample remain missing, not zero.
- Offensive snaps are never relabeled routes.

## v0.8 | Formal walk-forward signal scorecard / Step 12

### Estimation contract

- Primary sample: 2,212 draft-market player-seasons from 2021-2025.
- Positions modeled separately: QB, RB, WR, TE.
- Outer tests: 2023, 2024, 2025 using expanding prior seasons.
- Same-direct-source sensitivity tests: 2024 and 2025 using only 2022-forward direct annual consensus distributions.
- Inner tuning also uses expanding seasons.
- No random player-season split is permitted.

### Outcome contract

Regression targets:

- full-season PPR points;
- conditional PPR points per game for players with at least four games;
- games played.

Probability targets:

- top-five positional finish;
- top-12 QB/TE or top-24 RB/WR;
- fewer than 50% of consensus-projected points;
- eight or fewer games.

### Forecast guardrails

- Points and PPG models correct raw consensus rather than replacing it.
- Every fold includes a zero-correction candidate.
- Corrections are bounded by outer-training residual quantiles.
- Games are bounded to 0-17.
- Missingness indicators are retained.
- Efficiency shrinkage uses outer-training priors and actual denominators.

### Final signal-family decisions

#### Consensus components

Position-target-specific promotion. Strongest jobs: QB PPG, TE PPG, WR full-season points, and probability calibration.

#### Fantasy market

Conditional Player-Truth use. Promote for WR games and RB/WR availability probability. Keep central importance in Draft Price and survival regardless of Player-Truth verdict.

#### Team win total

No universal lift. Retain as context or low-weight interaction only.

#### Opportunity

Promote for RB and TE games, RB bust/availability, and TE production. WR point correction remains provisional.

#### Efficiency

Conditional only: TE PPG, provisional WR points/order, QB bust, and TE/WR availability.

#### FFPC

No Player-Truth weight from the available walk-forward test. Pooled non-TE MAE worsened from approximately 66.7 to 77.5. Retain as a price/behavior market candidate.

#### NFFC, movement, and player props

Insufficient temporal or representative coverage for universal production testing.

### Final Step 12 integrity

- 2,212 eligible scorecard rows;
- 360 regression fold rows;
- 38,694 regression predictions;
- 288 classification fold rows;
- 32,088 classification predictions;
- zero duplicate primary prediction keys;
- zero duplicate classification prediction keys;
- complete A0/A/B/C/F/G ladder;
- explicit nested-source statuses.

Canonical scorecard entrypoint:

- `fantasy-draft/research/build_walk_forward_signal_scorecard_v08.py`

Final workflow run: `33357740876`  
Artifact SHA-256: `9005a4ae2a5312917f445293ae1ee68a3fe7ece40cef9a1a0a3e5b5de9d0ae90`

**Step 12 status: COMPLETE.**

## Current status

Steps 8-12 are complete.

Next: Step 13 Model H context and availability features, then rerun this scorecard before production feature sets are frozen.
