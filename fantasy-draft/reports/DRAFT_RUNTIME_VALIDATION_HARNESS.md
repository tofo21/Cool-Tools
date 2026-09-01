# Draft Runtime Validation Harness

Version: 1.0.0

The harness validates contracts and the future browser interface without editing or importing behavior into current production application files. The two new Node test files call the dependency-free Python validator/builder and use an in-test browser-facing adapter stub.

## Commands

Regenerate synthetic source fixtures:

```bash
python3 fantasy-draft/tests/fixtures/runtime-contract/generate_fixtures.py
```

Validate the synthetic four-artifact set:

```bash
python3 fantasy-draft/research/validate_draft_runtime_bundle.py \
  --player-truth fantasy-draft/tests/fixtures/runtime-contract/synthetic_player_truth.json \
  --espn-market fantasy-draft/tests/fixtures/runtime-contract/synthetic_espn_market.json \
  --league-value fantasy-draft/tests/fixtures/runtime-contract/synthetic_league_value.json \
  --opponent-intent fantasy-draft/tests/fixtures/runtime-contract/synthetic_opponent_intent.json \
  --as-of 2026-08-31T23:00:00Z \
  --json
```

Build the deterministic synthetic candidate:

```bash
python3 fantasy-draft/research/build_draft_runtime_bundle.py \
  --player-truth fantasy-draft/tests/fixtures/runtime-contract/synthetic_player_truth.json \
  --espn-market fantasy-draft/tests/fixtures/runtime-contract/synthetic_espn_market.json \
  --league-value fantasy-draft/tests/fixtures/runtime-contract/synthetic_league_value.json \
  --opponent-intent fantasy-draft/tests/fixtures/runtime-contract/synthetic_opponent_intent.json \
  --output-dir fantasy-draft/data/candidate/runtime-contract \
  --bundle-filename synthetic_runtime_bundle.json \
  --manifest-filename synthetic_runtime_bundle_manifest.json \
  --report-filename synthetic_runtime_bundle_validation.md \
  --as-of 2026-08-31T23:00:00Z \
  --json
```

Run the complete repository test surface:

```bash
node --test fantasy-draft/tests/*.test.cjs
```

## A. Schema and artifact integrity

`draft-runtime-artifact-contract.test.cjs` verifies valid artifacts, required fields, nullable optional research outputs, strict finite numbers, position enums, probability bounds/sums, payload hashes, exact schema versions, duplicate IDs, stale artifacts, rejected/fallback status behavior, missing optional artifacts, and frozen-output overwrite refusal.

Committed negative fixtures cover malformed probabilities, duplicate Player Truth IDs, duplicate ESPN IDs, incompatible schema version, corrupt hash, stale market, top-160 missing League Value, and fallback Opponent Intent.

## B. Identity and coverage

The artifact test verifies stable-ID joins, rejection of a name field/name-only join attempt, exactly ten keeper identities, uniqueness of internal and ESPN IDs, one League Value record per mapped player, nonblocking lower-board identity reporting, overall/position/board-range coverage, top-160 blocking, and explicit per-ID approval behavior.

The real ESPN benchmark is documented but not copied into the synthetic fixture.

## C. Mathematical and semantic validation

The artifact and integration tests verify probability normalization, target taken/survival reconciliation, numeric League Value ordering, positional ordering, nullable sorting behavior, drafted-player exclusion, no duplicate selections, sequential depletion, roster mutation, fixed-seed reproducibility, Tony-label probability invariance, and strict separation among Player Truth, ESPN default rank, ESPN continuous ADP, and League Value.

## D. Draft Command compatibility stub

`draft-runtime-bundle-integration.test.cjs` verifies a populated Decision Board, reversible numeric League Value sorting, independent ESPN Price sorting, position filters, search, keeper/drafted exclusion, Tony/opponent roster updates, opponent-card updates, Threat Board updates, Manual picks, Hard Reset state, definite fallback/rejected states, missing/corrupt Opponent Intent, unresolved-pick continuation, and audit-friendly status/provenance.

The stub is test-only. Application changes are enumerated in `DRAFT_RUNTIME_INTEGRATION_HANDOFF.md`.

## E. Regression and reliability

Existing repository tests remain authoritative for production behavior:

| Existing suite | Reused coverage |
| --- | --- |
| `f5d-draft-state.test.cjs` | complete 160-pick source fixture, unresolved pick 26 continuing through 160, duplicate prevention, Hard Reset, same-room reconnection, Manual recovery/fallback, bounded stored-state growth, read-only audit export |
| `app-model-integration.test.cjs` | current fallback/research adapter behavior, numeric sorting, filters/search, drafted exclusion, sync compatibility, audit metadata |
| `espn-sync-reset.test.cjs` | extension bridge/reset compatibility and stale generation protection |
| `replay-engine.test.cjs` | deterministic 160-pick replay, keeper geometry, nonpersistent replay operation |
| `model-adapter.test.cjs` | current package validation, fallback, market/survival separation |
| `replay-page.test.cjs` | replay-page contract and no browser storage dependency |

The new runtime bundle is a fetched static input. Its compatibility policy explicitly forbids storage of the bundle or raw/simulation artifacts in `localStorage`.

## Synthetic fixture coverage

- 24 invented QB/RB/WR/TE records;
- 23 mapped ESPN IDs and one intentionally unresolved rank-200 identity;
- one missing ESPN default rank, one missing ESPN ADP, and omitted Player Truth distribution outputs;
- nine opponent keys with pseudonymous labels `M01`–`M09`;
- ten synthetic keeper slots;
- Tony at 1.05 in a 10-team, 16-round, 160-pick snake;
- normalized and malformed probabilities;
- sequential depletion with an unresolved overall pick 2 that does not block picks 3–10;
- missing-market, missing-Opponent-Intent, corrupt, stale, incompatible, duplicate, top-160 blocking, and fallback paths.

No raw league history or real manager identity is present in new fixtures. The existing safe 160-pick application/replay fixtures are reused rather than republished.
