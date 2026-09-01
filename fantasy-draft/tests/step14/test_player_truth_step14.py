from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


FANTASY = Path(__file__).resolve().parents[2]
REPOSITORY = FANTASY.parent
OUTPUT = FANTASY / "data/candidate/player-truth"
ARTIFACT_PATH = OUTPUT / "player_truth_step14.json"
sys.path.insert(0, str(FANTASY / "research"))

from runtime_contract_lib import load_and_validate_artifact, payload_sha256  # noqa: E402


def load(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Step14PlayerTruthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = load("player_truth_step14.json")
        cls.detail = load("player_truth_step14_detail.json")
        cls.coverage = load("player_truth_step14_coverage_report.json")
        cls.missing = load("player_truth_step14_missing_players.json")
        cls.candidates = load("player_truth_step14_candidate_decisions.json")
        cls.negative = load("player_truth_step14_negative_registry.json")

    def test_01_runtime_contract_and_payload_hash(self):
        _, issues, _ = load_and_validate_artifact(
            ARTIFACT_PATH,
            FANTASY / "contracts",
            "player-truth",
            datetime(2026, 9, 1, 0, 59, 51, tzinfo=timezone.utc),
        )
        self.assertEqual([], [item.as_dict() for item in issues if item.severity == "BLOCKING"])
        self.assertEqual(self.artifact["integrity"]["payloadSha256"], payload_sha256(self.artifact))

    def test_02_consensus_is_universal_center(self):
        self.assertEqual("standardized_full_ppr_points", self.detail["baseline_policy"]["universal_full_season_p50_field"])
        self.assertFalse(self.detail["baseline_policy"]["market_substitution_used"])
        self.assertFalse(self.detail["baseline_policy"]["rejected_august_31_page_capture_used"])
        for runtime, detailed in zip(self.artifact["players"], self.detail["players"], strict=True):
            self.assertEqual(runtime["projectedFullPprPoints"], runtime["fullPprPointsP50"])
            self.assertEqual(runtime["projectedFullPprPoints"], detailed["heads"]["full_season_ppr"]["p50"])

    def test_03_head_separation_and_null_missingness(self):
        self.assertEqual(
            {"full_season_points", "ppg", "expected_games", "event_probabilities"},
            set(self.detail["head_separation"]),
        )
        for player in self.artifact["players"]:
            self.assertIsNone(player["fullPprPointsP10"])
            self.assertIsNone(player["fullPprPointsP90"])
            self.assertIsNone(player["eliteProbability"])
            self.assertIsNone(player["starterProbability"])
            self.assertIsNone(player["bustProbability"])
            self.assertEqual(round(player["projectedFullPprPoints"] / 17, 3), player["projectedPpg"])
            self.assertEqual(17.0, player["expectedGames"])

    def test_04_candidate_decisions_are_exact_scope_and_weightless(self):
        self.assertEqual(13, self.candidates["candidate_count"])
        self.assertEqual(12, self.candidates["decision_counts"]["APPROVE_EXACT_SCOPE_SIGNAL"])
        self.assertEqual(1, self.candidates["decision_counts"]["REJECT_STEP14_CALIBRATION"])
        self.assertEqual(0, self.candidates["production_weights_promoted"])
        for decision in self.candidates["decisions"]:
            self.assertIn(decision["position"], {"QB", "TE"})
            self.assertIsNone(decision["numeric_2026_contribution"])
            self.assertTrue(decision["exact_input_columns"])
            self.assertIn("accepted_fold_hyperparameters", decision["exact_model_configuration_reference"])

    def test_05_binding_negative_registry_is_exact(self):
        self.assertEqual(
            {"rejected": 117, "contextual": 5, "quarantined": 5, "incomplete": 1, "rejected_H_ALL": 28},
            self.negative["counts"],
        )
        self.assertTrue(self.negative["binding_rules"]["H_ALL"].startswith("rejected"))
        self.assertEqual(156, len(self.negative["records"]))

    def test_06_coverage_and_explicit_gaps(self):
        self.assertEqual(199, len(self.artifact["players"]))
        self.assertEqual(199, self.coverage["player_truth_row_count"])
        self.assertEqual(159, self.coverage["top_160_coverage_count"])
        self.assertEqual(1, self.missing["missing_player_count"])
        self.assertEqual(0, self.missing["fallback_projection_count"])
        self.assertEqual("Keenan Allen", self.missing["records"][0]["display_name"])
        self.assertEqual(143, self.missing["records"][0]["internal_player_id"])

    def test_07_named_player_invariants(self):
        josh = next(row for row in self.detail["players"] if row["display_name"] == "Josh Jacobs")
        self.assertEqual("256.850", josh["heads"]["full_season_ppr"]["baseline_value_text"])
        self.assertEqual("COMMISSIONER_EXEMPT", josh["availability"]["source_status"])
        self.assertIsNone(josh["availability"]["expected_games_adjustment"])
        self.assertEqual("unknown_pending_NFL_review", josh["availability"]["expected_return_week"])
        boutte = next(row for row in self.detail["players"] if row["display_name"] == "Kayshon Boutte")
        self.assertEqual(("HOU", "NE", True), (boutte["current_nfl_team"], boutte["consensus_source_team"], boutte["team_conflict_preserved"]))
        blue = next(row for row in self.detail["players"] if row["display_name"] == "Jaydon Blue")
        self.assertEqual("unresolved", blue["identity"]["method"])

    def test_08_sha256_manifest(self):
        for line in (OUTPUT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            target = (OUTPUT / relative).resolve()
            self.assertTrue(target.exists(), relative)
            self.assertEqual(expected, sha256(target), relative)

    def test_09_deterministic_rebuild_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            output = target / "player-truth"
            reports = target / "reports"
            subprocess.run(
                [
                    sys.executable,
                    str(FANTASY / "research/step14/build_player_truth_step14.py"),
                    "--repo-root",
                    str(FANTASY),
                    "--output-dir",
                    str(output),
                    "--report-dir",
                    str(reports),
                ],
                cwd=REPOSITORY,
                check=True,
                capture_output=True,
                text=True,
            )
            for source in sorted(OUTPUT.iterdir()):
                if source.is_file():
                    self.assertEqual(source.read_bytes(), (output / source.name).read_bytes(), source.name)
            self.assertEqual(
                (FANTASY / "reports/STEP14_2026_PLAYER_TRUTH_REPORT.md").read_bytes(),
                (reports / "STEP14_2026_PLAYER_TRUTH_REPORT.md").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
