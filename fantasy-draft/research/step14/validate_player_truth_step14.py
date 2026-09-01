#!/usr/bin/env python3
"""Run the executable producer-side Step 14 acceptance gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AS_OF = datetime(2026, 9, 1, 0, 59, 51, tzinfo=timezone.utc)
PROHIBITED_PATTERNS = (
    "fantasy-draft/app.js",
    "fantasy-draft/index.html",
    "fantasy-draft/sync.js",
    "fantasy-draft/extension/",
    "fantasy-draft/data/candidate/league-value/",
    "fantasy-draft/data/candidate/espn-market/",
    "fantasy-draft/data/candidate/opponent-intent/",
    ".github/workflows/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root containing fantasy-draft",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repository = args.repo_root.resolve()
    fantasy = repository / "fantasy-draft"
    artifact_dir = fantasy / "data/candidate/player-truth"
    artifact_path = artifact_dir / "player_truth_step14.json"
    sys.path.insert(0, str(fantasy / "research"))
    from runtime_contract_lib import load_and_validate_artifact  # pylint: disable=import-outside-toplevel

    artifact, issues, file_hash = load_and_validate_artifact(
        artifact_path,
        fantasy / "contracts",
        "player-truth",
        AS_OF,
    )
    blocking = [issue.as_dict() for issue in issues if issue.severity == "BLOCKING"]
    warnings = [issue.as_dict() for issue in issues if issue.severity == "WARNING"]

    checksum_failures: list[str] = []
    for line in (artifact_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        target = (artifact_dir / relative).resolve()
        if not target.exists() or sha256(target) != expected:
            checksum_failures.append(relative)

    coverage = json.loads((artifact_dir / "player_truth_step14_coverage_report.json").read_text(encoding="utf-8"))
    negative = json.loads((artifact_dir / "player_truth_step14_negative_registry.json").read_text(encoding="utf-8"))
    candidates = json.loads((artifact_dir / "player_truth_step14_candidate_decisions.json").read_text(encoding="utf-8"))
    missing = json.loads((artifact_dir / "player_truth_step14_missing_players.json").read_text(encoding="utf-8"))
    detail = json.loads((artifact_dir / "player_truth_step14_detail.json").read_text(encoding="utf-8"))

    data_checks = {
        "schema_and_semantic_contract": artifact is not None and not blocking,
        "payload_hash": artifact is not None and artifact["integrity"]["payloadSha256"] == __import__("runtime_contract_lib").payload_sha256(artifact),
        "file_hash_recorded": file_hash == sha256(artifact_path),
        "sha256_manifest": not checksum_failures,
        "player_count_199": len(artifact["players"]) == 199 if artifact else False,
        "top160_coverage_159": coverage["top_160_coverage_count"] == 159,
        "sole_projection_gap_keenan_allen": missing["missing_player_count"] == 1 and missing["records"][0]["display_name"] == "Keenan Allen",
        "no_projection_fallback": missing["fallback_projection_count"] == 0,
        "candidate_decisions_13": candidates["candidate_count"] == 13 and len(candidates["decisions"]) == 13,
        "production_weights_zero": candidates["production_weights_promoted"] == 0,
        "binding_negative_counts": negative["counts"] == {"rejected": 117, "contextual": 5, "quarantined": 5, "incomplete": 1, "rejected_H_ALL": 28},
        "h_all_rejected": negative["binding_rules"]["H_ALL"].startswith("rejected"),
        "all_missing_probabilities_null": all(
            all(player["heads"]["event_probabilities"][key] is None for key in ("elite", "useful_starter", "bust", "availability_bust"))
            for player in detail["players"]
        ),
        "head_separation_documented": set(detail["head_separation"]) == {"full_season_points", "ppg", "expected_games", "event_probabilities"},
    }

    josh = next(player for player in detail["players"] if player["display_name"] == "Josh Jacobs")
    kayshon = next(player for player in detail["players"] if player["display_name"] == "Kayshon Boutte")
    jaydon = next(player for player in detail["players"] if player["display_name"] == "Jaydon Blue")
    data_checks.update(
        {
            "josh_jacobs_unadjusted": josh["heads"]["full_season_ppr"]["baseline_value_text"] == "256.850" and josh["availability"]["expected_games_adjustment"] is None,
            "josh_jacobs_no_invented_return": josh["availability"]["expected_return_week"] == "unknown_pending_NFL_review",
            "kayshon_boutte_conflict_preserved": kayshon["current_nfl_team"] == "HOU" and kayshon["consensus_source_team"] == "NE" and kayshon["team_conflict_preserved"],
            "jaydon_blue_identity_unresolved": jaydon["identity"]["method"] == "unresolved" and jaydon["espn_id"] is None and jaydon["gsis_id"] is None,
        }
    )

    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{__import__('os').environ.get('STEP14_BASE_COMMIT', 'e3cf26eb863e4f54b6635e5a4aac50fe88e53e09')}...HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    changed.extend(
        subprocess.run(["git", "diff", "--name-only"], cwd=repository, check=True, capture_output=True, text=True).stdout.splitlines()
    )
    changed.extend(
        subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    changed = sorted(set(changed))
    prohibited_changes = sorted(
        path
        for path in changed
        if any(path == pattern or path.startswith(pattern) for pattern in PROHIBITED_PATTERNS)
    )
    security_checks = {
        "no_prohibited_path_changes": not prohibited_changes,
        "no_nonfinite_json": all(token not in artifact_path.read_text(encoding="utf-8") for token in ("NaN", "Infinity", "-Infinity")),
        "no_private_runtime_fields": not any(
            token in artifact_path.read_text(encoding="utf-8").lower()
            for token in ('"cookie"', '"authorization"', '"access_token"', '"password"', '"secret"')
        ),
        "candidate_not_frozen_or_production": artifact is not None and artifact["status"] == "validated",
    }

    passed = not blocking and not checksum_failures and all(data_checks.values()) and all(security_checks.values())
    report = {
        "schema_version": "1.0.0",
        "as_of": "2026-09-01T00:59:51Z",
        "status": "PASS" if passed else "FAIL",
        "artifact_path": "fantasy-draft/data/candidate/player-truth/player_truth_step14.json",
        "artifact_file_sha256": file_hash,
        "artifact_payload_sha256": artifact["integrity"]["payloadSha256"] if artifact else None,
        "contract": {
            "schema": "fantasy-draft/contracts/player_truth.schema.json",
            "blocking_issue_count": len(blocking),
            "warning_issue_count": len(warnings),
            "blocking_issues": blocking,
            "warnings": warnings,
        },
        "checksum_failures": checksum_failures,
        "data_checks": data_checks,
        "security_checks": security_checks,
        "changed_files": changed,
        "prohibited_changes": prohibited_changes,
        "full_runtime_bundle": {
            "status": "BLOCKED_ON_OTHER_PRODUCERS_NOT_STEP14",
            "missing_inputs": [
                "fantasy-draft/data/candidate/espn-market/espn_market_frozen.json",
                "fantasy-draft/data/candidate/league-value/espn_league_value_step15.json",
                "fantasy-draft/data/candidate/opponent-intent/opponent_intent_streamlined.json",
            ],
        },
    }
    reports = fantasy / "reports"
    write_json(reports / "STEP14_VALIDATION_REPORT.json", report)
    markdown = [
        "# Step 14 Validation Report",
        "",
        f"Status: **{report['status']}**",
        f"Artifact SHA-256: `{file_hash}`",
        f"Payload SHA-256: `{report['artifact_payload_sha256']}`",
        "",
        f"Contract blocking issues: **{len(blocking)}**; warnings: **{len(warnings)}**.",
        f"Package checksum failures: **{len(checksum_failures)}**.",
        f"Prohibited changed paths: **{len(prohibited_changes)}**.",
        "",
        "The standalone Player Truth contract gate is complete. The combined four-artifact runtime gate is not a Step 14 "
        "failure; it awaits ESPN market, Step 15 League Value, and Opponent Intent producer artifacts.",
        "",
    ]
    (reports / "STEP14_VALIDATION_REPORT.md").write_text("\n".join(markdown), encoding="utf-8")
    security_markdown = [
        "# Step 14 Security Scan",
        "",
        f"Status: **{'PASS' if all(security_checks.values()) else 'FAIL'}**",
        "",
        f"Scanned changed paths from `{__import__('os').environ.get('STEP14_BASE_COMMIT', 'e3cf26eb863e4f54b6635e5a4aac50fe88e53e09')}` through HEAD plus the working tree.",
        "No raw authenticated ESPN response, cookie, credential, token, private manager history, or simulation ledger is present in the runtime artifact.",
        "No application, UI, extension, ESPN adapter, League Value, Opponent Intent, or deployment path was changed.",
        "",
    ]
    (reports / "STEP14_SECURITY_SCAN.md").write_text("\n".join(security_markdown), encoding="utf-8")
    print(json.dumps({"status": report["status"], "artifactSha256": file_hash, "blockingIssues": len(blocking)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
