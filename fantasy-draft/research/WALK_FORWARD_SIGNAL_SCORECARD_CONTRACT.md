# Walk-Forward Signal Scorecard Contract

**Project:** Fantasy Football 2026 Draft Intelligence  
**Research stage:** Step 12  
**Version:** v0.8  
**Status:** **STEP 12 COMPLETE** | first formal out-of-sample signal scorecard | production weights not yet frozen

## Purpose

This scorecard tests which preseason information families add predictive value beyond the immediately simpler model. It is designed to prevent intuitive or prestigious-looking data sources from receiving automatic weight.

The universal ladder is:

1. **A0 Raw Consensus:** unmodified consensus full-PPR projection.
2. **A Consensus:** consensus component statistics and position-specific calibration.
3. **B Fantasy Market:** A plus FantasyPros ECR, Fantasy Football Calculator ADP, ESPN rank and ADP, Sleeper order, market dispersion, and projection-versus-market disagreement.
4. **C Team Market:** B plus preseason team win total and source-timing class.
5. **F Opportunity:** C plus lagged role, snaps, shares, high-value work, expected fantasy points, and projection-versus-prior-role gaps.
6. **G Efficiency:** F plus denominator-shrunk position-specific efficiency.

Sparse FFPC/NFFC and player-prop evidence is tested separately rather than forced into the universal sample.

## Estimation universe

- Seasons with accepted consensus projections: **2021-2025**.
- Positions: QB, RB, WR, TE.
- Player-season rows: draft-market player, valid consensus projection, and realized full-PPR outcome.
- Eligible sample: **2,212 player-seasons**.

| Season | Rows |
|---|---:|
| 2021 | 446 |
| 2022 | 429 |
| 2023 | 440 |
| 2024 | 473 |
| 2025 | 424 |

| Position | Rows |
|---|---:|
| QB | 273 |
| RB | 659 |
| WR | 872 |
| TE | 408 |

## Walk-forward design

Primary outer folds:

- train 2021-2022, test 2023;
- train 2021-2023, test 2024;
- train 2021-2024, test 2025.

Hyperparameter selection uses expanding-year folds inside each outer training period. Random player-season splits are prohibited.

Because 2021 consensus projections use a separately flagged bridge distribution, a same-direct-source sensitivity repeats the regression ladder using:

- train 2022-2023, test 2024;
- train 2022-2024, test 2025.

## Targets

### Regression

- full-season PPR points;
- PPR points per game, conditional on at least four games;
- games played.

Points and PPG models predict a correction to raw consensus. Every fold includes a zero-correction candidate. Corrections are bounded by the 2.5th and 97.5th percentiles of training residuals before being added to consensus.

Games predictions are bounded to 0-17.

### Probability

- **Elite:** top-five positional finish;
- **Useful starter:** top-12 QB/TE or top-24 RB/WR;
- **Bust:** actual points below 50% of consensus projection;
- **Availability bust:** eight or fewer games.

Brier score is the primary probability metric. AUC, log loss, calibration error, and average predicted probability are secondary diagnostics.

## Feature processing

- Models are position-specific.
- Missing values are imputed from the outer-training sample with missingness indicators.
- Numeric features are standardized within training.
- Categorical timing values use training-fitted one-hot encoding with unknown-category handling.
- Prior-season missingness remains distinguishable from a true zero.
- Efficiency rates are shrunk toward position-specific training means using their actual opportunity denominators and conservative pseudo-counts.
- Shrinkage priors are recomputed within each outer training fold.
- ESPN rank and ESPN ADP remain separate.
- Sleeper order is counted once.
- Team win total remains a broad team-strength measure, not an offense-only forecast.

## Promotion logic

A feature family is not promoted from pooled performance alone. The scorecard evaluates:

- MAE or Brier improvement against the parent model;
- rank-correlation change;
- number of outer seasons improved;
- same-source sensitivity where available;
- sample size and coverage;
- whether the source family is representative and temporally comparable.

Final labels are:

- `PROMOTE`: useful for a specific position-target job;
- `CONDITIONAL`: small or unstable benefit requiring strong regularization and another validation stage;
- `NO_LIFT`: no evidence for production use in that job;
- `MIXED`: insufficient stability to decide.

No family receives one universal weight from this scorecard.

## Primary results

### Full-season point MAE

| Position | Raw consensus | A | B | C | F | G | Best observed model |
|---|---:|---:|---:|---:|---:|---:|---|
| QB | 57.60 | 57.79 | **57.31** | 57.31 | 57.64 | 57.72 | B, 0.5% better than raw |
| RB | **41.79** | 41.81 | 41.90 | 41.89 | 42.11 | 42.15 | Raw consensus |
| WR | 44.11 | **42.42** | 44.08 | 43.55 | 43.26 | 42.94 | A, 3.82% better than raw |
| TE | 32.67 | 32.59 | 32.62 | 32.42 | **32.01** | 32.33 | F, 2.01% better than raw |

### Conditional PPG MAE

| Position | Raw consensus / 17 | A | B | C | F | G |
|---|---:|---:|---:|---:|---:|---:|
| QB | 4.070 | **3.189** | 3.295 | 3.496 | 3.484 | 3.506 |
| RB | 2.696 | **2.641** | 2.646 | 2.644 | 2.663 | 2.663 |
| WR | 2.645 | 2.575 | **2.569** | 2.573 | 2.591 | 2.597 |
| TE | 2.152 | 1.865 | 1.911 | 1.899 | 1.825 | **1.797** |

### Games-played MAE

