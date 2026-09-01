# ESPN Market Final-Freeze Runbook

## Approved window

Run between **7:30 PM and 7:45 PM CDT on August 31, 2026**, before the 8:15 PM draft.

From the repository root:

```bash
python3 fantasy-draft/research/capture_espn_market_2026.py --status frozen
```

The command refuses frozen status outside the approved window, never overwrites an existing snapshot, and refuses promotion when blocking QA fails.

## Acceptance checks

1. The command exits 0 and prints the immutable snapshot ID and versioned manifest path.
2. The manifest says `status: frozen` and `freshness_status: draft_night_frozen`.
3. `blocking_conflicts` is empty.
4. Keeper coverage and top-160 identity coverage are 100%.
5. Draft Command identity coverage is at least 98%.
6. Dual ESPN rank/ADP coverage is at least 90%.
7. The raw response, metadata, processed JSON/CSV, crosswalk, QA, and league report hashes validate.
8. Validate the exact manifest path printed by the capture command:

```bash
python3 fantasy-draft/research/capture_espn_market_2026.py \
  --validate-only fantasy-draft/data/production/espn_2026_market_manifest_<snapshot-id>.json \
  --require-status frozen \
  --reject-older-than 2026-09-01T00:30:00Z
```

Do not use an unversioned `latest` filename. Give the explicit manifest path and raw SHA-256 to FFDA, ESPN Opponent Intent Build, ESPN League Analysis, and Deploy fantasy draft app.

Exact ESPN league scoring remains a separate verification item if the league-settings endpoint still requires authentication. Market capture and identity QA may pass while league-value conversion remains blocked.
