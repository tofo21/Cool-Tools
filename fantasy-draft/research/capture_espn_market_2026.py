#!/usr/bin/env python3
"""Capture and validate the 2026 ESPN PPR market without mutating app data.

The live source exposes ESPN PPR draft rank and ownership ADP as separate
measurements.  Every run is versioned, hashed, and immutable.  A frozen run
is refused outside the approved draft-night window and whenever blocking QA
fails.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


SEASON = 2026
SCHEMA_VERSION = "espn-market-2026-v1.1"
SCORING_KEY = "PPR"
SOURCE_ID = "espn-fantasy-api-kona-player-info-2026-ppr"
SOURCE_TIER = 1
ESPN_ENDPOINT = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/"
    "segments/0/leaguedefaults/1?view=kona_player_info"
)
LEAGUE_ENDPOINT = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/"
    "segments/0/leagues/167404?view=mSettings&view=mTeam&view=mRoster&view=mDraftDetail"
)
ESPN_FILTER = {
    "players": {
        "filterSlotIds": {"value": [0, 2, 4, 6, 23]},
        "filterStatsForExternalIds": {"value": [2026]},
        "sortDraftRanks": {"sortPriority": 1, "sortAsc": True, "value": "PPR"},
        "limit": 500,
    }
}

POSITION_BY_ID = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
TEAM_BY_ID = {
    0: "FA", 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL",
    7: "DEN", 8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV",
    14: "LAR", 15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG",
    20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF",
    26: "SEA", 27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL",
    34: "HOU",
}
TEAM_ALIASES = {"WSH": "WAS", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
APPROVED_ALIASES = {
    "gabe davis": "gabriel davis",
    "hollywood brown": "marquise brown",
    "tank dell": "nathaniel dell",
    "chig okonkwo": "chigoziem okonkwo",
    "dj chark": "d j chark",
    "dk metcalf": "d k metcalf",
}
EXPECTED_MANAGERS = [
    "Justin Gerkin", "Dan Merrick", "Matt Castleman", "Matt Hull", "Tony Fontana",
    "Matt Runge", "Jon Merrick", "Matt Sloka", "Kyle Cavanaugh", "Brenden Lautenbach",
]
EXPECTED_TONY_PICKS = [5, 16, 25, 36, 45, 56, 65, 76, 85, 96, 105, 116, 125, 136, 145, 156]
EXPECTED_PROFILE = {
    "league_id": "167404",
    "team_count": 10,
    "rounds": 16,
    "draft_type": "standard_snake",
    "scoring_format": "full_ppr",
    "lineup": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "RB_WR_TE_FLEX": 2, "K": 0, "DST": 0},
    "keeper_count_per_team": 1,
    "tony_draft_slot": 5,
}
UNRESOLVED_SCORING_FIELDS = [
    "passing yards", "passing touchdowns", "interceptions", "rushing yards",
    "receiving yards", "receptions", "rushing touchdowns", "receiving touchdowns",
    "two-point conversions", "fumbles", "yardage bonuses", "long-play bonuses",
    "first-down scoring", "return scoring", "custom scoring categories",
    "IR/Stash eligibility and limits",
]
CSV_FIELDS = [
    "season", "capture_timestamp_utc", "capture_timestamp_cdt", "snapshot_status",
    "source_id", "source_url", "source_tier", "scoring_format_key", "espn_player_id",
    "raw_player_name", "normalized_player_name", "nfl_team", "primary_position",
    "eligibility", "espn_official_ppr_rank", "espn_live_draft_room_rank", "espn_adp",
    "espn_adp_rank", "raw_ownership_draft_fields", "rank_adp_gap",
    "draft_command_player_id", "canonical_research_player_id", "mapping_method",
    "mapping_confidence", "unresolved_reason", "notes", "raw_record_hash", "snapshot_id",
]


class CaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class Paths:
    repo: Path
    raw: Path
    derived: Path
    production: Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_paths(repo: Path | None = None) -> Paths:
    root = (repo or repo_root()).resolve()
    return Paths(
        repo=root,
        raw=root / "fantasy-draft/data/raw/espn/2026",
        derived=root / "fantasy-draft/data/derived/espn_market",
        production=root / "fantasy-draft/data/production",
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_team(value: Any) -> str:
    team = str(value or "").upper().strip()
    return TEAM_ALIASES.get(team, team)


def as_number(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def parse_iso_utc(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cdt_label(value: datetime) -> str:
    return value.astimezone(ZoneInfo("America/Chicago")).replace(microsecond=0).isoformat()


def frozen_window_ok(captured: datetime) -> bool:
    local = captured.astimezone(ZoneInfo("America/Chicago"))
    return local.date().isoformat() == "2026-08-31" and (19, 30) <= (local.hour, local.minute) <= (19, 45)


def get_url(url: str, headers: dict[str, str] | None = None, timeout: int = 60) -> tuple[bytes, dict[str, str], int]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), dict(response.headers.items()), int(response.status)


def fetch_market() -> tuple[bytes, dict[str, Any]]:
    filter_text = json.dumps(ESPN_FILTER, separators=(",", ":"))
    headers = {
        "User-Agent": "DraftCommandESPNMarketFreeze/1.0 (+https://github.com/tofo21/Cool-Tools)",
        "x-fantasy-filter": filter_text,
    }
    raw, response_headers, status = get_url(ESPN_ENDPOINT, headers=headers)
    return raw, {
        "request_url": ESPN_ENDPOINT,
        "request_headers": {"x-fantasy-filter": filter_text, "User-Agent": headers["User-Agent"]},
        "http_status": status,
        "response_content_type": response_headers.get("Content-Type"),
        "source_state": "success",
    }


def probe_league_settings() -> dict[str, Any]:
    try:
        raw, headers, status = get_url(LEAGUE_ENDPOINT, headers={"User-Agent": "DraftCommandESPNMarketFreeze/1.0"})
        return {
            "status": "retrieved",
            "http_status": status,
            "endpoint": LEAGUE_ENDPOINT,
            "content_type": headers.get("Content-Type"),
            "raw_sha256": sha256_bytes(raw),
            "payload": json.loads(raw),
        }
    except urllib.error.HTTPError as exc:
        return {
            "status": "authentication_required" if exc.code in {401, 403} else "http_error",
            "http_status": exc.code,
            "endpoint": LEAGUE_ENDPOINT,
            "unresolved_fields": UNRESOLVED_SCORING_FIELDS,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "unavailable",
            "endpoint": LEAGUE_ENDPOINT,
            "error": type(exc).__name__,
            "unresolved_fields": UNRESOLVED_SCORING_FIELDS,
        }


def parse_json_array_assignment(path: Path, marker: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    start = text.index(marker) + len(marker)
    value, _ = json.JSONDecoder().raw_decode(text[start:].lstrip())
    if not isinstance(value, list):
        raise CaptureError(f"{path}: {marker} is not an array")
    return value


def load_internal_players(repo: Path) -> list[dict[str, Any]]:
    path = repo / "fantasy-draft/data/players.js"
    players = parse_json_array_assignment(path, "window.PLAYER_DATA =")
    ids = [int(row["id"]) for row in players]
    if len(ids) != len(set(ids)):
        raise CaptureError("Draft Command player master contains duplicate internal IDs")
    return players


def parse_app_config(repo: Path) -> dict[str, Any]:
    text = (repo / "fantasy-draft/app.js").read_text(encoding="utf-8")
    number = lambda name: int(re.search(rf"const {name} = (\d+);", text).group(1))  # noqa: E731
    picks_match = re.search(r"const TONY_PICKS = \[([^]]+)\];", text)
    keeper_block = re.search(r"const KEEPER_CONFIG = \[(.*?)\n  \];", text, re.S)
    manager_block = re.search(r"const MANAGERS = \[(.*?)\n  \];", text, re.S)
    if not (picks_match and keeper_block and manager_block):
        raise CaptureError("Could not parse the league adapter constants in app.js")
    picks = [int(value) for value in re.findall(r"\d+", picks_match.group(1))]
    keepers = [
        {"team": int(team), "player_id": int(player), "round": int(round_number)}
        for team, player, round_number in re.findall(
            r"\{ team: (\d+), playerId: (\d+), round: (\d+) \}", keeper_block.group(1)
        )
    ]
    managers = re.findall(r'name: "([^"]+)"', manager_block.group(1))
    return {
        "team_count": number("TEAM_COUNT"),
        "rounds": number("ROUNDS"),
        "tony_team": number("TONY_TEAM"),
        "tony_picks": picks,
        "keepers": keepers,
        "managers": managers,
    }


def load_prior_stable_map(path: Path | None) -> dict[int, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {
        int(row["espn_player_id"]): row
        for row in rows
        if row.get("espn_player_id") and row.get("draft_command_player_id")
    }


def default_prior_crosswalk(paths: Paths) -> Path | None:
    candidates = sorted(paths.derived.glob("espn_2026_player_identity_crosswalk_*.csv"))
    return candidates[-1] if candidates else None


def _internal_index(players: list[dict[str, Any]]) -> dict[str, Any]:
    exact: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    name_pos: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_id = {}
    for player in players:
        row = dict(player)
        row["_norm"] = normalize_name(row.get("name"))
        row["_team"] = canonical_team(row.get("team"))
        row["_pos"] = str(row.get("pos") or "").upper()
        by_id[int(row["id"])] = row
        exact[(row["_norm"], row["_team"], row["_pos"])].append(row)
        name_pos[(row["_norm"], row["_pos"])].append(row)
    return {"exact": exact, "name_pos": name_pos, "by_id": by_id}


def map_identity(
    espn_id: int,
    raw_name: str,
    team: str,
    position: str,
    index: dict[str, Any],
    prior: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    normalized = normalize_name(raw_name)
    team = canonical_team(team)
    position = position.upper()
    previous = prior.get(espn_id)
    if previous:
        internal = index["by_id"].get(int(previous["draft_command_player_id"]))
        if internal and internal["_norm"] == normalized and internal["_team"] == team and internal["_pos"] == position:
            return _mapped(internal, "exact stable-ID match", 1.0)

    exact = index["exact"].get((normalized, team, position), [])
    if len(exact) == 1:
        return _mapped(exact[0], "exact normalized-name/team/position match", 0.99)
    if len(exact) > 1:
        return _unmapped("same-name collision after team/position matching")

    alias_target = APPROVED_ALIASES.get(normalized)
    if alias_target:
        alias_hits = index["exact"].get((normalize_name(alias_target), team, position), [])
        if len(alias_hits) == 1:
            return _mapped(alias_hits[0], "approved alias", 0.97)
        if len(alias_hits) > 1:
            return _unmapped("approved alias resolves to multiple internal players")

    same_name = index["name_pos"].get((normalized, position), [])
    if same_name:
        teams = sorted({row["_team"] for row in same_name})
        return _unmapped(f"team conflict: ESPN {team}; Draft Command {','.join(teams)}")
    other_position = [
        row for (name, _), rows in index["name_pos"].items() if name == normalized for row in rows
    ]
    if other_position:
        positions = sorted({row["_pos"] for row in other_position})
        return _unmapped(f"position conflict: ESPN {position}; Draft Command {','.join(positions)}")
    return _unmapped("no Draft Command player match")


def _mapped(internal: dict[str, Any], method: str, confidence: float) -> dict[str, Any]:
    internal_id = int(internal["id"])
    return {
        "draft_command_player_id": internal_id,
        "canonical_research_player_id": f"draft-command:{internal_id}",
        "mapping_method": method,
        "mapping_confidence": confidence,
        "unresolved_reason": None,
    }


def _unmapped(reason: str) -> dict[str, Any]:
    return {
        "draft_command_player_id": None,
        "canonical_research_player_id": None,
        "mapping_method": "unresolved",
        "mapping_confidence": 0.0,
        "unresolved_reason": reason,
    }


def parse_market(
    raw: bytes,
    captured: datetime,
    status: str,
    snapshot_id: str,
    internal_players: list[dict[str, Any]],
    prior_map: dict[int, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(raw)
    source_rows = payload.get("players")
    if not isinstance(source_rows, list) or not source_rows:
        raise CaptureError("ESPN response does not contain a non-empty players array")
    ids = [int(row["id"]) for row in source_rows]
    if len(ids) != len(set(ids)):
        raise CaptureError("ESPN response contains duplicate ESPN player IDs")
    index = _internal_index(internal_players)
    rows, crosswalk = [], []
    for source_row in source_rows:
        player = source_row.get("player") or {}
        espn_id = int(source_row["id"])
        raw_name = str(player.get("fullName") or player.get("displayName") or "").strip()
        position = POSITION_BY_ID.get(as_number(player.get("defaultPositionId")), "UNKNOWN")
        team = TEAM_BY_ID.get(as_number(player.get("proTeamId")), f"ID:{player.get('proTeamId')}")
        ppr = (player.get("draftRanksByRankType") or {}).get("PPR") or {}
        ownership = player.get("ownership") or {}
        rank = as_number(ppr.get("rank"))
        adp = as_number(ownership.get("averageDraftPosition"))
        mapping = map_identity(espn_id, raw_name, team, position, index, prior_map or {})
        row = {
            "season": SEASON,
            "capture_timestamp_utc": iso_z(captured),
            "capture_timestamp_cdt": cdt_label(captured),
            "snapshot_status": status,
            "source_id": SOURCE_ID,
            "source_url": ESPN_ENDPOINT,
            "source_tier": SOURCE_TIER,
            "scoring_format_key": SCORING_KEY,
            "espn_player_id": espn_id,
            "raw_player_name": raw_name,
            "normalized_player_name": normalize_name(raw_name),
            "nfl_team": canonical_team(team),
            "primary_position": position,
            "eligibility": player.get("eligibleSlots") or [],
            "espn_official_ppr_rank": rank,
            "espn_live_draft_room_rank": None,
            "espn_adp": adp,
            "espn_adp_rank": None,
            "raw_ownership_draft_fields": {
                "draftRanksByRankType.PPR": ppr or None,
                "ownership": ownership or None,
            },
            "rank_adp_gap": round(float(adp) - float(rank), 4) if rank is not None and adp is not None else None,
            **mapping,
            "notes": "Live ESPN draft-room order was not separately observable from the public API capture.",
            "raw_record_hash": sha256_bytes(canonical_bytes(source_row)),
            "snapshot_id": snapshot_id,
        }
        rows.append(row)
        crosswalk.append({
            "snapshot_id": snapshot_id,
            "espn_player_id": espn_id,
            "raw_player_name": raw_name,
            "normalized_player_name": row["normalized_player_name"],
            "nfl_team": row["nfl_team"],
            "primary_position": position,
            "draft_command_player_id": mapping["draft_command_player_id"],
            "canonical_research_player_id": mapping["canonical_research_player_id"],
            "mapping_method": mapping["mapping_method"],
            "mapping_confidence": mapping["mapping_confidence"],
            "unresolved_reason": mapping["unresolved_reason"],
        })
    return rows, crosswalk


def top_numeric_union(
    rows: list[dict[str, Any]], threshold: int, *, include_adp: bool = True
) -> list[dict[str, Any]]:
    """Return players whose raw rank or continuous ADP is numerically top-N.

    This deliberately does not derive an ordinal rank from continuous ADP.
    ESPN's ADP saturates near 170, so ADP cannot identify a top-250 universe;
    callers disable ADP for that audit and report the cap explicitly.
    """
    return [
        row for row in rows
        if (row["espn_official_ppr_rank"] is not None and row["espn_official_ppr_rank"] <= threshold)
        or (
            include_adp
            and row["espn_adp"] is not None
            and row["espn_adp"] <= threshold
        )
    ]


def adp_cap_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["espn_adp"]) for row in rows if row["espn_adp"] is not None]
    clustered = sum(169 <= value <= 171 for value in values)
    detected = bool(values) and clustered / len(values) >= 0.20
    return {
        "detected": detected,
        "observed_maximum": max(values) if values else None,
        "rows_between_169_and_171": clustered,
        "percentage_between_169_and_171": clustered / len(values) if values else 0.0,
        "effect": "continuous ESPN ADP cannot identify an ordinal top-250 universe" if detected else None,
    }


def keeper_overall(round_number: int, team: int, team_count: int = 10) -> int:
    return (round_number - 1) * team_count + (team if round_number % 2 else team_count + 1 - team)


def verify_league_and_keepers(
    repo: Path,
    rows: list[dict[str, Any]],
    scoring_probe: dict[str, Any],
) -> dict[str, Any]:
    app = parse_app_config(repo)
    by_internal = {row["draft_command_player_id"]: row for row in rows if row["draft_command_player_id"] is not None}
    internal = {int(row["id"]): row for row in load_internal_players(repo)}
    keepers = []
    for keeper in app["keepers"]:
        player = internal.get(keeper["player_id"])
        market = by_internal.get(keeper["player_id"])
        keepers.append({
            "team_id": keeper["team"],
            "manager": app["managers"][keeper["team"] - 1] if len(app["managers"]) >= keeper["team"] else None,
            "keeper_round": keeper["round"],
            "overall_slot": keeper_overall(keeper["round"], keeper["team"], app["team_count"]),
            "internal_player_id": keeper["player_id"],
            "espn_player_id": market["espn_player_id"] if market else None,
            "player_name": player.get("name") if player else None,
            "position": player.get("pos") if player else None,
            "mapped": bool(market),
        })
    keeper_internal = [row["internal_player_id"] for row in keepers]
    keeper_espn = [row["espn_player_id"] for row in keepers if row["espn_player_id"] is not None]
    adapter_checks = {
        "team_count": app["team_count"] == EXPECTED_PROFILE["team_count"],
        "rounds": app["rounds"] == EXPECTED_PROFILE["rounds"],
        "tony_team": app["tony_team"] == EXPECTED_PROFILE["tony_draft_slot"],
        "tony_pick_calendar": app["tony_picks"] == EXPECTED_TONY_PICKS,
        "manager_order": app["managers"] == EXPECTED_MANAGERS,
        "one_keeper_per_team": sorted(row["team_id"] for row in keepers) == list(range(1, 11)),
        "ten_keeper_rows": len(keepers) == 10,
        "keeper_internal_ids_unique": len(keeper_internal) == len(set(keeper_internal)),
        "keeper_espn_ids_unique": len(keeper_espn) == len(set(keeper_espn)),
    }
    scoring_status = "verified" if scoring_probe.get("status") == "retrieved" else "incomplete_authentication_required"
    return {
        "canonical_profile": EXPECTED_PROFILE,
        "draft_order": EXPECTED_MANAGERS,
        "tony_pick_calendar": EXPECTED_TONY_PICKS,
        "adapter_checks": adapter_checks,
        "keepers": keepers,
        "keeper_coverage": sum(row["mapped"] for row in keepers) / len(keepers) if keepers else 0.0,
        "scoring_verification": {
            "status": scoring_status,
            "probe": {key: value for key, value in scoring_probe.items() if key != "payload"},
            "unresolved_fields": [] if scoring_status == "verified" else UNRESOLVED_SCORING_FIELDS,
            "required_user_capture": None if scoring_status == "verified" else {
                "page": "ESPN league 167404 > League > Settings > Scoring",
                "screenshots": ["Scoring settings (all categories)", "Roster settings including IR/Stash", "Draft settings and keeper rules"],
            },
        },
    }


def build_qa(
    rows: list[dict[str, Any]],
    internal_players: list[dict[str, Any]],
    league: dict[str, Any],
    status: str,
    captured: datetime,
) -> dict[str, Any]:
    mapped = [row for row in rows if row["draft_command_player_id"] is not None]
    mapped_internal_ids = [row["draft_command_player_id"] for row in mapped]
    duplicate_internal = sorted(player for player, count in Counter(mapped_internal_ids).items() if count > 1)
    espn_ids = [row["espn_player_id"] for row in rows]
    duplicate_espn = sorted(player for player, count in Counter(espn_ids).items() if count > 1)
    cap = adp_cap_analysis(rows)
    top160 = top_numeric_union(rows, 160, include_adp=True)
    top250 = top_numeric_union(rows, 250, include_adp=not cap["detected"])
    top160_unresolved = [summary(row) for row in top160 if row["draft_command_player_id"] is None]
    top250_unresolved = [summary(row) for row in top250 if row["draft_command_player_id"] is None]
    relevant = [row for row in rows if row["draft_command_player_id"] is not None]
    internal_count = len(internal_players)
    missing_internal = sorted(
        ({int(row["id"]) for row in internal_players} - set(mapped_internal_ids))
    )
    rank_cov = coverage(relevant, "espn_official_ppr_rank")
    adp_cov = coverage(relevant, "espn_adp")
    dual_count = sum(row["espn_official_ppr_rank"] is not None and row["espn_adp"] is not None for row in relevant)
    dual_cov = dual_count / len(relevant) if relevant else 0.0
    identity_cov = len(set(mapped_internal_ids)) / internal_count if internal_count else 0.0
    same_name_conflicts = [
        summary(row) for row in rows
        if row.get("unresolved_reason") and "collision" in row["unresolved_reason"]
    ]
    team_position_conflicts = [
        summary(row) for row in rows
        if row.get("unresolved_reason") and "conflict" in row["unresolved_reason"]
    ]
    blockers = []
    if duplicate_espn:
        blockers.append(f"duplicate ESPN IDs: {duplicate_espn}")
    if duplicate_internal:
        blockers.append(f"internal IDs assigned to multiple ESPN players: {duplicate_internal}")
    if top160_unresolved:
        blockers.append(f"unresolved top-160 players: {len(top160_unresolved)}")
    if league["keeper_coverage"] < 1:
        blockers.append("one or more keepers did not resolve")
    if not all(league["adapter_checks"].values()):
        blockers.append("league adapter differs from the canonical profile")
    if identity_cov < 0.98:
        blockers.append(f"Draft Command identity coverage {identity_cov:.2%} is below 98%")
    if dual_cov < 0.90:
        blockers.append(f"dual ESPN rank/ADP coverage {dual_cov:.2%} is below 90%")
    if status == "frozen" and not frozen_window_ok(captured):
        blockers.append("frozen capture is outside the approved 2026-08-31 19:30-19:45 CDT window")
    return {
        "schema_version": SCHEMA_VERSION,
        "blocking_conflicts": blockers,
        "release_ready": not blockers,
        "source_row_count": len(rows),
        "draft_command_player_count": internal_count,
        "mapped_draft_command_player_count": len(set(mapped_internal_ids)),
        "position_counts": dict(sorted(Counter(row["primary_position"] for row in rows).items())),
        "rank_coverage": rank_cov,
        "adp_coverage": adp_cov,
        "dual_coverage": {"count": dual_count, "denominator": len(relevant), "percentage": dual_cov},
        "identity_match_coverage": {"count": len(set(mapped_internal_ids)), "denominator": internal_count, "percentage": identity_cov},
        "keeper_coverage": league["keeper_coverage"],
        "top_160_union_count": len(top160),
        "top_160_unresolved": top160_unresolved,
        "top_250_union_count": len(top250),
        "top_250_unresolved": top250_unresolved,
        "adp_cap_analysis": cap,
        "missing_draft_command_player_ids": missing_internal,
        "duplicate_espn_player_ids": duplicate_espn,
        "duplicate_internal_player_ids": duplicate_internal,
        "same_name_conflicts": same_name_conflicts,
        "team_or_position_conflicts": team_position_conflicts,
        "scoring_verification_status": league["scoring_verification"]["status"],
        "notes": [
            "Coverage denominators use the 200-player Draft Command candidate universe; all 500 ESPN source rows are preserved.",
            "Top-160 uses raw ESPN rank <=160 or continuous ESPN ADP <=160; no ordinal ADP is invented.",
            "When the ESPN ADP cap near 170 is detected, top-250 identity QA uses ESPN rank <=250 and reports that continuous ADP cannot identify an ordinal top-250 universe.",
            "Exact live draft-room sort order was not separately observable and is not imputed from API rank.",
        ],
    }


def summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "espn_player_id": row["espn_player_id"],
        "player_name": row["raw_player_name"],
        "team": row["nfl_team"],
        "position": row["primary_position"],
        "espn_rank": row["espn_official_ppr_rank"],
        "espn_adp": row["espn_adp"],
        "reason": row.get("unresolved_reason"),
    }


def coverage(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    count = sum(row.get(field) is not None for row in rows)
    return {"count": count, "denominator": len(rows), "percentage": count / len(rows) if rows else 0.0}


def git_commit(repo: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def ensure_new(path: Path) -> None:
    if path.exists():
        raise CaptureError(f"Refusing to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def write_bytes_new(path: Path, value: bytes) -> None:
    ensure_new(path)
    with path.open("xb") as handle:
        handle.write(value)


def write_json_new(path: Path, value: Any) -> None:
    write_bytes_new(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")


def write_csv_new(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    ensure_new(path)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for original in rows:
            row = dict(original)
            for key, value in list(row.items()):
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value, sort_keys=True, separators=(",", ":"))
            writer.writerow(row)


def artifact_paths(paths: Paths, snapshot_id: str) -> dict[str, Path]:
    return {
        "raw_json": paths.raw / f"espn_market_raw_{snapshot_id}.json",
        "raw_metadata": paths.raw / f"espn_market_raw_{snapshot_id}.metadata.json",
        "snapshot_csv": paths.derived / f"espn_2026_market_snapshot_{snapshot_id}.csv",
        "snapshot_json": paths.derived / f"espn_2026_market_snapshot_{snapshot_id}.json",
        "crosswalk_csv": paths.derived / f"espn_2026_player_identity_crosswalk_{snapshot_id}.csv",
        "aliases_csv": paths.derived / f"espn_2026_alias_adjudications_{snapshot_id}.csv",
        "qa_json": paths.derived / f"espn_2026_market_qa_{snapshot_id}.json",
        "qa_md": paths.derived / f"espn_2026_market_qa_{snapshot_id}.md",
        "league_json": paths.derived / f"espn_2026_league_keeper_verification_{snapshot_id}.json",
        "league_md": paths.derived / f"espn_2026_league_keeper_verification_{snapshot_id}.md",
        "manifest": paths.production / f"espn_2026_market_manifest_{snapshot_id}.json",
    }


def relative(repo: Path, path: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def qa_markdown(snapshot_id: str, qa: dict[str, Any]) -> str:
    blockers = "\n".join(f"- {item}" for item in qa["blocking_conflicts"]) or "- None"
    unresolved = "\n".join(
        f"- {row['player_name']} ({row['team']} {row['position']}): {row['reason']}"
        for row in qa["top_250_unresolved"]
    ) or "- None"
    return f"""# ESPN Market QA — {snapshot_id}

