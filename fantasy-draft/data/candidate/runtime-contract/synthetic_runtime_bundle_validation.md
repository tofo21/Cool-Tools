# Draft Runtime Artifact Validation

- Promotion gate: **PASS**
- Validation time: `2026-08-31T23:00:00Z`
- Blocking issues: **0**
- Warnings: **1**
- Informational findings: **0**

## Input hashes

| Artifact | SHA-256 |
| --- | --- |
| player-truth | `2a4da36e59a0e70882a5fc6253c458982e4ec70b198a730a5331b50d3d5a10dc` |
| espn-market | `aa6470bad9c77626e6533a195c3a1b4965fbfb188bed8da4c74c006ca187119e` |
| espn-league-value | `2a5e999c31583146763f5590667bb4ceafecbeb5524d014348b91b5f6bfddc07` |
| opponent-intent | `9a30e5de70239fb5225536a40e2dac48aa6e13a2cc26fc7992c811ff9813e82d` |

## Coverage

| Slice | Eligible | Player Truth | ESPN rank | ESPN ADP | League Value |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 24 | 24 | 22 | 22 | 24 |
| QB | 6 | 6 | 6 | 6 | 6 |
| RB | 6 | 6 | 6 | 6 | 6 |
| WR | 6 | 6 | 5 | 6 | 6 |
| TE | 6 | 6 | 5 | 4 | 6 |
| Board 1-50 | 23 | 23 | 22 | 22 | 23 |
| Board 51-100 | 0 | 0 | 0 | 0 | 0 |
| Board 101-160 | 0 | 0 | 0 | 0 | 0 |
| Board 161+ | 1 | 1 | 0 | 0 | 1 |

Keeper identities: **10/10** resolved.

## Unresolved identities

| Internal ID | Board rank | Artifact | Blocking | Reason |
| ---: | ---: | --- | --- | --- |
| 1024 | 200 | player-truth | no | Player Truth identity remains unresolved |

## Gate findings

| Severity | Code | Artifact | Path | Finding |
| --- | --- | --- | --- | --- |
| WARNING | `LOWER_BOARD_IDENTITY_GAP` | player-truth | `internalPlayerId=1024` | Player Truth identity remains unresolved |

## Future real-artifact benchmark

The known ESPN candidate benchmark is 199/200 Draft Command identities matched, 10/10 keepers resolved, zero unresolved raw ESPN top-160 players, and zero unresolved raw ranked top-250 players. Jaydon Blue was the sole Draft Command-only miss and was absent from ESPN's 500-player payload. This benchmark is not synthetic data and is not used to manufacture a passing result.
