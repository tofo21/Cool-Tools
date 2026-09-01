# Draft Runtime Integration Handoff

Contract version: 1.0.0

Harness source branch: `codex/draft-runtime-contract-harness`

Final integration branch: `codex/final-draft-command-integration`

This handoff is the executable boundary for integrating the four completed intelligence artifacts. No undocumented columns, name-based joins, or zero-filled missing values are permitted.

## 1. Exact incoming artifact paths

The integration workstream must place or copy producer-approved JSON artifacts at these paths on its own integration branch:

| Producer | Required path | Contract |
| --- | --- | --- |
| Step 13B/14 Player Truth | `fantasy-draft/data/candidate/player-truth/player_truth_step14.json` | `fantasy-draft/contracts/player_truth.schema.json` |
| Frozen ESPN market | `fantasy-draft/data/candidate/espn-market/espn_market_frozen.json` | `fantasy-draft/contracts/espn_market.schema.json` |
| Thin Step 15 League Value adapter | `fantasy-draft/data/candidate/league-value/espn_league_value_step15.json` | `fantasy-draft/contracts/espn_league_value.schema.json` |
| Streamlined Opponent Intent | `fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json` | `fantasy-draft/contracts/opponent_intent.schema.json` |

If Opponent Intent is split internally by its producer, that workstream must emit one final contract artifact at the exact path above. Raw simulation ledgers, manager histories, training panels, and identity crosswalks are not bundle inputs.

## 2. Producer drop-in requirements

Before delivery, each producer must:

1. emit strict JSON with no non-finite values;
2. use schema version `1.0.0` and the exact `artifactType`;
3. join to the current integer `internalPlayerId` and provide `draftCommandBoardRank` in Player Truth;
4. preserve missing as omitted optional Player Truth output or explicit `null` where the schema requires the field;
5. calculate `integrity.payloadSha256` using `draft-command-canonical-json-v1`;
6. use only common artifact statuses: `candidate`, `validated`, `frozen`, `fallback`, or `rejected`;
7. keep ESPN default rank, continuous ADP, live-room rank, and source-supplied ordinal ADP separate;
8. provide source/model/formula versions exactly as specified in `ARTIFACT_CONTRACT.md`.

The fixture generator shows canonical payload signing. It is synthetic-only and must not be used to fabricate real values.

## 3. Validate real artifacts

Choose one RFC 3339 validation timestamp and reuse it for validation and build. It is part of the reproducible command input.

```bash
export DRAFT_RUNTIME_AS_OF="YYYY-MM-DDTHH:MM:SSZ"

python3 fantasy-draft/research/validate_draft_runtime_bundle.py \
  --player-truth fantasy-draft/data/candidate/player-truth/player_truth_step14.json \
  --espn-market fantasy-draft/data/candidate/espn-market/espn_market_frozen.json \
  --league-value fantasy-draft/data/candidate/league-value/espn_league_value_step15.json \
  --opponent-intent fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json \
  --approve-missing-projection 143 \
  --as-of "$DRAFT_RUNTIME_AS_OF" \
  --report fantasy-draft/reports/DRAFT_RUNTIME_REAL_ARTIFACT_VALIDATION.md \
  --json
```

Exit code `0` means the promotion gate passed. Exit code `1` means at least one blocking gate failed. Exit code `2` means command input was invalid.

Do not use `--approve-top160-identity-gap` without an explicit, recorded integration decision naming the exact stable internal ID. Approval downgrades the one gap to a visible warning; it does not create a mapping.

The final candidate uses only `--approve-missing-projection 143`. This is the recorded Keenan Allen exception: ESPN identity and market values are resolved, but no approved Player Truth projection or League Value exists. The validator separately blocks an unresolved market identity and an accidental top-160 Player Truth loss, even when ID 143 is approved.

## 4. Build the candidate runtime bundle

Run only after the validator passes:

```bash
python3 fantasy-draft/research/build_draft_runtime_bundle.py \
  --player-truth fantasy-draft/data/candidate/player-truth/player_truth_step14.json \
  --espn-market fantasy-draft/data/candidate/espn-market/espn_market_frozen.json \
  --league-value fantasy-draft/data/candidate/league-value/espn_league_value_step15.json \
  --opponent-intent fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json \
  --approve-missing-projection 143 \
  --output-dir fantasy-draft/data/candidate/runtime-contract \
  --bundle-filename draft_runtime_bundle.json \
  --manifest-filename draft_runtime_bundle_manifest.json \
  --report-filename draft_runtime_bundle_validation.md \
  --as-of "$DRAFT_RUNTIME_AS_OF" \
  --json
```

