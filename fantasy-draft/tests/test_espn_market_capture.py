import argparse
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "fantasy-draft/research/capture_espn_market_2026.py"
SPEC = importlib.util.spec_from_file_location("espn_market", MODULE_PATH)
espn = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = espn
SPEC.loader.exec_module(espn)
FIXTURE = Path(__file__).resolve().parent / "fixtures/espn_market_fixture.json"


def player(internal_id, name, team, pos):
    return {"id": internal_id, "name": name, "team": team, "pos": pos}


class ESPNMarketTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()
        self.internal = [
            player(1, "Jahmyr Gibbs", "DET", "RB"),
            player(2, "Bijan Robinson", "ATL", "RB"),
            player(3, "Ja'Marr Chase", "CIN", "WR"),
            player(4, "Amon-Ra St. Brown", "DET", "WR"),
            player(5, "Jaxon Smith-Njigba", "SEA", "WR"),
            player(6, "Marquise Brown", "KC", "WR"),
        ]
        self.captured = datetime(2026, 8, 31, 21, 0, tzinfo=timezone.utc)
        self.rows, self.crosswalk = espn.parse_market(
            self.raw, self.captured, "candidate", "fixture", self.internal, {}
        )

    def test_raw_response_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            espn.write_bytes_new(path, self.raw)
            self.assertEqual(path.read_bytes(), self.raw)

    def test_rank_and_adp_are_separate(self):
        self.assertEqual(self.rows[0]["espn_official_ppr_rank"], 1)
        self.assertEqual(self.rows[0]["espn_adp"], 1.35)
        self.assertEqual(self.rows[0]["rank_adp_gap"], 0.35)

    def test_no_invented_ordinal_adp(self):
        self.assertIsNone(self.rows[0]["espn_adp_rank"])

    def test_stable_id_matching(self):
        prior = {4429795: {"draft_command_player_id": "1"}}
        rows, _ = espn.parse_market(self.raw, self.captured, "candidate", "fixture", self.internal, prior)
        self.assertEqual(rows[0]["mapping_method"], "exact stable-ID match")

    def test_apostrophe_hyphen_suffix_normalization(self):
        self.assertEqual(espn.normalize_name("Ja'Marr Smith-Njigba III"), "ja marr smith njigba")

    def test_same_name_collision_detection(self):
        idx = espn._internal_index([player(1, "John Smith", "DET", "RB"), player(2, "John Smith", "DET", "RB")])
        result = espn.map_identity(9, "John Smith", "DET", "RB", idx, {})
        self.assertIn("collision", result["unresolved_reason"])

    def test_team_conflict_detection(self):
        idx = espn._internal_index([player(1, "John Smith", "DET", "RB")])
        result = espn.map_identity(9, "John Smith", "GB", "RB", idx, {})
        self.assertIn("team conflict", result["unresolved_reason"])

    def test_position_conflict_detection(self):
        idx = espn._internal_index([player(1, "John Smith", "DET", "WR")])
        result = espn.map_identity(9, "John Smith", "DET", "RB", idx, {})
        self.assertIn("position conflict", result["unresolved_reason"])

    def test_duplicate_espn_id_rejected(self):
        payload = json.loads(self.raw)
        payload["players"].append(payload["players"][0])
        with self.assertRaises(espn.CaptureError):
            espn.parse_market(json.dumps(payload).encode(), self.captured, "candidate", "x", self.internal, {})

    def test_duplicate_internal_id_reported(self):
        league = {"keeper_coverage": 1, "adapter_checks": {"ok": True}, "scoring_verification": {"status": "verified"}}
        duplicate = [dict(row) for row in self.rows]
        duplicate[1]["draft_command_player_id"] = duplicate[0]["draft_command_player_id"]
        qa = espn.build_qa(duplicate, self.internal, league, "candidate", self.captured)
        self.assertTrue(qa["duplicate_internal_player_ids"])

    def test_unresolved_player_reporting(self):
        rows, _ = espn.parse_market(self.raw, self.captured, "candidate", "x", self.internal[:-1], {})
        league = {"keeper_coverage": 1, "adapter_checks": {"ok": True}, "scoring_verification": {"status": "verified"}}
        qa = espn.build_qa(rows, self.internal[:-1], league, "candidate", self.captured)
        self.assertEqual(qa["top_250_unresolved"][0]["player_name"], "Marquise Brown")

    def test_keeper_overall_slots(self):
        self.assertEqual(espn.keeper_overall(6, 1), 60)
        self.assertEqual(espn.keeper_overall(9, 4), 84)

    def test_top_160_coverage_enforcement(self):
        rows, _ = espn.parse_market(self.raw, self.captured, "candidate", "x", self.internal[:-1], {})
        league = {"keeper_coverage": 1, "adapter_checks": {"ok": True}, "scoring_verification": {"status": "verified"}}
        qa = espn.build_qa(rows, self.internal[:-1], league, "candidate", self.captured)
        self.assertTrue(any("top-160" in blocker for blocker in qa["blocking_conflicts"]))

    def test_top_universe_uses_raw_numeric_cutoff(self):
        rows = [
            {"espn_player_id": index, "espn_official_ppr_rank": index, "espn_adp": 170 + index / 1000}
            for index in range(1, 11)
        ]
        universe = espn.top_numeric_union(rows, 3)
        self.assertEqual([row["espn_player_id"] for row in universe], [1, 2, 3])

    def test_adp_cap_detection_prevents_invented_top_250_order(self):
        rows = [
            {"espn_player_id": index, "espn_official_ppr_rank": index, "espn_adp": 169.9}
            for index in range(1, 301)
        ]
        self.assertTrue(espn.adp_cap_analysis(rows)["detected"])
        universe = espn.top_numeric_union(rows, 250, include_adp=False)
        self.assertEqual(len(universe), 250)

    def test_candidate_vs_frozen_status(self):
        self.assertEqual(self.rows[0]["snapshot_status"], "candidate")
        frozen_time = datetime(2026, 9, 1, 0, 35, tzinfo=timezone.utc)
        rows, _ = espn.parse_market(self.raw, frozen_time, "frozen", "f", self.internal, {})
        self.assertEqual(rows[0]["snapshot_status"], "frozen")

    def test_frozen_window_enforcement(self):
        self.assertFalse(espn.frozen_window_ok(self.captured))
        self.assertTrue(espn.frozen_window_ok(datetime(2026, 9, 1, 0, 35, tzinfo=timezone.utc)))

    def test_immutable_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "immutable"
            espn.write_bytes_new(path, b"one")
            with self.assertRaises(espn.CaptureError):
                espn.write_bytes_new(path, b"two")

    def test_stale_snapshot_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact"
            artifact.write_bytes(b"x")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "x", "snapshot_id": "x", "status": "candidate",
                "generation_time_utc": "2026-08-31T20:00:00Z", "git_commit": "x", "sources": [],
                "raw_hashes": {}, "processed_file_hashes": {}, "row_counts": {}, "position_counts": {},
                "rank_coverage": {}, "adp_coverage": {}, "dual_coverage": {}, "identity_match_coverage": {},
                "keeper_coverage": 1, "blocking_conflicts": [], "freshness_status": "x",
                "approved_downstream_uses": [], "prohibited_uses": [], "artifacts": {},
            }))
            result = espn.validate_manifest(manifest, reject_older_than="2026-08-31T21:00:00Z")
            self.assertFalse(result["valid"])

    def test_partial_source_failure_not_promoted(self):
        with self.assertRaises(espn.CaptureError):
            espn.parse_market(b'{"players":[]}', self.captured, "candidate", "x", self.internal, {})

    def test_no_august_21_fallback(self):
        self.assertNotIn("2026-08-21", espn.ESPN_ENDPOINT)
        self.assertEqual(espn.SOURCE_TIER, 1)

    def test_schema_required_fields(self):
        self.assertEqual(set(espn.CSV_FIELDS) - set(self.rows[0]), set())

    def test_manifest_hash_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "fantasy-draft/data/production").mkdir(parents=True)
            artifact = repo / "artifact.txt"
            artifact.write_text("value")
            manifest = repo / "fantasy-draft/data/production/manifest.json"
            base = {
                "schema_version": "x", "snapshot_id": "x", "status": "candidate",
                "generation_time_utc": "2026-08-31T21:00:00Z", "git_commit": "x", "sources": [],
                "raw_hashes": {"artifact.txt": hashlib.sha256(b"value").hexdigest()},
                "processed_file_hashes": {}, "row_counts": {}, "position_counts": {}, "rank_coverage": {},
                "adp_coverage": {}, "dual_coverage": {}, "identity_match_coverage": {}, "keeper_coverage": 1,
                "blocking_conflicts": [], "freshness_status": "x", "approved_downstream_uses": [],
                "prohibited_uses": [], "artifacts": {},
            }
            manifest.write_text(json.dumps(base))
            self.assertTrue(espn.validate_manifest(manifest)["valid"])
            artifact.write_text("changed")
            self.assertFalse(espn.validate_manifest(manifest)["valid"])

    def test_manifest_row_count_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            production = repo / "fantasy-draft/data/production"
            derived = repo / "fantasy-draft/data/derived"
            production.mkdir(parents=True)
            derived.mkdir(parents=True)
            snapshot = derived / "snapshot.json"
            snapshot.write_text(json.dumps({"players": [{"primary_position": "RB"}]}))
            manifest = production / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "x", "snapshot_id": "x", "status": "candidate",
                "generation_time_utc": "2026-08-31T21:00:00Z", "git_commit": "x", "sources": [],
                "raw_hashes": {}, "processed_file_hashes": {},
                "row_counts": {"source": 2}, "position_counts": {"RB": 1}, "rank_coverage": {},
                "adp_coverage": {}, "dual_coverage": {}, "identity_match_coverage": {}, "keeper_coverage": 1,
                "blocking_conflicts": [], "freshness_status": "x", "approved_downstream_uses": [],
                "prohibited_uses": [], "artifacts": {"snapshot_json": "fantasy-draft/data/derived/snapshot.json"},
            }))
            result = espn.validate_manifest(manifest)
            self.assertFalse(result["valid"])
            self.assertTrue(any("row-count mismatch" in error for error in result["errors"]))

    def test_deterministic_fixture_parse(self):
        again, _ = espn.parse_market(self.raw, self.captured, "candidate", "fixture", self.internal, {})
        self.assertEqual(json.dumps(self.rows, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_approved_alias(self):
        idx = espn._internal_index([player(1, "Marquise Brown", "KC", "WR")])
        result = espn.map_identity(9, "Hollywood Brown", "KC", "WR", idx, {})
        self.assertEqual(result["mapping_method"], "approved alias")


if __name__ == "__main__":
    unittest.main()
