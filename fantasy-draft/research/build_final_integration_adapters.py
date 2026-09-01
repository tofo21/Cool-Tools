#!/usr/bin/env python3
"""Build signed ESPN market and dynamic Opponent Intent contract adapters."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from runtime_contract_lib import canonical_pretty_bytes, file_sha256, sha256_bytes, sign_payload


SNAPSHOT_RELATIVE = Path("data/derived/espn_market/espn_2026_market_snapshot_espn_2026_frozen_20260901T003012Z_3379127ab1c0.json")
SNAPSHOT_SHA256 = "e333dfbc3196351ea1b04f6fa8a5525db5903067f38318c8d2a725d6f75bc2a2"
OPPONENT_PACKAGE_RELATIVE = Path("data/opponent-intent-package.js")
OPPONENT_PACKAGE_SHA256 = "c2f25109da2ba5b23e52b8e8cceb8da7736acfaf45a8ac083a9a6b79813c0beb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--node", default="node")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    if file_sha256(project_root / SNAPSHOT_RELATIVE) != SNAPSHOT_SHA256:
        raise SystemExit("Frozen ESPN market snapshot hash mismatch; adapters were not written.")
    if file_sha256(project_root / OPPONENT_PACKAGE_RELATIVE) != OPPONENT_PACKAGE_SHA256:
        raise SystemExit("Opponent Intent runtime package hash mismatch; adapters were not written.")

    node_builder = Path(__file__).with_suffix(".js")
    completed = subprocess.run(
        [args.node, str(node_builder), str(project_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    unsigned = json.loads(completed.stdout)
    espn_market = sign_payload(unsigned["espnMarket"])
    opponent_intent = sign_payload(unsigned["opponentIntent"])

    market_path = project_root / "data/candidate/espn-market/espn_market_frozen.json"
    opponent_path = project_root / "data/candidate/opponent-intent/opponent_intent_streamlined.json"
    market_path.parent.mkdir(parents=True, exist_ok=True)
    opponent_path.parent.mkdir(parents=True, exist_ok=True)
    market_bytes = canonical_pretty_bytes(espn_market)
    opponent_bytes = canonical_pretty_bytes(opponent_intent)
    market_path.write_bytes(market_bytes)
    opponent_path.write_bytes(opponent_bytes)

    manifest = {
        "schemaVersion": "1.0.0",
        "artifactType": "final-integration-adapter-manifest",
        "generator": "fantasy-draft/research/build_final_integration_adapters.py",
        "sourceHashes": {
            str(SNAPSHOT_RELATIVE): SNAPSHOT_SHA256,
            str(OPPONENT_PACKAGE_RELATIVE): OPPONENT_PACKAGE_SHA256,
        },
        "outputs": {
            str(market_path.relative_to(project_root)): {
                "bytes": len(market_bytes),
                "fileSha256": sha256_bytes(market_bytes),
                "payloadSha256": espn_market["integrity"]["payloadSha256"],
            },
            str(opponent_path.relative_to(project_root)): {
                "bytes": len(opponent_bytes),
                "fileSha256": sha256_bytes(opponent_bytes),
                "payloadSha256": opponent_intent["integrity"]["payloadSha256"],
            },
        },
        "determinism": "Identical verified source bytes produce byte-identical adapter outputs.",
    }
    manifest_path = project_root / "data/candidate/runtime-contract/final_integration_adapter_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = canonical_pretty_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    print(json.dumps({
        "espnMarket": manifest["outputs"][str(market_path.relative_to(project_root))],
        "opponentIntent": manifest["outputs"][str(opponent_path.relative_to(project_root))],
        "manifest": {"path": str(manifest_path), "sha256": sha256_bytes(manifest_bytes)},
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