## Release gate

- Ready: **{str(qa['release_ready']).lower()}**
- Source rows: {qa['source_row_count']}
- Draft Command identity coverage: {qa['identity_match_coverage']['percentage']:.2%}
- Rank coverage: {qa['rank_coverage']['percentage']:.2%}
- ADP coverage: {qa['adp_coverage']['percentage']:.2%}
- Dual rank/ADP coverage: {qa['dual_coverage']['percentage']:.2%}
- Keeper coverage: {qa['keeper_coverage']:.2%}
- Exact scoring verification: {qa['scoring_verification_status']}

## Blocking conflicts

{blockers}

## Unresolved top-250 union

{unresolved}
"""


def league_markdown(snapshot_id: str, league: dict[str, Any]) -> str:
    checks = "\n".join(f"- [{'x' if ok else ' '}] {name}" for name, ok in league["adapter_checks"].items())
    keepers = "\n".join(
        f"- Team {row['team_id']} — {row['manager']}: {row['player_name']} "
        f"({row['position']}), R{row['keeper_round']}, overall {row['overall_slot']}, "
        f"internal {row['internal_player_id']}, ESPN {row['espn_player_id']}"
        for row in league["keepers"]
    )
    unresolved = "\n".join(f"- {field}" for field in league["scoring_verification"]["unresolved_fields"]) or "- None"
    return f"""# ESPN League and Keeper Verification — {snapshot_id}

