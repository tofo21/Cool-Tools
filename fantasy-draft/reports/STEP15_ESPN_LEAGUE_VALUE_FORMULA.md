# Step 15 ESPN League Value Formula

Status: formula frozen for implementation

Formula version: `step15-espn-league-value-v1`

Replacement-level method: `keeper-initialized-starter-allocation-v1`

## Separation of concerns

Step 15 consumes `projectedFullPprPoints` from the immutable Step 14 Player Truth artifact and exposes it unchanged as `projectedLeaguePoints`. Full PPR requires no scoring conversion. ESPN rank, ESPN ADP, Sleeper rank, ECR, auction values, Opponent Intent, survival, and Tony's future live roster state are excluded from the base formula.

Keepers are league-state metadata. They occupy demand and are removed from the available-player pool, but their Player Truth projections are neither changed nor penalized. All keepers retain League Value records so coverage remains one-to-one with Player Truth.

## Verified league geometry

- ESPN league: `167404`
- Full PPR; 10 teams; 16 rounds; 160 total picks
- Tony: draft slot 5, stable team ID `team-05`
- Starters per team: 1 QB, 2 RB, 2 WR, 1 TE, 2 RB/WR/TE FLEX
- Active roster: 16 players; 8 starter spots and 8 bench spots; no K or DST
- IR is outside active draft demand and is represented as zero in the adapter socket
- One approved keeper per team; ten keepers total

The settings hash is SHA-256 over canonical JSON containing only the league ID, settings version, scoring format, roster format, team/round/draft geometry, Tony team ID, and the ten keeper tuples (`teamId`, `internalPlayerId`, `round`, `overallPick`). Source notes and player names are verification metadata and are outside the hash boundary.

## Deterministic allocation

Players are ordered for every allocation by descending `projectedLeaguePoints`, then ascending `internalPlayerId`. Let $P_i$ be player $i$'s Step 14 full-PPR projection.

1. Validate the ten keeper identities, names, teams, rounds, and snake-draft overall picks. Assign every keeper to one mandatory slot at the keeper's Player Truth position on the keeper's team.
2. Mandatory league demand is QB 10, RB 20, WR 20, and TE 10. For each position, subtract the keepers already occupying that position and fill the remaining mandatory slots with the highest projected non-keepers at that position.
3. Remove keepers and mandatory selections from the FLEX-eligible pool. Fill exactly 20 FLEX starters with the highest projected remaining RB/WR/TE players.
4. For each position, the effective replacement player is the highest projected non-keeper at that position remaining after mandatory and FLEX allocation. The effective replacement value $R_p$ is that player's projected points. The player is the first available replacement, not an additional starter.

This procedure allows the 20 FLEX slots to fall naturally across RB, WR, and TE. No fixed positional FLEX split is imposed and no market field can influence the split.

## Value equations

For a player $i$ at position $p$:

$$
M_i = P_i - R_p
$$

where $M_i$ is `marginalValue`.

For RB, WR, and TE, the post-FLEX replacement value already contains FLEX scarcity. Therefore:

$$
F_i = M_i
$$

where $F_i$ is `flexAdjustedValue`. The equality is intentional: adding a second FLEX premium would double-count scarcity. QB uses the same identity because QB is not FLEX-eligible.

The immutable base score is:

$$
L_i = F_i
$$

where $L_i$ is `leagueValueScore`. Values are calculated with decimal arithmetic and emitted to three decimal places. Negative values are retained rather than floored, which preserves a consistent ordering for below-replacement players.

## Ranking and confidence

Overall League Value rank sorts by descending emitted numeric `leagueValueScore`, with ascending `internalPlayerId` as the only tie breaker. Positional rank uses the same rule within QB, RB, WR, and TE. Formatted display text is never used.

`confidence` is copied from the upstream Step 14 `modelConfidence`; it does not change the score. Every record is `validated`, not frozen or production, after the Step 15 acceptance gate passes.

## Roster fit and later recalculation

Tony's keeper-initialized state contains Jaxson Dart (internal ID 90) in the QB slot. The Step 15 base score is universal to the verified league and does not bake Tony's roster needs into player value. Following the Step 14 handoff, `rosterFitAdjustment` is `null` for every record because a live roster-fit function is not an approved Step 15 input.

The application may later compute a separate live adjustment from Tony's current roster and open slots, then combine it for a presentation or recommendation layer. That recalculation must not overwrite `projectedLeaguePoints`, any replacement value, `marginalValue`, `flexAdjustedValue`, or `leagueValueScore`.

## Sensitivity protocol

The published sensitivity report reruns the same algorithm with 18 and 22 league-wide FLEX slots. It reports replacement values, FLEX allocation by position, top-20 overlap, rank correlation, and rank shifts against the 20-FLEX baseline. These scenarios are diagnostics only and do not tune or alter the approved formula.
