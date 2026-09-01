#!/usr/bin/env python3
"""Regenerate the public-safe synthetic runtime-contract fixture family."""

from __future__ import annotations

import copy
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2] / "research"
sys.path.insert(0, str(RESEARCH))

from runtime_contract_lib import canonical_pretty_bytes, sign_payload  # noqa: E402


GENERATED_AT = "2026-08-31T22:00:00Z"
EFFECTIVE_AT = "2026-08-31T22:00:00Z"
EXPIRES_AT = "2026-09-03T12:00:00Z"
SOURCE_COMMIT = "bfe0bfd000137115b774718851fac999f08bec36"
POSITIONS = ("QB", "RB", "WR", "TE")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_pretty_bytes(value))


def artifact_header(artifact_type: str, artifact_id: str, artifact_version: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "artifactType": artifact_type,
        "artifactId": artifact_id,
        "artifactVersion": artifact_version,
        "generatedAt": GENERATED_AT,
        "effectiveAt": EFFECTIVE_AT,
        "expiresAt": EXPIRES_AT,
        "status": "candidate",
        "integrity": {
            "canonicalization": "draft-command-canonical-json-v1",
            "payloadSha256": "0" * 64,
        },
    }


def player_truth() -> dict:
    players = []
    for index in range(1, 25):
        player_id = 1000 + index
        position = POSITIONS[(index - 1) % len(POSITIONS)]
        points = round(342 - index * 5.75, 2)
        unresolved = index == 24
        player = {
            "internalPlayerId": player_id,
            "draftCommandBoardRank": 200 if unresolved else index,
            "canonicalPlayerKey": f"synthetic.player.{index:02d}",
            "espnPlayerId": None if unresolved else str(900000 + index),
            "normalizedName": f"Synthetic Player {index:02d}",
            "nflTeam": ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")[(index - 1) % 6],
            "position": position,
            "identityMatchMethod": "unresolved" if unresolved else "espn-id",
            "identityConfidence": 0.45 if unresolved else 0.99,
            "projectedFullPprPoints": points,
            "projectedPpg": round(points / 16, 4),
            "expectedGames": 16,
            "availabilityStatus": "questionable" if index == 9 else "available",
            "availabilityConfidence": 0.8 if index == 9 else 0.98,
            "modelConfidence": round(0.94 - index * 0.006, 3),
            "eligibleFeatureFamilies": ["consensus-projection", "football-fundamentals"],
            "quarantinedFeatureFamilies": ["unvalidated-signal"] if index % 7 == 0 else [],
            "provenance": {
                "modelVersion": "synthetic-player-truth-model-v1",
                "sourceArtifactIds": ["synthetic-consensus", "synthetic-fundamentals"],
            },
            "limitations": ["Synthetic fixture; not a player valuation."],
        }
        if index != 6:
            player.update({
                "fullPprPointsP10": round(points * 0.72, 2),
                "fullPprPointsP50": round(points * 0.98, 2),
                "fullPprPointsP90": round(points * 1.24, 2),
                "eliteProbability": round(max(0.05, 0.36 - index * 0.01), 3),
                "starterProbability": round(max(0.25, 0.89 - index * 0.015), 3),
                "bustProbability": round(min(0.5, 0.1 + index * 0.01), 3),
            })
        players.append(player)
    artifact = artifact_header("player-truth", "synthetic-player-truth", "synthetic-pt-v1")
    artifact.update({
        "season": 2026,
        "provenance": {
            "modelVersion": "synthetic-player-truth-model-v1",
            "generator": "generate_fixtures.py",
            "sourceCommits": [SOURCE_COMMIT],
            "sourceArtifactIds": ["synthetic-consensus", "synthetic-fundamentals"],
        },
        "players": players,
    })
    return sign_payload(artifact)


