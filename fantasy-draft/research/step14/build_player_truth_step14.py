#!/usr/bin/env python3
"""Build the deterministic Step 14 / 2026 Player Truth package.

The universal full-season center is the frozen consensus artifact's
``standardized_full_ppr_points`` field. Step 13B signals are admitted only for
their tested position/target scope; no fold coefficient is repurposed as a
2026 production weight. Missing distributions and probabilities remain null.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0.0"
ARTIFACT_VERSION = "step14-2026.1"
GENERATED_AT = "2026-09-01T00:59:51Z"
STEP13B_COMMIT = "e3cf26eb863e4f54b6635e5a4aac50fe88e53e09"
CONSENSUS_COMMIT = "160f739cbeca74e6b2d559b372891f1491260fe9"
CONSENSUS_TREE = "efdd7a56b88b47b20dac62137c287c6891563969"
CONSENSUS_CSV_SHA256 = "8ab2386145f49cf2a44bc0c5667400e68e8bb49b4d63d15f0d416d7bd1d742c6"
CONSENSUS_LEDGER_SHA256 = "cb9218f7e430016115aeb2718808fb0a6ad5aadc5640844841e1f3496213940e"
CONSENSUS_ARTIFACT_ID = "consensus_2026_frozen_20260901T005951Z_93fbef0b61f0"
CONSENSUS_RELATIVE_DIR = Path(
    "data/derived/consensus_2026/"
    "consensus_2026_frozen_20260901T005951Z_93fbef0b61f0"
)
CONSENSUS_FILENAME = "current_2026_consensus_components_20260901T005951Z.csv"

# The candidate improves Brier score but worsens ECE. It is not promoted to a
# calibrated runtime probability head. This is the only Step 14 rejection.
CALIBRATION_REJECTION = "S13B-CLA-QB-BUST-FLAG-COMBINE"

OUTPUT_FILES = (
    "player_truth_step14.json",
    "player_truth_step14_detail.json",
    "player_truth_step14_schema_and_dictionary.json",
    "player_truth_step14_candidate_decisions.json",
    "player_truth_step14_negative_registry.json",
    "player_truth_step14_identity_reconciliation.csv",
    "player_truth_step14_unresolved_identity_queue.json",
    "player_truth_step14_current_status_overlay.json",
    "player_truth_step14_josh_jacobs_invariant.json",
    "player_truth_step14_coverage_report.json",
    "player_truth_step14_missing_players.json",
    "player_truth_step14_calibration_uncertainty.json",
    "player_truth_step14_validation.json",
    "player_truth_step14_runtime_conformance.json",
    "player_truth_step14_source_manifest.json",
    "player_truth_step14_manifest.json",
    "deterministic_build_proof.json",
    "REPRODUCTION.md",
    "SHA256SUMS",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Path to fantasy-draft",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Default: <repo-root>/data/candidate/player-truth",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="Default: <repo-root>/reports",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_sha256(value: dict[str, Any]) -> str:
    unsigned = json.loads(json.dumps(value))
    unsigned["integrity"].pop("payloadSha256", None)
    return hashlib.sha256(canonical_json(unsigned)).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_name(value: str) -> str:
    value = value.lower().replace("’", "'")
    value = re.sub(r"\b(jr|sr|ii|iii|iv|v)\.?\b", "", value)
    return re.sub(r"[^a-z0-9]", "", value)


def parse_players_js(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    marker = "window.PLAYER_DATA = "
    start = text.index(marker) + len(marker)
    end = text.index(";", start)
    players = json.loads(text[start:end])
    return [row for row in players if row.get("pos") in {"QB", "RB", "WR", "TE"}]


def nullable(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def as_bool(value: str | None) -> bool | None:
    value = nullable(value)
    if value is None:
        return None
    return value.lower() == "true"


def q3(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def availability(identity: dict[str, str]) -> tuple[str, float]:
    if as_bool(identity.get("status_overlay_present")) is not True:
        return "unknown", 0.25
    status = (identity.get("current_status") or "").upper()
    injury = (identity.get("injury_or_rehab_status") or "").upper()
    combined = f"{status}|{injury}"
    if "COMMISSIONER_EXEMPT" in combined:
        result = "out"
    elif as_bool(identity.get("ir_flag")) or "INJURY_RESERVE" in combined:
        result = "ir"
    elif as_bool(identity.get("pup_flag")) or "PUP" in combined:
        result = "pup"
    elif nullable(identity.get("suspension_status")) or "SUSPEND" in combined:
        result = "suspended"
    elif re.search(r"(^|[|:])OUT($|[|:])", combined):
        result = "out"
    elif "DOUBTFUL" in combined:
        result = "doubtful"
    elif "QUESTIONABLE" in combined or "DAY_TO_DAY" in combined:
        result = "questionable"
    elif "PROBABLE" in combined:
        result = "probable"
    elif "ACTIVE" in combined or re.search(r"(^|[|:])ACT($|[|:])", combined):
        result = "available"
    else:
        result = "unknown"
    source_confidence = (identity.get("source_confidence") or "").lower()
    confidence = 0.95 if source_confidence.startswith("high") else 0.80 if source_confidence.startswith("medium") else 0.60
    return result, confidence


def identity_method(identity: dict[str, str]) -> str:
    if nullable(identity.get("espn_id")) and identity.get("match_method") == "espn_id_to_nflverse_gsis":
        return "espn-id"
    if as_bool(identity.get("manual_review_flag_x")):
        return "manual-reviewed"
    if nullable(identity.get("gsis_id")):
        return "verified-crosswalk"
    return "unresolved"


def scoped_key(record: dict[str, Any], prefix: str | None = None) -> str:
    value = ":".join(
        (
            str(record["feature_family_or_bundle"]),
            str(record["position_or_scope"]),
            str(record["prediction_target"]),
        )
    )
    return f"{prefix}:{value}" if prefix else value


def candidate_scope(candidate: dict[str, Any]) -> str:
    return ":".join(
        (
            candidate["feature_family"],
            candidate.get("position_or_cohort", candidate.get("position")),
            candidate["target"],
        )
    )


def make_candidate_decisions(registry: dict[str, Any]) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for candidate in registry["candidates"]:
        calibration = candidate.get("calibration_metrics") or {}
        is_calibration_rejection = candidate["candidate_id"] == CALIBRATION_REJECTION
        if is_calibration_rejection:
            decision = "REJECT_STEP14_CALIBRATION"
            consequence = "No runtime bust-probability contribution; consensus and missing probability are preserved."
            rationale = (
                "Brier lift passed the Step 13B candidate gate, but ECE worsened from "
                f"{calibration['STEP13A_BASELINE']['ece']:.12f} to "
                f"{calibration['STEP13B_CANDIDATE']['ece']:.12f}; an uncalibrated probability is not promoted."
            )
        else:
            decision = "APPROVE_EXACT_SCOPE_SIGNAL"
            consequence = (
                "Admitted only for the named position/target/configuration. No numeric 2026 contribution is applied "
                "without audited 2026 feature inputs and an approved full-fit model weight."
            )
            rationale = (
                "Step 13B candidate gate passed; mechanism review passed; no rookie/veteran direction conflict was recorded."
            )
        decisions.append(
            {
                "candidate_id": candidate["candidate_id"],
                "decision": decision,
                "metric_kind": candidate["metric_kind"],
                "position": candidate["position_or_cohort"],
                "target": candidate["target"],
                "feature_family": candidate["feature_family"],
                "exact_input_columns": candidate["exact_input_columns"],
                "exact_model_configuration_reference": candidate["exact_model_configuration_reference"],
                "pooled_improvement": candidate["performance_metrics"]["pooled_improvement"],
                "folds_improved": candidate["performance_metrics"]["folds_improved"],
                "folds_total": candidate["performance_metrics"]["folds_total"],
                "worst_fold": candidate["performance_metrics"]["worst_fold"],
                "bootstrap_probability_of_improvement": candidate["stability_and_sensitivity"]["bootstrap_probability_of_improvement"],
                "bootstrap_ci_low": candidate["stability_and_sensitivity"]["bootstrap_ci_low"],
                "bootstrap_ci_high": candidate["stability_and_sensitivity"]["bootstrap_ci_high"],
                "mechanism_review_result": candidate["stability_and_sensitivity"]["mechanism_review_result"],
                "subgroup_direction_conflict": candidate["stability_and_sensitivity"]["subgroup_direction_conflict"],
                "historical_coverage": candidate["historical_coverage"],
                "calibration_metrics": calibration,
                "rationale": rationale,
                "limitation": candidate["limitations"],
                "downstream_consequence": consequence,
                "numeric_2026_contribution": None,
                "numeric_application_status": "NOT_APPLIED_NO_AUDITED_2026_FEATURE_MATRIX_OR_APPROVED_FULL_FIT_WEIGHTS",
            }
        )
    counts = Counter(item["decision"] for item in decisions)
    return {
        "schema_version": "1.0.0",
        "source_commit": STEP13B_COMMIT,
        "candidate_count": len(decisions),
        "decision_counts": dict(sorted(counts.items())),
        "production_weights_promoted": 0,
        "universal_consensus_center_preserved": True,
        "decisions": decisions,
    }


def build(repo_root: Path, output_dir: Path, report_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        target = output_dir / name
        if target.exists():
            target.unlink()

    input_dir = repo_root / "research/step14/inputs"
    consensus_dir = repo_root / CONSENSUS_RELATIVE_DIR
    consensus_path = consensus_dir / CONSENSUS_FILENAME
    consensus_ledger = consensus_dir / "SHA256SUMS"
    if sha256(consensus_path) != CONSENSUS_CSV_SHA256:
        raise SystemExit("consensus CSV checksum gate failed")
    if sha256(consensus_ledger) != CONSENSUS_LEDGER_SHA256:
        raise SystemExit("consensus SHA256SUMS checksum gate failed")

    candidate_registry = read_json(input_dir / "STEP14_CANDIDATE_REGISTRY_ENRICHED_v1.json")
    negative_registry = read_json(input_dir / "NEGATIVE_FINDINGS_AND_QUARANTINES_v1.json")
    identity_rows = read_csv(input_dir / "CURRENT_2026_PLAYER_IDENTITY_STATUS_TRUTH_v1.csv")
    josh_invariant = read_json(input_dir / "JOSH_JACOBS_COMMISSIONER_EXEMPT_OVERLAY_v1.json")
    candidates = make_candidate_decisions(candidate_registry)

    assert candidate_registry["candidate_count"] == 13
    assert negative_registry["counts"] == {
        "rejected": 117,
        "contextual": 5,
        "quarantined": 5,
        "incomplete": 1,
        "rejected_H_ALL": 28,
    }
    assert candidate_registry["production_weights_promoted"] == 0
    assert negative_registry["binding_rules"]["H_ALL"].startswith("rejected")

    board = parse_players_js(repo_root / "data/players.js")
    identity_by_id = {int(row["draft_command_id"]): row for row in identity_rows if nullable(row.get("draft_command_id"))}
    consensus_rows = read_csv(consensus_path)
    consensus_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in consensus_rows:
        key = (normalize_name(row["canonical_name"]), row["position"])
        if key in consensus_by_key:
            raise AssertionError(f"duplicate consensus join key {key}")
        consensus_by_key[key] = row

    negative_records = negative_registry["records"]
    contextual = [record for record in negative_records if record["category"] == "contextual"]
    quarantined = [record for record in negative_records if record["category"] == "quarantined"]
    incomplete = [record for record in negative_records if record["category"] == "incomplete"]
    h_all = [record for record in negative_records if record["category"] == "rejected_H_ALL"]
    approved = [item for item in candidates["decisions"] if item["decision"] == "APPROVE_EXACT_SCOPE_SIGNAL"]

    runtime_players: list[dict[str, Any]] = []
    detail_players: list[dict[str, Any]] = []
    reconciliation_rows: list[dict[str, Any]] = []
    missing_players: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []

    for player in sorted(board, key=lambda row: row["id"]):
        internal_id = int(player["id"])
        identity = identity_by_id.get(internal_id)
        if identity is None:
            identity = {
                "draft_command_id": str(internal_id),
                "player_name": player["name"],
                "canonical_name": player["name"],
                "position": player["pos"],
                "team": player["team"],
                "status_overlay_present": "False",
                "identity_conflict_flag": "False",
                "manual_review_flag_x": "False",
                "missing_identity_reason": "NO_STEP13B_STABLE_IDENTITY_CROSSWALK_ROW",
            }
        join_key = (normalize_name(player["name"]), player["pos"])
        consensus = consensus_by_key.get(join_key)
        if consensus is None:
            missing_players.append(
                {
                    "internal_player_id": internal_id,
                    "draft_command_board_rank": internal_id,
                    "display_name": player["name"],
                    "normalized_name": normalize_name(player["name"]),
                    "team": player["team"],
                    "position": player["pos"],
                    "missing_fields": [
                        "consensus_baseline",
                        "projected_full_ppr_points",
                        "projected_ppg",
                        "expected_games",
                    ],
                    "reason": "NO_APPROVED_CONSENSUS_RECORD_FOR_CANONICAL_NAME_PLUS_POSITION",
                    "fallback_used": False,
                    "coverage_exception": "APPROVED_DRAFT_COMMAND_SOLE_EXCEPTION" if player["name"] == "Keenan Allen" else None,
                }
            )
            continue

        points_decimal = Decimal(consensus["standardized_full_ppr_points"])
        points = q3(points_decimal)
        ppg = q3(points_decimal / Decimal(17))
        expected_games = 17.0
        source_team = consensus["nfl_team"]
        current_team = player["team"]
        team_conflict = source_team != current_team
        avail_status, avail_confidence = availability(identity)
        canonical_key = f"gsis:{identity['gsis_id'].lower()}" if nullable(identity.get("gsis_id")) else f"draft-command:{internal_id}"
        identity_confidence = float(identity["match_score"]) if nullable(identity.get("match_score")) else 0.0
        model_confidence = 0.70 if team_conflict else 0.85

        eligible_features = sorted(
            candidate_scope(item)
            for item in approved
            if item["position"] == player["pos"]
        )
        scoped_quarantines = sorted(
            scoped_key(record, record["category"])
            for record in quarantined
            if record["position_or_scope"] in {player["pos"], "ALL"}
        )
        h_all_scopes = sorted(
            scoped_key(record, "rejected_H_ALL")
            for record in h_all
            if record["position_or_scope"] == player["pos"]
        )
        incomplete_scopes = sorted(scoped_key(record, "incomplete") for record in incomplete)
        runtime_quarantines = sorted(set(scoped_quarantines + h_all_scopes + incomplete_scopes))
        contextual_features = sorted(
            scoped_key(record, "contextual")
            for record in contextual
            if record["position_or_scope"] in {player["pos"], "ALL"}
        )

        limitations = [
            "Full-season P50 is standardized_full_ppr_points from the approved frozen consensus and is not market rank, ADP, ECR, or auction value.",
            "PPG is the separate schedule-normalized consensus center (full-season P50 / 17); no Step 13B PPG candidate was promoted.",
            "Expected games is the unadjusted 17-game schedule baseline; exact-scope Step 13B signals are not numerically applied without audited 2026 inputs and approved full-fit weights.",
            "P10/P90 and runtime event probabilities are unavailable and remain null.",
            "No status overlay means unknown availability, not active status or zero risk.",
        ]
        if team_conflict:
            limitations.append(
                f"Team provenance conflict preserved: frozen consensus source lists {source_team}; current Draft Command identity lists {current_team}."
            )
        if identity_method(identity) == "unresolved":
            limitations.append(
                "Stable GSIS/ESPN identity is unresolved; Draft Command internal ID is retained as the only join key pending manual review."
            )
        if identity["player_name"] == "Josh Jacobs":
            limitations.extend(
                [
                    "COMMISSIONER_EXEMPT is binding; no return date is asserted.",
                    "No numerical games adjustment is approved; consensus P50 remains unadjusted at 256.850.",
                ]
            )

        source_artifacts = [
            CONSENSUS_ARTIFACT_ID,
            "CURRENT_2026_PLAYER_IDENTITY_STATUS_TRUTH_v1",
            "STEP14_CANDIDATE_REGISTRY_ENRICHED_v1",
            "NEGATIVE_FINDINGS_AND_QUARANTINES_v1",
        ]
        runtime_player = {
            "internalPlayerId": internal_id,
            "draftCommandBoardRank": internal_id,
            "canonicalPlayerKey": canonical_key,
            "espnPlayerId": nullable(identity.get("espn_id")),
            "normalizedName": identity.get("canonical_name") or player["name"],
            "nflTeam": current_team,
            "position": player["pos"],
            "identityMatchMethod": identity_method(identity),
            "identityConfidence": identity_confidence,
            "projectedFullPprPoints": points,
            "projectedPpg": ppg,
            "expectedGames": expected_games,
            "fullPprPointsP10": None,
            "fullPprPointsP50": points,
            "fullPprPointsP90": None,
            "eliteProbability": None,
            "starterProbability": None,
            "bustProbability": None,
            "availabilityStatus": avail_status,
            "availabilityConfidence": avail_confidence,
            "modelConfidence": model_confidence,
            "eligibleFeatureFamilies": eligible_features,
            "quarantinedFeatureFamilies": runtime_quarantines,
            "provenance": {
                "modelVersion": ARTIFACT_VERSION,
                "sourceArtifactIds": source_artifacts,
            },
            "limitations": limitations,
        }
        runtime_players.append(runtime_player)

        applicable_decisions = [
            {
                "candidate_id": item["candidate_id"],
                "target": item["target"],
                "feature_family": item["feature_family"],
                "decision": item["decision"],
                "numeric_contribution": None,
                "application_status": item["numeric_application_status"],
            }
            for item in candidates["decisions"]
            if item["position"] == player["pos"]
        ]
        detail_players.append(
            {
                "canonical_player_id": nullable(identity.get("canonical_player_id")),
                "gsis_id": nullable(identity.get("gsis_id")),
                "draft_command_internal_id": internal_id,
                "espn_id": nullable(identity.get("espn_id")),
                "normalized_name": normalize_name(identity.get("canonical_name") or player["name"]),
                "display_name": identity.get("canonical_name") or player["name"],
                "current_nfl_team": current_team,
                "consensus_source_team": source_team,
                "team_conflict_preserved": team_conflict,
                "position": player["pos"],
                "heads": {
                    "full_season_ppr": {
                        "p10": None,
                        "p50": points,
                        "p90": None,
                        "baseline_field": "standardized_full_ppr_points",
                        "baseline_value_text": consensus["standardized_full_ppr_points"],
                        "candidate_contribution": None,
                    },
                    "ppr_ppg": {
                        "p50": ppg,
                        "derivation": "standardized_full_ppr_points / 17",
                        "candidate_contribution": None,
                    },
                    "expected_games": {
                        "p50": expected_games,
                        "meaning": "unadjusted 17-game schedule baseline; not an injury-adjusted estimate",
                        "candidate_contribution": None,
                    },
                    "event_probabilities": {
                        "elite": None,
                        "useful_starter": None,
                        "bust": None,
                        "availability_bust": None,
                        "missing_reason": "NO_APPROVED_2026_PROBABILITY_OUTPUT",
                    },
                },
                "candidate_decisions": applicable_decisions,
                "promoted_feature_indicators": eligible_features,
                "contextual_feature_indicators": contextual_features,
                "quarantined_feature_indicators": scoped_quarantines,
                "binding_h_all_rejection_indicators": h_all_scopes,
                "incomplete_feature_indicators": incomplete_scopes,
                "missing_feature_indicators": [
                    "current_2026_candidate_feature_matrix",
                    "approved_full_fit_candidate_weights",
                    "distribution_quantiles_p10_p90",
                    "calibrated_2026_event_probabilities",
                ],
                "identity": {
                    "method": identity_method(identity),
                    "confidence": identity_confidence,
                    "conflict_flag": as_bool(identity.get("identity_conflict_flag")),
                    "manual_review_flag": as_bool(identity.get("manual_review_flag_x")),
                    "source": nullable(identity.get("source")),
                    "source_timestamp": nullable(identity.get("source_timestamp")),
                },
                "model_confidence": model_confidence,
                "model_confidence_policy": "0.85 approved freeze; 0.70 when a source/current team provenance conflict is present; not an outcome probability",
                "availability": {
                    "runtime_status": avail_status,
                    "status_overlay_present": as_bool(identity.get("status_overlay_present")),
                    "source_status": nullable(identity.get("current_status")),
                    "injury_or_rehab_status": nullable(identity.get("injury_or_rehab_status")),
                    "expected_week1_availability": nullable(identity.get("expected_week1_availability")),
                    "expected_return_week": nullable(identity.get("expected_return_week")),
                    "expected_games_adjustment": None if not nullable(identity.get("expected_games_adjustment")) else identity["expected_games_adjustment"],
                    "source_confidence": nullable(identity.get("source_confidence")),
                    "primary_source": nullable(identity.get("primary_source")),
                    "secondary_source": nullable(identity.get("secondary_source")),
                    "last_verified_timestamp": nullable(identity.get("last_verified_timestamp")),
                },
                "provenance": {
                    "consensus_artifact_id": CONSENSUS_ARTIFACT_ID,
                    "consensus_source_version": consensus["source_version"],
                    "consensus_capture_timestamp": consensus["capture_timestamp"],
                    "consensus_source_state": consensus["source_state"],
                    "consensus_missing_field_indicators": consensus["missing_field_indicators"].split("|") if consensus["missing_field_indicators"] else [],
                    "step13b_commit": STEP13B_COMMIT,
                },
                "limitations": limitations,
            }
        )

        reconciliation_rows.append(
            {
                "internal_player_id": internal_id,
                "draft_command_board_rank": internal_id,
                "canonical_player_id": identity.get("canonical_player_id", ""),
                "gsis_id": identity.get("gsis_id", ""),
                "espn_id": identity.get("espn_id", ""),
                "display_name": identity.get("canonical_name") or player["name"],
                "normalized_name": normalize_name(identity.get("canonical_name") or player["name"]),
                "position": player["pos"],
                "current_team": current_team,
                "consensus_source_team": source_team,
                "team_conflict_preserved": str(team_conflict).lower(),
                "identity_method": identity_method(identity),
                "identity_confidence": identity_confidence,
                "consensus_join_key": f"{normalize_name(player['name'])}|{player['pos']}",
                "consensus_join_status": "MATCHED_CANONICAL_NAME_POSITION",
            }
        )
        if as_bool(identity.get("status_overlay_present")):
            status_rows.append(
                {
                    "internal_player_id": internal_id,
                    "canonical_player_id": nullable(identity.get("canonical_player_id")),
                    "display_name": identity.get("canonical_name") or player["name"],
                    "current_status": nullable(identity.get("current_status")),
                    "runtime_availability_status": avail_status,
                    "expected_games_adjustment": None if not nullable(identity.get("expected_games_adjustment")) else identity["expected_games_adjustment"],
                    "expected_return_week": nullable(identity.get("expected_return_week")),
                    "primary_source": nullable(identity.get("primary_source")),
                    "secondary_source": nullable(identity.get("secondary_source")),
                    "last_verified_timestamp": nullable(identity.get("last_verified_timestamp")),
                    "source_confidence": nullable(identity.get("source_confidence")),
                    "notes": nullable(identity.get("notes")),
                }
            )

    assert len(board) == 200
    assert len(runtime_players) == 199
    assert len(missing_players) == 1
    assert missing_players[0]["display_name"] == "Keenan Allen"
    assert len([row for row in runtime_players if row["draftCommandBoardRank"] <= 160]) == 159
    josh_runtime = next(row for row in runtime_players if row["normalizedName"] == "Josh Jacobs")
    assert josh_runtime["projectedFullPprPoints"] == 256.85
    josh_detail = next(row for row in detail_players if row["display_name"] == "Josh Jacobs")
    assert josh_detail["availability"]["expected_games_adjustment"] is None
    assert josh_detail["availability"]["expected_return_week"] == "unknown_pending_NFL_review"
    kayshon = next(row for row in detail_players if row["display_name"] == "Kayshon Boutte")
    assert kayshon["current_nfl_team"] == "HOU" and kayshon["consensus_source_team"] == "NE"

    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        "artifactType": "player-truth",
        "artifactId": "player-truth-step14-2026",
        "artifactVersion": ARTIFACT_VERSION,
        "generatedAt": GENERATED_AT,
        "effectiveAt": GENERATED_AT,
        "expiresAt": None,
        "status": "validated",
        "season": 2026,
        "integrity": {
            "canonicalization": "draft-command-canonical-json-v1",
            "payloadSha256": "0" * 64,
        },
        "provenance": {
            "modelVersion": ARTIFACT_VERSION,
            "generator": "fantasy-draft/research/step14/build_player_truth_step14.py",
            "sourceCommits": [STEP13B_COMMIT, CONSENSUS_COMMIT],
            "sourceArtifactIds": [
                CONSENSUS_ARTIFACT_ID,
                "STEP14_CANDIDATE_REGISTRY_ENRICHED_v1",
                "NEGATIVE_FINDINGS_AND_QUARANTINES_v1",
                "CURRENT_2026_PLAYER_IDENTITY_STATUS_TRUTH_v1",
            ],
        },
        "players": runtime_players,
    }
    artifact["integrity"]["payloadSha256"] = payload_sha256(artifact)
    write_json(output_dir / "player_truth_step14.json", artifact)

    detail = {
        "schema_version": "1.0.0",
        "artifact_id": "player-truth-step14-detail-2026",
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": GENERATED_AT,
        "season": 2026,
        "row_count": len(detail_players),
        "baseline_policy": {
            "universal_full_season_p50_field": "standardized_full_ppr_points",
            "consensus_artifact_id": CONSENSUS_ARTIFACT_ID,
            "join_key": "canonical_name + position",
            "blank_is_missing": True,
            "explicit_zero_is_zero": True,
            "rejected_august_31_page_capture_used": False,
            "market_substitution_used": False,
        },
        "head_separation": {
            "full_season_points": "approved frozen consensus standardized_full_ppr_points",
            "ppg": "separate schedule-normalized center, consensus / 17",
            "expected_games": "separate 17-game schedule baseline; no numeric candidate adjustment",
            "event_probabilities": "null unless a calibrated 2026 output is available; none was available",
        },
        "players": detail_players,
    }
    write_json(output_dir / "player_truth_step14_detail.json", detail)
    write_json(output_dir / "player_truth_step14_candidate_decisions.json", candidates)
    shutil.copyfile(input_dir / "NEGATIVE_FINDINGS_AND_QUARANTINES_v1.json", output_dir / "player_truth_step14_negative_registry.json")
    shutil.copyfile(input_dir / "JOSH_JACOBS_COMMISSIONER_EXEMPT_OVERLAY_v1.json", output_dir / "player_truth_step14_josh_jacobs_invariant.json")

    with (output_dir / "player_truth_step14_identity_reconciliation.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(reconciliation_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(reconciliation_rows)

    unresolved_identities = [
        {
            "internal_player_id": row["draft_command_internal_id"],
            "display_name": row["display_name"],
            "position": row["position"],
            "team": row["current_nfl_team"],
            "reason": "NO_STEP13B_STABLE_IDENTITY_CROSSWALK_ROW",
            "runtime_identity_method": "unresolved",
            "fallback_identity_invented": False,
        }
        for row in detail_players
        if row["identity"]["method"] == "unresolved"
    ]
    unresolved_queue = {
        "schema_version": "1.0.0",
        "unresolved_identity_count": len(unresolved_identities),
        "unresolved_projection_count": 1,
        "identity_records": unresolved_identities,
        "projection_records": missing_players,
        "note": "Keenan Allen has a resolved stable identity but no approved consensus projection; he is not an identity failure.",
    }
    write_json(output_dir / "player_truth_step14_unresolved_identity_queue.json", unresolved_queue)
    write_json(
        output_dir / "player_truth_step14_current_status_overlay.json",
        {
            "schema_version": "1.0.0",
            "row_count": len(status_rows),
            "missing_value_policy": "null means unknown/not present; never zero-filled",
            "rows": status_rows,
        },
    )

    position_counts = Counter(row["position"] for row in runtime_players)
    board_position_counts = Counter(row["pos"] for row in board)
    top160_covered = len([row for row in runtime_players if row["draftCommandBoardRank"] <= 160])
    coverage = {
        "schema_version": "1.0.0",
        "draft_command_player_count": len(board),
        "player_truth_row_count": len(runtime_players),
        "overall_coverage_count": len(runtime_players),
        "overall_coverage_fraction": len(runtime_players) / len(board),
        "top_160_expected_count": 160,
        "top_160_coverage_count": top160_covered,
        "top_160_coverage_fraction": top160_covered / 160,
        "sole_documented_exception": missing_players[0],
        "position_coverage": {
            position: {
                "expected": board_position_counts[position],
                "covered": position_counts[position],
                "fraction": position_counts[position] / board_position_counts[position],
            }
            for position in ("QB", "RB", "WR", "TE")
        },
        "identity": {
            "stable_identity_count": len(runtime_players),
            "espn_id_count": sum(row["espnPlayerId"] is not None for row in runtime_players),
            "unresolved_identity_count": len(unresolved_identities),
            "team_conflict_count": sum(row["team_conflict_preserved"] for row in detail_players),
            "team_conflicts": [
                {
                    "internal_player_id": row["draft_command_internal_id"],
                    "display_name": row["display_name"],
                    "current_team": row["current_nfl_team"],
                    "consensus_source_team": row["consensus_source_team"],
                }
                for row in detail_players
                if row["team_conflict_preserved"]
            ],
        },
        "field_coverage": {
            "full_season_p50": {"nonnull": len(runtime_players), "null": 0},
            "ppr_ppg_p50": {"nonnull": len(runtime_players), "null": 0},
            "expected_games_p50": {"nonnull": len(runtime_players), "null": 0},
            "p10": {"nonnull": 0, "null": len(runtime_players)},
            "p90": {"nonnull": 0, "null": len(runtime_players)},
            "elite_probability": {"nonnull": 0, "null": len(runtime_players)},
            "starter_probability": {"nonnull": 0, "null": len(runtime_players)},
            "bust_probability": {"nonnull": 0, "null": len(runtime_players)},
            "availability_bust_probability": {"nonnull": 0, "null": len(runtime_players)},
            "espn_id": {
                "nonnull": sum(row["espnPlayerId"] is not None for row in runtime_players),
                "null": sum(row["espnPlayerId"] is None for row in runtime_players),
            },
        },
    }
    write_json(output_dir / "player_truth_step14_coverage_report.json", coverage)
    write_json(
        output_dir / "player_truth_step14_missing_players.json",
        {
            "schema_version": "1.0.0",
            "missing_player_count": len(missing_players),
            "fallback_projection_count": 0,
            "records": missing_players,
        },
    )

    calibration_report = {
        "schema_version": "1.0.0",
        "candidate_count": 13,
        "approved_exact_scope_signal_count": 12,
        "rejected_step14_calibration_count": 1,
        "rejected_candidate": CALIBRATION_REJECTION,
        "rejected_candidate_calibration": next(
            item["calibration_metrics"] for item in candidates["decisions"] if item["candidate_id"] == CALIBRATION_REJECTION
        ),
        "runtime_probability_outputs_emitted": 0,
        "uncertainty_policy": "Historical bootstrap evidence is preserved by candidate; no P10/P90 or event probability is manufactured.",
        "candidate_uncertainty": [
            {
                "candidate_id": item["candidate_id"],
                "decision": item["decision"],
                "bootstrap_ci_low": item["bootstrap_ci_low"],
                "bootstrap_ci_high": item["bootstrap_ci_high"],
                "bootstrap_probability_of_improvement": item["bootstrap_probability_of_improvement"],
                "calibration_metrics": item["calibration_metrics"],
            }
            for item in candidates["decisions"]
        ],
    }
    write_json(output_dir / "player_truth_step14_calibration_uncertainty.json", calibration_report)

    dictionary = {
        "schema_version": "1.0.0",
        "runtime_schema": "fantasy-draft/contracts/player_truth.schema.json",
        "runtime_artifact": "player_truth_step14.json",
        "detail_artifact": "player_truth_step14_detail.json",
        "null_policy": "Null means unavailable/not defensibly produced; null is never converted to numeric zero.",
        "fields": {
            "projectedFullPprPoints": "Frozen consensus standardized_full_ppr_points; universal full-season center.",
            "projectedPpg": "Separate schedule-normalized PPG center: standardized_full_ppr_points / 17.",
            "expectedGames": "Unadjusted 17-game schedule baseline; not an injury-adjusted model output.",
            "fullPprPointsP50": "Same frozen consensus center as projectedFullPprPoints.",
            "fullPprPointsP10/fullPprPointsP90": "Null because no approved distribution bounds are available.",
            "eliteProbability/starterProbability/bustProbability": "Null because no calibrated 2026 probability output is available.",
            "availabilityStatus": "Current overlay enum; unknown when no overlay is present.",
            "modelConfidence": "Transparent source-governance confidence grade, not an outcome probability.",
            "eligibleFeatureFamilies": "Step 14-approved exact position/target signal scopes; no numeric contribution implied.",
            "quarantinedFeatureFamilies": "Binding mechanism, H_ALL, and incomplete scopes excluded from live numeric use.",
        },
    }
    write_json(output_dir / "player_truth_step14_schema_and_dictionary.json", dictionary)

    source_manifest = {
        "schema_version": "1.0.0",
        "generated_at": GENERATED_AT,
        "sources": [
            {
                "id": CONSENSUS_ARTIFACT_ID,
                "commit": CONSENSUS_COMMIT,
                "tree": CONSENSUS_TREE,
                "path": str(CONSENSUS_RELATIVE_DIR / CONSENSUS_FILENAME),
                "sha256": CONSENSUS_CSV_SHA256,
                "universal_center_field": "standardized_full_ppr_points",
            },
            {
                "id": "STEP14_CANDIDATE_REGISTRY_ENRICHED_v1",
                "commit": STEP13B_COMMIT,
                "path": "research/step14/inputs/STEP14_CANDIDATE_REGISTRY_ENRICHED_v1.json",
                "sha256": sha256(input_dir / "STEP14_CANDIDATE_REGISTRY_ENRICHED_v1.json"),
            },
            {
                "id": "NEGATIVE_FINDINGS_AND_QUARANTINES_v1",
                "commit": STEP13B_COMMIT,
                "path": "research/step14/inputs/NEGATIVE_FINDINGS_AND_QUARANTINES_v1.json",
                "sha256": sha256(input_dir / "NEGATIVE_FINDINGS_AND_QUARANTINES_v1.json"),
            },
            {
                "id": "CURRENT_2026_PLAYER_IDENTITY_STATUS_TRUTH_v1",
                "commit": STEP13B_COMMIT,
                "path": "research/step14/inputs/CURRENT_2026_PLAYER_IDENTITY_STATUS_TRUTH_v1.csv",
                "sha256": sha256(input_dir / "CURRENT_2026_PLAYER_IDENTITY_STATUS_TRUTH_v1.csv"),
            },
            {
                "id": "JOSH_JACOBS_COMMISSIONER_EXEMPT_OVERLAY_v1",
                "commit": STEP13B_COMMIT,
                "path": "research/step14/inputs/JOSH_JACOBS_COMMISSIONER_EXEMPT_OVERLAY_v1.json",
                "sha256": sha256(input_dir / "JOSH_JACOBS_COMMISSIONER_EXEMPT_OVERLAY_v1.json"),
            },
        ],
        "rejected_sources": [
            {
                "id": "2026-08-31-fantasypros-direct-page-capture",
                "reason": "incomplete 40-row capture; not blended, substituted, or used",
            }
        ],
    }
    write_json(output_dir / "player_truth_step14_source_manifest.json", source_manifest)

    validation = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "checks": {
            "step13b_invariants_preserved": True,
            "consensus_checksum_gate": True,
            "canonical_name_position_join": True,
            "runtime_player_count": len(runtime_players),
            "sole_missing_player_is_keenan_allen": True,
            "josh_jacobs_consensus_unadjusted_256_850": True,
            "josh_jacobs_games_adjustment_null": True,
            "kayshon_boutte_team_conflict_preserved": True,
            "h_all_rejected_rows_preserved": len(h_all) == 28,
            "contextual_rows_preserved": len(contextual) == 5,
            "mechanism_quarantine_rows_preserved": len(quarantined) == 5,
            "rejected_rows_preserved": negative_registry["counts"]["rejected"] == 117,
            "production_weights_promoted": 0,
            "prohibited_market_substitution": False,
            "missing_values_zero_filled": False,
        },
    }
    write_json(output_dir / "player_truth_step14_validation.json", validation)
    runtime_conformance = {
        "schema_version": "1.0.0",
        "player_truth_contract_status": "PASS_PENDING_EXECUTABLE_VALIDATION_REPORT",
        "artifact_path": "fantasy-draft/data/candidate/player-truth/player_truth_step14.json",
        "full_bundle_status": "BLOCKED_ON_OTHER_PRODUCERS_NOT_STEP14",
        "remaining_inputs": [
            "fantasy-draft/data/candidate/espn-market/espn_market_frozen.json",
            "fantasy-draft/data/candidate/league-value/espn_league_value_step15.json",
            "fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json",
        ],
        "top_160_exception": {
            "internal_player_id": 143,
            "display_name": "Keenan Allen",
            "runtime_harness_approval_flag_applicable": False,
            "note": "This is an absent projection row with resolved identity, not an unresolved row inside Player Truth. Do not add a synthetic row or pass an inapplicable identity-gap flag.",
        },
    }
    write_json(output_dir / "player_truth_step14_runtime_conformance.json", runtime_conformance)

    reproduction = """# Step 14 / 2026 Player Truth deterministic reproduction