The builder validates all inputs again. It refuses to emit a candidate if a blocking gate exists and refuses to overwrite an existing output whose `status` is `frozen`.

## 5. Expected outputs

| Output | Path |
| --- | --- |
| Browser runtime bundle | `fantasy-draft/data/candidate/runtime-contract/draft_runtime_bundle.json` |
| Manifest | `fantasy-draft/data/candidate/runtime-contract/draft_runtime_bundle_manifest.json` |
| Human validation report | `fantasy-draft/data/candidate/runtime-contract/draft_runtime_bundle_validation.md` |
| Pre-build artifact report | `fantasy-draft/reports/DRAFT_RUNTIME_REAL_ARTIFACT_VALIDATION.md` |

The manifest contains exact input file hashes, source payload hashes, output hashes and byte sizes, coverage, blocking/warning counts, generation-time policy, and deterministic-build declaration.

## 6. Gates

### Blocking

- invalid strict JSON, schema failure, unsupported version, non-finite number, or payload hash mismatch;
- artifact status `rejected` or expiry at/before the validation time;
- duplicate stable IDs, canonical keys, board ranks, non-null ESPN IDs, or League Value ranks;
- stable-ID/ESPN-ID cross-artifact conflict;
- any silent/name-only join attempt;
- a mapped Player Truth record without one League Value record at board rank 160 or better;
- any other top-160 identity gap unless the exact ID has explicit command-line approval;
- any unresolved keeper identity or invalid keeper snake geometry;
- League Value rank inconsistent with descending numeric `leagueValueScore` or positional score order;
- ordinal ADP without an explicit source;
- position probabilities not summing to 1 within `1e-9`;
- top-five exact-player probabilities plus `otherProbability` not summing to 1 within `1e-9`;
- taken plus survival not summing to 1 within `1e-9`;
- incorrect league/team/opponent/source-version geometry;
- runtime schema failure or output attempting an orphan stable-ID join.

### Nonblocking but visible

- missing optional Player Truth distribution/probability output;
- individual missing ESPN rank or ADP, preserved as `null`;
- lower-board identity gap beyond rank 160;
- a structurally valid artifact with `fallback` status;
- missing ESPN market only when `--allow-missing-espn-market` is explicitly supplied;
- missing Opponent Intent only when `--allow-missing-opponent-intent` is explicitly supplied;
- unknown noncritical Opponent Intent roster/target ID, excluded from that affected join while later records continue.

For an unknown player in an opponent top-five list, the builder preserves the probability mass by moving only that entry’s probability to `otherProbability`. It does not renormalize or modify the remaining probabilities.

The final Step 18 candidate should not use missing-artifact flags when all four real artifacts are available.

## 7. Final application integration

The final candidate loads:

1. `data/players.js`;
2. `data/model-package.js`;
3. `data/opponent-intent-package.js`;
4. `model/model-adapter.js`;
5. `model/opponent-intent.js`;
6. `model/runtime-bundle-adapter.js`;
7. `app.js`;
8. `sync.js`.

`runtime-bundle-adapter.js` starts in a definite `fallback` state, fetches the bundle and manifest without browser persistence, verifies byte count and SHA-256, validates compatibility and stable-ID joins, and then enters `ready`, `fallback`, or `rejected`. It indexes `playerRecords`, `marketRecords`, and `leagueValueRecords` by `internalPlayerId`; no runtime name join is allowed.

Completed application behavior:

- Step 15 `leagueValueScore` and `leagueValueRank` are immutable base fields and numeric sort inputs; live roster fit remains recommendation-only.
- Frozen ESPN default rank and continuous ADP are independent, nullable fields.
- Step 14 optional P10/P90/event probabilities remain blank when null; the old outcome heuristics are not substituted in validated mode.
- Dynamic Opponent Intent recalculates after accepted picks using a fixed seed and all currently available players. Its failure hides/downgrades threat information without blocking the board, Manual entry, or synchronization.
- Drafted and deliberately loaded keeper players are excluded sequentially; keeper mode remains off at first load and Tony's configured keeper is Jaxson Dart, ID 90.
- Keenan Allen remains visible with market fields and no fabricated Player Truth/League Value. Jaydon Blue remains visible with Player Truth/League Value and null ESPN fields.
- Bundle source hashes and approved exceptions are included in the read-only audit export. Runtime artifacts and simulation output never enter `localStorage`.

