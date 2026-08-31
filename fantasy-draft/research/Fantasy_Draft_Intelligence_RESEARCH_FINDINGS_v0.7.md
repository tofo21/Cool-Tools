# Fantasy Draft Intelligence Research Findings v0.7

**Project:** Fantasy Football 2026 Draft Intelligence  
**Status:** Historical panel construction complete through Step 11  
**Historical panel:** 2020-2025  
**Canonical rows:** 3,902 player-seasons  
**Canonical fields:** 268  
**Next research step:** Formal walk-forward signal scorecard

## 1. Current architecture

The project keeps three concepts separate:

1. **Underlying NFL outcome distribution**
2. **League-specific fantasy value**
3. **Platform- and room-specific draft price**

The live application will ultimately optimize the cost of drafting a player now versus waiting until the next pick.

## 2. Consensus projections

Consensus statistical projections remain the central forecast baseline, not another market-price variable.

The canonical historical series is:

- 2021: FantasyPros consensus through the Roto Street / ElBoberto-derived workbook;
- 2022-2025: direct annual ElBoberto workbooks using FantasyPros consensus projections;
- 2020: explicit source gap, not imputed.

Projected full-PPR points are recalculated from component football statistics using the same scoring formula as realized outcomes.

Primary Model A / Model B validation uses 2021-2025, with a same-direct-source sensitivity analysis for 2022-2025.

## 3. Draft markets

FantasyPros ECR, Fantasy Football Calculator ADP, ESPN rank and ADP, and Sleeper ADP remain both preseason information signals and draft-cost variables.

Their roles stay conceptually separate:

- a market can contain useful information;
- the same market determines acquisition cost;
- an informative price is not necessarily a fair price.

### ESPN

Preserve separately:

- ESPN official/default PPR rank;
- ESPN realized ADP rank or continuous average pick when available.

Their disagreement is a potentially useful behavioral feature.

### Sleeper

Sleeper's default redraft order is generally ADP-driven. Sleeper default order and Sleeper ADP do not receive two independent votes when they are the same underlying statistic.

## 4. High-stakes markets

There is no defensible universal historical `high_stakes_adp` field.

The v0.5 layer preserves:

- 2021-2023 FFPC/FPC season-long ADP;
- 2024-2025 NFFC ordinal observations.

FFPC is TE-premium and must be position/scoring adjusted. NFFC historical evidence is ordinal and early and cannot be converted into invented continuous ADP.

High-stakes sources receive no production weight until they improve walk-forward prediction or calibration on comparable samples.

## 5. Sportsbook and Vegas findings

The original theory that raw Vegas season totals are unbiased clinical forecasts does not survive unchanged.

The model now separates:

1. team betting environment;
2. player season-total markets;
3. category-level calibration evidence;
4. availability risk versus performance conditional on playing.

### Team environment

The v0.6 archive contains 192 team-season win-total observations, exactly 32 teams for each season from 2020 through 2025.

Team win totals attach to 3,736 of 3,902 player-season rows and are eligible for controlled historical testing as broad team-strength/environment features.

They are not treated as offense-only forecasts.

### Player props

No comprehensive, consistently sampled public archive of historical NFL season-long player props was verified for 2020-2025.

The long-form archive preserves 68 selected observations, but all remain `primary_model_eligible = false` because their sampling frames are regional, editorial, or projection-screened.

The primary player-level `vegas_*` fields therefore remain blank.

## 6. Football fundamentals layer

Step 11 adds 132 fields to the panel, expanding it from 136 to 268 columns without changing its 3,902 canonical player-season rows.

All football features are lagged exactly one completed regular season:

`football_source_season = target season - 1`

This means a 2025 preseason row can use 2024 NFL performance, but no 2025 regular-season information.

### Opportunity and role now included

- games and prior fantasy production;
- pass attempts, carries, targets, receptions, and touches;
- offensive snaps and weighted snap share;
- carry, target, and air-yard shares across active games;
- WOPR;
- red-zone, goal-line, end-zone, deep, third-down, and two-minute opportunities;
- expected fantasy points and expected-fantasy-point team share;
- opportunities per snap and expected points per opportunity.

### Efficiency families now included

