# 2026 Consensus Projection Source Comparison

**Snapshot ID:** `consensus_2026_frozen_20260901T005951Z_93fbef0b61f0`

## Selection decision

The unauthenticated direct FantasyPros pages are verified as 2026 component-projection pages with August 31, 2026 update timestamps, but each public response exposes only 10 rows behind a registration fence. That 40-row capture is incomplete and is not promoted.

The preserved `ElBoberto 2026 v0.4` workbook is selected as the canonical baseline. Its package metadata reports `2026-08-08T13:32:00Z`; its Intro sheet attributes all consensus projections to FantasyPros; its hidden raw tabs contain complete position-applicable components; and it covers 199/200 (99.50%) of the current Draft Command QB/RB/WR/TE universe.

The snapshots are not averaged or blended.

## Source gate comparison

| Candidate | Source date | QB/RB/WR/TE rows | Coverage state | Decision |
|---|---:|---:|---|---|
| Direct FantasyPros public pages | QB 2026-08-31 15:07:24, RB 2026-08-31 15:07:21, WR 2026-08-31 15:07:17, TE 2026-08-31 15:07:14 | 10/10/10/10 | Incomplete unauthenticated top-10-only capture | Rejected as canonical |
| ElBoberto 2026 v0.4 | 2026-08-08T13:32:00Z | 81/131/190/118 | 99.50% current board; 100% top 100 | Selected canonical |

## Same-family sensitivity on the public overlap

`Difference` is August 31 direct standardized full-PPR points minus August 8 workbook standardized full-PPR points, calculated only from displayed component fields.

| Position | Direct rows | Overlap | Mean difference | Median absolute difference | Max absolute difference |
|---|---:|---:|---:|---:|---:|
| QB | 10 | 10 | -0.929 | 1.036 | 6.194 |
| RB | 10 | 10 | -3.101 | 0.89 | 15.52 |
| WR | 10 | 10 | -1.262 | 0.875 | 12.43 |
| TE | 10 | 10 | 2.222 | 2.03 | 17.97 |

## Limitations

- The chosen snapshot is August 8, not August 31; it must retain that timestamp in Step 14.
- FantasyPros' direct page datetime strings do not declare a timezone; they are preserved verbatim and not assigned one.
- The direct pages cannot establish full-universe August 31 coverage without an account or API key, both excluded by this task.
- Keenan Allen (IND, WR, board order 143) is the sole current-board source gap.
- Source-provided FPTS are preserved but are not the canonical scoring field; standardized full-PPR is recalculated from components.
- Position families absent from a raw tab remain null. They are not silently converted to zero.