The integration branch must retain the current deterministic UI tests for League Value sorting, ESPN Price sorting, position filtering, search, and drafted-player exclusion.

## 8. Rollback behavior

1. A candidate bundle is never allowed to trigger Hard Reset.
2. If load, schema, hash, compatibility, or adapter initialization fails, retain the active draft state and switch the intelligence label to the documented fallback/rejected state.
3. Opponent Intent can be removed independently by setting feature availability false and hiding/downgrading its views.
4. ESPN market can be removed independently while Player Truth, Manual entry, roster tracking, and synchronization continue.
5. Roll back code by reverting only the later runtime-integration commit or switching back to the last compatible frozen runtime artifact. Do not delete or rewrite draft-state storage as part of rollback.
6. A frozen runtime artifact must be replaced under a new version/path; the builder will not overwrite it.

## 9. Security/publication checklist

Before publishing any integration branch:

- [ ] every new input is producer-approved and its payload hash validates;
- [ ] fixtures contain only synthetic labels `M01`–`M09` and synthetic players, or an already approved repository fixture;
- [ ] no raw historical draft, training ledger, raw manager history, authenticated ESPN response, local crosswalk, cookies, credentials, tokens, or private fields are present;
- [ ] no raw simulation ledger is in the browser bundle or browser storage design;
- [ ] `git diff --name-only origin/main...HEAD` contains no unexpected app/UI/extension/deployment file;
- [ ] full new-commit history is scanned, not only the working-tree diff;
- [ ] output manifest hashes match independently calculated `sha256sum` values;
- [ ] all existing and new Draft Command tests pass;
- [ ] GitHub Pages deployment was not modified or invoked;
- [ ] candidate status is not mislabeled as frozen/production.

## 10. Final Step 18 acceptance sequence

Run from the repository root after setting `DRAFT_RUNTIME_AS_OF` once:

```bash
python3 fantasy-draft/research/validate_draft_runtime_bundle.py \
  --player-truth fantasy-draft/data/candidate/player-truth/player_truth_step14.json \
  --espn-market fantasy-draft/data/candidate/espn-market/espn_market_frozen.json \
  --league-value fantasy-draft/data/candidate/league-value/espn_league_value_step15.json \
  --opponent-intent fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json \
  --approve-missing-projection 143 \
  --as-of "$DRAFT_RUNTIME_AS_OF" \
  --report fantasy-draft/reports/DRAFT_RUNTIME_REAL_ARTIFACT_VALIDATION.md \
  --json

python3 fantasy-draft/research/build_draft_runtime_bundle.py \
  --player-truth fantasy-draft/data/candidate/player-truth/player_truth_step14.json \
  --espn-market fantasy-draft/data/candidate/espn-market/espn_market_frozen.json \
  --league-value fantasy-draft/data/candidate/league-value/espn_league_value_step15.json \
  --opponent-intent fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json \
  --approve-missing-projection 143 \
  --output-dir fantasy-draft/data/candidate/runtime-contract \
  --bundle-filename draft_runtime_bundle.json \
  --manifest-filename draft_runtime_bundle_manifest.json \
  --report-filename draft_runtime_bundle_validation.md \
  --as-of "$DRAFT_RUNTIME_AS_OF" \
  --json

node --test fantasy-draft/tests/*.test.cjs

sha256sum \
  fantasy-draft/data/candidate/runtime-contract/draft_runtime_bundle.json \
  fantasy-draft/data/candidate/runtime-contract/draft_runtime_bundle_manifest.json \
  fantasy-draft/data/candidate/runtime-contract/draft_runtime_bundle_validation.md

git diff --check
git diff --name-status origin/main...HEAD
git log --stat --oneline origin/main..HEAD
```

Return the candidate runtime manifest, coverage report, exact hashes, and blocking-gate result to the integration workstream. Do not deploy from this sequence.
