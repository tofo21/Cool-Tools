#!/usr/bin/env python3
"""Build the thin, deterministic Step 15 ESPN League Value adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0.0"
ARTIFACT_VERSION = "step15-2026.1"
FORMULA_VERSION = "step15-espn-league-value-v1"
REPLACEMENT_METHOD_VERSION = "keeper-initialized-starter-allocation-v1"
GENERATED_AT = "2026-09-01T02:18:40Z"
STEP14_COMMIT = "827a8f0fddc8ad979565edea0ab7e8138840f15b"
STEP14_TREE = "b08d889414b5d9c18fdb86ace48abe799cfff81c"
RUNTIME_CONTRACT_COMMIT = "546687a9f462ae6b26693055b15c0f13044f84e2"
ESPN_MARKET_COMMIT = "49951ca1d45b92a906f84366a02d40c8c2e07e12"
PLAYER_TRUTH_FILE_SHA256 = "f6488e648af2549f1b7fa50eb485aa8f29784280144796e5e6d581a13b477bd3"
PLAYER_TRUTH_PAYLOAD_SHA256 = "be052a59ad9a0643246b2ed113e2c728fc5abfafb97e4278c53b8ea621f89694"
LEAGUE_VALUE_SCHEMA_SHA256 = "4c72326f4e30d265c8a9f0a13349cbbe7ed462ff8a9abbb3b0756d5c2427b01e"
POSITIONS = ("QB", "RB", "WR", "TE")
FLEX_POSITIONS = ("RB", "WR", "TE")
EXPECTED_PLAYER_COUNT = 199
EXPECTED_TOP160_COUNT = 159
KEENAN_ALLEN_ID = 143
JAYDON_BLUE_ID = 190
JOSH_JACOBS_ID = 34
KAYSHON_BOUTTE_ID = 180


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
        help="Default: <repo-root>/data/candidate/league-value",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="Default: <repo-root>/reports",
    )
    parser.add_argument(
        "--generated-at",
        default=GENERATED_AT,
        help="Fixed RFC 3339 publication timestamp used for deterministic reproduction",
    )
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def pretty_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty_json(value))


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def q3_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def q3(value: Decimal) -> float:
    return float(q3_decimal(value))


def snake_overall(round_number: int, team_number: int, team_count: int) -> int:
    in_round = team_number if round_number % 2 else team_count + 1 - team_number
    return (round_number - 1) * team_count + in_round


def player_sort_key(player: dict[str, Any]) -> tuple[Decimal, int]:
    return (-player["projected"], player["internalPlayerId"])


def load_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], Path, Path, Path]:
    truth_path = repo_root / "data/candidate/player-truth/player_truth_step14.json"
    schema_path = repo_root / "contracts/espn_league_value.schema.json"
    settings_path = repo_root / "research/step15/config/espn_league_settings_2026_v1.json"

    if sha256(truth_path) != PLAYER_TRUTH_FILE_SHA256:
        raise RuntimeError("Player Truth file SHA-256 invariant failed")
    if sha256(schema_path) != LEAGUE_VALUE_SCHEMA_SHA256:
        raise RuntimeError("runtime-contract League Value schema SHA-256 invariant failed")

    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    if truth.get("integrity", {}).get("payloadSha256") != PLAYER_TRUTH_PAYLOAD_SHA256:
        raise RuntimeError("Player Truth declared canonical payload SHA-256 invariant failed")
    unsigned_truth = json.loads(json.dumps(truth))
    unsigned_truth["integrity"].pop("payloadSha256", None)
    if sha256_bytes(canonical_json(unsigned_truth)) != PLAYER_TRUTH_PAYLOAD_SHA256:
        raise RuntimeError("Player Truth calculated canonical payload SHA-256 invariant failed")

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    return truth, settings, truth_path, schema_path, settings_path


def normalized_settings(settings: dict[str, Any]) -> dict[str, Any]:
    keepers = [
        {
            "teamId": keeper["teamId"],
            "internalPlayerId": keeper["internalPlayerId"],
            "round": keeper["round"],
            "overallPick": keeper["overallPick"],
        }
        for keeper in sorted(settings["keepers"], key=lambda item: item["teamId"])
    ]
    return {
        "leagueId": settings["leagueId"],
        "leagueSettingsVersion": settings["leagueSettingsVersion"],
        "scoringFormat": settings["scoringFormat"],
        "rosterFormat": settings["rosterFormat"],
        "teamCount": settings["teamCount"],
        "rounds": settings["rounds"],
        "draftSlot": settings["draftSlot"],
        "totalPicks": settings["totalPicks"],
        "tonyTeamId": settings["tonyTeamId"],
        "keepers": keepers,
    }


def validate_settings(settings: dict[str, Any], players_by_id: dict[int, dict[str, Any]]) -> None:
    expected = {
        "leagueId": "167404",
        "season": 2026,
        "platform": "ESPN",
        "scoringFormat": "full_ppr",
        "teamCount": 10,
        "rounds": 16,
        "draftSlot": 5,
        "totalPicks": 160,
        "tonyTeamId": "team-05",
    }
    for key, value in expected.items():
        if settings.get(key) != value:
            raise RuntimeError(f"binding league setting conflict for {key}: {settings.get(key)!r} != {value!r}")

    roster = settings.get("rosterFormat", {})
    expected_starters = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 2, "K": 0, "DST": 0}
    if roster.get("starters") != expected_starters or roster.get("bench") != 8 or roster.get("ir") != 0:
        raise RuntimeError("binding roster-format conflict")
    if sum(expected_starters[position] for position in ("QB", "RB", "WR", "TE", "FLEX")) + roster["bench"] != 16:
        raise RuntimeError("active roster does not total 16")

    keepers = settings.get("keepers", [])
    if len(keepers) != 10:
        raise RuntimeError("exactly ten keepers are required")
    if len({item["teamId"] for item in keepers}) != 10:
        raise RuntimeError("keeper teams are not unique")
    if len({item["internalPlayerId"] for item in keepers}) != 10:
        raise RuntimeError("keeper internalPlayerIds are not unique")
    if len({item["overallPick"] for item in keepers}) != 10:
        raise RuntimeError("keeper overall picks are not unique")

    for keeper in keepers:
        team_number = int(keeper["teamId"].split("-")[1])
        expected_overall = snake_overall(keeper["round"], team_number, settings["teamCount"])
        if keeper["overallPick"] != expected_overall:
            raise RuntimeError(f"invalid snake geometry for keeper {keeper['internalPlayerId']}")
        player = players_by_id.get(keeper["internalPlayerId"])
        if player is None:
            raise RuntimeError(f"keeper {keeper['internalPlayerId']} is absent from Player Truth")
        if player["normalizedName"] != keeper["normalizedName"]:
            raise RuntimeError(f"keeper identity mismatch for {keeper['internalPlayerId']}")


def runtime_players(truth: dict[str, Any]) -> list[dict[str, Any]]:
    players = []
    for row in truth["players"]:
        if row["position"] not in POSITIONS:
            raise RuntimeError(f"unsupported Player Truth position {row['position']!r}")
        points = Decimal(str(row["projectedFullPprPoints"]))
        if not points.is_finite():
            raise RuntimeError(f"non-finite projection for player {row['internalPlayerId']}")
        players.append(
            {
                "internalPlayerId": row["internalPlayerId"],
                "normalizedName": row["normalizedName"],
                "position": row["position"],
                "projected": points,
                "modelConfidence": Decimal(str(row["modelConfidence"])),
                "draftCommandBoardRank": row["draftCommandBoardRank"],
                "source": row,
            }
        )
    if len(players) != EXPECTED_PLAYER_COUNT:
        raise RuntimeError(f"expected {EXPECTED_PLAYER_COUNT} Player Truth rows, found {len(players)}")
    ids = [row["internalPlayerId"] for row in players]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate Player Truth internalPlayerId")
    if KEENAN_ALLEN_ID in ids:
        raise RuntimeError("Keenan Allen must remain absent")
    return players


def allocate_lineups(
    players: list[dict[str, Any]],
    settings: dict[str, Any],
    flex_slots: int,
) -> dict[str, Any]:
    players_by_id = {row["internalPlayerId"]: row for row in players}
    keepers = settings["keepers"]
    keeper_ids = {row["internalPlayerId"] for row in keepers}
    keeper_position_counts = Counter(players_by_id[row["internalPlayerId"]]["position"] for row in keepers)
    mandatory_demand = {
        position: settings["teamCount"] * settings["rosterFormat"]["starters"][position]
        for position in POSITIONS
    }

    mandatory_nonkeepers: dict[str, list[dict[str, Any]]] = {}
    mandatory_ids = set(keeper_ids)
    for position in POSITIONS:
        remaining_demand = mandatory_demand[position] - keeper_position_counts[position]
        if remaining_demand < 0:
            raise RuntimeError(f"keepers exceed mandatory {position} demand")
        candidates = sorted(
            [row for row in players if row["position"] == position and row["internalPlayerId"] not in keeper_ids],
            key=player_sort_key,
        )
        selected = candidates[:remaining_demand]
        if len(selected) != remaining_demand:
            raise RuntimeError(f"insufficient Player Truth depth for mandatory {position} demand")
        mandatory_nonkeepers[position] = selected
        mandatory_ids.update(row["internalPlayerId"] for row in selected)

    flex_pool = sorted(
        [
            row
            for row in players
            if row["position"] in FLEX_POSITIONS
            and row["internalPlayerId"] not in keeper_ids
            and row["internalPlayerId"] not in mandatory_ids
        ],
        key=player_sort_key,
    )
    flex_players = flex_pool[:flex_slots]
    if len(flex_players) != flex_slots:
        raise RuntimeError("insufficient Player Truth depth for FLEX demand")
    selected_ids = mandatory_ids | {row["internalPlayerId"] for row in flex_players}

    replacements: dict[str, dict[str, Any]] = {}
    for position in POSITIONS:
        remaining = sorted(
            [
                row
                for row in players
                if row["position"] == position
                and row["internalPlayerId"] not in keeper_ids
                and row["internalPlayerId"] not in selected_ids
            ],
            key=player_sort_key,
        )
        if not remaining:
            raise RuntimeError(f"no available {position} replacement player")
        replacements[position] = remaining[0]

    return {
        "mandatoryDemand": mandatory_demand,
        "keeperPositionCounts": dict(sorted(keeper_position_counts.items())),
        "mandatoryNonkeepers": mandatory_nonkeepers,
        "mandatoryIds": mandatory_ids,
        "flexPlayers": flex_players,
        "flexPositionCounts": dict(sorted(Counter(row["position"] for row in flex_players).items())),
        "selectedIds": selected_ids,
        "replacements": replacements,
    }


def calculate_scores(
    players: list[dict[str, Any]],
    allocation: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, int]]:
    scored = []
    for player in players:
        replacement = allocation["replacements"][player["position"]]["projected"]
        marginal = q3_decimal(player["projected"] - replacement)
        scored.append(
            {
                "player": player,
                "projected": q3_decimal(player["projected"]),
                "replacement": q3_decimal(replacement),
                "marginal": marginal,
                "flexAdjusted": marginal,
                "score": marginal,
            }
        )

    ranked = sorted(scored, key=lambda row: (-row["score"], row["player"]["internalPlayerId"]))
    overall_ranks = {row["player"]["internalPlayerId"]: rank for rank, row in enumerate(ranked, start=1)}
    positional_ranks: dict[int, int] = {}
    for position in POSITIONS:
        positional = sorted(
            [row for row in scored if row["player"]["position"] == position],
            key=lambda row: (-row["score"], row["player"]["internalPlayerId"]),
        )
        positional_ranks.update(
            {row["player"]["internalPlayerId"]: rank for rank, row in enumerate(positional, start=1)}
        )
    for row in ranked:
        player_id = row["player"]["internalPlayerId"]
        row["overallRank"] = overall_ranks[player_id]
        row["positionalRank"] = positional_ranks[player_id]
    return ranked, overall_ranks


def settings_hash(settings: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(normalized_settings(settings)))


def build_artifact(
    truth: dict[str, Any],
    settings: dict[str, Any],
    players: list[dict[str, Any]],
    allocation: dict[str, Any],
    ranked: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    source_artifact_ids = [
        truth["artifactId"],
        "espn-keeper-10-ppr-2flex-2026",
        "espn_2026_league_keeper_verification_espn_2026_frozen_20260901T003012Z_3379127ab1c0",
    ]
    records = []
    for row in ranked:
        player = row["player"]
        records.append(
            {
                "internalPlayerId": player["internalPlayerId"],
                "projectedLeaguePoints": q3(row["projected"]),
                "replacementValueByPosition": q3(row["replacement"]),
                "marginalValue": q3(row["marginal"]),
                "flexAdjustedValue": q3(row["flexAdjusted"]),
                "leagueValueScore": q3(row["score"]),
                "leagueValueRank": row["overallRank"],
                "positionalRank": row["positionalRank"],
                "rosterFitAdjustment": None,
                "confidence": float(player["modelConfidence"]),
                "status": "validated",
                "provenance": {
                    "formulaVersion": FORMULA_VERSION,
                    "sourceArtifactIds": [truth["artifactId"]],
                },
            }
        )

    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        "artifactType": "espn-league-value",
        "artifactId": "espn-league-value-step15-2026",
        "artifactVersion": ARTIFACT_VERSION,
        "generatedAt": generated_at,
        "effectiveAt": truth["effectiveAt"],
        "expiresAt": None,
        "status": "validated",
        "season": 2026,
        "integrity": {
            "canonicalization": "draft-command-canonical-json-v1",
            "payloadSha256": "0" * 64,
        },
        "leagueConfiguration": {
            **normalized_settings(settings),
            "settingsHash": settings_hash(settings),
            "replacementLevelMethodVersion": REPLACEMENT_METHOD_VERSION,
        },
        "formula": {
            "formulaVersion": FORMULA_VERSION,
            "generator": "fantasy-draft/research/step15/build_espn_league_value_step15.py",
            "sourceArtifactIds": source_artifact_ids,
            "sourceCommits": [STEP14_COMMIT, RUNTIME_CONTRACT_COMMIT, ESPN_MARKET_COMMIT],
            "description": (
                "Keeper-initialized mandatory starter allocation followed by exactly 20 highest-projected "
                "remaining RB/WR/TE FLEX starters; base score is projection minus the post-allocation "
                "position replacement value, with no second FLEX premium."
            ),
        },
        "records": records,
    }
    artifact["integrity"]["payloadSha256"] = payload_sha256(artifact)
    return artifact


def payload_sha256(artifact: dict[str, Any]) -> str:
    unsigned = json.loads(json.dumps(artifact))
    unsigned["integrity"].pop("payloadSha256", None)
    return sha256_bytes(canonical_json(unsigned))


def player_summary(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "internalPlayerId": player["internalPlayerId"],
        "normalizedName": player["normalizedName"],
        "position": player["position"],
        "projectedLeaguePoints": q3(player["projected"]),
    }


def build_coverage_report(
    truth: dict[str, Any],
    artifact: dict[str, Any],
    players: list[dict[str, Any]],
    settings: dict[str, Any],
) -> dict[str, Any]:
    truth_ids = {row["internalPlayerId"] for row in players}
    record_ids = [row["internalPlayerId"] for row in artifact["records"]]
    record_id_set = set(record_ids)
    top160_ids = {
        row["internalPlayerId"] for row in players if row["draftCommandBoardRank"] <= 160
    }
    return {
        "schemaVersion": "1.0.0",
        "artifactId": artifact["artifactId"],
        "artifactVersion": ARTIFACT_VERSION,
        "generatedAt": artifact["generatedAt"],
        "status": "PASS",
        "playerTruth": {
            "artifactId": truth["artifactId"],
            "fileSha256": PLAYER_TRUTH_FILE_SHA256,
            "payloadSha256": PLAYER_TRUTH_PAYLOAD_SHA256,
        },
        "coverage": {
            "playerTruthRows": len(truth_ids),
            "leagueValueRows": len(record_ids),
            "matchedRows": len(truth_ids & record_id_set),
            "top160RepresentedPlayerTruthRows": len(top160_ids),
            "top160MatchedRows": len(top160_ids & record_id_set),
            "duplicateInternalPlayerIds": sorted(
                player_id for player_id, count in Counter(record_ids).items() if count > 1
            ),
            "orphanLeagueValueIds": sorted(record_id_set - truth_ids),
            "missingLeagueValueIds": sorted(truth_ids - record_id_set),
            "positionCounts": dict(sorted(Counter(row["position"] for row in players).items())),
        },
        "keepers": {
            "approvedCount": len(settings["keepers"]),
            "resolvedCount": sum(
                1 for keeper in settings["keepers"] if keeper["internalPlayerId"] in record_id_set
            ),
            "internalPlayerIds": [keeper["internalPlayerId"] for keeper in settings["keepers"]],
        },
        "specialCases": {
            "keenanAllen143Absent": KEENAN_ALLEN_ID not in record_id_set,
            "jaydonBlue190PresentByInternalId": JAYDON_BLUE_ID in record_id_set,
            "joshJacobs34ProjectionUnadjusted": next(
                row["projectedLeaguePoints"] for row in artifact["records"] if row["internalPlayerId"] == JOSH_JACOBS_ID
            ) == 256.85,
            "kayshonBoutte180RecordPresent": KAYSHON_BOUTTE_ID in record_id_set,
        },
    }


def build_replacement_report(
    artifact: dict[str, Any],
    settings: dict[str, Any],
    players: list[dict[str, Any]],
    allocation: dict[str, Any],
) -> dict[str, Any]:
    players_by_id = {row["internalPlayerId"]: row for row in players}
    return {
        "schemaVersion": "1.0.0",
        "artifactId": artifact["artifactId"],
        "artifactVersion": ARTIFACT_VERSION,
        "generatedAt": artifact["generatedAt"],
        "methodVersion": REPLACEMENT_METHOD_VERSION,
        "formulaVersion": FORMULA_VERSION,
        "mandatoryDemand": allocation["mandatoryDemand"],
        "keeperPositionCounts": {
            position: allocation["keeperPositionCounts"].get(position, 0) for position in POSITIONS
        },
        "keeperAssignments": [
            {
                "teamId": keeper["teamId"],
                **player_summary(players_by_id[keeper["internalPlayerId"]]),
                "assignedSlot": f"{players_by_id[keeper['internalPlayerId']]['position']}1",
                "round": keeper["round"],
                "overallPick": keeper["overallPick"],
            }
            for keeper in settings["keepers"]
        ],
        "mandatoryNonkeeperCounts": {
            position: len(allocation["mandatoryNonkeepers"][position]) for position in POSITIONS
        },
        "flex": {
            "required": settings["teamCount"] * settings["rosterFormat"]["starters"]["FLEX"],
            "allocated": len(allocation["flexPlayers"]),
            "positionCounts": {
                position: allocation["flexPositionCounts"].get(position, 0) for position in FLEX_POSITIONS
            },
            "players": [player_summary(row) for row in allocation["flexPlayers"]],
        },
        "replacementLevels": {
            position: {
                **player_summary(allocation["replacements"][position]),
                "definition": "highest projected available non-keeper after mandatory and FLEX allocation",
            }
            for position in POSITIONS
        },
        "initialRosterFitState": {
            "teamId": settings["tonyTeamId"],
            "keeper": player_summary(players_by_id[90]),
            "assignedSlot": "QB",
            "rosterFitAdjustment": None,
            "reason": "live roster-fit function is separate from immutable base League Value",
        },
    }


def spearman(rank_a: dict[int, int], rank_b: dict[int, int]) -> float:
    ids = sorted(rank_a)
    if ids != sorted(rank_b):
        raise RuntimeError("sensitivity rank universes differ")
    n = len(ids)
    sum_d2 = sum((rank_a[player_id] - rank_b[player_id]) ** 2 for player_id in ids)
    return round(1 - (6 * sum_d2) / (n * (n * n - 1)), 6)


def scenario_summary(
    label: str,
    flex_slots: int,
    players: list[dict[str, Any]],
    settings: dict[str, Any],
    baseline_ranks: dict[int, int],
) -> dict[str, Any]:
    allocation = allocate_lineups(players, settings, flex_slots)
    ranked, ranks = calculate_scores(players, allocation)
    shifts = sorted(
        (
            {
                "internalPlayerId": player_id,
                "normalizedName": next(
                    row["normalizedName"] for row in players if row["internalPlayerId"] == player_id
                ),
                "baselineRank": baseline_ranks[player_id],
                "scenarioRank": ranks[player_id],
                "absoluteRankShift": abs(baseline_ranks[player_id] - ranks[player_id]),
            }
            for player_id in baseline_ranks
        ),
        key=lambda row: (-row["absoluteRankShift"], row["internalPlayerId"]),
    )
    baseline_top20 = {player_id for player_id, rank in baseline_ranks.items() if rank <= 20}
    scenario_top20 = {player_id for player_id, rank in ranks.items() if rank <= 20}
    return {
        "label": label,
        "flexSlots": flex_slots,
        "flexPositionCounts": {
            position: allocation["flexPositionCounts"].get(position, 0) for position in FLEX_POSITIONS
        },
        "replacementLevels": {
            position: q3(allocation["replacements"][position]["projected"])
            for position in POSITIONS
        },
        "spearmanRankCorrelation": spearman(baseline_ranks, ranks),
        "top20OverlapCount": len(baseline_top20 & scenario_top20),
        "maximumAbsoluteRankShift": shifts[0]["absoluteRankShift"],
        "largestRankShifts": shifts[:10],
        "topTen": [
            {
                "internalPlayerId": row["player"]["internalPlayerId"],
                "normalizedName": row["player"]["normalizedName"],
                "leagueValueScore": q3(row["score"]),
                "leagueValueRank": row["overallRank"],
            }
            for row in ranked[:10]
        ],
    }


def build_sensitivity_report(
    artifact: dict[str, Any],
    players: list[dict[str, Any]],
    settings: dict[str, Any],
    baseline_allocation: dict[str, Any],
    baseline_ranks: dict[int, int],
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "artifactId": artifact["artifactId"],
        "artifactVersion": ARTIFACT_VERSION,
        "generatedAt": artifact["generatedAt"],
        "status": "PASS",
        "purpose": "Diagnostic only; the published formula remains fixed at 20 FLEX starters.",
        "baseline": {
            "flexSlots": 20,
            "flexPositionCounts": {
                position: baseline_allocation["flexPositionCounts"].get(position, 0)
                for position in FLEX_POSITIONS
            },
            "replacementLevels": {
                position: q3(baseline_allocation["replacements"][position]["projected"])
                for position in POSITIONS
            },
        },
        "scenarios": [
            scenario_summary("flex-minus-2", 18, players, settings, baseline_ranks),
            scenario_summary("flex-plus-2", 22, players, settings, baseline_ranks),
        ],
    }


def validation_checks(
    truth: dict[str, Any],
    artifact: dict[str, Any],
    coverage: dict[str, Any],
    replacement: dict[str, Any],
    settings: dict[str, Any],
) -> list[dict[str, str]]:
    records = artifact["records"]
    record_by_id = {row["internalPlayerId"]: row for row in records}
    truth_by_id = {row["internalPlayerId"]: row for row in truth["players"]}
    unsigned_truth = json.loads(json.dumps(truth))
    unsigned_truth["integrity"].pop("payloadSha256", None)
    calculated_truth_payload_sha256 = sha256_bytes(canonical_json(unsigned_truth))
    checks: list[tuple[str, bool, str]] = [
        ("player_truth_file_hash", sha256_bytes(pretty_json(truth)) == PLAYER_TRUTH_FILE_SHA256, PLAYER_TRUTH_FILE_SHA256),
        ("player_truth_payload_hash", calculated_truth_payload_sha256 == PLAYER_TRUTH_PAYLOAD_SHA256, calculated_truth_payload_sha256),
        ("coverage_199_of_199", coverage["coverage"]["matchedRows"] == EXPECTED_PLAYER_COUNT, str(coverage["coverage"]["matchedRows"])),
        ("top160_159_of_159", coverage["coverage"]["top160MatchedRows"] == EXPECTED_TOP160_COUNT, str(coverage["coverage"]["top160MatchedRows"])),
        ("no_duplicates", not coverage["coverage"]["duplicateInternalPlayerIds"], str(coverage["coverage"]["duplicateInternalPlayerIds"])),
        ("no_orphans", not coverage["coverage"]["orphanLeagueValueIds"], str(coverage["coverage"]["orphanLeagueValueIds"])),
        ("no_missing_records", not coverage["coverage"]["missingLeagueValueIds"], str(coverage["coverage"]["missingLeagueValueIds"])),
        ("keenan_allen_absent", KEENAN_ALLEN_ID not in record_by_id, "internalPlayerId 143 absent"),
        ("jaydon_blue_internal_id_only", JAYDON_BLUE_ID in record_by_id and truth_by_id[JAYDON_BLUE_ID]["espnPlayerId"] is None, "internalPlayerId 190 present; ESPN ID remains null upstream"),
        ("josh_jacobs_unadjusted", record_by_id[JOSH_JACOBS_ID]["projectedLeaguePoints"] == 256.85 and truth_by_id[JOSH_JACOBS_ID]["expectedGames"] == 17.0, "256.850 points; 17 games"),
        ("kayshon_boutte_conflict_preserved", truth_by_id[KAYSHON_BOUTTE_ID]["nflTeam"] == "HOU" and any("source lists NE" in item for item in truth_by_id[KAYSHON_BOUTTE_ID]["limitations"]), "Draft Command HOU; source NE limitation retained"),
        ("keeper_count_and_identity", replacement["keeperPositionCounts"] == {"QB": 1, "RB": 3, "WR": 4, "TE": 2}, str(replacement["keeperPositionCounts"])),
        ("league_geometry", (settings["teamCount"], settings["rounds"], settings["draftSlot"], settings["totalPicks"], settings["tonyTeamId"]) == (10, 16, 5, 160, "team-05"), "10/16/5/160/team-05"),
        ("mandatory_allocation", sum(replacement["mandatoryDemand"].values()) == 60, str(replacement["mandatoryDemand"])),
        ("flex_allocation", replacement["flex"]["allocated"] == 20 and sum(replacement["flex"]["positionCounts"].values()) == 20, str(replacement["flex"]["positionCounts"])),
        ("no_flex_double_counting", all(row["flexAdjustedValue"] == row["marginalValue"] == row["leagueValueScore"] for row in records), "flexAdjustedValue == marginalValue == leagueValueScore"),
        ("numeric_rank_consistency", [row["leagueValueRank"] for row in records] == list(range(1, len(records) + 1)), "records emitted in numeric League Value rank order"),
        ("tie_breaking", records == sorted(records, key=lambda row: (-row["leagueValueScore"], row["internalPlayerId"])), "score descending; ID ascending"),
        ("finite_numeric_values", all(math.isfinite(row[key]) for row in records for key in ("projectedLeaguePoints", "replacementValueByPosition", "marginalValue", "flexAdjustedValue", "leagueValueScore", "confidence")), "all required numeric fields finite"),
        ("roster_fit_separate", all(row["rosterFitAdjustment"] is None for row in records), "all rosterFitAdjustment values null"),
        ("negative_values_retained", any(row["leagueValueScore"] < 0 for row in records), "below-replacement values are not floored"),
        ("market_fields_absent", all(not any(key in row for key in ("espnRank", "espnAdp", "sleeperRank", "ecr", "auctionValue", "opponentIntent")) for row in records), "no market or Opponent Intent fields in records"),
        ("payload_signature", artifact["integrity"]["payloadSha256"] == payload_sha256(artifact), artifact["integrity"]["payloadSha256"]),
    ]
    return [
        {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}
        for name, passed, detail in checks
    ]


def coverage_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    return f"""# Step 15 ESPN League Value Coverage