def espn_market(truth: dict) -> dict:
    records = []
    for index, player in enumerate(truth["players"], start=1):
        unresolved = player["espnPlayerId"] is None
        records.append({
            "internalPlayerId": player["internalPlayerId"],
            "espnPlayerId": player["espnPlayerId"],
            "espnDefaultRank": None if index == 7 or unresolved else index,
            "espnContinuousAdp": None if index == 8 or unresolved else round(index + 0.37, 2),
            "liveRoomRank": None,
            "ordinalAdpRank": None,
            "ordinalAdpRankSource": None,
            "mappingConfidence": 0.4 if unresolved else 0.99,
            "captureStatus": "unmapped" if unresolved else "captured",
        })
    eligible = len(records)
    artifact = artifact_header("espn-market", "synthetic-espn-market", "synthetic-market-v1")
    artifact.update({
        "season": 2026,
        "captureTimestamp": "2026-08-31T21:55:00Z",
        "captureStatus": "partial",
        "sourceArtifactId": "synthetic-espn-capture",
        "sourceHash": "a" * 64,
        "coverage": {
            "eligiblePlayerCount": eligible,
            "mappedPlayerCount": sum(item["espnPlayerId"] is not None for item in records),
            "rankCoverage": sum(item["espnDefaultRank"] is not None for item in records) / eligible,
            "adpCoverage": sum(item["espnContinuousAdp"] is not None for item in records) / eligible,
        },
        "records": records,
    })
    return sign_payload(artifact)


def keeper_overall(round_number: int, team: int, team_count: int = 10) -> int:
    return ((round_number - 1) * team_count) + (team if round_number % 2 else team_count + 1 - team)


def league_value(truth: dict) -> dict:
    position_counts = {position: 0 for position in POSITIONS}
    records = []
    for rank, player in enumerate(truth["players"], start=1):
        position = player["position"]
        position_counts[position] += 1
        score = round(204 - rank * 4.125, 3)
        replacement = {"QB": 248, "RB": 174, "WR": 166, "TE": 135}[position]
        records.append({
            "internalPlayerId": player["internalPlayerId"],
            "projectedLeaguePoints": player["projectedFullPprPoints"],
            "replacementValueByPosition": replacement,
            "marginalValue": round(player["projectedFullPprPoints"] - replacement, 3),
            "flexAdjustedValue": round(score - (1.5 if position in ("QB", "TE") else 0), 3),
            "leagueValueScore": score,
            "leagueValueRank": rank,
            "positionalRank": position_counts[position],
            "rosterFitAdjustment": None if rank % 6 == 0 else round((rank % 3 - 1) * 0.4, 2),
            "confidence": round(0.92 - rank * 0.005, 3),
            "status": "candidate",
            "provenance": {
                "formulaVersion": "synthetic-step15-socket-v1",
                "sourceArtifactIds": [truth["artifactId"]],
            },
        })
    keepers = []
    for team in range(1, 11):
        keepers.append({
            "teamId": f"team-{team:02d}",
            "internalPlayerId": 1014 + team,
            "round": 16,
            "overallPick": keeper_overall(16, team),
        })
    artifact = artifact_header("espn-league-value", "synthetic-espn-league-value", "synthetic-lv-v1")
    artifact.update({
        "season": 2026,
        "leagueConfiguration": {
            "leagueId": "synthetic-espn-league",
            "leagueSettingsVersion": "synthetic-settings-v1",
            "settingsHash": "b" * 64,
            "scoringFormat": "full-PPR",
            "rosterFormat": {
                "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 2},
                "bench": 7,
                "ir": 1,
            },
            "replacementLevelMethodVersion": "synthetic-replacement-v1",
            "teamCount": 10,
            "rounds": 16,
            "draftSlot": 5,
            "totalPicks": 160,
            "tonyTeamId": "team-05",
            "keepers": keepers,
        },
        "formula": {
            "formulaVersion": "synthetic-step15-socket-v1",
            "generator": "synthetic-step15-adapter",
            "sourceArtifactIds": [truth["artifactId"]],
            "sourceCommits": [SOURCE_COMMIT],
            "description": "Synthetic numeric outputs that exercise the Step 15 socket; not a production formula.",
        },
        "records": records,
    })
    return sign_payload(artifact)