| Position | Training-mean baseline | A | B | C | F | G |
|---|---:|---:|---:|---:|---:|---:|
| QB | 5.06 | **3.17** | 3.26 | 3.30 | 3.47 | 3.33 |
| RB | 5.01 | 4.32 | 4.18 | 4.33 | **4.15** | 4.17 |
| WR | 4.18 | 3.82 | **3.38** | 3.75 | 3.85 | 3.97 |
| TE | 3.73 | 3.56 | 3.39 | 3.67 | 3.35 | **3.35** |

## Signal-family decisions

### A: consensus components

**Promote position-target specifically.**

- QB PPG MAE improves 21.6% versus raw season points divided by 17, with all three folds better.
- TE PPG improves 13.3%, with all three folds better.
- WR full-season points improve 3.82%, with two of three folds better.
- Probability models improve 15 of 16 elite/starter/bust/availability comparisons versus prevalence.

Consensus components are the only broadly reliable enhancement in the first scorecard.

### B: fantasy markets

**Conditional only for Player Truth; retain major importance in Draft Price and survival.**

Promoted jobs:

- WR games-played MAE improves 11.6%, all three folds;
- RB and WR availability-bust probability improves in all three folds.

Conditional jobs:

- QB full-season points;
- RB and TE games played;
- QB availability and RB/WR bust probability.

Fantasy markets generally do not improve elite or useful-starter probability after consensus components are known. They remain essential for forecasting draft-room behavior even where they do not improve Player Truth.

### C: team win total

**No universal player-level lift.**

The primary series shows only tiny point corrections. Games-played and probability models generally worsen, and the direct-source sensitivity is unstable. Team win total remains context or a low-weight interaction candidate, not a standalone production feature.

### F: opportunity and role

**Promote only for specific jobs.**

- RB games-played MAE improves 4.13%, all three folds.
- TE games-played MAE improves 8.77%, all three folds.
- TE points improve 1.26% and TE PPG improves 3.91%.
- RB bust and availability-bust Brier scores improve in all three folds.
- WR point correction is provisional: modest primary lift, but no clean same-source confirmation.

Opportunity does not improve QB or RB full-season point P50 in the current sample.

### G: shrunk efficiency

**Narrow, conditional use only.**

- TE PPG improves another 1.49%, all three folds.
- WR full-season points improve 0.74% with better rank correlation, two of three folds.
- QB bust, TE availability, and WR availability probability improve.

Most other efficiency additions are neutral or harmful. No universal efficiency weight is allowed.

## High-stakes nested study

The only defensible temporal FFPC test trains on 2021-2022 and tests 2023.

| Sample | B fantasy market MAE | B + FFPC MAE |
|---|---:|---:|
| All positions | 65.06 | 74.39 |
| Non-TE | 66.70 | 77.48 |

RB and TE are essentially flat; QB and WR materially worsen. FFPC receives no Player-Truth weight from this sample. It remains potentially useful as a draft-price or opponent-behavior market.

NFFC 2024-2025 has insufficient temporal depth for a genuine walk-forward test. The historical player-prop archive remains ineligible because every observation was regionally, editorially, or projection-screened selected. Comparable multi-snapshot movement data remains insufficient for Model E.

## Production gates after Step 12

The current candidate map is:

| Job | Candidate feature families |
|---|---|
| QB full-season P50 | raw consensus; optional very small B correction |
| RB full-season P50 | raw consensus |
| WR full-season P50 | consensus components; provisional shrunk efficiency correction |
| TE full-season P50 | consensus components + opportunity |
| QB active-game PPG | consensus components |
| TE active-game PPG | consensus components + opportunity + narrow efficiency |
| WR games / availability | fantasy markets |
| RB games / bust risk | fantasy markets + opportunity |
| TE games / availability | fantasy markets + opportunity; efficiency only for availability |
| Elite / starter probability | consensus components as the primary layer |
| Draft price / survival | platform and public markets remain central regardless of Player-Truth weight |

Every promoted correction must remain bounded and independently switchable by position and target.

## Limitations

- Only three primary outer test seasons are available.
- Same-direct-source sensitivity has only two outer test seasons.
- 2021 projections use a different accepted distribution bridge.
- Team win-total snapshots are source- and timing-heterogeneous.
- Public historical route and first-read data remain unavailable.
- Injury, age, rookie, coaching, offensive-line, quarterback-environment, and forward-looking schedule features are not yet in Model H.
- The scorecard evaluates historical preseason prediction, not yet league-specific championship equity.

## Reproducible outputs

Canonical entrypoint:

- `fantasy-draft/research/build_walk_forward_signal_scorecard_v08.py`

Primary outputs:

- `SIGNAL_SCORECARD_REPORT_v0.8.md`
- `walk_forward_regression_fold_metrics_v08.csv`
- `walk_forward_regression_pooled_metrics_v08.csv`
- `walk_forward_regression_predictions_v08.csv`
- `walk_forward_regression_incremental_v08.csv`
- `walk_forward_classification_fold_metrics_v08.csv`
- `walk_forward_classification_pooled_metrics_v08.csv`
- `walk_forward_classification_predictions_v08.csv`
- `walk_forward_classification_incremental_v08.csv`
- `signal_family_summary_v08.csv`
- `high_stakes_nested_scorecard_v08.csv`
- `signal_scorecard_feature_contract_v08.json`
- `signal_scorecard_integrity_v08.json`

Final workflow run: `33357740876`  
Final artifact SHA-256: `9005a4ae2a5312917f445293ae1ee68a3fe7ece40cef9a1a0a3e5b5de9d0ae90`

## Completion decision

**STEP 12 IS COMPLETE.**

The first scorecard rejects a universal blended-weight philosophy. Consensus remains the central forecast anchor. Markets, opportunity, and efficiency earn only position-target-specific jobs. Step 13 must add Model H context and rerun the scorecard before production Player Truth feature sets are frozen.
