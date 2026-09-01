#!/usr/bin/env python3
"""Validate the four Draft Command source artifacts without building a bundle."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from runtime_contract_lib import (
    parse_datetime,
    public_validation_result,
    validate_contract_set,
    validation_report_markdown,
)


def path_or_none(value: str | None) -> Path | None:
    return Path(value).resolve() if value else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-truth", help="Path to the Step 13B/14 Player Truth JSON artifact")
    parser.add_argument("--espn-market", help="Path to the frozen ESPN market JSON artifact")
    parser.add_argument("--league-value", help="Path to the thin Step 15 League Value JSON artifact")
    parser.add_argument("--opponent-intent", help="Path to the streamlined Opponent Intent JSON artifact")
    parser.add_argument("--contracts-dir", default=str(Path(__file__).resolve().parents[1] / "contracts"))
    parser.add_argument("--as-of", required=True, help="RFC 3339 validation time; required for reproducible stale-artifact gates")
    parser.add_argument("--allow-missing-espn-market", action="store_true", help="Permit a degraded manual-board bundle without ESPN market")
    parser.add_argument("--allow-missing-opponent-intent", action="store_true", help="Permit a degraded bundle with threat predictions disabled")
    parser.add_argument("--approve-top160-identity-gap", type=int, action="append", default=[], metavar="INTERNAL_ID")
    parser.add_argument("--report", help="Optional deterministic Markdown report path")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable validation result")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    as_of = parse_datetime(args.as_of)
    if as_of is None:
        print("--as-of must be an RFC 3339 date-time with a timezone", file=sys.stderr)
        return 2
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
    )
    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(validation_report_markdown(result), encoding="utf-8")
    if args.json:
        print(json.dumps(public_validation_result(result), sort_keys=True, indent=2))
    else:
        status = "PASS" if result["promotionEligible"] else "FAIL"
        counts = result["issueCounts"]
        print(f"{status}: {counts['BLOCKING']} blocking, {counts['WARNING']} warnings, {counts['INFO']} info")
        for issue in result["issues"]:
            print(f"{issue.severity} {issue.code} {issue.artifact} {issue.path}: {issue.message}")
    return 0 if result["promotionEligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
