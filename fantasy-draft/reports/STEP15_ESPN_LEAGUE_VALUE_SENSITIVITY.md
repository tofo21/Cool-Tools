# Step 15 ESPN League Value Sensitivity

Status: **PASS**

The diagnostics change only league-wide FLEX demand. They do not tune the published 20-FLEX formula.

| Scenario | FLEX | RB/WR/TE split | Spearman rank correlation | Top-20 overlap | Max rank shift |
| --- | ---: | --- | ---: | ---: | ---: |
| flex-minus-2 | 18 | 6/12/0 | 0.999869 | 19/20 | 4 |
| flex-plus-2 | 22 | 8/14/0 | 0.999849 | 20/20 | 4 |

Baseline replacement values: QB 290.826, RB 189.860, WR 190.270, TE 170.920.