Status: **{report['status']}**

| Gate | Result |
| --- | ---: |
| Player Truth to League Value | {coverage['matchedRows']}/{coverage['playerTruthRows']} |
| Represented top-160 coverage | {coverage['top160MatchedRows']}/{coverage['top160RepresentedPlayerTruthRows']} |
| Duplicate internal IDs | {len(coverage['duplicateInternalPlayerIds'])} |
| Orphan League Value rows | {len(coverage['orphanLeagueValueIds'])} |
| Missing League Value rows | {len(coverage['missingLeagueValueIds'])} |
| Keeper identities resolved | {report['keepers']['resolvedCount']}/{report['keepers']['approvedCount']} |

Keenan Allen (143) remains absent. Jaydon Blue (190) is present by stable internal ID without an invented ESPN mapping. Josh Jacobs (34) remains unadjusted at 256.850 projected full-PPR points. Kayshon Boutte's upstream HOU/NE team-provenance conflict remains untouched.
"""


def replacement_markdown(report: dict[str, Any]) -> str:
    flex = report["flex"]
    lines = [
        "# Step 15 ESPN League Value Replacement Levels",
        "",
        f"Method: `{report['methodVersion']}`",
        "",
        f"Formula: `{report['formulaVersion']}`",
        "",
        "## Allocation",
        "",
        "| Position | Mandatory demand | Keepers occupying demand | Non-keepers allocated |",
        "| --- | ---: | ---: | ---: |",
    ]
    for position in POSITIONS:
        lines.append(
            f"| {position} | {report['mandatoryDemand'][position]} | {report['keeperPositionCounts'][position]} | {report['mandatoryNonkeeperCounts'][position]} |"
        )
    lines += [
        "",
        f"Exactly {flex['allocated']} FLEX starters were allocated: "
        + ", ".join(f"{position} {flex['positionCounts'][position]}" for position in FLEX_POSITIONS)
        + ".",
        "",
        "Every keeper is initialized on the listed stable team in the first mandatory slot at the keeper's Player Truth position; no keeper requires a FLEX assignment because each team has exactly one keeper.",
        "",
        "## Effective replacement players",
        "",
        "| Position | Player | Internal ID | Points |",
        "| --- | --- | ---: | ---: |",
    ]
    for position in POSITIONS:
        row = report["replacementLevels"][position]
        lines.append(
            f"| {position} | {row['normalizedName']} | {row['internalPlayerId']} | {row['projectedLeaguePoints']:.3f} |"
        )
    lines += [
        "",
        "Replacement is the highest projected available non-keeper at the position after mandatory and FLEX allocation. The replacement player is not counted as a starter.",
        "",
        "Tony's initialized roster contains Jaxson Dart (90) at QB. Roster fit remains null and separate from base League Value.",
    ]
    return "\n".join(lines) + "\n"


def sensitivity_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Step 15 ESPN League Value Sensitivity",
        "",
        "Status: **PASS**",
        "",
        "The diagnostics change only league-wide FLEX demand. They do not tune the published 20-FLEX formula.",
        "",
        "| Scenario | FLEX | RB/WR/TE split | Spearman rank correlation | Top-20 overlap | Max rank shift |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for scenario in report["scenarios"]:
        split = "/".join(str(scenario["flexPositionCounts"][position]) for position in FLEX_POSITIONS)
        lines.append(
            f"| {scenario['label']} | {scenario['flexSlots']} | {split} | {scenario['spearmanRankCorrelation']:.6f} | {scenario['top20OverlapCount']}/20 | {scenario['maximumAbsoluteRankShift']} |"
        )
    lines += [
        "",
        "Baseline replacement values: "
        + ", ".join(
            f"{position} {report['baseline']['replacementLevels'][position]:.3f}"
            for position in POSITIONS
        )
        + ".",
    ]
    return "\n".join(lines) + "\n"


def validation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Step 15 ESPN League Value Validation",
        "",
        f"Overall status: **{report['status']}**",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        detail = check["detail"].replace("|", "\\|")
        lines.append(f"| `{check['check']}` | {check['status']} | {detail} |")
    return "\n".join(lines) + "\n"


def reproduction_markdown(generated_at: str) -> str:
    return f"""# Step 15 deterministic reproduction

