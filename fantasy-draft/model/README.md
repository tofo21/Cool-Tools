# Draft Command model handoff

The app consumes one versioned intelligence package from `../data/model-package.js`.
The research pipeline can replace that file without changing draft-state, sync,
keeper, recovery, or interface code.

## Contract

- Schema: `model-package.schema.json`
- Runtime adapter: `model-adapter.js`
- Schema version: `1.0.0`
- Active league profile: `espn-keeper-10-ppr-2flex-2026`

Every player record may contain five independent layers:

1. `outcome`: the underlying outcome distribution, availability and upside/downside probabilities.
2. `leagueValue`: league-specific score, VORP, fair pick, tier and base roster/championship impact.
3. `market`: ESPN and Sleeper prices preserved separately.
4. `survival`: calibrated platform-specific curves or exact pick anchors.
5. `decision`: confidence, risk, upside and human-readable reason codes.

The package-level `decisionPolicy` holds calibrated TAKE/WAIT/value/cliff/fade
thresholds. These are runtime policy inputs, not hard-coded research conclusions.

## Output definitions

- **Best Player:** highest league-adjusted base value before Tony's live roster-fit adjustment.
- **Best Value:** strongest positive difference between platform price and league fair pick.
- **Best Fit:** best combination of league value, live roster need and positional cliff.
- **Best Ceiling:** strongest calibrated upside/elite outcome after bust risk.
- **Safest Wait:** best option that combines next-pick survival with limited VORP loss.
- **Projected Target:** best expected option before Tony is on the clock, including arrival probability.
- **Best Pick Now:** on-clock composite of league value, price, fit, urgency, VORP loss and championship-equity input.

The app keeps these lenses separate. `TAKE`, `WAIT`, `VALUE`, `UPSIDE`,
`POSITION CLIFF` and `FADE AT PRICE` are policy tags derived from the active
package and live draft state, not substitutes for the underlying scores.

## Safe fallback

The adapter rejects an incompatible schema, season or league profile. Missing
player fields fall back individually to the existing ECR/room-price/roster
heuristics. Model health exposes package validity, mode, version, freshness and
coverage so a partial or invalid research package cannot silently masquerade as
the production model.

Set `metadata.expiresAt` on candidate or production exports when the package
depends on time-sensitive rankings, injuries or room markets. An expired
research package is rejected at runtime and the visible fallback takes over.

## Research export

Generate a JavaScript assignment with this envelope:

```js
window.DRAFT_INTELLIGENCE_PACKAGE = { /* schema-valid package */ };
```

Do not collapse ESPN default rank and ESPN ADP. Do not double-count Sleeper ADP
and order. Preserve source metadata and point-in-time timestamps. A package may
be labeled `production` only after the contracted walk-forward and survival-
calibration tests pass.

## Replay acceptance gate

Use the isolated [replay harness](../replay/README.md) before promoting a
research package. It consumes this same adapter and league profile, records
model version/coverage in the exported report, and withholds calibration scores
when a decision window contains unresolved picks. Candidate-to-production
promotion should compare walk-forward reports rather than the bundled
deterministic UI fixture, whose purpose is functional verification only.
