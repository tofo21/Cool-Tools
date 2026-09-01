# Step 14 Acceptance Gate

Status: **PASS**

## Mandatory source gates

| Gate | Required | Verified |
| --- | --- | --- |
| Step 13B ZIP SHA-256 | `83a5a6a699c767d73e13281188294053657a999dd87f1328fda89d9e52fef2e6` | exact match |
| Step 13B archive structure | valid central directory and all entries extractable | pass |
| Step 13B internal ledger | 131 / 131 files | pass |
| Step 13B head | `e3cf26eb863e4f54b6635e5a4aac50fe88e53e09` | exact match |
| Step 13B tree | `15e9c03a220b632c776a96d1db4d85839065924f` | exact match |
| Required commit sequence | `6015ed1`, `0ede7a2`, `e3cf26e` | exact order |
| Consensus source commit | `160f739cbeca74e6b2d559b372891f1491260fe9` | exact match |
| Consensus source tree | `efdd7a56b88b47b20dac62137c287c6891563969` | exact match |
| Consensus CSV SHA-256 | `8ab2386145f49cf2a44bc0c5667400e68e8bb49b4d63d15f0d416d7bd1d742c6` | exact match |
| Consensus `SHA256SUMS` SHA-256 | `cb9218f7e430016115aeb2718808fb0a6ad5aadc5640844841e1f3496213940e` | exact match |
| Consensus source workbook SHA-256 | `93fbef0b61f070d1a1ee66afa1d49355e739bd1b9277459dd1149717c909c48c` | exact match |

The Step 13B gate also reconfirmed 2,212 eligible player-seasons, zero leakage violations, 140 completed ablation jobs, 13 candidates, five contextual findings, five mechanism quarantines, 117 rejected jobs, all 28 binding `H_ALL` rows, and zero production weights.

## Executed tests

| Command/suite | Result |
| --- | --- |
| `python3 -m unittest discover -s fantasy-draft/tests/step13b -p 'test_*.py' -v` | 9 / 9 pass |
| `python3 -m unittest fantasy-draft/tests/test_consensus_projection_freeze_2026.py -v` | 5 / 5 pass |
| `python3 -m unittest discover -s fantasy-draft/tests/step14 -p 'test_*.py' -v` | 9 / 9 pass, including byte-identical rebuild |
| `node --test fantasy-draft/tests/*.test.cjs` | 8 / 8 suites pass, including the original six compatibility suites and both runtime-contract suites |
| `python3 fantasy-draft/research/step14/validate_player_truth_step14.py` | pass, zero contract blockers/warnings |
| `git diff --check` | pass |
| Python compile check | pass |

## Artifact gates

- Runtime contract: pass against `fantasy-draft/contracts/player_truth.schema.json`.
- Player Truth file SHA-256: `f6488e648af2549f1b7fa50eb485aa8f29784280144796e5e6d581a13b477bd3`.
- Runtime payload SHA-256: `be052a59ad9a0643246b2ed113e2c728fc5abfafb97e4278c53b8ea621f89694`.
- Player count: 199 / 200 (99.5%).
- Top-160 count: 159 / 160 (99.375%).
- Sole projection gap: Keenan Allen, ID 143; no fallback.
- Stable GSIS/ESPN identity gap inside produced rows: Jaydon Blue, ID 190; explicitly unresolved and lower-board.
- Optional P10/P90 and event-probability fields: 199 null values per field, not zero-filled.
- Candidate decisions: 12 exact-scope approvals, 1 Step 14 calibration rejection, 0 numeric 2026 candidate contributions, 0 production weights.
- Josh Jacobs: `COMMISSIONER_EXEMPT`, unadjusted 256.850, null games adjustment, no invented return date.
- Kayshon Boutte: current HOU and consensus-source NE both preserved.

## Security and scope

Static secret-pattern scanning, strict JSON/non-finite checks, payload/file hash verification, changed-path review, and prohibited-path review passed. No application, UI, ESPN synchronization/adapter, League Value, Opponent Intent, extension, or deployment file was changed by Step 14. No authenticated response, cookie, credential, token, raw manager history, or simulation ledger is present in the runtime artifact.

The standalone Player Truth gate is complete. Full four-artifact runtime validation remains an external integration dependency on the approved ESPN market file, the thin Step 15 League Value artifact, and the final Opponent Intent artifact.
