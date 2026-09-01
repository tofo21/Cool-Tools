from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "fantasy-draft/research/freeze_consensus_projections_2026.py"
CAPTURE_TAG = "20260901T005951Z"
EXPECTED_CANONICAL_SHA256 = (
    "8ab2386145f49cf2a44bc0c5667400e68e8bb49b4d63d15f0d416d7bd1d742c6"
)


class ConsensusProjectionFreeze2026Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="consensus-freeze-test-")
        cls.output_root = Path(cls.temp_dir.name) / "bundle"
        subprocess.run(
            [sys.executable, str(SCRIPT), "--output-root", str(cls.output_root)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.canonical_path = (
            cls.output_root
            / f"current_2026_consensus_components_{CAPTURE_TAG}.csv"
        )
        with cls.canonical_path.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_canonical_hash_and_row_counts(self) -> None:
        digest = hashlib.sha256(self.canonical_path.read_bytes()).hexdigest()
        self.assertEqual(digest, EXPECTED_CANONICAL_SHA256)
        self.assertEqual(len(self.rows), 520)
        self.assertEqual(
            Counter(row["position"] for row in self.rows),
            {"QB": 81, "RB": 131, "WR": 190, "TE": 118},
        )

    def test_unique_qb_rb_wr_te_records_and_no_market_substitution(self) -> None:
        self.assertEqual(
            len({(row["canonical_name"], row["position"]) for row in self.rows}),
            520,
        )
        self.assertEqual(
            {row["position"] for row in self.rows}, {"QB", "RB", "WR", "TE"}
        )
        self.assertFalse(
            any(
                "rank" in field.lower() or "adp" in field.lower()
                for field in self.rows[0]
            )
        )

    def test_josh_jacobs_is_source_preserved_and_unadjusted(self) -> None:
        josh = [row for row in self.rows if row["source_name"] == "Josh Jacobs"]
        self.assertEqual(len(josh), 1)
        self.assertEqual(
            {
                "nfl_team": josh[0]["nfl_team"],
                "rushing_attempts": josh[0]["rushing_attempts"],
                "rushing_yards": josh[0]["rushing_yards"],
                "rushing_touchdowns": josh[0]["rushing_touchdowns"],
                "receptions": josh[0]["receptions"],
                "receiving_yards": josh[0]["receiving_yards"],
                "receiving_touchdowns": josh[0]["receiving_touchdowns"],
                "fumbles_lost": josh[0]["fumbles_lost"],
                "source_provided_fantasy_points": josh[0][
                    "source_provided_fantasy_points"
                ],
                "standardized_full_ppr_points": josh[0][
                    "standardized_full_ppr_points"
                ],
            },
            {
                "nfl_team": "GB",
                "rushing_attempts": "288.8",
                "rushing_yards": "1161.6",
                "rushing_touchdowns": "12.0",
                "receptions": "35.7",
                "receiving_yards": "283.9",
                "receiving_touchdowns": "1.2",
                "fumbles_lost": "1.3",
                "source_provided_fantasy_points": "239.1",
                "standardized_full_ppr_points": "256.850",
            },
        )

    def test_validation_coverage_and_determinism(self) -> None:
        validation = json.loads(
            (
                self.output_root / f"validation_report_{CAPTURE_TAG}.json"
            ).read_text(encoding="utf-8")
        )
        proof = json.loads(
            (self.output_root / "deterministic_build_proof.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(validation["overall_status"], "PASS")
        self.assertEqual(validation["coverage"]["overall_pct"], "99.50")
        self.assertEqual(validation["coverage"]["top_100_pct"], "100.00")
        self.assertEqual(validation["coverage"]["board_gap_count"], 1)
        self.assertEqual(validation["coverage"]["board_gaps"][0]["name"], "Keenan Allen")
        self.assertTrue(proof["build_a_equals_build_b"])
        self.assertTrue(proof["byte_identical"])
        self.assertEqual(proof["compared_file_count"], 18)

    def test_standardized_full_ppr_reconciles_from_components(self) -> None:
        weights = {
            "passing_yards": Decimal("0.04"),
            "passing_touchdowns": Decimal("4"),
            "interceptions": Decimal("-2"),
            "rushing_yards": Decimal("0.10"),
            "rushing_touchdowns": Decimal("6"),
            "receptions": Decimal("1"),
            "receiving_yards": Decimal("0.10"),
            "receiving_touchdowns": Decimal("6"),
            "fumbles_lost": Decimal("-2"),
        }
        scoring_fields = {
            "QB": [
                "passing_yards",
                "passing_touchdowns",
                "interceptions",
                "rushing_yards",
                "rushing_touchdowns",
                "fumbles_lost",
            ],
            "RB": [
                "rushing_yards",
                "rushing_touchdowns",
                "receptions",
                "receiving_yards",
                "receiving_touchdowns",
                "fumbles_lost",
            ],
            "WR": [
                "rushing_yards",
                "rushing_touchdowns",
                "receptions",
                "receiving_yards",
                "receiving_touchdowns",
                "fumbles_lost",
            ],
            "TE": [
                "receptions",
                "receiving_yards",
                "receiving_touchdowns",
                "fumbles_lost",
            ],
        }
        for row in self.rows:
            recalculated = sum(
                Decimal(row[field]) * weights[field]
                for field in scoring_fields[row["position"]]
            )
            self.assertEqual(
                recalculated.quantize(Decimal("0.001")),
                Decimal(row["standardized_full_ppr_points"]),
                row["canonical_name"],
            )


if __name__ == "__main__":
    unittest.main()