def opponent_intent(truth: dict, market: dict, league: dict) -> dict:
    opponents = {}
    opponent_teams = [team for team in range(1, 11) if team != 5]
    keeper_by_team = {item["teamId"]: item for item in league["leagueConfiguration"]["keepers"]}
    player_by_id = {item["internalPlayerId"]: item for item in truth["players"]}
    top_ids = [item["internalPlayerId"] for item in truth["players"][:5]]
    probabilities = [0.18, 0.14, 0.10, 0.08, 0.05]
    for label_index, team in enumerate(opponent_teams, start=1):
        team_id = f"team-{team:02d}"
        keeper_id = keeper_by_team[team_id]["internalPlayerId"]
        keeper = player_by_id[keeper_id]
        opponents[team_id] = {
            "teamId": team_id,
            "displayLabel": f"M{label_index:02d}",
            "nextOverallPick": team,
            "currentRoster": [{"internalPlayerId": keeper_id, "position": keeper["position"], "rosterSlot": "KEEPER"}],
            "openRosterPositions": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 2, "BENCH": 7},
            "positionProbabilities": {"QB": 0.10, "RB": 0.35, "WR": 0.40, "TE": 0.15},
            "topFivePlayerProbabilities": [
                {"internalPlayerId": player_id, "probability": probability}
                for player_id, probability in zip(top_ids, probabilities)
            ],
            "otherProbability": 0.45,
            "confidence": round(0.78 - label_index * 0.01, 3),
            "predictionStatus": "contextual",
            "explanatoryDrivers": ["synthetic roster state", "synthetic room price"],
            "limitations": ["Synthetic fixture; not an opponent forecast."],
        }
    target_survival = []
    primary_takers = ("team-01", "team-02", "team-03", "team-04", "team-06")
    secondary_takers = ("team-02", "team-03", "team-04", "team-06", "team-07")
    for index, player_id in enumerate(top_ids):
        taken = round(0.72 - index * 0.11, 3)
        target_survival.append({
            "internalPlayerId": player_id,
            "probabilityTakenBeforeTony": taken,
            "probabilitySurvives": round(1 - taken, 3),
            "mostLikelyTakerTeamId": primary_takers[index],
            "secondMostLikelyTakerTeamId": secondary_takers[index],
        })
    artifact = artifact_header("opponent-intent", "synthetic-opponent-intent", "synthetic-oi-v1")
    artifact.update({
        "modelArtifactVersion": "synthetic-oi-v1",
        "espnLeagueId": league["leagueConfiguration"]["leagueId"],
        "tonyTeamId": "team-05",
        "tonyNextOverallPick": 5,
        "simulation": {"seed": 20260831, "count": 10000},
        "opponents": opponents,
        "targetSurvival": target_survival,
        "tierSurvival": [
            {"tierId": "synthetic-tier-a", "probabilityAtLeastOneSurvives": 0.64, "expectedSurvivors": 1.3},
            {"tierId": "synthetic-tier-b", "probabilityAtLeastOneSurvives": 0.91, "expectedSurvivors": 2.8},
        ],
        "sourceVersions": {
            "playerTruth": truth["artifactVersion"],
            "espnMarket": market["artifactVersion"],
            "leagueValue": league["artifactVersion"],
            "opponentModel": "synthetic-oi-v1",
        },
        "limitations": ["Synthetic fixture; not an opponent forecast."],
    })
    return sign_payload(artifact)


def recompute_league_ranks(league: dict, truth: dict) -> None:
    truth_by_id = {item["internalPlayerId"]: item for item in truth["players"]}
    records = sorted(league["records"], key=lambda item: (-item["leagueValueScore"], item["internalPlayerId"]))
    position_counts = {position: 0 for position in POSITIONS}
    for rank, record in enumerate(records, start=1):
        record["leagueValueRank"] = rank
        position = truth_by_id[record["internalPlayerId"]]["position"]
        position_counts[position] += 1
        record["positionalRank"] = position_counts[position]


