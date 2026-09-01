# Portable Step 14 Handoff — 2026 Consensus Projection Freeze

## Approved input

- Snapshot ID: `consensus_2026_frozen_20260901T005951Z_93fbef0b61f0`
- Canonical file: `current_2026_consensus_components_20260901T005951Z.csv`
- Source: `ElBoberto 2026 v0.4` using FantasyPros consensus projections
- Source timestamp: `2026-08-08T13:32:00Z`
- Capture timestamp: `2026-09-01T00:59:51Z`
- Validation: `PASS`

## Exact Step 14 consumption

1. Verify every artifact against `SHA256SUMS`.
2. Read `current_2026_consensus_components_20260901T005951Z.csv` as UTF-8 CSV.
3. Require `source_state == FROZEN_CANONICAL_SAME_FAMILY_WORKBOOK_DIRECT_CAPTURE_INCOMPLETE` on every row.
4. Join to the Step 14 player universe using `canonical_name + position`; use
   `identity_crosswalk_20260901T005951Z.csv` to audit Draft Command joins and source-name variants.
5. Use `standardized_full_ppr_points` as the universal full-season P50 consensus center.
6. Preserve every component column as the auditable source basis. Do not use
   `source_provided_fantasy_points` as the PPR center.
7. Treat blank component fields as source-unreported, not zero. Explicit `0.0` remains a real source zero.
8. Keep the sole board gap, Keenan Allen (IND, WR, board order 143), missing unless a new approved source
   addendum is created. Do not infer his projection from rank, ADP, ECR, auction value, or nearby players.
9. Preserve Josh Jacobs' row exactly as the consensus center. Any Step 14 status or availability treatment
   must be a separate, traceable adjustment layer; it may not mutate this CSV.
10. Do not blend the rejected 40-row August 31 direct capture with the August 8 workbook.

## Required preflight assertions

- CSV rows: `520` (`QB=81`,
  `RB=131`, `WR=190`,
  `TE=118`)
- Unique `canonical_name + position`: yes
- Current Draft Command coverage: `99.50%`
- Current Draft Command top-100 coverage: `100.00%`
- Validation report overall status: `PASS`
- Deterministic build proof: `byte_identical == true`

## Non-authorizations

This handoff does not authorize Player Truth adjustments, candidate promotion, model tuning, weight changes,
Draft Command changes, deployment, or a merge to `main`.
