from __future__ import annotations

"""Finalize Step 13 Model H outputs after source-gap audit.

The first Model H execution intentionally tested the reserved age/rookie columns.
The canonical v0.7 panel contains no populated age or rookie_flag values in the
eligible 2021-2025 sample, so those fields are a source gap, not an accepted
Model H family. This finalizer removes the null-only audit bundle from exported
scorecards and rewrites provenance accordingly. H_ALL is unchanged numerically
because the age/rookie inputs were entirely missing and therefore contributed
no model information.
"""

import json
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
PANEL = OUT / "master_player_season_panel_2020_2025_v0_7.csv"

panel = pd.read_csv(PANEL, low_memory=False)
for col in ["age", "rookie_flag"]:
    if col not in panel.columns:
        raise RuntimeError(f"Expected reserved Model H column missing: {col}")

eligible = panel[
    panel["season"].between(2021, 2025)
    & panel["draft_market_present"].astype(str).str.lower().isin(["true", "1", "1.0"])
    & panel["consensus_proj_points"].notna()
    & panel["ppr_points"].notna()
].copy()

age_count = int(pd.to_numeric(eligible["age"], errors="coerce").notna().sum())
rookie_count = int(
    eligible["rookie_flag"]
    .astype(str)
    .str.lower()
    .map({"true": 1.0, "false": 0.0, "1": 1.0, "0": 0.0, "1.0": 1.0, "0.0": 0.0})
    .notna()
    .sum()
)
if age_count != 0 or rookie_count != 0:
    raise RuntimeError(
        f"Age/rookie source-gap assumption changed: age={age_count}, rookie={rookie_count}. "
        "Rebuild Step 13 instead of silently finalizing."
    )

# Remove the null-only audit bundle from all user-facing scorecard tables.
for name in [
    "model_h_regression_fold_metrics_v09.csv",
    "model_h_regression_predictions_v09.csv",
    "model_h_classification_fold_metrics_v09.csv",
    "model_h_classification_predictions_v09.csv",
    "model_h_regression_pooled_metrics_v09.csv",
    "model_h_classification_pooled_metrics_v09.csv",
    "model_h_incremental_v09.csv",
]:
    path = OUT / name
    frame = pd.read_csv(path)
    if "bundle" in frame.columns:
        frame = frame[frame["bundle"] != "H_AGE_ROOKIE"].copy()
    frame.to_csv(path, index=False)

inc = pd.read_csv(OUT / "model_h_incremental_v09.csv")
sel = inc[inc["decision"].isin(["PROMOTE", "CONDITIONAL"])].sort_values(
    "relative_improvement", ascending=False
)

# Meaningful historical availability coverage is derived from Step 13's output
# contract when available; fall back to a conservative unknown marker rather
# than inventing a count.
old_contract_path = OUT / "MODEL_H_CONTEXT_SOURCE_CONTRACT_v0.9.json"
old_contract = json.load(open(old_contract_path, encoding="utf-8"))
old_cov = old_contract.get("coverage", {})
prior_history_count = old_cov.get("rows_with_at_least_one_prior_season_history")
if prior_history_count is None:
    # The initial script used not-null on a count field, so do not relabel that
    # value as observed-history coverage. Preserve only rows with a positive
    # history count if that column was written into predictions in a future run.
    prior_history_count = "NOT_REPORTED_IN_INITIAL_RUN"