def main() -> None:
    truth = player_truth()
    market = espn_market(truth)
    league = league_value(truth)
    opponent = opponent_intent(truth, market, league)
    write_json(HERE / "synthetic_player_truth.json", truth)
    write_json(HERE / "synthetic_espn_market.json", market)
    write_json(HERE / "synthetic_league_value.json", league)
    write_json(HERE / "synthetic_opponent_intent.json", opponent)

    malformed_probabilities = copy.deepcopy(opponent)
    malformed_probabilities["opponents"]["team-01"]["positionProbabilities"]["QB"] = 0.2
    write_json(HERE / "failures" / "malformed_probabilities.json", sign_payload(malformed_probabilities))

    duplicate_truth = copy.deepcopy(truth)
    duplicate_truth["players"].append(copy.deepcopy(duplicate_truth["players"][0]))
    write_json(HERE / "failures" / "duplicate_player_truth.json", sign_payload(duplicate_truth))

    incompatible_truth = copy.deepcopy(truth)
    incompatible_truth["schemaVersion"] = "9.0.0"
    write_json(HERE / "failures" / "incompatible_player_truth.json", sign_payload(incompatible_truth))

    corrupt_market = copy.deepcopy(market)
    corrupt_market["integrity"]["payloadSha256"] = "0" * 64
    write_json(HERE / "failures" / "corrupt_hash_espn_market.json", corrupt_market)

    stale_market = copy.deepcopy(market)
    stale_market["expiresAt"] = "2026-08-30T12:00:00Z"
    write_json(HERE / "failures" / "stale_espn_market.json", sign_payload(stale_market))

    unresolved_league = copy.deepcopy(league)
    unresolved_league["records"] = [item for item in unresolved_league["records"] if item["internalPlayerId"] != 1001]
    recompute_league_ranks(unresolved_league, truth)
    write_json(HERE / "failures" / "top160_missing_league_value.json", sign_payload(unresolved_league))

    duplicate_espn = copy.deepcopy(market)
    duplicate_espn["records"][1]["espnPlayerId"] = duplicate_espn["records"][0]["espnPlayerId"]
    write_json(HERE / "failures" / "duplicate_espn_id.json", sign_payload(duplicate_espn))

    fallback_opponent = copy.deepcopy(opponent)
    fallback_opponent["status"] = "fallback"
    for entry in fallback_opponent["opponents"].values():
        entry["predictionStatus"] = "fallback"
    write_json(HERE / "failures" / "fallback_opponent_intent.json", sign_payload(fallback_opponent))

    sequence = {
        "schemaVersion": "synthetic-draft-sequence/1.0.0",
        "teamCount": 10,
        "rounds": 16,
        "draftSlot": 5,
        "totalPicks": 160,
        "keepers": league["leagueConfiguration"]["keepers"],
        "picks": [
            {"overall": 1, "teamId": "team-01", "internalPlayerId": 1001, "source": "synthetic"},
            {"overall": 2, "teamId": "team-02", "externalPlayerId": "unresolved-synthetic-02", "source": "synthetic", "status": "unresolved"},
            {"overall": 3, "teamId": "team-03", "internalPlayerId": 1003, "source": "synthetic"},
            {"overall": 4, "teamId": "team-04", "internalPlayerId": 1004, "source": "synthetic"},
            {"overall": 5, "teamId": "team-05", "internalPlayerId": 1005, "source": "manual"},
            {"overall": 6, "teamId": "team-06", "internalPlayerId": 1006, "source": "synthetic"},
            {"overall": 7, "teamId": "team-07", "internalPlayerId": 1007, "source": "synthetic"},
            {"overall": 8, "teamId": "team-08", "internalPlayerId": 1008, "source": "synthetic"},
            {"overall": 9, "teamId": "team-09", "internalPlayerId": 1009, "source": "synthetic"},
            {"overall": 10, "teamId": "team-10", "internalPlayerId": 1010, "source": "synthetic"}
        ]
    }
    write_json(HERE / "synthetic_draft_sequence.json", sequence)


if __name__ == "__main__":
    main()
