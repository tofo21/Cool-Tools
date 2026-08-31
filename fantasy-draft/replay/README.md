# Draft Command replay contract

The replay lab evaluates an intelligence package against historical draft
events without reading or writing the live draft's browser storage.

## Input

The preferred envelope is:

```json
{
  "schemaVersion": "1.0.0",
  "platform": "espn",
  "teamCount": 10,
  "rounds": 16,
  "completeThrough": 160,
  "events": [
    { "overall": 1, "playerId": 1, "playerName": "Jahmyr Gibbs" }
  ]
}
```

The normalizer also accepts:

- Draft Command backup files with an `events` array.
- Sleeper picks with `pick_no`, `draft_slot`, `player_id`, and `metadata`.
- ESPN-style picks with `pickNumber` or `overallPickNumber` and a player name.
- A bare pick array. A `pick_no` field causes the Sleeper price layer to be
  inferred automatically.

Canonical `playerId` values take precedence. Platform-native IDs are treated as
external identifiers and resolved by normalized player name. Pick ownership is
rebuilt from the configured snake order. Duplicate players, duplicate picks,
keeper conflicts, unresolved names, and format differences are reported rather
than silently included.

## Evaluation

Immediately before every non-keeper Tony selection, the engine reconstructs
the available pool and roster context and captures:

- Best Player, room-price leader, and Best Pick Now.
- The recorded selection and its draft-time league score/value gap.
- Individual and tier survival probabilities to Tony's next open pick.
- TAKE/WAIT policy tag and completed-window counterfactual.

Calibration outcomes are scored only when every intervening selection is
resolved. Individual and tier predictions report Brier score, expected
calibration error, and five probability buckets. An incomplete or partially
unresolved window remains pending instead of being treated as survival.

Strategy scores are decision-time comparisons, not realized fantasy-season
results. Outcome-value and championship-equity comparisons become meaningful
when the research package supplies those fields and the evaluation log is
joined to season results.

## Output

`Export report` produces a JSON file containing the normalized log, model
health/version, decision snapshots, strategy comparison, calibration records,
and import issues. That report is the handoff artifact for research-model
acceptance and regression testing.
