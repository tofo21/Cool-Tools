# Step 14 / 2026 Player Truth deterministic reproduction

Run from `fantasy-draft` at the committed Step 14 head:

```bash
python3 research/step14/build_player_truth_step14.py
python3 research/step14/validate_player_truth_step14.py
python3 -m unittest discover -s tests/step14 -p 'test_*.py'
```

The build refuses to run unless the canonical consensus CSV and its `SHA256SUMS`
ledger have the approved hashes. It joins by normalized `canonical_name + position`,
never by rank/ADP, and emits the fixed source capture time for byte reproducibility.
