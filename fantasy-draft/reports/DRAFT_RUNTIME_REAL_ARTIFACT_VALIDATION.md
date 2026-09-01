# Draft Runtime Artifact Validation

- Promotion gate: **PASS**
- Validation time: `2026-09-01T04:04:09Z`
- Blocking issues: **0**
- Warnings: **2**
- Informational findings: **0**

## Input hashes

| Artifact | SHA-256 |
| --- | --- |
| player-truth | `f6488e648af2549f1b7fa50eb485aa8f29784280144796e5e6d581a13b477bd3` |
| espn-market | `a6037c4b575f9c9a9381812d8d27ad0c741c36caefa899bdf5ddea683f4bc87a` |
| espn-league-value | `d3acb8a3e681df4835e512cb6a3b694c7d470787a76be072166876db489b2272` |
| opponent-intent | `c839913ddd199d87b6260eca543af60d934641243d2e7409fb26263d0fad72ed` |

## Coverage

| Slice | Eligible | Player Truth | ESPN rank | ESPN ADP | League Value |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 200 | 199 | 199 | 199 | 199 |
| QB | 27 | 27 | 27 | 27 | 27 |
| RB | 65 | 65 | 64 | 64 | 65 |
| WR | 82 | 81 | 82 | 82 | 81 |
| TE | 26 | 26 | 26 | 26 | 26 |
| Board 1-50 | 50 | 50 | 50 | 50 | 50 |
| Board 51-100 | 50 | 50 | 50 | 50 | 50 |
| Board 101-160 | 60 | 59 | 60 | 60 | 59 |
| Board 161+ | 40 | 40 | 39 | 39 | 40 |

Keeper identities: **10/10** resolved.

## Unresolved identities

| Internal ID | Board rank | Artifact | Blocking | Reason |
| ---: | ---: | --- | --- | --- |
| 143 | 143 | player-truth | no | resolved market identity has no approved Player Truth projection or League Value record |
| 190 | 190 | player-truth | no | Player Truth identity remains unresolved |

## Gate findings

| Severity | Code | Artifact | Path | Finding |
| --- | --- | --- | --- | --- |
| WARNING | `APPROVED_MISSING_PROJECTION` | player-truth | `internalPlayerId=143` | resolved identity is explicitly approved to remain without Player Truth or League Value; market data remains independently usable |
| WARNING | `LOWER_BOARD_IDENTITY_GAP` | player-truth | `internalPlayerId=190` | Player Truth identity remains unresolved |

## Approved missing-projection exceptions

`143`

## Future real-artifact benchmark

The known ESPN candidate benchmark is 199/200 Draft Command identities matched, 10/10 keepers resolved, zero unresolved raw ESPN top-160 players, and zero unresolved raw ranked top-250 players. Jaydon Blue was the sole Draft Command-only miss and was absent from ESPN's 500-player payload. This benchmark is not synthetic data and is not used to manufacture a passing result.