From the repository root:

```bash
python3 fantasy-draft/research/step15/build_espn_league_value_step15.py --generated-at {generated_at}
python3 -m unittest fantasy-draft/tests/step15/test_espn_league_value_step15.py
```

The builder refuses to run unless the authoritative Step 14 Player Truth file/payload and runtime League Value schema hashes match their frozen invariants. It uses no current time, network data, market rank, ADP, ECR, auction value, or Opponent Intent input.
"""


def build_manifest(
    artifact: dict[str, Any],
    output_dir: Path,
    report_dir: Path,
    settings_path: Path,
    builder_path: Path,
    deliverables: list[Path],
) -> dict[str, Any]:
    entries = []
    for path in sorted(deliverables, key=lambda value: os.path.relpath(value, output_dir)):
        entries.append(
            {
                "path": os.path.relpath(path, output_dir),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return {
        "schemaVersion": "1.0.0",
        "artifactId": artifact["artifactId"],
        "artifactVersion": artifact["artifactVersion"],
        "generatedAt": artifact["generatedAt"],
        "status": "PASS",
        "canonicalPayloadSha256": artifact["integrity"]["payloadSha256"],
        "settingsHash": artifact["leagueConfiguration"]["settingsHash"],
        "sourceInvariants": {
            "step14Commit": STEP14_COMMIT,
            "step14Tree": STEP14_TREE,
            "playerTruthFileSha256": PLAYER_TRUTH_FILE_SHA256,
            "playerTruthPayloadSha256": PLAYER_TRUTH_PAYLOAD_SHA256,
            "runtimeContractCommit": RUNTIME_CONTRACT_COMMIT,
            "leagueValueSchemaSha256": LEAGUE_VALUE_SCHEMA_SHA256,
            "settingsFileSha256": sha256(settings_path),
            "builderFileSha256": sha256(builder_path),
        },
        "files": entries,
    }


def write_ledger(output_dir: Path, files: list[Path]) -> None:
    lines = [
        f"{sha256(path)}  {os.path.relpath(path, output_dir)}"
        for path in sorted(files, key=lambda value: os.path.relpath(value, output_dir))
    ]
    write_text(output_dir / "SHA256SUMS", "\n".join(lines))


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = (args.output_dir or repo_root / "data/candidate/league-value").resolve()
    report_dir = (args.report_dir or repo_root / "reports").resolve()
    try:
        datetime.fromisoformat(args.generated_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError("--generated-at must be RFC 3339") from error

    truth, settings, truth_path, schema_path, settings_path = load_inputs(repo_root)
    players = runtime_players(truth)
    players_by_id = {row["internalPlayerId"]: row for row in players}
    validate_settings(settings, players_by_id)
    flex_slots = settings["teamCount"] * settings["rosterFormat"]["starters"]["FLEX"]
    allocation = allocate_lineups(players, settings, flex_slots)
    ranked, ranks = calculate_scores(players, allocation)
    artifact = build_artifact(truth, settings, players, allocation, ranked, args.generated_at)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "espn_league_value_step15.json"
    artifact_bytes_first = pretty_json(artifact)
    artifact_bytes_second = pretty_json(json.loads(artifact_bytes_first))
    if artifact_bytes_first != artifact_bytes_second:
        raise RuntimeError("artifact serialization is not byte-identical")
    artifact_path.write_bytes(artifact_bytes_first)

    coverage = build_coverage_report(truth, artifact, players, settings)
    replacement = build_replacement_report(artifact, settings, players, allocation)
    sensitivity = build_sensitivity_report(artifact, players, settings, allocation, ranks)
    checks = validation_checks(truth, artifact, coverage, replacement, settings)
    validation = {
        "schemaVersion": "1.0.0",
        "artifactId": artifact["artifactId"],
        "artifactVersion": ARTIFACT_VERSION,
        "generatedAt": artifact["generatedAt"],
        "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "checks": checks,
    }
    if validation["status"] != "PASS":
        failed = [item["check"] for item in checks if item["status"] != "PASS"]
        raise RuntimeError(f"Step 15 internal validation failed: {failed}")

    coverage_path = output_dir / "espn_league_value_step15_coverage_report.json"
    replacement_path = output_dir / "espn_league_value_step15_replacement_level_report.json"
    sensitivity_path = output_dir / "espn_league_value_step15_sensitivity_report.json"
    validation_path = output_dir / "espn_league_value_step15_validation_report.json"
    proof_path = output_dir / "espn_league_value_step15_deterministic_build_proof.json"
    reproduction_path = output_dir / "REPRODUCTION.md"
    write_json(coverage_path, coverage)
    write_json(replacement_path, replacement)
    write_json(sensitivity_path, sensitivity)
    write_json(validation_path, validation)
    write_json(
        proof_path,
        {
            "schemaVersion": "1.0.0",
            "artifactId": artifact["artifactId"],
            "artifactVersion": ARTIFACT_VERSION,
            "generatedAt": artifact["generatedAt"],
            "serializationBuildCount": 2,
            "byteIdentical": True,
            "firstBuildSha256": sha256_bytes(artifact_bytes_first),
            "secondBuildSha256": sha256_bytes(artifact_bytes_second),
            "canonicalPayloadSha256": artifact["integrity"]["payloadSha256"],
        },
    )
    write_text(reproduction_path, reproduction_markdown(args.generated_at))

    formula_source = repo_root / "reports/STEP15_ESPN_LEAGUE_VALUE_FORMULA.md"
    formula_target = report_dir / "STEP15_ESPN_LEAGUE_VALUE_FORMULA.md"
    if formula_source.resolve() != formula_target.resolve():
        formula_target.write_bytes(formula_source.read_bytes())
    coverage_md_path = report_dir / "STEP15_ESPN_LEAGUE_VALUE_COVERAGE.md"
    replacement_md_path = report_dir / "STEP15_ESPN_LEAGUE_VALUE_REPLACEMENT_LEVELS.md"
    sensitivity_md_path = report_dir / "STEP15_ESPN_LEAGUE_VALUE_SENSITIVITY.md"
    validation_md_path = report_dir / "STEP15_ESPN_LEAGUE_VALUE_VALIDATION.md"
    write_text(coverage_md_path, coverage_markdown(coverage))
    write_text(replacement_md_path, replacement_markdown(replacement))
    write_text(sensitivity_md_path, sensitivity_markdown(sensitivity))
    write_text(validation_md_path, validation_markdown(validation))

    deliverables = [
        artifact_path,
        coverage_path,
        replacement_path,
        sensitivity_path,
        validation_path,
        proof_path,
        reproduction_path,
        formula_target,
        coverage_md_path,
        replacement_md_path,
        sensitivity_md_path,
        validation_md_path,
    ]
    manifest_path = output_dir / "espn_league_value_step15_manifest.json"
    manifest = build_manifest(
        artifact,
        output_dir,
        report_dir,
        settings_path,
        Path(__file__).resolve(),
        deliverables,
    )
    write_json(manifest_path, manifest)
    write_ledger(output_dir, deliverables + [manifest_path])

    print(
        json.dumps(
            {
                "artifact": str(artifact_path),
                "fileSha256": sha256(artifact_path),
                "payloadSha256": artifact["integrity"]["payloadSha256"],
                "settingsHash": artifact["leagueConfiguration"]["settingsHash"],
                "records": len(artifact["records"]),
                "top160": coverage["coverage"]["top160MatchedRows"],
                "flexPositionCounts": replacement["flex"]["positionCounts"],
                "replacementLevels": {
                    position: replacement["replacementLevels"][position]["projectedLeaguePoints"]
                    for position in POSITIONS
                },
                "status": validation["status"],
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
