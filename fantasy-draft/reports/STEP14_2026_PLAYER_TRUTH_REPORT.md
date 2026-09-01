# Step 14 / 2026 Player Truth Report

Generated: `2026-09-01T00:59:51Z`
Runtime rows: **199 / 200**
Top-160 coverage: **159 / 160**

The frozen consensus `standardized_full_ppr_points` field remains the universal full-season P50. No ESPN rank, ADP, ECR, auction value, or incomplete August 31 page capture was substituted.

## Candidate decisions

| Candidate | Exact scope | Decision |
| --- | --- | --- |
| `S13B-REG-QB-GAMES-PLAYED-AGE-EXPERIENCE` | QB / games_played / age_experience | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-REG-QB-GAMES-PLAYED-COMBINE` | QB / games_played / combine | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-REG-TE-GAMES-PLAYED-HISTORICAL-INJURY` | TE / games_played / historical_injury | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-REG-QB-GAMES-PLAYED-ROOKIE-DRAFT-CAPITAL` | QB / games_played / rookie_draft_capital | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-REG-QB-GAMES-PLAYED-WEEKLY-ROSTER-STATUS` | QB / games_played / weekly_roster_status | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-CLA-QB-AVAILABILITY-BUST-FLAG-AGE-EXPERIENCE` | QB / availability_bust_flag / age_experience | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-CLA-TE-ELITE-FLAG-AGE-EXPERIENCE` | TE / elite_flag / age_experience | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-CLA-TE-STARTER-FLAG-AGE-EXPERIENCE` | TE / starter_flag / age_experience | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-CLA-QB-AVAILABILITY-BUST-FLAG-COMBINE` | QB / availability_bust_flag / combine | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-CLA-QB-BUST-FLAG-COMBINE` | QB / bust_flag / combine | REJECT_STEP14_CALIBRATION |
| `S13B-CLA-TE-ELITE-FLAG-HISTORICAL-INJURY` | TE / elite_flag / historical_injury | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-CLA-TE-STARTER-FLAG-ROOKIE-DRAFT-CAPITAL` | TE / starter_flag / rookie_draft_capital | APPROVE_EXACT_SCOPE_SIGNAL |
| `S13B-CLA-QB-AVAILABILITY-BUST-FLAG-WEEKLY-ROSTER-STATUS` | QB / availability_bust_flag / weekly_roster_status | APPROVE_EXACT_SCOPE_SIGNAL |

Twelve signals are admitted only for their exact tested scopes. No numeric 2026 contribution is applied because the handoff contains neither an audited current-season candidate feature matrix nor approved full-fit production weights. The QB bust/combine candidate remains rejected at Step 14 because ECE worsened.

## Binding exclusions

`H_ALL` remains rejected (28 binding rows). The package preserves 5 contextual, 5 mechanism-quarantined, 117 rejected, and 1 incomplete record. No Step 13B production weight is created.

## Named invariants

- Keenan Allen (Draft Command ID 143) is the sole missing projection and is omitted; no fallback was invented.
- Kayshon Boutte retains current team HOU and frozen-consensus source team NE as an explicit provenance conflict.
- Josh Jacobs remains COMMISSIONER_EXEMPT; full-season P50 is unadjusted 256.850, expected-games adjustment is null, and return week remains unknown pending NFL review.

## Runtime boundary

The Player Truth artifact is self-contained and contract-valid. Full four-artifact runtime validation remains blocked on the independent ESPN market, thin Step 15 League Value adapter, and Opponent Intent inputs.