## Repository adapter

{checks}

## Keepers

{keepers}

Keeper identity coverage: **{league['keeper_coverage']:.2%}**

## Exact scoring/settings

Status: **{league['scoring_verification']['status']}**

The unauthenticated league endpoint requires authorization. No credentials were requested or stored.

Unresolved fields:

{unresolved}

Capture these pages if exact scoring is required: ESPN league 167404 → League → Settings → Scoring; roster/IR settings; draft/keeper settings.
"""


def alias_rows(rows: list[dict[str, Any]], snapshot_id: str) -> list[dict[str, Any]]:
    used = {row["normalized_player_name"] for row in rows if row["mapping_method"] == "approved alias"}
    return [
        {
            "snapshot_id": snapshot_id,
            "alias": alias,
            "alias_normalized": normalize_name(alias),
            "canonical_name": canonical,
            "canonical_normalized": normalize_name(canonical),
            "adjudication": "approved alias",
            "used_in_snapshot": normalize_name(alias) in used,
        }
        for alias, canonical in sorted(APPROVED_ALIASES.items())
    ]


def manifest_payload(
    repo: Path,
    snapshot_id: str,
    status: str,
    captured: datetime,
    raw_hash: str,
    artifacts: dict[str, Path],
    rows: list[dict[str, Any]],
    qa: dict[str, Any],
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    hash_keys = [key for key in artifacts if key != "manifest"]
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "status": status,
        "generation_time_utc": iso_z(captured),
        "generation_time_cdt": cdt_label(captured),
        "git_commit": git_commit(repo),
        "sources": [
            {
                "source_id": SOURCE_ID,
                "endpoint": ESPN_ENDPOINT,
                "source_tier": SOURCE_TIER,
                "scoring_key": SCORING_KEY,
                "state": source_metadata.get("source_state", "fixture"),
            },
            {
                "source_id": "espn-league-167404-settings",
                "endpoint": LEAGUE_ENDPOINT,
                "source_tier": SOURCE_TIER,
                "state": qa["scoring_verification_status"],
            },
        ],
        "scoring_key": SCORING_KEY,
        "scoring_verification_status": qa["scoring_verification_status"],
        "raw_hashes": {relative(repo, artifacts["raw_json"]): raw_hash},
        "processed_file_hashes": {relative(repo, artifacts[key]): sha256_file(artifacts[key]) for key in hash_keys},
        "row_counts": {"source": len(rows), "mapped_to_draft_command": qa["mapped_draft_command_player_count"]},
        "position_counts": qa["position_counts"],
        "rank_coverage": qa["rank_coverage"],
        "adp_coverage": qa["adp_coverage"],
        "dual_coverage": qa["dual_coverage"],
        "identity_match_coverage": qa["identity_match_coverage"],
        "keeper_coverage": qa["keeper_coverage"],
        "unresolved_players": qa["top_250_unresolved"],
        "blocking_conflicts": qa["blocking_conflicts"],
        "freshness_status": "current_candidate" if status == "candidate" else "draft_night_frozen",
        "approved_downstream_uses": [
            "ESPN room-price analysis",
            "Opponent Intent available-board inputs",
            "Step 15 league adapter inputs",
            "Step 17 survival inputs",
            "Draft Command display and matching after integration approval",
        ],
        "prohibited_uses": [
            "changing Player Truth",
            "using ADP as a projection",
            "overriding BPA by itself",
            "enabling TAKE/WAIT",
            "silently blending ESPN rank with ESPN ADP",
        ],
        "artifacts": {key: relative(repo, value) for key, value in artifacts.items() if key != "manifest"},
        "manifest_path": relative(repo, artifacts["manifest"]),
    }


def validate_manifest(path: Path, require_status: str | None = None, reject_older_than: str | None = None) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "snapshot_id", "status", "generation_time_utc", "git_commit", "sources",
        "raw_hashes", "processed_file_hashes", "row_counts", "position_counts", "rank_coverage",
        "adp_coverage", "dual_coverage", "identity_match_coverage", "keeper_coverage",
        "blocking_conflicts", "freshness_status", "approved_downstream_uses", "prohibited_uses", "artifacts",
    }
    missing = sorted(required - set(manifest))
    errors = [f"missing manifest fields: {missing}"] if missing else []
    if manifest.get("schema_version") == SCHEMA_VERSION and "scoring_verification_status" not in manifest:
        errors.append("missing manifest field: scoring_verification_status")
    repo = path.resolve().parents[3] if "fantasy-draft" in path.parts else repo_root()
    for rel, expected in {**manifest.get("raw_hashes", {}), **manifest.get("processed_file_hashes", {})}.items():
        artifact = repo / rel
        if not artifact.exists():
            errors.append(f"missing artifact: {rel}")
        elif sha256_file(artifact) != expected:
            errors.append(f"hash mismatch: {rel}")
    artifacts = manifest.get("artifacts", {})
    snapshot_rel = artifacts.get("snapshot_json")
    if snapshot_rel and (repo / snapshot_rel).exists():
        snapshot = json.loads((repo / snapshot_rel).read_text(encoding="utf-8"))
        players = snapshot.get("players") or []
        expected_rows = manifest.get("row_counts", {}).get("source")
        if expected_rows is not None and len(players) != expected_rows:
            errors.append(f"row-count mismatch: snapshot has {len(players)}; manifest says {expected_rows}")
        positions = dict(sorted(Counter(row.get("primary_position") for row in players).items()))
        if manifest.get("position_counts") and positions != manifest["position_counts"]:
            errors.append("position-count mismatch between snapshot and manifest")
    crosswalk_rel = artifacts.get("crosswalk_csv")
    if crosswalk_rel and (repo / crosswalk_rel).exists():
        with (repo / crosswalk_rel).open(newline="", encoding="utf-8") as handle:
            crosswalk = list(csv.DictReader(handle))
        expected_rows = manifest.get("row_counts", {}).get("source")
        if expected_rows is not None and len(crosswalk) != expected_rows:
            errors.append(f"row-count mismatch: crosswalk has {len(crosswalk)}; manifest says {expected_rows}")
        mapped = sum(bool(row.get("draft_command_player_id")) for row in crosswalk)
        expected_mapped = manifest.get("row_counts", {}).get("mapped_to_draft_command")
        if expected_mapped is not None and mapped != expected_mapped:
            errors.append(f"mapped-row mismatch: crosswalk has {mapped}; manifest says {expected_mapped}")
    if require_status and manifest.get("status") != require_status:
        errors.append(f"required status {require_status}; found {manifest.get('status')}")
    if require_status == "frozen" and manifest.get("blocking_conflicts"):
        errors.append("frozen manifest has blocking conflicts")
    if reject_older_than:
        required_time = parse_iso_utc(reject_older_than)
        actual_time = parse_iso_utc(manifest.get("generation_time_utc"))
        if actual_time < required_time:
            errors.append(f"snapshot is stale: {iso_z(actual_time)} < {iso_z(required_time)}")
    return {"valid": not errors, "errors": errors, "manifest": manifest}


def run_capture(args: argparse.Namespace) -> dict[str, Any]:
    captured = parse_iso_utc(args.captured_at)
    if args.status == "frozen" and not frozen_window_ok(captured):
        raise CaptureError("Refusing frozen status outside 2026-08-31 19:30-19:45 CDT")
    paths = default_paths(Path(args.repo) if args.repo else None)
    raw_path = Path(args.fixture).resolve() if args.fixture else None
    if raw_path:
        raw = raw_path.read_bytes()
        source_metadata = {"source_state": "saved_fixture", "fixture_path": str(raw_path)}
    else:
        raw, source_metadata = fetch_market()
    raw_hash = sha256_bytes(raw)
    stamp = captured.strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"espn_2026_{args.status}_{stamp}_{raw_hash[:12]}"
    artifacts = artifact_paths(paths, snapshot_id)
    internal = load_internal_players(paths.repo)
    prior_path = Path(args.prior_crosswalk).resolve() if args.prior_crosswalk else default_prior_crosswalk(paths)
    prior = load_prior_stable_map(prior_path)
    rows, crosswalk = parse_market(raw, captured, args.status, snapshot_id, internal, prior)
    scoring_probe = probe_league_settings() if not args.skip_league_probe else {
        "status": "not_probed", "endpoint": LEAGUE_ENDPOINT, "unresolved_fields": UNRESOLVED_SCORING_FIELDS
    }
    league = verify_league_and_keepers(paths.repo, rows, scoring_probe)
    qa = build_qa(rows, internal, league, args.status, captured)
    if args.status == "frozen" and qa["blocking_conflicts"]:
        raise CaptureError("Refusing frozen snapshot because blocking QA failed: " + "; ".join(qa["blocking_conflicts"]))

    raw_metadata = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "status": args.status,
        "captured_at_utc": iso_z(captured),
        "captured_at_cdt": cdt_label(captured),
        "source_id": SOURCE_ID,
        "source_tier": SOURCE_TIER,
        "scoring_key": SCORING_KEY,
        "raw_sha256": raw_hash,
        "raw_bytes": len(raw),
        "source_request": source_metadata,
        "prior_crosswalk": relative(paths.repo, prior_path) if prior_path and prior_path.is_relative_to(paths.repo) else str(prior_path) if prior_path else None,
    }
    write_bytes_new(artifacts["raw_json"], raw)
    write_json_new(artifacts["raw_metadata"], raw_metadata)
    write_csv_new(artifacts["snapshot_csv"], rows, CSV_FIELDS)
    write_json_new(artifacts["snapshot_json"], {"metadata": raw_metadata, "players": rows})
    crosswalk_fields = list(crosswalk[0].keys()) if crosswalk else []
    write_csv_new(artifacts["crosswalk_csv"], crosswalk, crosswalk_fields)
    aliases = alias_rows(rows, snapshot_id)
    write_csv_new(artifacts["aliases_csv"], aliases, list(aliases[0].keys()))
    write_json_new(artifacts["qa_json"], qa)
    write_bytes_new(artifacts["qa_md"], qa_markdown(snapshot_id, qa).encode("utf-8"))
    write_json_new(artifacts["league_json"], league)
    write_bytes_new(artifacts["league_md"], league_markdown(snapshot_id, league).encode("utf-8"))
    manifest = manifest_payload(paths.repo, snapshot_id, args.status, captured, raw_hash, artifacts, rows, qa, source_metadata)
    write_json_new(artifacts["manifest"], manifest)
    validation = validate_manifest(artifacts["manifest"], require_status=args.status)
    if not validation["valid"]:
        raise CaptureError("Generated manifest failed validation: " + "; ".join(validation["errors"]))
    return {
        "manifest": str(artifacts["manifest"]),
        "snapshot_id": snapshot_id,
        "release_ready": qa["release_ready"],
        "blocking_conflicts": qa["blocking_conflicts"],
        "source_row_count": qa["source_row_count"],
        "identity_match_percentage": qa["identity_match_coverage"]["percentage"],
        "dual_coverage_percentage": qa["dual_coverage"]["percentage"],
        "keeper_coverage": qa["keeper_coverage"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", choices=("candidate", "frozen"), help="Snapshot lifecycle status")
    parser.add_argument("--fixture", help="Use a saved ESPN response instead of the live endpoint")
    parser.add_argument("--captured-at", help="UTC ISO timestamp; defaults to now")
    parser.add_argument("--prior-crosswalk", help="Explicit prior crosswalk for stable ESPN-ID matching")
    parser.add_argument("--repo", help="Repository root override (used by deterministic tests)")
    parser.add_argument("--skip-league-probe", action="store_true", help="Skip the unauthenticated league-settings probe")
    parser.add_argument("--validate-only", metavar="MANIFEST", help="Validate hashes/schema without capturing")
    parser.add_argument("--require-status", choices=("candidate", "frozen"))
    parser.add_argument("--reject-older-than", help="Reject manifest if generated before this UTC ISO timestamp")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.validate_only:
            result = validate_manifest(Path(args.validate_only), args.require_status, args.reject_older_than)
            print(json.dumps({"valid": result["valid"], "errors": result["errors"], "snapshot_id": result["manifest"].get("snapshot_id")}, indent=2))
            return 0 if result["valid"] else 1
        if not args.status:
            raise CaptureError("--status is required unless --validate-only is used")
        result = run_capture(args)
        print(json.dumps(result, indent=2))
        return 0
    except (CaptureError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
