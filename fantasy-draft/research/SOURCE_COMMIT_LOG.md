# Fantasy Draft Research Source Commit Log

This file records source-interpretation decisions that materially affect the historical player-season panel schema or downstream model treatment. It supplements, but does not replace, the canonical research contract and sourcebooks.

## v0.2 | ESPN + Sleeper historical platform layers | 2026-08-30

### ESPN

1. **Treat ESPN official/default rank and realized ESPN ADP as separate features.** Their disagreement is a potentially useful behavioral signal and should not be collapsed during ingestion.
2. **Store the preserved 2020-2025 ESPN ADP archive as `espn_adp_rank` (ordinal), not `espn_adp` (continuous average pick).** Do not manufacture decimal ADP from ordinal archive values. Leave `espn_adp` null unless a defensible continuous source is acquired.
3. **Store ranking and ADP snapshot dates separately.** The official ranking artifact and the historical ADP archive often come from different preseason dates. Use `espn_rank_snapshot_date` and `espn_adp_snapshot_date`; retain `espn_snapshot_date` only for backwards compatibility with the official ranking snapshot.
4. **Compute `espn_rank_adp_gap = espn_adp_rank - espn_rank` only when both values exist.** This is a derived divergence feature, not a new independent source.
5. **Canonical rank source:** official ESPN PPR draft-kit PDFs. **Canonical ADP source:** FantasyPros historical ESPN-specific PPR ADP column. Public GitHub CSV copies are retrieval mirrors only and their currentized team metadata must not be used.

### Sleeper

1. **Sleeper's default redraft board is ADP-driven.** Do not count a separate Sleeper 'rank' and Sleeper ADP as two independent market votes.
2. **For 2021-2025, store the preserved FantasyPros Sleeper-specific historical PPR value as `sleeper_adp_order` (ordinal).** Do not convert the ordinal archive into fictitious continuous ADP.
3. **For 2020 only, use FantasyData historical PPR ADP as a medium-confidence reconstruction.** Populate continuous `sleeper_adp`, derive `sleeper_adp_order`, and mark `sleeper_source_state = reconstructed`. This must remain distinguishable from the preserved 2021-2025 Sleeper-specific archive.
4. **Sensitivity rule:** analyses that require strict identical-source comparability across all seasons should either exclude the 2020 Sleeper feature or run it as a separate sensitivity specification.

### General provenance / QA

1. Preserve both **canonical source URL** and **retrieval mirror URL** when the historical data is downloaded from a public archival copy.
2. Never use currentized team fields from historical mirror CSVs for player-season identity or preseason team assignment.
3. Missing platform values remain null. Coverage limits are source coverage, not values to impute during ingestion.
4. Validate each season against known sourcebook anchors (official ESPN top-five ordering and ESPN/Sleeper ADP leaders) before accepting the build.

### Implemented panel fields

- `espn_rank`
- `espn_rank_snapshot_date`
- `espn_adp_rank`
- `espn_adp_snapshot_date`
- `espn_rank_adp_gap`
- `espn_rank_source_url`
- `espn_adp_source_url`
- `espn_adp_retrieval_url`
- `sleeper_adp`
- `sleeper_adp_order`
- `sleeper_snapshot_date`
- `sleeper_source_state`
- `sleeper_source_url`
- `sleeper_retrieval_url`
- `sleeper_source_note`

### Build

Reproducible pipeline entrypoint: `fantasy-draft/research/attach_platform_layers_v02c.py` via `.github/workflows/build-fantasy-research-panel.yml`.