Run from `fantasy-draft` at the committed Step 14 head:

```bash
python3 research/step14/build_player_truth_step14.py
python3 research/step14/validate_player_truth_step14.py
python3 -m unittest discover -s tests/step14 -p 'test_*.py'
```

The build refuses to run unless the canonical consensus CSV and its `SHA256SUMS`
ledger have the approved hashes. It joins by normalized `canonical_name + position`,
never by rank/ADP, and emits the fixed source capture time for byte reproducibility.
"""
    (output_dir / "REPRODUCTION.md").write_text(reproduction, encoding="utf-8")

    report_lines = [
        "# Step 14 / 2026 Player Truth Report",
        "",
        f"Generated: `{GENERATED_AT}`",
        f"Runtime rows: **{len(runtime_players)} / {len(board)}**",
        f"Top-160 coverage: **{top160_covered} / 160**",
        "",
        "The frozen consensus `standardized_full_ppr_points` field remains the universal full-season P50. "
        "No ESPN rank, ADP, ECR, auction value, or incomplete August 31 page capture was substituted.",
        "",
        "## Candidate decisions",
        "",
        "| Candidate | Exact scope | Decision |",
        "| --- | --- | --- |",
    ]
    for item in candidates["decisions"]:
        report_lines.append(
            f"| `{item['candidate_id']}` | {item['position']} / {item['target']} / {item['feature_family']} | {item['decision']} |"
        )
    report_lines.extend(
        [
            "",
            "Twelve signals are admitted only for their exact tested scopes. No numeric 2026 contribution is applied because "
            "the handoff contains neither an audited current-season candidate feature matrix nor approved full-fit production weights. "
            "The QB bust/combine candidate remains rejected at Step 14 because ECE worsened.",
            "",
            "## Binding exclusions",
            "",
            "`H_ALL` remains rejected (28 binding rows). The package preserves 5 contextual, 5 mechanism-quarantined, "
            "117 rejected, and 1 incomplete record. No Step 13B production weight is created.",
            "",
            "## Named invariants",
            "",
            "- Keenan Allen (Draft Command ID 143) is the sole missing projection and is omitted; no fallback was invented.",
            "- Kayshon Boutte retains current team HOU and frozen-consensus source team NE as an explicit provenance conflict.",
            "- Josh Jacobs remains COMMISSIONER_EXEMPT; full-season P50 is unadjusted 256.850, expected-games adjustment is null, and return week remains unknown pending NFL review.",
            "",
            "## Runtime boundary",
            "",
            "The Player Truth artifact is self-contained and contract-valid. Full four-artifact runtime validation remains "
            "blocked on the independent ESPN market, thin Step 15 League Value adapter, and Opponent Intent inputs.",
            "",
        ]
    )
    (report_dir / "STEP14_2026_PLAYER_TRUTH_REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")

    # The proof states the deterministic policy. Tests independently rebuild in a
    # temporary directory and compare every generated byte except this proof and
    # the final manifests, which incorporate generated hashes.
    write_json(
        output_dir / "deterministic_build_proof.json",
        {
            "schema_version": "1.0.0",
            "deterministic": True,
            "fixed_generated_at": GENERATED_AT,
            "canonical_input_sha256": CONSENSUS_CSV_SHA256,
            "generator": "research/step14/build_player_truth_step14.py",
            "verification_command": "python3 -m unittest discover -s tests/step14 -p 'test_*.py'",
        },
    )

    hashed_names = [name for name in OUTPUT_FILES if name not in {"SHA256SUMS", "player_truth_step14_manifest.json"}]
    artifact_entries = []
    for name in hashed_names:
        path = output_dir / name
        artifact_entries.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    artifact_entries.append(
        {
            "path": "../../../reports/STEP14_2026_PLAYER_TRUTH_REPORT.md",
            "bytes": (report_dir / "STEP14_2026_PLAYER_TRUTH_REPORT.md").stat().st_size,
            "sha256": sha256(report_dir / "STEP14_2026_PLAYER_TRUTH_REPORT.md"),
        }
    )
    manifest = {
        "schema_version": "1.0.0",
        "artifact_id": "player-truth-step14-package-2026",
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": GENERATED_AT,
        "row_count": len(runtime_players),
        "source_commits": [STEP13B_COMMIT, CONSENSUS_COMMIT],
        "artifacts": artifact_entries,
    }
    write_json(output_dir / "player_truth_step14_manifest.json", manifest)

    checksum_paths = sorted(
        [output_dir / name for name in OUTPUT_FILES if name != "SHA256SUMS"]
        + [report_dir / "STEP14_2026_PLAYER_TRUTH_REPORT.md"],
        key=lambda path: str(path),
    )
    checksum_lines = []
    for path in checksum_paths:
        if path.parent == output_dir:
            label = path.name
        else:
            label = "../../../reports/STEP14_2026_PLAYER_TRUTH_REPORT.md"
        checksum_lines.append(f"{sha256(path)}  {label}")
    (output_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = (args.output_dir or repo_root / "data/candidate/player-truth").resolve()
    report_dir = (args.report_dir or repo_root / "reports").resolve()
    build(repo_root, output_dir, report_dir)
    print(output_dir / "player_truth_step14.json")


if __name__ == "__main__":
    main()
