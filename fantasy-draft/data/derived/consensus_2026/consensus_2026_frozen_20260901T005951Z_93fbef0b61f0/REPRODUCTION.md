# Reproduce the 2026 Consensus Projection Freeze

Run from the repository root with Python 3.11+:

```bash
python3 fantasy-draft/research/freeze_consensus_projections_2026.py
```

The command reads only the five frozen raw files under
`fantasy-draft/data/raw/consensus/2026/`, verifies their hashes and source metadata, performs two
independent temporary builds, byte-compares every output, and writes:

`fantasy-draft/data/derived/consensus_2026/consensus_2026_frozen_20260901T005951Z_93fbef0b61f0/`

To prove the build without changing the canonical output path:

```bash
tmp_dir=$(mktemp -d)
python3 fantasy-draft/research/freeze_consensus_projections_2026.py --output-root "$tmp_dir/build"
sha256sum "$tmp_dir/build/current_2026_consensus_components_20260901T005951Z.csv"
```

Expected canonical CSV SHA-256 is recorded in `SHA256SUMS` and
`deterministic_build_proof.json`. Do not recapture the live pages for a deterministic rebuild; a live
recapture is a new source snapshot and requires a new timestamp, hashes, validation, and selection decision.

The original unauthenticated capture commands are documented in the raw-source manifest. They used
plain HTTPS GET requests with a descriptive user agent, no API key, no credentials, and no cookie jar.

For provenance only, the live capture pattern was:

```bash
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/qb.php?scoring=PPR&week=draft' --output fantasypros_2026_qb.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/rb.php?scoring=PPR&week=draft' --output fantasypros_2026_rb.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/wr.php?scoring=PPR&week=draft' --output fantasypros_2026_wr.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/te.php?scoring=PPR&week=draft' --output fantasypros_2026_te.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.dropbox.com/scl/fi/jz9ao02y3xn61bbt469f7/2026_FantasyFootball_0.4_elboberto.xlsm?rlkey=vk0kb2nhf2wel5453erzu4wo9&st=szgxu53i&dl=1' --output 2026_FantasyFootball_0.4_elboberto.xlsm
```

A live recapture will not reproduce the frozen raw hashes and must never overwrite this snapshot.
