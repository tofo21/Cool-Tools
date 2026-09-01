# Step 15 deterministic reproduction

From the repository root:

```bash
python3 fantasy-draft/research/step15/build_espn_league_value_step15.py --generated-at 2026-09-01T02:18:40Z
python3 -m unittest fantasy-draft/tests/step15/test_espn_league_value_step15.py
```

The builder refuses to run unless the authoritative Step 14 Player Truth file/payload and runtime League Value schema hashes match their frozen invariants. It uses no current time, network data, market rank, ADP, ECR, auction value, or Opponent Intent input.
