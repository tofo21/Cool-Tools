from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


FANTASY = Path(__file__).resolve().parents[2]
REPOSITORY = FANTASY.parent
OUTPUT = FANTASY / "data/candidate/league-value"
REPORTS = FANTASY / "reports"
ARTIFACT_PATH = OUTPUT / "espn_league_value_step15.json"
TRUTH_PATH = FANTASY / "data/candidate/player-truth/player_truth_step14.json"
SETTINGS_PATH = FANTASY / "research/step15/config/espn_league_settings_2026_v1.json"
sys.path.insert(0, str(FANTASY / "research"))
sys.path.insert(0, str(FANTASY / "research/step15"))

from runtime_contract_lib import load_and_validate_artifact, payload_sha256  # noqa: E402
import build_espn_league_value_step15 as builder  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Step15EspnLeagueValueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = load(ARTIFACT_PATH)
        cls.truth = load(TRUTH_PATH)
        cls.settings = load(SETTINGS_PATH)
        cls.coverage = load(OUTPUT / "espn_league_value_step15_coverage_report.json")
        cls.replacement = load(OUTPUT / "espn_league_value_step15_replacement_level_report.json")
        cls.sensitivity = load(OUTPUT / "espn_league_value_step15_sensitivity_report.json")
        cls.validation = load(OUTPUT / "espn_league_value_step15_validation_report.json")
        cls.records = cls.artifact["records"]
        cls.records_by_id = {row["internalPlayerId"]: row for row in cls.records}
        cls.truth_by_id = {row["internalPlayerId"]: row for row in cls.truth["players"]}

    def test_01_schema_semantics_and_canonical_signature(self):
        value, issues, _ = load_and_validate_artifact(
            ARTIFACT_PATH,
            FANTASY / "contracts",
            "espn-league-value",
            datetime(2026, 9, 1, 2, 18, 40, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(value)
        self.assertEqual([], [issue.as_dict() for issue in issues if issue.severity == "BLOCKING"])
        self.assertEqual(self.artifact["integrity"]["payloadSha256"], payload_sha256(self.artifact))
        self.assertEqual(builder.LEAGUE_VALUE_SCHEMA_SHA256, sha256(FANTASY / "contracts/espn_league_value.schema.json"))

    def test_02_player_truth_is_immutable_and_points_are_copied(self):
        self.assertEqual(builder.PLAYER_TRUTH_FILE_SHA256, sha256(TRUTH_PATH))
        self.assertEqual(builder.PLAYER_TRUTH_PAYLOAD_SHA256, payload_sha256(self.truth))
        self.assertEqual(set(self.truth_by_id), set(self.records_by_id))
        for player_id, truth_row in self.truth_by_id.items():
            self.assertEqual(
                truth_row["projectedFullPprPoints"],
                self.records_by_id[player_id]["projectedLeaguePoints"],
                player_id,
            )

    def test_03_binding_league_settings_and_settings_hash(self):
        config = self.artifact["leagueConfiguration"]
        self.assertEqual("167404", config["leagueId"])
        self.assertEqual("full_ppr", config["scoringFormat"])
        self.assertEqual((10, 16, 5, 160, "team-05"), (
            config["teamCount"], config["rounds"], config["draftSlot"], config["totalPicks"], config["tonyTeamId"]
        ))
        self.assertEqual(
            {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 2, "K": 0, "DST": 0},
            config["rosterFormat"]["starters"],
        )
        self.assertEqual((8, 0), (config["rosterFormat"]["bench"], config["rosterFormat"]["ir"]))
        self.assertEqual(builder.settings_hash(self.settings), config["settingsHash"])

    def test_04_keeper_identities_slots_and_snake_geometry(self):
        expected_ids = [68, 24, 45, 50, 90, 30, 47, 52, 26, 33]
        keepers = self.artifact["leagueConfiguration"]["keepers"]
        self.assertEqual(expected_ids, [row["internalPlayerId"] for row in keepers])
        self.assertEqual(10, len({row["teamId"] for row in keepers}))
        self.assertEqual(10, len({row["overallPick"] for row in keepers}))
        for keeper in keepers:
            team_number = int(keeper["teamId"].split("-")[1])
            self.assertEqual(
                builder.snake_overall(keeper["round"], team_number, 10),
                keeper["overallPick"],
            )
        assignments = self.replacement["keeperAssignments"]
        self.assertEqual(expected_ids, [row["internalPlayerId"] for row in assignments])
        for assignment in assignments:
            truth = self.truth_by_id[assignment["internalPlayerId"]]
            self.assertEqual(f"{truth['position']}1", assignment["assignedSlot"])

    def test_05_coverage_is_exact(self):
        coverage = self.coverage["coverage"]
        self.assertEqual((199, 199, 199), (
            coverage["playerTruthRows"], coverage["leagueValueRows"], coverage["matchedRows"]
        ))
        self.assertEqual((159, 159), (
            coverage["top160RepresentedPlayerTruthRows"], coverage["top160MatchedRows"]
        ))
        self.assertEqual([], coverage["duplicateInternalPlayerIds"])
        self.assertEqual([], coverage["orphanLeagueValueIds"])
        self.assertEqual([], coverage["missingLeagueValueIds"])

    def test_06_mandatory_and_flex_allocation(self):
        self.assertEqual({"QB": 10, "RB": 20, "WR": 20, "TE": 10}, self.replacement["mandatoryDemand"])
        self.assertEqual({"QB": 1, "RB": 3, "WR": 4, "TE": 2}, self.replacement["keeperPositionCounts"])
        self.assertEqual({"QB": 9, "RB": 17, "WR": 16, "TE": 8}, self.replacement["mandatoryNonkeeperCounts"])
        self.assertEqual(20, self.replacement["flex"]["allocated"])
        self.assertEqual({"RB": 7, "WR": 13, "TE": 0}, self.replacement["flex"]["positionCounts"])
        self.assertEqual(20, len({row["internalPlayerId"] for row in self.replacement["flex"]["players"]}))

    def test_07_replacement_and_value_equations_have_no_flex_double_count(self):
        expected_replacement = {"QB": 290.826, "RB": 189.86, "WR": 190.27, "TE": 170.92}
        actual_replacement = {
            position: row["projectedLeaguePoints"]
            for position, row in self.replacement["replacementLevels"].items()
        }
        self.assertEqual(expected_replacement, actual_replacement)
        for record in self.records:
            position = self.truth_by_id[record["internalPlayerId"]]["position"]
            self.assertEqual(expected_replacement[position], record["replacementValueByPosition"])
            self.assertAlmostEqual(
                round(record["projectedLeaguePoints"] - record["replacementValueByPosition"], 3),
                record["marginalValue"],
                places=3,
            )
            self.assertEqual(record["marginalValue"], record["flexAdjustedValue"])
            self.assertEqual(record["flexAdjustedValue"], record["leagueValueScore"])

    def test_08_numeric_ranking_and_stable_tie_breaking(self):
        ordered = sorted(self.records, key=lambda row: (-row["leagueValueScore"], row["internalPlayerId"]))
        self.assertEqual(self.records, ordered)
        self.assertEqual(list(range(1, 200)), [row["leagueValueRank"] for row in self.records])
        for position in builder.POSITIONS:
            positional = sorted(
                [row for row in self.records if self.truth_by_id[row["internalPlayerId"]]["position"] == position],
                key=lambda row: (-row["leagueValueScore"], row["internalPlayerId"]),
            )
            self.assertEqual(list(range(1, len(positional) + 1)), [row["positionalRank"] for row in positional])
        tied_scores = Counter(row["leagueValueScore"] for row in self.records)
        for score, count in tied_scores.items():
            if count > 1:
                ids = [row["internalPlayerId"] for row in self.records if row["leagueValueScore"] == score]
                self.assertEqual(sorted(ids), ids)

    def test_09_special_identity_and_availability_cases(self):
        self.assertNotIn(143, self.records_by_id)
        self.assertIn(190, self.records_by_id)
        self.assertIsNone(self.truth_by_id[190]["espnPlayerId"])
        self.assertEqual(256.85, self.records_by_id[34]["projectedLeaguePoints"])
        self.assertEqual(17.0, self.truth_by_id[34]["expectedGames"])
        self.assertIn("COMMISSIONER_EXEMPT", " ".join(self.truth_by_id[34]["limitations"]))
        self.assertEqual("HOU", self.truth_by_id[180]["nflTeam"])
        self.assertIn("source lists NE", " ".join(self.truth_by_id[180]["limitations"]))

    def test_10_roster_fit_and_availability_are_separate_state(self):
        self.assertTrue(all(row["rosterFitAdjustment"] is None for row in self.records))
        self.assertEqual(90, self.replacement["initialRosterFitState"]["keeper"]["internalPlayerId"])
        self.assertEqual("QB", self.replacement["initialRosterFitState"]["assignedSlot"])
        self.assertEqual(10, len(self.artifact["leagueConfiguration"]["keepers"]))

    def test_11_market_and_opponent_fields_are_absent_from_formula(self):
        forbidden = {
            "espnRank", "espnAdp", "continuousAdp", "sleeperRank", "sleeperAdp",
            "ecr", "auctionValue", "opponentIntent", "survival", "availabilityStatus",
        }
        for record in self.records:
            self.assertFalse(forbidden & set(record), record["internalPlayerId"])
        description = self.artifact["formula"]["description"].lower()
        self.assertNotIn("adp", description)
        self.assertNotIn("rank", description)

    def test_12_finite_and_negative_values_are_consistent(self):
        numeric_fields = (
            "projectedLeaguePoints", "replacementValueByPosition", "marginalValue",
            "flexAdjustedValue", "leagueValueScore", "confidence",
        )
        for record in self.records:
            self.assertTrue(all(math.isfinite(record[field]) for field in numeric_fields))
        self.assertTrue(any(row["leagueValueScore"] < 0 for row in self.records))
        self.assertTrue(any(row["leagueValueScore"] > 0 for row in self.records))

    def test_13_sensitivity_is_reasonable_and_diagnostic_only(self):
        self.assertEqual("PASS", self.sensitivity["status"])
        self.assertEqual(20, self.sensitivity["baseline"]["flexSlots"])
        self.assertEqual([18, 22], [row["flexSlots"] for row in self.sensitivity["scenarios"]])
        for scenario in self.sensitivity["scenarios"]:
            self.assertGreater(scenario["spearmanRankCorrelation"], 0.99)
            self.assertGreaterEqual(scenario["top20OverlapCount"], 19)
            self.assertLessEqual(scenario["maximumAbsoluteRankShift"], 4)

    def test_14_manifest_ledger_and_validation_report(self):
        self.assertEqual("PASS", self.validation["status"])
        self.assertTrue(all(row["status"] == "PASS" for row in self.validation["checks"]))
        manifest = load(OUTPUT / "espn_league_value_step15_manifest.json")
        self.assertEqual(self.artifact["integrity"]["payloadSha256"], manifest["canonicalPayloadSha256"])
        self.assertEqual(self.artifact["leagueConfiguration"]["settingsHash"], manifest["settingsHash"])
        for line in (OUTPUT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            target = (OUTPUT / relative).resolve()
            self.assertTrue(target.exists(), relative)
            self.assertEqual(expected, sha256(target), relative)

    def test_15_deterministic_rebuild_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fantasy-draft"
            output = root / "data/candidate/league-value"
            reports = root / "reports"
            result = subprocess.run(
                [
                    sys.executable,
                    str(FANTASY / "research/step15/build_espn_league_value_step15.py"),
                    "--repo-root", str(FANTASY),
                    "--output-dir", str(output),
                    "--report-dir", str(reports),
                    "--generated-at", builder.GENERATED_AT,
                ],
                cwd=REPOSITORY,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "PASS"', result.stdout)
            for source in sorted(OUTPUT.iterdir()):
                if source.is_file():
                    self.assertEqual(source.read_bytes(), (output / source.name).read_bytes(), source.name)
            report_names = (
                "STEP15_ESPN_LEAGUE_VALUE_FORMULA.md",
                "STEP15_ESPN_LEAGUE_VALUE_COVERAGE.md",
                "STEP15_ESPN_LEAGUE_VALUE_REPLACEMENT_LEVELS.md",
                "STEP15_ESPN_LEAGUE_VALUE_SENSITIVITY.md",
                "STEP15_ESPN_LEAGUE_VALUE_VALIDATION.md",
            )
            for name in report_names:
                self.assertEqual((REPORTS / name).read_bytes(), (reports / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