source = {
    "version": "v0.9",
    "step": 13,
    "status": "MODEL_H_CONTEXT_TEST_COMPLETE",
    "accepted_families": {
        "historical_availability": (
            "Earlier canonical player-season realized games/PPG only, strictly season < target season."
        ),
        "qb_team_environment": (
            "Same-season accepted preseason consensus projections aggregated by preseason team."
        ),
    },
    "explicit_source_gaps": {
        "age_rookie": (
            "Canonical v0.7 age and rookie_flag columns are reserved but contain no populated values "
            "in the eligible 2021-2025 sample; no age/rookie feature is promoted or imputed."
        ),
        "point_in_time_preseason_injury_designations": (
            "No comparable accepted 2021-2025 point-in-time preseason injury series; not imputed."
        ),
        "coaching_play_caller": "Not attached in v0.9; not imputed.",
        "offensive_line": (
            "No comparable public preseason series accepted across 2021-2025; not imputed."
        ),
        "forward_looking_schedule": (
            "No audited preseason fantasy schedule-strength series attached in v0.9; not imputed."
        ),
    },
    "method_note": (
        "Incremental H bundles are compared to a reconstructed G baseline with identical features/folds "
        "and frozen strong regularization (Ridge alpha 1000, logistic C 0.3). This is a conservative "
        "Step 13 incremental test; v0.8 remains canonical for earlier A-G family conclusions."
    ),
    "coverage": {
        "eligible_rows": int(len(eligible)),
        "age_populated": age_count,
        "rookie_flag_populated": rookie_count,
        "rows_with_at_least_one_prior_season_history": prior_history_count,
        "team_qb_environment": int(old_cov.get("team_qb_environment", 0)),
    },
    "audit_note": (
        "The initial null-only H_AGE_ROOKIE test is removed from canonical exports. H_ALL numerical results "
        "are unaffected because those inputs had zero populated values."
    ),
}
old_contract_path.write_text(json.dumps(source, indent=2), encoding="utf-8")

lines = [
    "# Step 13 Model H Context Scorecard v0.9",
    "",
    "**Status: MODEL H CONTEXT TEST COMPLETE**",
    "",
    (
        "Accepted context added: leak-safe multi-year historical availability and same-season preseason "
        "QB/team environment derived from accepted consensus projections. Age/rookie, coaching, "
        "offensive-line, direct preseason injury, and forward schedule remain explicit source gaps rather "
        "than imputed inputs."
    ),
    "",
    "## Jobs clearing conservative gates",
    "",
]
if len(sel):
    lines += [
        "|Family|Pos|Target|Metric|Improvement vs G|Folds improved|Decision|",
        "|---|---|---|---|---:|---:|---|",
    ]
    lines += [
        f"|{r.bundle}|{r.position}|{r.target}|{r.metric_family}|{r.relative_improvement:.2%}|"
        f"{int(r.folds_improved)}/3|{r.decision}|"
        for _, r in sel.iterrows()
    ]
else:
    lines += ["No H context job cleared the gate."]

lines += ["", "## H_ALL pooled deltas", ""]
lines += [
    f"- {r.position} {r.target} ({r.metric_family}): {r.relative_improvement:+.2%}, "
    f"{int(r.folds_improved)}/3 folds, {r.decision}"
    for _, r in inc[inc["bundle"] == "H_ALL"]
    .sort_values("relative_improvement", ascending=False)
    .iterrows()
]
lines += [
    "",
    "## Production interpretation",
    "",
    (
        "Only position-target jobs that clear the frozen gate should be candidates for 2026 Player Truth. "
        "Context is not granted one universal weight. Several classification jobs degrade sharply under "
        "H_ALL, so source families stay independently switchable. The failed F5B TAKE/WAIT gate is untouched."
    ),
]
(OUT / "MODEL_H_SCORECARD_REPORT_v0.9.md").write_text("\n".join(lines), encoding="utf-8")

integrity_path = OUT / "model_h_integrity_v09.json"
integrity = json.load(open(integrity_path, encoding="utf-8"))
integrity["source_contract"] = source
integrity["null_only_age_rookie_bundle_removed"] = True
integrity["canonical_bundles"] = ["H_AVAILABILITY", "H_QB_TEAM_ENV", "H_ALL"]
integrity_path.write_text(json.dumps(integrity, indent=2), encoding="utf-8")

print(json.dumps({
    "status": source["status"],
    "eligible_rows": len(eligible),
    "age_populated": age_count,
    "rookie_flag_populated": rookie_count,
    "canonical_bundles": integrity["canonical_bundles"],
}, indent=2))