- EPA and CPOE;
- yards per carry, target, and reception;
- RACR and explosive-play rates;
- PFR yards before/after contact and broken tackles;
- PFR receiving aDOT, drop rate, YAC, and rating when targeted;
- NGS receiver separation, cushion, intended air yards, expected YAC, and YAC over expectation;
- NGS rushing yards over expectation, stacked-box rate, and time to line of scrimmage;
- NGS quarterback time to throw, aggressiveness, air yards, expected completion percentage, and CPOE;
- ffopportunity fantasy points over expectation and actual-versus-expected yards.

Efficiency values remain raw with their opportunity denominators. Shrinkage, minimum-volume rules, and nonlinear transformations belong inside each training fold during model validation.

### Coverage

Among draft-market players, prior core NFL stats, snap share, play-by-play opportunity, and expected-fantasy-point opportunity generally cover about 80% of rows in each target season.

PFR advanced coverage is also about 79%-82%. NGS coverage is lower, about 39%-47% overall, because NGS publishes qualifying-player summaries rather than all-player statistics.

The missing prior-season sample is meaningful. It disproportionately contains rookies, inactive players, and fringe players and must not be converted to zero.

### Route and first-read gaps

No comparable public all-player route-run series spanning 2019-2024 was accepted.

The fields below remain explicitly null:

- `prev_routes`
- `prev_route_participation`
- `prev_targets_per_route`
- `prev_yards_per_route`

Offensive snaps are retained as a role proxy but are never relabeled as routes. First-read target share remains a public historical source gap.

## 7. Canonical panel status

The panel now includes:

- stable player-season identity;
- actual games and full-PPR outcomes;
- FantasyPros preseason ECR and dispersion;
- Fantasy Football Calculator PPR ADP and sample metadata;
- ESPN rank and ESPN ADP;
- Sleeper ADP/order;
- consensus projected component statistics and full-PPR points for 2021-2025;
- FFPC and NFFC family-specific market fields;
- team win totals and source provenance;
- selected player-prop observation metadata;
- prior-season role, opportunity, high-value opportunity, weighted opportunity, and efficiency;
- source dates, source states, URLs, match QA, field dictionary, and explicit missingness.

Final v0.7 integrity:

- 3,902 player-season rows;
- 268 fields;
- 0 duplicate season/player IDs;
- 0 lag-alignment violations;
- 2,905 rows with prior core NFL statistics;
- 2,943 rows with snap share;
- 2,947 rows with weighted opportunity;
- 0 fabricated route values.

## 8. Current model ladder

### Model A
Consensus statistical projection only.

### Model B
Model A plus ECR, public ADP, and platform-market signals.

### Model C
Model B plus controlled sportsbook information. Team win totals are eligible; universal player props are not.

### Model D
Model C plus family-specific high-stakes signals on comparable samples.

### Model E
Timestamped market movement where defensible historical snapshots exist.

### Model F
Earlier model plus opportunity and role features from v0.7.

### Model G
Model F plus position-specific, appropriately shrunk efficiency features from v0.7.

### Model H
Later addition of injury/availability, coaching, offensive environment, rookies, and forward-looking schedule context.

## 9. Principal conclusions to date

1. Consensus projections are the correct central baseline.
2. ADP contains information but is also the price paid.
3. ESPN rank and ESPN ADP are separate behavioral signals.
4. Sleeper default order and Sleeper ADP should not be double-counted.
5. High stakes is a source family, not an automatic credential.
6. Raw season-long sportsbook lines are not unbiased expected means.
7. Team win totals are usable as broad environment signals.
8. Historical player props remain too selectively sampled for universal weighting.
9. Prior-season opportunity and role are now available at broad historical coverage.
10. Efficiency must be tested after opportunity and shrunk within training folds.
11. Rookies and no-prior-sample players require explicit treatment, not zero filling.
12. Missing route and first-read data is preferable to mislabeled proxies.
13. Every new signal must earn weight through walk-forward improvement or materially better calibration.

## 10. Next step

Build the first formal **walk-forward signal scorecard**.

The scorecard should begin with the cleanest comparable sequence:

1. Model A: consensus projection;
2. Model B: fantasy market signals;
3. Model C-team: add team win total with timing/source controls;
4. Model F: add opportunity and role;
5. Model G: add position-specific, shrunk efficiency.

High-stakes and selected player-prop tests should run as separate nested-sample studies rather than forcing sparse features into the universal ladder.

The scorecard must report, by position and target:

- sample size and seasons;
- MAE and Spearman rank correlation;
- calibration for elite, starter, and bust outcomes;
- incremental change versus the immediately simpler model;
- feature stability across test seasons;
- whether improvement survives same-source and minimum-volume sensitivity tests.
