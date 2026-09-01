#!/usr/bin/env python3
"""Build a deterministic, browser-ready Draft Command runtime bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from runtime_contract_lib import (
    Issue,
    assemble_runtime_bundle,
    canonical_pretty_bytes,
    count_issues,
    parse_datetime,
    public_validation_result,
    sha256_bytes,
    strict_json_load,
    validate_contract_set,
    validate_runtime_bundle,
    validation_report_markdown,
)


def path_or_none(value: str | None) -> Path | None:
    return Path(value).resolve() if value else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-truth", required=True)
    parser.add_argument("--espn-market")
    parser.add_argument("--league-value", required=True)
    parser.add_argument("--opponent-intent")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--contracts-dir", default=str(Path(__file__).resolve().parents[1] / "contracts"))
    parser.add_argument("--as-of", required=True, help="RFC 3339 validation time; required for deterministic stale-artifact gates")
    parser.add_argument("--allow-missing-espn-market", action="store_true")
    parser.add_argument("--allow-missing-opponent-intent", action="store_true")
    parser.add_argument("--approve-top160-identity-gap", type=int, action="append", default=[], metavar="INTERNAL_ID")
    parser.add_argument(
        "--approve-missing-projection",
        type=int,
        action="append",
        default=[],
        metavar="INTERNAL_ID",
        help="Approve a resolved market-only identity to remain without Player Truth or League Value",
    )
    parser.add_argument("--bundle-filename", default="draft_runtime_bundle.json")
    parser.add_argument("--manifest-filename", default="draft_runtime_bundle_manifest.json")
    parser.add_argument("--report-filename", default="draft_runtime_bundle_validation.md")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def ensure_not_frozen(path: Path) -> None:
    if not path.exists():
        return
    try:
        existing = strict_json_load(path)
    except Exception:
        return
    if isinstance(existing, dict) and existing.get("status") == "frozen":
        raise RuntimeError(f"refusing to overwrite frozen artifact: {path}")


def main() -> int:
    args = parse_args()
    as_of = parse_datetime(args.as_of)
    if as_of is None:
        print("--as-of must be an RFC 3339 date-time with a timezone", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir).resolve()
    bundle_path = output_dir / args.bundle_filename
    manifest_path = output_dir / args.manifest_filename
    report_path = output_dir / args.report_filename
    try:
        for path in (bundle_path, manifest_path):
            ensure_not_frozen(path)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    result = validate_contract_set(
        contracts_dir=Path(args.contracts_dir).resolve(),
        player_truth_path=path_or_none(args.player_truth),
        espn_market_path=path_or_none(args.espn_market),
        league_value_path=path_or_none(args.league_value),
        opponent_intent_path=path_or_none(args.opponent_intent),
        as_of=as_of,
        allow_missing_espn_market=args.allow_missing_espn_market,
        allow_missing_opponent_intent=args.allow_missing_opponent_intent,
        approved_top160_ids=set(args.approve_top160_identity_gap),
        approved_missing_projection_ids=set(args.approve_missing_projection),
    )
    if not result["promotionEligible"]:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(validation_report_markdown(result), encoding="utf-8")
        if args.json:
            print(json.dumps(public_validation_result(result), sort_keys=True, indent=2))
        else:
            print(f"REFUSED: {result['issueCounts']['BLOCKING']} blocking gates; report written to {report_path}", file=sys.stderr)
        return 1

    bundle = assemble_runtime_bundle(result)
    runtime_issues = validate_runtime_bundle(bundle, Path(args.contracts_dir).resolve())
    if runtime_issues:
        result["issues"].extend(runtime_issues)
        result["issues"] = sorted(result["issues"], key=lambda issue: (issue.severity, issue.code, issue.path))
        result["issueCounts"] = count_issues(result["issues"])
        result["promotionEligible"] = result["issueCounts"]["BLOCKING"] == 0
    if not result["promotionEligible"]:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(validation_report_markdown(result), encoding="utf-8")
        print(f"REFUSED: assembled runtime bundle failed {result['issueCounts']['BLOCKING']} blocking gates", file=sys.stderr)
        return 1

    bundle_bytes = canonical_pretty_bytes(bundle)
    report_bytes = validation_report_markdown(result).encode("utf-8")
    bundle_hash = sha256_bytes(bundle_bytes)
    report_hash = sha256_bytes(report_bytes)
    manifest = {
        "schemaVersion": "1.0.0",
        "artifactType": "draft-runtime-manifest",
        "bundleVersion": bundle["bundleVersion"],
        "generatedAt": bundle["generatedAt"],
        "status": bundle["status"],
        "promotionEligible": True,
        "canonicalization": "draft-command-canonical-json-v1",
        "inputs": bundle["sourceArtifacts"],
        "outputs": {
            "bundle": {"path": args.bundle_filename, "sha256": bundle_hash, "bytes": len(bundle_bytes)},
            "validationReport": {"path": args.report_filename, "sha256": report_hash, "bytes": len(report_bytes)},
        },
        "coverage": result["coverage"],
        "approvedExceptions": bundle["approvedExceptions"],
        "gates": {
            "result": "pass",
            "blocking": result["issueCounts"]["BLOCKING"],
            "warnings": result["issueCounts"]["WARNING"],
            "informational": result["issueCounts"]["INFO"],
        },
        "determinism": {
            "generationTimeSource": "maximum source artifact generatedAt",
            "bundleVersionSource": "canonical source file hashes and league ID",
            "identicalInputsProduceIdenticalBytes": True,
        },
    }
    manifest_bytes = canonical_pretty_bytes(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path.write_bytes(bundle_bytes)
    report_path.write_bytes(report_bytes)
    manifest_path.write_bytes(manifest_bytes)
    output = {
        "promotionEligible": True,
        "bundle": str(bundle_path),
        "bundleSha256": bundle_hash,
        "manifest": str(manifest_path),
        "manifestSha256": sha256_bytes(manifest_bytes),
        "validationReport": str(report_path),
        "validationReportSha256": report_hash,
        "coverage": result["coverage"],
        "warnings": result["issueCounts"]["WARNING"],
    }
    if args.json:
        print(json.dumps(output, sort_keys=True, indent=2))
    else:
        print(f"PASS: {bundle_path} sha256={bundle_hash}")
        print(f"MANIFEST: {manifest_path} sha256={output['manifestSha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
