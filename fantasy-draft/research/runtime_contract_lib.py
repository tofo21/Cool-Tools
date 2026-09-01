#!/usr/bin/env python3
"""Self-contained Draft Command runtime-contract validation and assembly support.

The repository intentionally has no Python dependency manifest. This module therefore
implements the small, documented JSON Schema 2020-12 subset used by the five runtime
contracts, then applies cross-artifact semantic gates that JSON Schema cannot express.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.0.0"
CANONICALIZATION = "draft-command-canonical-json-v1"
PROBABILITY_TOLERANCE = 1e-9
ARTIFACT_TYPES = (
    "player-truth",
    "espn-market",
    "espn-league-value",
    "opponent-intent",
)
SCHEMA_FILES = {
    "player-truth": "player_truth.schema.json",
    "espn-market": "espn_market.schema.json",
    "espn-league-value": "espn_league_value.schema.json",
    "opponent-intent": "opponent_intent.schema.json",
    "draft-runtime-bundle": "draft_runtime_bundle.schema.json",
}
POSITIONS = ("QB", "RB", "WR", "TE")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    artifact: str
    path: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "artifact": self.artifact,
            "path": self.path,
            "message": self.message,
        }


def strict_json_load(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def payload_sha256(value: dict[str, Any]) -> str:
    payload = copy.deepcopy(value)
    integrity = payload.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("payloadSha256", None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sign_payload(value: dict[str, Any]) -> dict[str, Any]:
    signed = copy.deepcopy(value)
    signed.setdefault("integrity", {})["canonicalization"] = CANONICALIZATION
    signed["integrity"]["payloadSha256"] = payload_sha256(signed)
    return signed


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def json_equal(left: Any, right: Any) -> bool:
    try:
        return canonical_json_bytes(left) == canonical_json_bytes(right)
    except (TypeError, ValueError):
        return False


class SchemaSubsetValidator:
    """Validate the JSON Schema keywords used by this contract package.

    Supported keywords: $ref (local), type, const, enum, oneOf, required,
    properties, patternProperties, additionalProperties, min/maxProperties,
    items, min/maxItems, uniqueItems, pattern, minLength, minimum, maximum,
    exclusiveMinimum, exclusiveMaximum, and date-time format.
    """

    def __init__(self, schema: dict[str, Any], artifact: str):
        self.schema = schema
        self.artifact = artifact

    def validate(self, instance: Any) -> list[Issue]:
        errors: list[Issue] = []
        self._walk(instance, self.schema, "$", errors)
        return errors

    def _issue(self, errors: list[Issue], path: str, keyword: str, message: str) -> None:
        errors.append(Issue("BLOCKING", f"SCHEMA_{keyword.upper()}", self.artifact, path, message))

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValueError(f"only local schema refs are supported: {ref}")
        value: Any = self.schema
        for part in ref[2:].split("/"):
            value = value[part.replace("~1", "/").replace("~0", "~")]
        return value

    @staticmethod
    def _matches_type(instance: Any, expected: str) -> bool:
        if expected == "null":
            return instance is None
        if expected == "boolean":
            return isinstance(instance, bool)
        if expected == "integer":
            return isinstance(instance, int) and not isinstance(instance, bool)
        if expected == "number":
            return isinstance(instance, (int, float)) and not isinstance(instance, bool) and math.isfinite(instance)
        if expected == "string":
            return isinstance(instance, str)
        if expected == "array":
            return isinstance(instance, list)
        if expected == "object":
            return isinstance(instance, dict)
        return False

    def _walk(self, instance: Any, schema: Any, path: str, errors: list[Issue]) -> None:
        if isinstance(schema, bool):
            if not schema:
                self._issue(errors, path, "additionalProperties", "value is not permitted")
            return
        if not isinstance(schema, dict):
            self._issue(errors, path, "schema", "schema node is invalid")
            return
        if "$ref" in schema:
            self._walk(instance, self._resolve_ref(schema["$ref"]), path, errors)
            return
        if "oneOf" in schema:
            successful = 0
            for option in schema["oneOf"]:
                candidate: list[Issue] = []
                self._walk(instance, option, path, candidate)
                if not candidate:
                    successful += 1
            if successful != 1:
                self._issue(errors, path, "oneOf", f"value matched {successful} oneOf branches; expected exactly one")
            return
        if "const" in schema and not json_equal(instance, schema["const"]):
            self._issue(errors, path, "const", f"expected constant {schema['const']!r}")
        if "enum" in schema and not any(json_equal(instance, allowed) for allowed in schema["enum"]):
            self._issue(errors, path, "enum", f"value {instance!r} is not in the allowed set")

        expected = schema.get("type")
        if expected is not None:
            expected_types = expected if isinstance(expected, list) else [expected]
            if not any(self._matches_type(instance, item) for item in expected_types):
                self._issue(errors, path, "type", f"expected {expected_types}, received {type(instance).__name__}")
                return

        if isinstance(instance, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    self._issue(errors, path, "required", f"missing required property {key!r}")
            min_properties = schema.get("minProperties")
            max_properties = schema.get("maxProperties")
            if min_properties is not None and len(instance) < min_properties:
                self._issue(errors, path, "minProperties", f"expected at least {min_properties} properties")
            if max_properties is not None and len(instance) > max_properties:
                self._issue(errors, path, "maxProperties", f"expected at most {max_properties} properties")
            properties = schema.get("properties", {})
            patterns = schema.get("patternProperties", {})
            for key, value in instance.items():
                child_path = f"{path}.{key}"
                matched = False
                if key in properties:
                    matched = True
                    self._walk(value, properties[key], child_path, errors)
                for pattern, sub_schema in patterns.items():
                    if re.search(pattern, key):
                        matched = True
                        self._walk(value, sub_schema, child_path, errors)
                if not matched and "additionalProperties" in schema:
                    additional = schema["additionalProperties"]
                    if additional is False:
                        self._issue(errors, child_path, "additionalProperties", "property is not allowed")
                    elif isinstance(additional, dict):
                        self._walk(value, additional, child_path, errors)

        if isinstance(instance, list):
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if min_items is not None and len(instance) < min_items:
                self._issue(errors, path, "minItems", f"expected at least {min_items} items")
            if max_items is not None and len(instance) > max_items:
                self._issue(errors, path, "maxItems", f"expected at most {max_items} items")
            if schema.get("uniqueItems"):
                seen: set[bytes] = set()
                for index, item in enumerate(instance):
                    key = canonical_json_bytes(item)
                    if key in seen:
                        self._issue(errors, f"{path}[{index}]", "uniqueItems", "array item is duplicated")
                    seen.add(key)
            item_schema = schema.get("items")
            if item_schema is not None:
                for index, item in enumerate(instance):
                    self._walk(item, item_schema, f"{path}[{index}]", errors)

        if isinstance(instance, str):
            min_length = schema.get("minLength")
            if min_length is not None and len(instance) < min_length:
                self._issue(errors, path, "minLength", f"string must contain at least {min_length} characters")
            pattern = schema.get("pattern")
            if pattern is not None and re.search(pattern, instance) is None:
                self._issue(errors, path, "pattern", f"string does not match {pattern!r}")
            if schema.get("format") == "date-time" and parse_datetime(instance) is None:
                self._issue(errors, path, "format", "value is not an RFC 3339 date-time with timezone")

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if not math.isfinite(instance):
                self._issue(errors, path, "finite", "number must be finite")
                return
            if "minimum" in schema and instance < schema["minimum"]:
                self._issue(errors, path, "minimum", f"number must be at least {schema['minimum']}")
            if "maximum" in schema and instance > schema["maximum"]:
                self._issue(errors, path, "maximum", f"number must be at most {schema['maximum']}")
            if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
                self._issue(errors, path, "exclusiveMinimum", f"number must be greater than {schema['exclusiveMinimum']}")
            if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
                self._issue(errors, path, "exclusiveMaximum", f"number must be less than {schema['exclusiveMaximum']}")


def load_schema(contracts_dir: Path, artifact_type: str) -> dict[str, Any]:
    return strict_json_load(contracts_dir / SCHEMA_FILES[artifact_type])


def schema_issues(value: Any, contracts_dir: Path, artifact_type: str) -> list[Issue]:
    schema = load_schema(contracts_dir, artifact_type)
    return SchemaSubsetValidator(schema, artifact_type).validate(value)


def duplicate_issues(
    records: Iterable[dict[str, Any]],
    key: str,
    artifact: str,
    *,
    ignore_null: bool = False,
) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[Any, int] = {}
    code_key = re.sub(r"(?<!^)(?=[A-Z])", "_", key).upper()
    for index, record in enumerate(records):
        value = record.get(key)
        if ignore_null and value is None:
            continue
        if value in seen:
            issues.append(Issue(
                "BLOCKING",
                f"DUPLICATE_{code_key}",
                artifact,
                f"$.records[{index}].{key}",
                f"{key} {value!r} duplicates record {seen[value]}",
            ))
        else:
            seen[value] = index
    return issues


def common_semantic_issues(value: dict[str, Any], artifact: str, as_of: datetime) -> list[Issue]:
    issues: list[Issue] = []
    integrity = value.get("integrity")
    if isinstance(integrity, dict):
        expected = integrity.get("payloadSha256")
        actual = payload_sha256(value)
        if expected != actual:
            issues.append(Issue(
                "BLOCKING",
                "HASH_MISMATCH",
                artifact,
                "$.integrity.payloadSha256",
                f"declared payload hash {expected!r} does not match calculated {actual}",
            ))
    status = value.get("status")
    if status == "rejected":
        issues.append(Issue("BLOCKING", "ARTIFACT_REJECTED", artifact, "$.status", "rejected artifacts are not loadable"))
    elif status == "fallback":
        issues.append(Issue("WARNING", "ARTIFACT_FALLBACK", artifact, "$.status", "artifact is explicitly degraded/fallback"))
    expires_at = parse_datetime(value.get("expiresAt"))
    if expires_at is not None and expires_at <= as_of:
        issues.append(Issue(
            "BLOCKING",
            "STALE_ARTIFACT",
            artifact,
            "$.expiresAt",
            f"artifact expired at {value.get('expiresAt')} before validation time {as_of.isoformat()}",
        ))
    return issues


def player_truth_semantic_issues(value: dict[str, Any]) -> list[Issue]:
    players = value.get("players") if isinstance(value.get("players"), list) else []
    issues = duplicate_issues(players, "internalPlayerId", "player-truth")
    issues += duplicate_issues(players, "canonicalPlayerKey", "player-truth")
    issues += duplicate_issues(players, "draftCommandBoardRank", "player-truth")
    issues += duplicate_issues(players, "espnPlayerId", "player-truth", ignore_null=True)
    for index, player in enumerate(players):
        path = f"$.players[{index}]"
        values = [player.get("fullPprPointsP10"), player.get("fullPprPointsP50"), player.get("fullPprPointsP90")]
        present = [item for item in values if item is not None]
        if len(present) >= 2 and present != sorted(present):
            issues.append(Issue("BLOCKING", "DISTRIBUTION_ORDER", "player-truth", path, "P10/P50/P90 values must be nondecreasing when present"))
        eligible = set(player.get("eligibleFeatureFamilies") or [])
        quarantined = set(player.get("quarantinedFeatureFamilies") or [])
        overlap = sorted(eligible & quarantined)
        if overlap:
            issues.append(Issue("BLOCKING", "FEATURE_FAMILY_CONFLICT", "player-truth", path, f"feature families appear in both eligible and quarantined lists: {overlap}"))
    return issues


def espn_market_semantic_issues(value: dict[str, Any]) -> list[Issue]:
    records = value.get("records") if isinstance(value.get("records"), list) else []
    issues = duplicate_issues(records, "internalPlayerId", "espn-market")
    issues += duplicate_issues(records, "espnPlayerId", "espn-market", ignore_null=True)
    for index, record in enumerate(records):
        if record.get("ordinalAdpRank") is not None and not record.get("ordinalAdpRankSource"):
            issues.append(Issue(
                "BLOCKING",
                "ORDINAL_ADP_WITHOUT_SOURCE",
                "espn-market",
                f"$.records[{index}].ordinalAdpRank",
                "ordinal ADP rank is permitted only with an explicit source field",
            ))
        if record.get("ordinalAdpRank") is None and record.get("ordinalAdpRankSource") is not None:
            issues.append(Issue(
                "BLOCKING",
                "ORDINAL_ADP_SOURCE_WITHOUT_VALUE",
                "espn-market",
                f"$.records[{index}].ordinalAdpRankSource",
                "ordinal ADP source must be null when the source supplied no ordinal rank",
            ))
    coverage = value.get("coverage") if isinstance(value.get("coverage"), dict) else {}
    eligible = coverage.get("eligiblePlayerCount")
    if isinstance(eligible, int) and eligible > 0:
        expected_mapped = sum(record.get("espnPlayerId") is not None for record in records)
        expected_rank = sum(record.get("espnDefaultRank") is not None for record in records) / eligible
        expected_adp = sum(record.get("espnContinuousAdp") is not None for record in records) / eligible
        declared = (
            ("mappedPlayerCount", expected_mapped),
            ("rankCoverage", expected_rank),
            ("adpCoverage", expected_adp),
        )
        for key, expected in declared:
            actual = coverage.get(key)
            if not isinstance(actual, (int, float)) or abs(actual - expected) > PROBABILITY_TOLERANCE:
                issues.append(Issue("BLOCKING", "DECLARED_COVERAGE_MISMATCH", "espn-market", f"$.coverage.{key}", f"declared {actual!r}; calculated {expected}"))
    return issues


def league_value_semantic_issues(value: dict[str, Any]) -> list[Issue]:
    records = value.get("records") if isinstance(value.get("records"), list) else []
    issues = duplicate_issues(records, "internalPlayerId", "espn-league-value")
    issues += duplicate_issues(records, "leagueValueRank", "espn-league-value")
    expected_order = sorted(records, key=lambda record: (-record.get("leagueValueScore", float("-inf")), record.get("internalPlayerId", 0)))
    for rank, record in enumerate(expected_order, start=1):
        if record.get("leagueValueRank") != rank:
            issues.append(Issue(
                "BLOCKING",
                "LEAGUE_VALUE_RANK_INCONSISTENT",
                "espn-league-value",
                f"$.records[internalPlayerId={record.get('internalPlayerId')}].leagueValueRank",
                f"numeric League Value score ordering requires rank {rank}, received {record.get('leagueValueRank')}",
            ))
    formula_version = value.get("formula", {}).get("formulaVersion")
    for index, record in enumerate(records):
        if record.get("provenance", {}).get("formulaVersion") != formula_version:
            issues.append(Issue("BLOCKING", "FORMULA_VERSION_MISMATCH", "espn-league-value", f"$.records[{index}].provenance.formulaVersion", "record formula version differs from artifact formula version"))
    config = value.get("leagueConfiguration") if isinstance(value.get("leagueConfiguration"), dict) else {}
    teams = config.get("teamCount")
    rounds = config.get("rounds")
    if isinstance(teams, int) and isinstance(rounds, int) and config.get("totalPicks") != teams * rounds:
        issues.append(Issue("BLOCKING", "DRAFT_GEOMETRY", "espn-league-value", "$.leagueConfiguration.totalPicks", "totalPicks must equal teamCount multiplied by rounds"))
    if isinstance(teams, int) and isinstance(config.get("draftSlot"), int) and config["draftSlot"] > teams:
        issues.append(Issue("BLOCKING", "DRAFT_SLOT", "espn-league-value", "$.leagueConfiguration.draftSlot", "draftSlot is outside the league"))
    keepers = config.get("keepers") if isinstance(config.get("keepers"), list) else []
    issues += duplicate_issues(keepers, "teamId", "espn-league-value")
    issues += duplicate_issues(keepers, "internalPlayerId", "espn-league-value")
    issues += duplicate_issues(keepers, "overallPick", "espn-league-value")
    for index, keeper in enumerate(keepers):
        team_match = re.search(r"([0-9]{2})$", str(keeper.get("teamId", "")))
        team = int(team_match.group(1)) if team_match else None
        round_number = keeper.get("round")
        if isinstance(teams, int) and isinstance(team, int) and isinstance(round_number, int):
            expected = ((round_number - 1) * teams) + (team if round_number % 2 else teams + 1 - team)
            if keeper.get("overallPick") != expected:
                issues.append(Issue("BLOCKING", "KEEPER_GEOMETRY", "espn-league-value", f"$.leagueConfiguration.keepers[{index}].overallPick", f"snake geometry requires overall pick {expected}"))
    return issues


def opponent_intent_semantic_issues(value: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    opponents = value.get("opponents") if isinstance(value.get("opponents"), dict) else {}
    for key, opponent in opponents.items():
        path = f"$.opponents.{key}"
        if opponent.get("teamId") != key:
            issues.append(Issue("BLOCKING", "TEAM_KEY_MISMATCH", "opponent-intent", f"{path}.teamId", "opponent object key must equal stable teamId"))
        position_total = sum(opponent.get("positionProbabilities", {}).values()) if isinstance(opponent.get("positionProbabilities"), dict) else 0
        if abs(position_total - 1) > PROBABILITY_TOLERANCE:
            issues.append(Issue("BLOCKING", "POSITION_PROBABILITY_SUM", "opponent-intent", f"{path}.positionProbabilities", f"position probabilities total {position_total}, expected 1"))
        player_probabilities = opponent.get("topFivePlayerProbabilities") if isinstance(opponent.get("topFivePlayerProbabilities"), list) else []
        player_total = sum(item.get("probability", 0) for item in player_probabilities) + (opponent.get("otherProbability") or 0)
        if abs(player_total - 1) > PROBABILITY_TOLERANCE:
            issues.append(Issue("BLOCKING", "PLAYER_PROBABILITY_SUM", "opponent-intent", f"{path}.topFivePlayerProbabilities", f"top-five plus other totals {player_total}, expected 1"))
        issues += duplicate_issues(player_probabilities, "internalPlayerId", "opponent-intent")
    targets = value.get("targetSurvival") if isinstance(value.get("targetSurvival"), list) else []
    issues += duplicate_issues(targets, "internalPlayerId", "opponent-intent")
    for index, target in enumerate(targets):
        total = (target.get("probabilityTakenBeforeTony") or 0) + (target.get("probabilitySurvives") or 0)
        if abs(total - 1) > PROBABILITY_TOLERANCE:
            issues.append(Issue("BLOCKING", "TAKEN_SURVIVAL_RECONCILIATION", "opponent-intent", f"$.targetSurvival[{index}]", f"taken plus survival totals {total}, expected 1"))
        if target.get("mostLikelyTakerTeamId") == target.get("secondMostLikelyTakerTeamId") and target.get("mostLikelyTakerTeamId") is not None:
            issues.append(Issue("BLOCKING", "TAKER_ORDER", "opponent-intent", f"$.targetSurvival[{index}]", "most-likely and second-most-likely takers must differ"))
    return issues


def artifact_semantic_issues(value: dict[str, Any], artifact: str, as_of: datetime) -> list[Issue]:
    issues = common_semantic_issues(value, artifact, as_of)
    if artifact == "player-truth":
        issues += player_truth_semantic_issues(value)
    elif artifact == "espn-market":
        issues += espn_market_semantic_issues(value)
    elif artifact == "espn-league-value":
        issues += league_value_semantic_issues(value)
    elif artifact == "opponent-intent":
        issues += opponent_intent_semantic_issues(value)
    return issues


def load_and_validate_artifact(
    path: Path,
    contracts_dir: Path,
    artifact: str,
    as_of: datetime,
) -> tuple[dict[str, Any] | None, list[Issue], str | None]:
    try:
        value = strict_json_load(path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return None, [Issue("BLOCKING", "INVALID_JSON", artifact, "$", f"cannot read strict JSON: {error}")], None
    if not isinstance(value, dict):
        return None, [Issue("BLOCKING", "INVALID_ARTIFACT_ROOT", artifact, "$", "artifact root must be an object")], file_sha256(path)
    issues = schema_issues(value, contracts_dir, artifact)
    issues += artifact_semantic_issues(value, artifact, as_of)
    return value, issues, file_sha256(path)


def board_bucket(rank: int) -> str:
    if rank <= 50:
        return "1-50"
    if rank <= 100:
        return "51-100"
    if rank <= 160:
        return "101-160"
    return "161+"


def empty_coverage_slice() -> dict[str, int]:
    return {"eligible": 0, "playerTruth": 0, "marketRank": 0, "marketAdp": 0, "leagueValue": 0}


def calculate_coverage(
    player_truth: dict[str, Any] | None,
    market: dict[str, Any] | None,
    league_value: dict[str, Any] | None,
    unresolved: list[dict[str, Any]],
) -> dict[str, Any]:
    players = player_truth.get("players", []) if player_truth else []
    market_by_id = {item.get("internalPlayerId"): item for item in market.get("records", [])} if market else {}
    league_by_id = {item.get("internalPlayerId"): item for item in league_value.get("records", [])} if league_value else {}
    overall = empty_coverage_slice()
    positions = {position: empty_coverage_slice() for position in POSITIONS}
    ranges = {key: empty_coverage_slice() for key in ("1-50", "51-100", "101-160", "161+")}
    for player in players:
        player_id = player.get("internalPlayerId")
        rank = player.get("draftCommandBoardRank", 9999)
        slices = [overall, positions.get(player.get("position"), empty_coverage_slice()), ranges[board_bucket(rank)]]
        market_record = market_by_id.get(player_id)
        for current in slices:
            current["eligible"] += 1
            current["playerTruth"] += 1
            current["marketRank"] += int(market_record is not None and market_record.get("espnDefaultRank") is not None)
            current["marketAdp"] += int(market_record is not None and market_record.get("espnContinuousAdp") is not None)
            current["leagueValue"] += int(player_id in league_by_id)
    keepers = league_value.get("leagueConfiguration", {}).get("keepers", []) if league_value else []
    player_ids = {player.get("internalPlayerId") for player in players}
    league_ids = set(league_by_id)
    resolved_keepers = sum(keeper.get("internalPlayerId") in player_ids and keeper.get("internalPlayerId") in league_ids for keeper in keepers)
    return {
        "overall": overall,
        "byPosition": positions,
        "byBoardRange": ranges,
        "keeperIdentities": {"resolved": resolved_keepers, "expected": len(keepers)},
        "unresolvedIdentities": sorted(unresolved, key=lambda item: (item["boardRank"], item["artifactType"], item["internalPlayerId"])),
    }


def cross_artifact_issues(
    artifacts: dict[str, dict[str, Any] | None],
    approved_top160_ids: set[int],
) -> tuple[list[Issue], list[dict[str, Any]], dict[str, Any]]:
    issues: list[Issue] = []
    unresolved: list[dict[str, Any]] = []
    truth = artifacts.get("player-truth")
    market = artifacts.get("espn-market")
    league = artifacts.get("espn-league-value")
    opponent = artifacts.get("opponent-intent")
    truth_players = truth.get("players", []) if truth else []
    truth_by_id = {item.get("internalPlayerId"): item for item in truth_players}
    market_records = market.get("records", []) if market else []
    market_by_id = {item.get("internalPlayerId"): item for item in market_records}
    league_records = league.get("records", []) if league else []
    league_by_id = {item.get("internalPlayerId"): item for item in league_records}

    if truth and market and truth.get("season") != market.get("season"):
        issues.append(Issue("BLOCKING", "SEASON_MISMATCH", "contract-set", "$.season", "Player Truth and ESPN market seasons differ"))
    if truth and league and truth.get("season") != league.get("season"):
        issues.append(Issue("BLOCKING", "SEASON_MISMATCH", "contract-set", "$.season", "Player Truth and League Value seasons differ"))

    for player in truth_players:
        player_id = player.get("internalPlayerId")
        board_rank = player.get("draftCommandBoardRank", 9999)
        mapped = player.get("identityMatchMethod") != "unresolved"

        def report_gap(artifact_type: str, reason: str) -> None:
            blocking = board_rank <= 160 and player_id not in approved_top160_ids
            unresolved.append({
                "internalPlayerId": player_id,
                "boardRank": board_rank,
                "artifactType": artifact_type,
                "blocking": blocking,
                "reason": reason,
            })
            if blocking:
                issues.append(Issue("BLOCKING", "TOP160_IDENTITY_GAP", artifact_type, f"internalPlayerId={player_id}", reason))
            else:
                code = "APPROVED_TOP160_IDENTITY_GAP" if board_rank <= 160 else "LOWER_BOARD_IDENTITY_GAP"
                issues.append(Issue("WARNING", code, artifact_type, f"internalPlayerId={player_id}", reason))

        if not mapped:
            report_gap("player-truth", "Player Truth identity remains unresolved")
        market_record = market_by_id.get(player_id)
        if market and market_record is None:
            report_gap("espn-market", "no ESPN market record exists for the stable internal player ID")
        elif market_record is not None:
            truth_espn = player.get("espnPlayerId")
            market_espn = market_record.get("espnPlayerId")
            if truth_espn is not None and market_espn is not None and truth_espn != market_espn:
                report_gap("espn-market", f"ESPN ID mismatch: Player Truth {truth_espn!r}, market {market_espn!r}")
        if mapped and league and player_id not in league_by_id:
            report_gap("espn-league-value", "mapped Player Truth record has no League Value record")

    for artifact_type, records in (("espn-market", market_records), ("espn-league-value", league_records)):
        for record in records:
            if record.get("internalPlayerId") not in truth_by_id:
                issues.append(Issue("WARNING", "UNKNOWN_STABLE_ID", artifact_type, f"internalPlayerId={record.get('internalPlayerId')}", "record is excluded because it cannot join by stable ID; name-only joins are forbidden"))

    if truth and league:
        position_groups: dict[str, list[dict[str, Any]]] = {position: [] for position in POSITIONS}
        for record in league_records:
            player = truth_by_id.get(record.get("internalPlayerId"))
            if player and player.get("position") in position_groups:
                position_groups[player["position"]].append(record)
        for position, records in position_groups.items():
            for rank, record in enumerate(sorted(records, key=lambda item: (-item["leagueValueScore"], item["internalPlayerId"])), start=1):
                if record.get("positionalRank") != rank:
                    issues.append(Issue("BLOCKING", "POSITIONAL_RANK_INCONSISTENT", "espn-league-value", f"internalPlayerId={record.get('internalPlayerId')}", f"numeric score ordering within {position} requires positional rank {rank}"))

    if league:
        config = league.get("leagueConfiguration", {})
        expected_geometry = {"teamCount": 10, "rounds": 16, "draftSlot": 5, "totalPicks": 160, "tonyTeamId": "team-05"}
        for key, expected in expected_geometry.items():
            if config.get(key) != expected:
                issues.append(Issue("BLOCKING", "LEAGUE_GEOMETRY_MISMATCH", "espn-league-value", f"$.leagueConfiguration.{key}", f"expected {expected!r}, received {config.get(key)!r}"))
        for keeper in config.get("keepers", []):
            player_id = keeper.get("internalPlayerId")
            if player_id not in truth_by_id or player_id not in league_by_id:
                issues.append(Issue("BLOCKING", "KEEPER_IDENTITY_UNRESOLVED", "contract-set", f"keeper={player_id}", "keeper must resolve in both Player Truth and League Value"))

    if opponent and league:
        config = league.get("leagueConfiguration", {})
        if opponent.get("espnLeagueId") != config.get("leagueId"):
            issues.append(Issue("BLOCKING", "LEAGUE_ID_MISMATCH", "opponent-intent", "$.espnLeagueId", "Opponent Intent league ID differs from League Value adapter output"))
        if opponent.get("tonyTeamId") != config.get("tonyTeamId"):
            issues.append(Issue("BLOCKING", "TONY_TEAM_MISMATCH", "opponent-intent", "$.tonyTeamId", "Opponent Intent Tony team differs from league configuration"))
        expected_teams = {f"team-{team:02d}" for team in range(1, config.get("teamCount", 0) + 1)} - {config.get("tonyTeamId")}
        actual_teams = set(opponent.get("opponents", {}))
        if actual_teams != expected_teams:
            issues.append(Issue("BLOCKING", "OPPONENT_TEAM_SET", "opponent-intent", "$.opponents", f"expected stable opponent keys {sorted(expected_teams)}, received {sorted(actual_teams)}"))
        expected_versions = {
            "playerTruth": truth.get("artifactVersion") if truth else None,
            "espnMarket": market.get("artifactVersion") if market else None,
            "leagueValue": league.get("artifactVersion"),
            "opponentModel": opponent.get("modelArtifactVersion"),
        }
        for key, expected in expected_versions.items():
            if expected is not None and opponent.get("sourceVersions", {}).get(key) != expected:
                issues.append(Issue("BLOCKING", "SOURCE_VERSION_MISMATCH", "opponent-intent", f"$.sourceVersions.{key}", f"expected {expected!r}"))

    if opponent:
        opponent_ids = set(opponent.get("opponents", {}))
        seen_roster_players: dict[int, str] = {}
        for team_id, entry in opponent.get("opponents", {}).items():
            for roster_player in entry.get("currentRoster", []):
                player_id = roster_player.get("internalPlayerId")
                if player_id not in truth_by_id:
                    issues.append(Issue("WARNING", "OPPONENT_ROSTER_UNKNOWN_ID", "opponent-intent", f"$.opponents.{team_id}.currentRoster", f"player {player_id} is excluded from the join"))
                elif roster_player.get("position") != truth_by_id[player_id].get("position"):
                    issues.append(Issue("BLOCKING", "OPPONENT_ROSTER_POSITION_MISMATCH", "opponent-intent", f"$.opponents.{team_id}.currentRoster", f"player {player_id} position differs from Player Truth"))
                if player_id in seen_roster_players and seen_roster_players[player_id] != team_id:
                    issues.append(Issue("BLOCKING", "DUPLICATE_SIMULATED_PLAYER", "opponent-intent", f"internalPlayerId={player_id}", "player appears on more than one opponent roster"))
                seen_roster_players[player_id] = team_id
            for index, player_probability in enumerate(entry.get("topFivePlayerProbabilities", [])):
                player_id = player_probability.get("internalPlayerId")
                if player_id not in truth_by_id:
                    issues.append(Issue("WARNING", "OPPONENT_PLAYER_UNKNOWN_ID", "opponent-intent", f"$.opponents.{team_id}.topFivePlayerProbabilities[{index}]", f"player {player_id} is folded into otherProbability; later probabilities remain usable"))
        for index, target in enumerate(opponent.get("targetSurvival", [])):
            if target.get("internalPlayerId") not in truth_by_id:
                issues.append(Issue("WARNING", "OPPONENT_TARGET_UNKNOWN_ID", "opponent-intent", f"$.targetSurvival[{index}]", "target is excluded from the join; later targets remain usable"))
            for key in ("mostLikelyTakerTeamId", "secondMostLikelyTakerTeamId"):
                taker = target.get(key)
                if taker is not None and taker not in opponent_ids:
                    issues.append(Issue("BLOCKING", "UNKNOWN_TAKER_TEAM", "opponent-intent", f"$.targetSurvival[{index}].{key}", f"unknown stable team ID {taker!r}"))

    coverage = calculate_coverage(truth, market, league, unresolved)
    return issues, unresolved, coverage


def count_issues(issues: Iterable[Issue]) -> dict[str, int]:
    result = {"BLOCKING": 0, "WARNING": 0, "INFO": 0}
    for issue in issues:
        result[issue.severity] = result.get(issue.severity, 0) + 1
    return result


def validate_contract_set(
    *,
    contracts_dir: Path,
    player_truth_path: Path | None,
    espn_market_path: Path | None,
    league_value_path: Path | None,
    opponent_intent_path: Path | None,
    as_of: datetime,
    allow_missing_espn_market: bool = False,
    allow_missing_opponent_intent: bool = False,
    approved_top160_ids: set[int] | None = None,
) -> dict[str, Any]:
    paths = {
        "player-truth": player_truth_path,
        "espn-market": espn_market_path,
        "espn-league-value": league_value_path,
        "opponent-intent": opponent_intent_path,
    }
    optional = {
        "espn-market": allow_missing_espn_market,
        "opponent-intent": allow_missing_opponent_intent,
    }
    artifacts: dict[str, dict[str, Any] | None] = {}
    file_hashes: dict[str, str | None] = {}
    issues: list[Issue] = []
    for artifact, path in paths.items():
        if path is None:
            artifacts[artifact] = None
            file_hashes[artifact] = None
            if optional.get(artifact, False):
                issues.append(Issue("WARNING", "MISSING_OPTIONAL_ARTIFACT", artifact, "$", "artifact is absent; the associated feature must use its documented fallback"))
            else:
                issues.append(Issue("BLOCKING", "MISSING_REQUIRED_ARTIFACT", artifact, "$", "artifact path is required for promotion"))
            continue
        if not path.exists():
            artifacts[artifact] = None
            file_hashes[artifact] = None
            if optional.get(artifact, False):
                issues.append(Issue("WARNING", "MISSING_OPTIONAL_ARTIFACT", artifact, str(path), "artifact file is absent; the associated feature must use its documented fallback"))
            else:
                issues.append(Issue("BLOCKING", "MISSING_REQUIRED_ARTIFACT", artifact, str(path), "artifact file does not exist"))
            continue
        value, artifact_issues, digest = load_and_validate_artifact(path, contracts_dir, artifact, as_of)
        artifacts[artifact] = value
        file_hashes[artifact] = digest
        issues.extend(artifact_issues)
    cross_issues, unresolved, coverage = cross_artifact_issues(artifacts, approved_top160_ids or set())
    issues.extend(cross_issues)
    issues = sorted(issues, key=lambda item: ({"BLOCKING": 0, "WARNING": 1, "INFO": 2}.get(item.severity, 3), item.code, item.artifact, item.path, item.message))
    counts = count_issues(issues)
    return {
        "promotionEligible": counts["BLOCKING"] == 0,
        "asOf": as_of.isoformat().replace("+00:00", "Z"),
        "artifacts": artifacts,
        "paths": paths,
        "fileHashes": file_hashes,
        "issues": issues,
        "issueCounts": counts,
        "unresolved": unresolved,
        "coverage": coverage,
    }


def public_validation_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "promotionEligible": result["promotionEligible"],
        "asOf": result["asOf"],
        "issueCounts": result["issueCounts"],
        "issues": [issue.as_dict() for issue in result["issues"]],
        "coverage": result["coverage"],
        "inputHashes": {key: value for key, value in result["fileHashes"].items()},
    }


def collect_source_commits(artifacts: dict[str, dict[str, Any] | None]) -> list[str]:
    commits: set[str] = set()
    truth = artifacts.get("player-truth") or {}
    commits.update(truth.get("provenance", {}).get("sourceCommits", []))
    league = artifacts.get("espn-league-value") or {}
    commits.update(league.get("formula", {}).get("sourceCommits", []))
    return sorted(commits)


def source_artifact_entries(result: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for artifact_type in ARTIFACT_TYPES:
        artifact = result["artifacts"].get(artifact_type)
        if not artifact:
            continue
        entries.append({
            "artifactType": artifact_type,
            "artifactId": artifact["artifactId"],
            "artifactVersion": artifact["artifactVersion"],
            "schemaVersion": artifact["schemaVersion"],
            "status": artifact["status"],
            "fileSha256": result["fileHashes"][artifact_type],
            "payloadSha256": artifact["integrity"]["payloadSha256"],
        })
    return entries


def assemble_runtime_bundle(result: dict[str, Any]) -> dict[str, Any]:
    artifacts = result["artifacts"]
    truth = artifacts["player-truth"]
    league = artifacts["espn-league-value"]
    market = artifacts.get("espn-market")
    opponent = artifacts.get("opponent-intent")
    if not truth or not league:
        raise ValueError("Player Truth and League Value artifacts are required to assemble a bundle")
    sources = source_artifact_entries(result)
    signature_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "sources": [{"artifactType": item["artifactType"], "fileSha256": item["fileSha256"]} for item in sources],
        "leagueId": league["leagueConfiguration"]["leagueId"],
    }
    bundle_version = f"runtime-{sha256_bytes(canonical_json_bytes(signature_payload))[:16]}"
    generated_at = max(
        artifact["generatedAt"]
        for artifact in artifacts.values()
        if artifact is not None
    )
    degraded = market is None or opponent is None or any(artifact.get("status") == "fallback" for artifact in artifacts.values() if artifact)
    player_records = []
    for player in sorted(truth["players"], key=lambda item: (item["draftCommandBoardRank"], item["internalPlayerId"])):
        player_records.append({
            "internalPlayerId": player["internalPlayerId"],
            "boardRank": player["draftCommandBoardRank"],
            "canonicalPlayerKey": player["canonicalPlayerKey"],
            "espnPlayerId": player["espnPlayerId"],
            "name": player["normalizedName"],
            "nflTeam": player["nflTeam"],
            "position": player["position"],
            "identity": {"method": player["identityMatchMethod"], "confidence": player["identityConfidence"]},
            "outcome": {
                "projectedFullPprPoints": player["projectedFullPprPoints"],
                "projectedPpg": player["projectedPpg"],
                "expectedGames": player["expectedGames"],
                "p10": player.get("fullPprPointsP10"),
                "p50": player.get("fullPprPointsP50"),
                "p90": player.get("fullPprPointsP90"),
                "eliteProbability": player.get("eliteProbability"),
                "starterProbability": player.get("starterProbability"),
                "bustProbability": player.get("bustProbability"),
            },
            "availability": {"status": player["availabilityStatus"], "confidence": player["availabilityConfidence"]},
            "modelConfidence": player["modelConfidence"],
            "features": {"eligible": player["eligibleFeatureFamilies"], "quarantined": player["quarantinedFeatureFamilies"]},
            "provenance": player["provenance"],
            "limitations": player["limitations"],
        })
    truth_ids = {player["internalPlayerId"] for player in truth["players"]}
    market_records = []
    if market:
        for record in sorted(market["records"], key=lambda item: item["internalPlayerId"]):
            if record["internalPlayerId"] not in truth_ids:
                continue
            market_records.append({
                "internalPlayerId": record["internalPlayerId"],
                "espnPlayerId": record["espnPlayerId"],
                "defaultRank": record["espnDefaultRank"],
                "continuousAdp": record["espnContinuousAdp"],
                "liveRoomRank": record["liveRoomRank"],
                "ordinalAdpRank": record["ordinalAdpRank"],
                "captureStatus": record["captureStatus"],
                "mappingConfidence": record["mappingConfidence"],
            })
    league_records = []
    for record in sorted(league["records"], key=lambda item: item["internalPlayerId"]):
        if record["internalPlayerId"] not in truth_ids:
            continue
        league_records.append({key: record[key] for key in (
            "internalPlayerId",
            "projectedLeaguePoints",
            "replacementValueByPosition",
            "marginalValue",
            "flexAdjustedValue",
            "leagueValueScore",
            "leagueValueRank",
            "positionalRank",
            "rosterFitAdjustment",
            "confidence",
            "status",
        )})
    opponent_payload = None
    if opponent:
        target_survival = [item for item in opponent["targetSurvival"] if item["internalPlayerId"] in truth_ids]
        sanitized_opponents = {}
        for team_id, entry in opponent["opponents"].items():
            sanitized = copy.deepcopy(entry)
            sanitized["currentRoster"] = [item for item in sanitized["currentRoster"] if item["internalPlayerId"] in truth_ids]
            unknown_probability = sum(
                item["probability"]
                for item in sanitized["topFivePlayerProbabilities"]
                if item["internalPlayerId"] not in truth_ids
            )
            sanitized["topFivePlayerProbabilities"] = [
                item for item in sanitized["topFivePlayerProbabilities"]
                if item["internalPlayerId"] in truth_ids
            ]
            sanitized["otherProbability"] = round(sanitized["otherProbability"] + unknown_probability, 12)
            sanitized_opponents[team_id] = sanitized
        opponent_payload = {
            "modelArtifactVersion": opponent["modelArtifactVersion"],
            "simulation": opponent["simulation"],
            "opponents": sanitized_opponents,
            "targetSurvival": target_survival,
            "tierSurvival": opponent["tierSurvival"],
        }
    config = league["leagueConfiguration"]
    limitations = set()
    for player in truth["players"]:
        limitations.update(player.get("limitations", []))
    if opponent:
        limitations.update(opponent.get("limitations", []))
    for issue in result["issues"]:
        if issue.severity == "WARNING":
            limitations.add(f"{issue.code}: {issue.message}")
    bundle = {
        "schemaVersion": SCHEMA_VERSION,
        "artifactType": "draft-runtime-bundle",
        "bundleVersion": bundle_version,
        "generatedAt": generated_at,
        "status": "fallback" if degraded else "candidate",
        "overallStatus": "degraded" if degraded else "ready",
        "modelState": "fallback" if degraded else "ready",
        "sourceCommits": collect_source_commits(artifacts),
        "sourceArtifacts": sources,
        "coverage": result["coverage"],
        "confidencePolicy": {
            "playerTruthMinimum": 0.6,
            "identityMinimum": 0.8,
            "leagueValueMinimum": 0.6,
            "opponentPredictionLabels": ["calibrated", "contextual", "unvalidated", "fallback"],
            "nullMeansMissing": True,
        },
        "leagueConfiguration": {
            "leagueId": config["leagueId"],
            "leagueSettingsVersion": config["leagueSettingsVersion"],
            "settingsHash": config["settingsHash"],
            "scoringFormat": config["scoringFormat"],
            "rosterFormat": config["rosterFormat"],
            "teamCount": config["teamCount"],
            "rounds": config["rounds"],
            "draftSlot": config["draftSlot"],
            "totalPicks": config["totalPicks"],
            "tonyTeamId": config["tonyTeamId"],
            "tonyFirstPick": config["draftSlot"],
            "keepers": config["keepers"],
        },
        "playerRecords": player_records,
        "marketRecords": market_records,
        "leagueValueRecords": league_records,
        "opponentIntent": opponent_payload,
        "featureAvailability": {
            "playerTruth": True,
            "leagueValue": True,
            "espnRank": any(item["defaultRank"] is not None for item in market_records),
            "espnAdp": any(item["continuousAdp"] is not None for item in market_records),
            "opponentIntent": opponent_payload is not None,
            "roomSurvival": opponent_payload is not None,
            "manualDraft": True,
        },
        "knownLimitations": sorted(limitations),
        "fallbackPolicy": {
            "playerTruthFailure": "provisional-labeled-valuation",
            "espnMarketFailure": "manual-board-without-market",
            "leagueValueFailure": "provisional-labeled-valuation",
            "opponentIntentFailure": "hide-or-downgrade-threats",
            "playerMismatch": "exclude-affected-join-and-continue",
            "bundleIncompatibility": "reject-bundle-preserve-draft-tracking",
        },
        "compatibility": {
            "applicationId": "draft-command",
            "minimumApplicationRelease": "post-runtime-contract-integration",
            "supportedSchemaMajor": 1,
            "requiredCapabilities": [
                "definite-model-state",
                "numeric-league-value-sort",
                "separate-espn-rank-adp",
                "stable-id-only-joins",
            ],
            "persistencePolicy": "bundle-fetch-only-no-localStorage",
        },
    }
    return bundle


def validation_report_markdown(result: dict[str, Any], title: str = "Draft Runtime Artifact Validation") -> str:
    counts = result["issueCounts"]
    gate = "PASS" if result["promotionEligible"] else "FAIL"
    coverage = result["coverage"]
    lines = [
        f"# {title}",
        "",
        f"- Promotion gate: **{gate}**",
        f"- Validation time: `{result['asOf']}`",
        f"- Blocking issues: **{counts['BLOCKING']}**",
        f"- Warnings: **{counts['WARNING']}**",
        f"- Informational findings: **{counts['INFO']}**",
        "",
        "## Input hashes",
        "",
        "| Artifact | SHA-256 |",
        "| --- | --- |",
    ]
    for artifact in ARTIFACT_TYPES:
        lines.append(f"| {artifact} | `{result['fileHashes'].get(artifact) or 'missing'}` |")
    lines += [
        "",
        "## Coverage",
        "",
        "| Slice | Eligible | Player Truth | ESPN rank | ESPN ADP | League Value |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    def coverage_row(label: str, item: dict[str, int]) -> str:
        return f"| {label} | {item['eligible']} | {item['playerTruth']} | {item['marketRank']} | {item['marketAdp']} | {item['leagueValue']} |"

    lines.append(coverage_row("Overall", coverage["overall"]))
    for position in POSITIONS:
        lines.append(coverage_row(position, coverage["byPosition"][position]))
    for board_range in ("1-50", "51-100", "101-160", "161+"):
        lines.append(coverage_row(f"Board {board_range}", coverage["byBoardRange"][board_range]))
    keepers = coverage["keeperIdentities"]
    lines += [
        "",
        f"Keeper identities: **{keepers['resolved']}/{keepers['expected']}** resolved.",
        "",
        "## Unresolved identities",
        "",
    ]
    if coverage["unresolvedIdentities"]:
        lines += [
            "| Internal ID | Board rank | Artifact | Blocking | Reason |",
            "| ---: | ---: | --- | --- | --- |",
        ]
        for item in coverage["unresolvedIdentities"]:
            lines.append(f"| {item['internalPlayerId']} | {item['boardRank']} | {item['artifactType']} | {'yes' if item['blocking'] else 'no'} | {item['reason']} |")
    else:
        lines.append("None.")
    lines += ["", "## Gate findings", ""]
    if result["issues"]:
        lines += [
            "| Severity | Code | Artifact | Path | Finding |",
            "| --- | --- | --- | --- | --- |",
        ]
        for issue in result["issues"]:
            message = issue.message.replace("|", "\\|")
            lines.append(f"| {issue.severity} | `{issue.code}` | {issue.artifact} | `{issue.path}` | {message} |")
    else:
        lines.append("No findings.")
    lines += [
        "",
        "## Future real-artifact benchmark",
        "",
        "The known ESPN candidate benchmark is 199/200 Draft Command identities matched, 10/10 keepers resolved, zero unresolved raw ESPN top-160 players, and zero unresolved raw ranked top-250 players. Jaydon Blue was the sole Draft Command-only miss and was absent from ESPN's 500-player payload. This benchmark is not synthetic data and is not used to manufacture a passing result.",
        "",
    ]
    return "\n".join(lines)


def validate_runtime_bundle(bundle: dict[str, Any], contracts_dir: Path) -> list[Issue]:
    issues = schema_issues(bundle, contracts_dir, "draft-runtime-bundle")
    player_ids = [item.get("internalPlayerId") for item in bundle.get("playerRecords", [])]
    market_ids = [item.get("internalPlayerId") for item in bundle.get("marketRecords", [])]
    league_ids = [item.get("internalPlayerId") for item in bundle.get("leagueValueRecords", [])]
    if len(player_ids) != len(set(player_ids)):
        issues.append(Issue("BLOCKING", "DUPLICATE_INTERNAL_PLAYER_ID", "draft-runtime-bundle", "$.playerRecords", "player IDs must be unique"))
    if len(market_ids) != len(set(market_ids)):
        issues.append(Issue("BLOCKING", "DUPLICATE_INTERNAL_PLAYER_ID", "draft-runtime-bundle", "$.marketRecords", "market IDs must be unique"))
    if len(league_ids) != len(set(league_ids)):
        issues.append(Issue("BLOCKING", "DUPLICATE_INTERNAL_PLAYER_ID", "draft-runtime-bundle", "$.leagueValueRecords", "League Value IDs must be unique"))
    if set(market_ids) - set(player_ids) or set(league_ids) - set(player_ids):
        issues.append(Issue("BLOCKING", "RUNTIME_ORPHAN_JOIN", "draft-runtime-bundle", "$", "runtime child records must join to playerRecords by stable ID"))
    if bundle.get("modelState") == "loading":
        issues.append(Issue("BLOCKING", "INDEFINITE_LOADING_STATE", "draft-runtime-bundle", "$.modelState", "runtime contract requires a definite ready, fallback, or rejected state"))
    return issues
