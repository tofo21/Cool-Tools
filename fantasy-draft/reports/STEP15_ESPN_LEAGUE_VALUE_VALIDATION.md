# Step 15 ESPN League Value Validation

Overall status: **PASS**

| Check | Status | Detail |
| --- | --- | --- |
| `player_truth_file_hash` | PASS | f6488e648af2549f1b7fa50eb485aa8f29784280144796e5e6d581a13b477bd3 |
| `player_truth_payload_hash` | PASS | be052a59ad9a0643246b2ed113e2c728fc5abfafb97e4278c53b8ea621f89694 |
| `coverage_199_of_199` | PASS | 199 |
| `top160_159_of_159` | PASS | 159 |
| `no_duplicates` | PASS | [] |
| `no_orphans` | PASS | [] |
| `no_missing_records` | PASS | [] |
| `keenan_allen_absent` | PASS | internalPlayerId 143 absent |
| `jaydon_blue_internal_id_only` | PASS | internalPlayerId 190 present; ESPN ID remains null upstream |
| `josh_jacobs_unadjusted` | PASS | 256.850 points; 17 games |
| `kayshon_boutte_conflict_preserved` | PASS | Draft Command HOU; source NE limitation retained |
| `keeper_count_and_identity` | PASS | {'QB': 1, 'RB': 3, 'WR': 4, 'TE': 2} |
| `league_geometry` | PASS | 10/16/5/160/team-05 |
| `mandatory_allocation` | PASS | {'QB': 10, 'RB': 20, 'WR': 20, 'TE': 10} |
| `flex_allocation` | PASS | {'RB': 7, 'WR': 13, 'TE': 0} |
| `no_flex_double_counting` | PASS | flexAdjustedValue == marginalValue == leagueValueScore |
| `numeric_rank_consistency` | PASS | records emitted in numeric League Value rank order |
| `tie_breaking` | PASS | score descending; ID ascending |
| `finite_numeric_values` | PASS | all required numeric fields finite |
| `roster_fit_separate` | PASS | all rosterFitAdjustment values null |
| `negative_values_retained` | PASS | below-replacement values are not floored |
| `market_fields_absent` | PASS | no market or Opponent Intent fields in records |
| `payload_signature` | PASS | 5957c33276b19d5d73305e1be50f9649c97be55c9bc55932ed9bafc39fd5f785 |
