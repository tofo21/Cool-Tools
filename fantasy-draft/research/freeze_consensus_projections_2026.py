#!/usr/bin/env python3
"""Build the frozen 2026 consensus component-projection package.

The build is deliberately offline. It reads only the frozen raw inputs committed
with this branch, preserves source missingness and explicit zeroes, and writes a
deterministic Step 14 handoff bundle.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import shutil
import statistics
import tempfile
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


CAPTURE_TAG = "20260901T005951Z"
CAPTURE_TIMESTAMP = "2026-09-01T00:59:51Z"
WORKBOOK_FILENAME = f"2026_FantasyFootball_0.4_elboberto_{CAPTURE_TAG}.xlsm"
DIRECT_FILENAME = f"fantasypros_2026_{{position}}_{CAPTURE_TAG}.html"
WORKBOOK_URL = (
    "https://www.dropbox.com/scl/fi/jz9ao02y3xn61bbt469f7/"
    "2026_FantasyFootball_0.4_elboberto.xlsm?"
    "rlkey=vk0kb2nhf2wel5453erzu4wo9&st=szgxu53i&dl=1"
)
DIRECT_URLS = {
    position: (
        f"https://www.fantasypros.com/nfl/projections/{position.lower()}.php"
        "?scoring=PPR&week=draft"
    )
    for position in ("QB", "RB", "WR", "TE")
}
WORKBOOK_VERSION = "ElBoberto 2026 v0.4"
WORKBOOK_SOURCE_STATE = (
    "FROZEN_CANONICAL_SAME_FAMILY_WORKBOOK_DIRECT_CAPTURE_INCOMPLETE"
)
DIRECT_SOURCE_STATE = "REJECTED_INCOMPLETE_UNAUTHENTICATED_TOP_10_ONLY"
EXPECTED_WORKBOOK_SHA256 = (
    "93fbef0b61f070d1a1ee66afa1d49355e739bd1b9277459dd1149717c909c48c"
)
EXPECTED_DIRECT_SHA256 = {
    "QB": "7cc684630b2571ea4552c0dd0d64e1ced346a776ce8121fe5ddff3c0cb0c9b3b",
    "RB": "e1237cb2861bb42d5fe7f3bf849a7ce1878fb3a951a580a845317a414793015b",
    "WR": "876834d626a13f4936961b50fd09c2b876e3ce7cfdddbf93da6d329e3f2e912f",
    "TE": "1635346aa71a65ba3f080324b588f9771f8139800a96fc4a82252d30bcec935a",
}
EXPECTED_PLAYER_UNIVERSE_SHA256 = (
    "0550e7275294e3573f9fb3b7818fc110bc3925e08a30833f31def8647662eca3"
)
SNAPSHOT_ID = f"consensus_2026_frozen_{CAPTURE_TAG}_{EXPECTED_WORKBOOK_SHA256[:12]}"

COMPONENT_FIELDS = [
    "passing_attempts",
    "passing_completions",
    "passing_yards",
    "passing_touchdowns",
    "interceptions",
    "rushing_attempts",
    "rushing_yards",
    "rushing_touchdowns",
    "receptions",
    "receiving_yards",
    "receiving_touchdowns",
    "fumbles_lost",
]
OUTPUT_FIELDS = [
    "canonical_name",
    "source_name",
    "nfl_team",
    "position",
    *COMPONENT_FIELDS,
    "source_provided_fantasy_points",
    "standardized_full_ppr_points",
    "identity_match_method",
    "identity_match_confidence",
    "source_url",
    "source_version",
    "capture_timestamp",
    "source_state",
    "missing_field_indicators",
]

POSITION_SCORING_FIELDS = {
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
POSITION_REQUIRED_SOURCE_FIELDS = {
    "QB": [
        "passing_attempts",
        "passing_completions",
        "passing_yards",
        "passing_touchdowns",
        "interceptions",
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
    "RB": [
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        "receptions",
        "receiving_yards",
        "receiving_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
    "WR": [
        "receptions",
        "receiving_yards",
        "receiving_touchdowns",
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
    "TE": [
        "receptions",
        "receiving_yards",
        "receiving_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
}
SCORING_WEIGHTS = {
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

WORKBOOK_SHEETS = {
    "QB": "QB_Raw",
    "RB": "RB_Raw",
    "WR": "WR_Raw",
    "TE": "TE_Raw",
}
WORKBOOK_FIELD_ALIASES = {
    "PLAYER": "source_name",
    "TEAM": "nfl_team",
    "PASSATT": "passing_attempts",
    "PASSCMP": "passing_completions",
    "PASSYDS": "passing_yards",
    "PASSTDS": "passing_touchdowns",
    "PASSINTS": "interceptions",
    "RUSHATT": "rushing_attempts",
    "RUSHYDS": "rushing_yards",
    "RUSHTDS": "rushing_touchdowns",
    "RUDHTDS": "rushing_touchdowns",
    "REC": "receptions",
    "RECYDS": "receiving_yards",
    "RECTDS": "receiving_touchdowns",
    "FL": "fumbles_lost",
    "FPTS": "source_provided_fantasy_points",
}
DIRECT_FIELDS = {
    "QB": [
        "passing_attempts",
        "passing_completions",
        "passing_yards",
        "passing_touchdowns",
        "interceptions",
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
    "RB": [
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        "receptions",
        "receiving_yards",
        "receiving_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
    "WR": [
        "receptions",
        "receiving_yards",
        "receiving_touchdowns",
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
    "TE": [
        "receptions",
        "receiving_yards",
        "receiving_touchdowns",
        "fumbles_lost",
        "source_provided_fantasy_points",
    ],
}


@dataclass(frozen=True)
class BuildContext:
    repo_root: Path
    raw_root: Path
    player_universe_path: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    normalized = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", normalized)
    return re.sub(r"[^a-z0-9]", "", normalized)


def parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        number = float(str(value).replace(",", "").strip())
    if not math.isfinite(number):
        raise ValueError(f"non-finite numeric value: {value!r}")
    return number


def decimal_number(value: float) -> Decimal:
    return Decimal(str(value))


def full_ppr_points(row: dict[str, Any]) -> Decimal:
    position = row["position"]
    total = Decimal("0")
    for field in POSITION_SCORING_FIELDS[position]:
        value = row.get(field)
        if value is None:
            raise ValueError(
                f"{position} {row.get('source_name')} missing scoring field {field}"
            )
        total += decimal_number(value) * SCORING_WEIGHTS[field]
    return total.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def missing_indicators(row: dict[str, Any]) -> str:
    return "|".join(field for field in COMPONENT_FIELDS if row.get(field) is None)


def cell_column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if not letters:
        raise ValueError(f"invalid cell reference: {reference}")
    index = 0
    for char in letters.group(0):
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(payload)
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values = []
    for item in root.findall("x:si", ns):
        values.append("".join(node.text or "" for node in item.findall(".//x:t", ns)))
    return values


def workbook_sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    ns = {
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "p": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("p:Relationship", ns)
    }
    paths: dict[str, str] = {}
    for sheet in workbook.findall("x:sheets/x:sheet", ns):
        target = targets[sheet.attrib[f"{{{ns['r']}}}id"]]
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        paths[sheet.attrib["name"]] = target
    return paths


def worksheet_rows(
    archive: zipfile.ZipFile, path: str, strings: list[str]
) -> list[list[Any]]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(archive.read(path))
    output: list[list[Any]] = []
    for row_node in root.findall(".//x:sheetData/x:row", ns):
        values: dict[int, Any] = {}
        for cell in row_node.findall("x:c", ns):
            index = cell_column_index(cell.attrib["r"])
            cell_type = cell.attrib.get("t")
            value_node = cell.find("x:v", ns)
            if cell_type == "inlineStr":
                value = "".join(
                    node.text or "" for node in cell.findall(".//x:is/x:t", ns)
                )
            elif value_node is None:
                value = None
            elif cell_type == "s":
                value = strings[int(value_node.text or "0")]
            elif cell_type in {"str", "e"}:
                value = value_node.text
            elif cell_type == "b":
                value = value_node.text == "1"
            else:
                raw = value_node.text
                value = None if raw in (None, "") else float(raw)
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
            values[index] = value
        if values:
            width = max(values) + 1
            output.append([values.get(index) for index in range(width)])
    return output


def workbook_core_metadata(archive: zipfile.ZipFile) -> dict[str, str]:
    ns = {
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
    }
    root = ET.fromstring(archive.read("docProps/core.xml"))
    output: dict[str, str] = {}
    for label, expression in {
        "creator": "dc:creator",
        "last_modified_by": "cp:lastModifiedBy",
        "created": "dcterms:created",
        "modified": "dcterms:modified",
    }.items():
        node = root.find(expression, ns)
        output[label] = (node.text or "") if node is not None else ""
    return output


def load_workbook_source(
    path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[Any]]]:
    if sha256_file(path) != EXPECTED_WORKBOOK_SHA256:
        raise ValueError(f"unexpected workbook SHA-256: {path}")
    with zipfile.ZipFile(path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise ValueError(f"corrupt workbook member: {corrupt_member}")
        strings = shared_strings(archive)
        paths = workbook_sheet_paths(archive)
        metadata = workbook_core_metadata(archive)
        sheet_rows = {
            name: worksheet_rows(archive, paths[name], strings)
            for name in ["Intro", *WORKBOOK_SHEETS.values()]
        }

    attribution = ""
    for row in sheet_rows["Intro"]:
        for value in row:
            if isinstance(value, str) and "fantasypros.com/nfl/projections" in value.lower():
                attribution = value
    if not attribution:
        raise ValueError("workbook FantasyPros consensus attribution not found")

    records: list[dict[str, Any]] = []
    source_headers: dict[str, list[Any]] = {}
    for position, sheet_name in WORKBOOK_SHEETS.items():
        rows = sheet_rows[sheet_name]
        if not rows:
            raise ValueError(f"empty workbook sheet: {sheet_name}")
        raw_headers = rows[0]
        source_headers[position] = raw_headers
        mapped_headers = []
        for value in raw_headers:
            key = str(value or "").strip().upper()
            mapped_headers.append(WORKBOOK_FIELD_ALIASES.get(key, key))
        for raw_row in rows[1:]:
            values = list(raw_row) + [None] * (len(mapped_headers) - len(raw_row))
            candidate = dict(zip(mapped_headers, values))
            source_name = candidate.get("source_name")
            if source_name in (None, ""):
                continue
            record: dict[str, Any] = {
                "source_name": str(source_name).strip(),
                "nfl_team": str(candidate.get("nfl_team") or "").strip(),
                "position": position,
            }
            for field in COMPONENT_FIELDS + ["source_provided_fantasy_points"]:
                record[field] = parse_number(candidate.get(field))
            record["standardized_full_ppr_points"] = full_ppr_points(record)
            records.append(record)

    metadata["attribution"] = attribution
    metadata["archive_valid"] = True
    return records, metadata, source_headers


def parse_direct_html(path: Path, position: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    payload = path.read_text(encoding="utf-8")
    title_match = re.search(r"Fantasy Football Projections \(2026\)", payload)
    update_match = re.search(
        r"Consensus last updated\s*<time datetime=\"([^\"]+)\"", payload
    )
    tbody_match = re.search(
        r"<table[^>]+id=\"data\".*?<tbody>(.*?)</tbody>", payload, re.S | re.I
    )
    if not title_match or not update_match or not tbody_match:
        raise ValueError(f"direct source metadata/table not found: {path}")
    row_blocks = re.findall(r"<tr\b(.*?)</tr>", tbody_match.group(1), re.S | re.I)
    records: list[dict[str, Any]] = []
    for block in row_blocks:
        player_match = re.search(
            r"class=\"[^\"]*fp-id-(\d+)[^\"]*\"[^>]*fp-player-name=\"([^\"]+)\"",
            block,
            re.S | re.I,
        )
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", block, re.S | re.I)
        if not player_match or not cells:
            continue
        source_name = html.unescape(player_match.group(2)).strip()
        first_text = html.unescape(re.sub(r"<[^>]+>", " ", cells[0]))
        first_text = re.sub(r"\s+", " ", first_text).strip()
        team = first_text[len(source_name) :].strip() if first_text.startswith(source_name) else ""
        numeric_cells = [
            html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
            for value in cells[1:]
        ]
        fields = DIRECT_FIELDS[position]
        if len(numeric_cells) != len(fields):
            raise ValueError(
                f"unexpected direct {position} field count for {source_name}: "
                f"{len(numeric_cells)} != {len(fields)}"
            )
        record: dict[str, Any] = {
            "source_player_id": player_match.group(1),
            "source_name": source_name,
            "nfl_team": team,
            "position": position,
        }
        for field in COMPONENT_FIELDS + ["source_provided_fantasy_points"]:
            record[field] = None
        for field, value in zip(fields, numeric_cells):
            record[field] = parse_number(value)
        record["standardized_full_ppr_points"] = full_ppr_points(record)
        records.append(record)
    return records, {
        "season_label": "2026",
        "displayed_update_timestamp": update_match.group(1),
        "registration_fence": str("Create a free account to unlock" in payload),
    }


def load_player_universe(path: Path) -> list[dict[str, Any]]:
    payload = path.read_text(encoding="utf-8")
    match = re.search(r"window\.PLAYER_DATA\s*=\s*(\[.*?\]);", payload, re.S)
    if not match:
        raise ValueError(f"PLAYER_DATA not found in {path}")
    players = json.loads(match.group(1))
    return [player for player in players if player.get("pos") in WORKBOOK_SHEETS]


def attach_identity(
    records: list[dict[str, Any]], players: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    board_lookup: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for player in players:
        board_lookup[(normalize_name(player["name"]), player["pos"])].append(player)
    ambiguous_board_keys = [key for key, values in board_lookup.items() if len(values) != 1]
    if ambiguous_board_keys:
        raise ValueError(f"ambiguous Draft Command identity keys: {ambiguous_board_keys}")

    output: list[dict[str, Any]] = []
    crosswalk: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    matched_board_ids: set[int] = set()
    for source_order, source in enumerate(records, start=1):
        key = (normalize_name(source["source_name"]), source["position"])
        match = board_lookup.get(key, [])
        target = match[0] if match else None
        exact_name = target is not None and source["source_name"] == target["name"]
        team_match = target is not None and source["nfl_team"] == target["team"]
        if target is None:
            canonical_name = source["source_name"]
            method = "source_only_exact_name_position"
            confidence = Decimal("1.000")
        else:
            canonical_name = target["name"]
            matched_board_ids.add(int(target["id"]))
            if exact_name and team_match:
                method = "exact_name_position_team"
                confidence = Decimal("1.000")
            elif exact_name:
                method = "exact_name_position_team_conflict"
                confidence = Decimal("0.990")
            elif team_match:
                method = "normalized_name_position_team"
                confidence = Decimal("0.995")
            else:
                method = "normalized_name_position_team_conflict"
                confidence = Decimal("0.980")
            if not team_match:
                conflicts.append(
                    {
                        "conflict_type": "TEAM_MISMATCH_SOURCE_VS_DRAFT_COMMAND",
                        "severity": "INFORMATIONAL_SOURCE_TIMESTAMP_DIFFERENCE",
                        "position": source["position"],
                        "source_name": source["source_name"],
                        "canonical_name": canonical_name,
                        "source_team": source["nfl_team"],
                        "draft_command_team": target["team"],
                        "resolution": "preserve_source_team_do_not_overwrite",
                    }
                )

        row = dict(source)
        row.update(
            {
                "canonical_name": canonical_name,
                "identity_match_method": method,
                "identity_match_confidence": confidence,
                "source_url": WORKBOOK_URL,
                "source_version": (
                    f"{WORKBOOK_VERSION}; workbook modified 2026-08-08T13:32:00Z"
                ),
                "capture_timestamp": CAPTURE_TIMESTAMP,
                "source_state": WORKBOOK_SOURCE_STATE,
                "missing_field_indicators": missing_indicators(row),
            }
        )
        output.append(row)
        crosswalk.append(
            {
                "source_order": source_order,
                "source_name": source["source_name"],
                "source_team": source["nfl_team"],
                "position": source["position"],
                "normalized_name": key[0],
                "canonical_name": canonical_name,
                "draft_command_id": "" if target is None else target["id"],
                "draft_command_name": "" if target is None else target["name"],
                "draft_command_team": "" if target is None else target["team"],
                "draft_command_board_order": "" if target is None else target["id"],
                "match_method": method,
                "match_confidence": confidence,
                "join_state": (
                    "MATCHED_DRAFT_COMMAND" if target is not None else "SOURCE_ONLY"
                ),
            }
        )

    duplicate_keys = [
        key
        for key, count in Counter(
            (normalize_name(row["canonical_name"]), row["position"]) for row in output
        ).items()
        if count > 1
    ]
    for normalized, position in duplicate_keys:
        conflicts.append(
            {
                "conflict_type": "DUPLICATE_CANONICAL_NAME_POSITION",
                "severity": "ERROR",
                "position": position,
                "source_name": "|".join(
                    row["source_name"]
                    for row in output
                    if normalize_name(row["canonical_name"]) == normalized
                    and row["position"] == position
                ),
                "canonical_name": normalized,
                "source_team": "",
                "draft_command_team": "",
                "resolution": "UNRESOLVED",
            }
        )

    unmatched: list[dict[str, Any]] = []
    for player in players:
        if int(player["id"]) not in matched_board_ids:
            unmatched.append(
                {
                    "unmatched_scope": "DRAFT_COMMAND_MISSING_FROM_CANONICAL_SOURCE",
                    "draft_command_id": player["id"],
                    "board_order": player["id"],
                    "canonical_name": player["name"],
                    "team": player["team"],
                    "position": player["pos"],
                    "source_name": "",
                    "reason": "no normalized name + position row in preserved workbook",
                    "top_board_gap": "YES",
                }
            )
    for row in crosswalk:
        if row["join_state"] == "SOURCE_ONLY":
            unmatched.append(
                {
                    "unmatched_scope": "CANONICAL_SOURCE_OUTSIDE_DRAFT_COMMAND_UNIVERSE",
                    "draft_command_id": "",
                    "board_order": "",
                    "canonical_name": row["canonical_name"],
                    "team": row["source_team"],
                    "position": row["position"],
                    "source_name": row["source_name"],
                    "reason": "valid source projection outside current 200-player skill-position board",
                    "top_board_gap": "NO",
                }
            )
    return output, crosswalk, unmatched, conflicts


def coverage_rows(
    players: list[dict[str, Any]], crosswalk: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    matched_ids = {
        int(row["draft_command_id"])
        for row in crosswalk
        if row["draft_command_id"] != ""
    }
    rows: list[dict[str, Any]] = []
    for limit in (50, 100, 150, 200, None):
        scope = "ALL_BOARD" if limit is None else f"TOP_{limit}"
        scoped = players if limit is None else [p for p in players if int(p["id"]) <= limit]
        for position in ("ALL", "QB", "RB", "WR", "TE"):
            subset = scoped if position == "ALL" else [p for p in scoped if p["pos"] == position]
            matched = sum(int(player["id"]) in matched_ids for player in subset)
            count = len(subset)
            rows.append(
                {
                    "scope": scope,
                    "position": position,
                    "draft_command_rows": count,
                    "matched_projection_rows": matched,
                    "unmatched_projection_rows": count - matched,
                    "coverage_pct": Decimal(matched * 100 / count).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    if count
                    else "",
                    "coverage_gate": (
                        "PASS"
                        if (not count or matched / count >= Decimal("0.95"))
                        else "FAIL"
                    ),
                }
            )
    return rows


def source_comparison(
    workbook_records: list[dict[str, Any]],
    direct_by_position: dict[str, list[dict[str, Any]]],
    direct_meta: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    workbook_lookup = {
        (normalize_name(row["source_name"]), row["position"]): row
        for row in workbook_records
    }
    rows: list[dict[str, Any]] = []
    summary: dict[str, dict[str, Any]] = {}
    for position in ("QB", "RB", "WR", "TE"):
        position_rows = []
        for direct in direct_by_position[position]:
            workbook = workbook_lookup.get(
                (normalize_name(direct["source_name"]), position)
            )
            if workbook is None:
                continue
            component_deltas = {}
            for field in COMPONENT_FIELDS:
                if direct.get(field) is not None and workbook.get(field) is not None:
                    component_deltas[field] = round(
                        direct[field] - workbook[field], 3
                    )
            direct_points = direct["standardized_full_ppr_points"]
            workbook_points = workbook["standardized_full_ppr_points"]
            difference = direct_points - workbook_points
            record = {
                "position": position,
                "canonical_name": workbook["source_name"],
                "direct_source_name": direct["source_name"],
                "workbook_source_name": workbook["source_name"],
                "direct_team": direct["nfl_team"],
                "workbook_team": workbook["nfl_team"],
                "direct_update_timestamp": direct_meta[position][
                    "displayed_update_timestamp"
                ],
                "workbook_modified_timestamp": "2026-08-08T13:32:00Z",
                "direct_standardized_full_ppr_points": direct_points,
                "workbook_standardized_full_ppr_points": workbook_points,
                "difference_direct_minus_workbook": difference,
                "component_differences_json": json.dumps(
                    component_deltas, sort_keys=True, separators=(",", ":")
                ),
            }
            rows.append(record)
            position_rows.append(record)
        differences = [
            float(row["difference_direct_minus_workbook"]) for row in position_rows
        ]
        summary[position] = {
            "direct_rows_exposed": len(direct_by_position[position]),
            "overlap_rows": len(position_rows),
            "mean_direct_minus_workbook_points": round(statistics.mean(differences), 3)
            if differences
            else None,
            "median_absolute_point_difference": round(
                statistics.median(abs(value) for value in differences), 3
            )
            if differences
            else None,
            "max_absolute_point_difference": round(
                max(abs(value) for value in differences), 3
            )
            if differences
            else None,
        }
    return rows, summary


def csv_value(value: Any) -> str | int:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        if value.is_integer():
            return f"{value:.1f}"
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            default=lambda value: format(value, "f")
            if isinstance(value, Decimal)
            else str(value),
        )
        + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def relative_repo_path(context: BuildContext, path: Path) -> str:
    return path.resolve().relative_to(context.repo_root.resolve()).as_posix()


def raw_manifest_rows(
    context: BuildContext,
    workbook_path: Path,
    workbook_records: list[dict[str, Any]],
    direct_paths: dict[str, Path],
    direct_by_position: dict[str, list[dict[str, Any]]],
    direct_meta: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "artifact_path": relative_repo_path(context, workbook_path),
            "source_family": "FantasyPros consensus via ElBoberto preserved workbook",
            "source_url": WORKBOOK_URL,
            "source_version": WORKBOOK_VERSION,
            "declared_source_timestamp": "2026-08-08T13:32:00Z",
            "capture_timestamp": CAPTURE_TIMESTAMP,
            "sha256": sha256_file(workbook_path),
            "bytes": workbook_path.stat().st_size,
            "rows_exposed": len(workbook_records),
            "retrieval_mode": "unauthenticated HTTPS GET; no credentials; no cookies",
            "source_state": WORKBOOK_SOURCE_STATE,
            "notes": "ZIP integrity passed; hidden QB/RB/WR/TE raw tabs parsed",
        }
    ]
    for position in ("QB", "RB", "WR", "TE"):
        path = direct_paths[position]
        rows.append(
            {
                "artifact_path": relative_repo_path(context, path),
                "source_family": "FantasyPros direct public projection page",
                "source_url": DIRECT_URLS[position],
                "source_version": (
                    "FantasyPros 2026 consensus; displayed update "
                    + direct_meta[position]["displayed_update_timestamp"]
                ),
                "declared_source_timestamp": direct_meta[position][
                    "displayed_update_timestamp"
                ],
                "capture_timestamp": CAPTURE_TIMESTAMP,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "rows_exposed": len(direct_by_position[position]),
                "retrieval_mode": "unauthenticated HTTPS GET; no credentials; no cookies",
                "source_state": DIRECT_SOURCE_STATE,
                "notes": (
                    "public response exposed 10 rows behind registration fence; "
                    "displayed datetime does not declare a timezone"
                ),
            }
        )
    return rows


def schema_payload() -> dict[str, Any]:
    nullable_components = {
        "QB": ["receptions", "receiving_yards", "receiving_touchdowns"],
        "RB": [
            "passing_attempts",
            "passing_completions",
            "passing_yards",
            "passing_touchdowns",
            "interceptions",
        ],
        "WR": [
            "passing_attempts",
            "passing_completions",
            "passing_yards",
            "passing_touchdowns",
            "interceptions",
        ],
        "TE": [
            "passing_attempts",
            "passing_completions",
            "passing_yards",
            "passing_touchdowns",
            "interceptions",
            "rushing_attempts",
            "rushing_yards",
            "rushing_touchdowns",
        ],
    }
    properties = {
        field: {
            "type": ["number", "null"],
            "description": "source component; null means not reported by the source tab",
        }
        for field in COMPONENT_FIELDS
    }
    properties.update(
        {
            "canonical_name": {"type": "string"},
            "source_name": {"type": "string"},
            "nfl_team": {"type": "string"},
            "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE"]},
            "source_provided_fantasy_points": {"type": "number"},
            "standardized_full_ppr_points": {"type": "number"},
            "identity_match_method": {"type": "string"},
            "identity_match_confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "source_url": {"type": "string"},
            "source_version": {"type": "string"},
            "capture_timestamp": {"type": "string", "format": "date-time"},
            "source_state": {"type": "string"},
            "missing_field_indicators": {"type": "string"},
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Frozen 2026 Consensus Projection Components",
        "type": "object",
        "additionalProperties": False,
        "required": OUTPUT_FIELDS,
        "properties": properties,
        "x-null-policy": {
            "rule": "missing source components remain null/blank and are never zero-filled",
            "structurally_unreported_by_position": nullable_components,
        },
        "x-standardized-full-ppr-scoring": {
            "passing_yards": 0.04,
            "passing_touchdowns": 4,
            "interceptions": -2,
            "rushing_yards": 0.10,
            "rushing_touchdowns": 6,
            "receptions": 1,
            "receiving_yards": 0.10,
            "receiving_touchdowns": 6,
            "fumbles_lost": -2,
            "calculation_rule": (
                "sum only the component families explicitly reported for that position; "
                "retain all unreported fields as null"
            ),
        },
    }


def validation_payload(
    records: list[dict[str, Any]],
    workbook_metadata: dict[str, Any],
    direct_by_position: dict[str, list[dict[str, Any]]],
    direct_meta: dict[str, dict[str, str]],
    players: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    record_counts = Counter(row["position"] for row in records)
    duplicate_count = len(records) - len(
        {(normalize_name(row["canonical_name"]), row["position"]) for row in records}
    )
    finite_errors = []
    missing_required = []
    recalc_errors = []
    for row in records:
        for field in COMPONENT_FIELDS + [
            "source_provided_fantasy_points",
            "standardized_full_ppr_points",
        ]:
            value = row.get(field)
            if value is not None and not math.isfinite(float(value)):
                finite_errors.append(f"{row['source_name']}:{field}")
        for field in POSITION_REQUIRED_SOURCE_FIELDS[row["position"]]:
            if row.get(field) is None:
                missing_required.append(f"{row['source_name']}:{field}")
        if full_ppr_points(row) != row["standardized_full_ppr_points"]:
            recalc_errors.append(row["source_name"])

    all_board = next(
        row for row in coverage if row["scope"] == "ALL_BOARD" and row["position"] == "ALL"
    )
    top_100 = next(
        row for row in coverage if row["scope"] == "TOP_100" and row["position"] == "ALL"
    )
    position_coverage = [
        row
        for row in coverage
        if row["scope"] == "ALL_BOARD" and row["position"] != "ALL"
    ]
    board_gaps = [
        row
        for row in unmatched
        if row["unmatched_scope"] == "DRAFT_COMMAND_MISSING_FROM_CANONICAL_SOURCE"
    ]
    josh_rows = [row for row in records if row["source_name"] == "Josh Jacobs"]
    josh_pass = (
        len(josh_rows) == 1
        and josh_rows[0]["position"] == "RB"
        and josh_rows[0]["nfl_team"] == "GB"
        and josh_rows[0]["rushing_attempts"] == 288.8
        and josh_rows[0]["rushing_yards"] == 1161.6
        and josh_rows[0]["rushing_touchdowns"] == 12.0
        and josh_rows[0]["receptions"] == 35.7
        and josh_rows[0]["receiving_yards"] == 283.9
        and josh_rows[0]["receiving_touchdowns"] == 1.2
        and josh_rows[0]["fumbles_lost"] == 1.3
        and josh_rows[0]["source_provided_fantasy_points"] == 239.1
    )
    gates = {
        "archive_integrity": workbook_metadata.get("archive_valid") is True,
        "workbook_sha256": True,
        "direct_raw_sha256": True,
        "draft_command_universe_sha256": True,
        "workbook_fantasypros_attribution": "fantasypros.com/nfl/projections"
        in workbook_metadata.get("attribution", "").lower(),
        "explicit_workbook_source_date": workbook_metadata.get("modified")
        == "2026-08-08T13:32:00Z",
        "direct_pages_identified_as_2026": all(
            meta["season_label"] == "2026" for meta in direct_meta.values()
        ),
        "direct_pages_explicit_august_31_dates": all(
            meta["displayed_update_timestamp"].startswith("2026-08-31")
            for meta in direct_meta.values()
        ),
        "direct_capture_rejected_for_incomplete_coverage": all(
            len(direct_by_position[position]) == 10
            for position in ("QB", "RB", "WR", "TE")
        ),
        "required_positions_only": set(record_counts) == {"QB", "RB", "WR", "TE"},
        "unique_canonical_name_position_records": duplicate_count == 0,
        "finite_numeric_values": not finite_errors,
        "complete_position_applicable_components": not missing_required,
        "no_rank_or_adp_fields": not any(
            "rank" in field.lower() or "adp" in field.lower() for field in OUTPUT_FIELDS
        ),
        "full_ppr_recalculation_exact": not recalc_errors,
        "stable_unambiguous_identity_joins": not any(
            row["severity"] == "ERROR" for row in conflicts
        ),
        "overall_board_coverage_at_least_95_pct": float(all_board["coverage_pct"]) >= 95,
        "each_position_coverage_at_least_95_pct": all(
            float(row["coverage_pct"]) >= 95 for row in position_coverage
        ),
        "top_100_board_coverage_100_pct": float(top_100["coverage_pct"]) == 100,
        "all_top_board_gaps_identified": len(board_gaps)
        == int(all_board["unmatched_projection_rows"]),
        "josh_jacobs_source_projection_preserved_without_adjustment": josh_pass,
        "no_credentials_cookies_or_authenticated_responses": all(
            meta["registration_fence"] == "True" for meta in direct_meta.values()
        ),
        "deterministic_build_design": True,
    }
    return {
        "snapshot_id": SNAPSHOT_ID,
        "canonical_source": WORKBOOK_VERSION,
        "canonical_source_state": WORKBOOK_SOURCE_STATE,
        "row_counts": {position: record_counts[position] for position in ("QB", "RB", "WR", "TE")}
        | {"total": len(records), "draft_command_universe": len(players)},
        "coverage": {
            "overall_pct": all_board["coverage_pct"],
            "top_100_pct": top_100["coverage_pct"],
            "board_gap_count": len(board_gaps),
            "board_gaps": [
                {
                    "board_order": row["board_order"],
                    "name": row["canonical_name"],
                    "team": row["team"],
                    "position": row["position"],
                }
                for row in board_gaps
            ],
        },
        "josh_jacobs": {
            "source_name": josh_rows[0]["source_name"] if josh_rows else None,
            "team": josh_rows[0]["nfl_team"] if josh_rows else None,
            "source_provided_fantasy_points": josh_rows[0][
                "source_provided_fantasy_points"
            ]
            if josh_rows
            else None,
            "standardized_full_ppr_points": str(
                josh_rows[0]["standardized_full_ppr_points"]
            )
            if josh_rows
            else None,
            "adjustment_applied": False,
        },
        "diagnostics": {
            "duplicate_count": duplicate_count,
            "finite_error_count": len(finite_errors),
            "missing_required_component_count": len(missing_required),
            "recalculation_error_count": len(recalc_errors),
            "informational_team_conflict_count": sum(
                row["conflict_type"] == "TEAM_MISMATCH_SOURCE_VS_DRAFT_COMMAND"
                for row in conflicts
            ),
        },
        "gates": {key: "PASS" if value else "FAIL" for key, value in gates.items()},
        "overall_status": "PASS" if all(gates.values()) else "FAIL",
    }


def comparison_markdown(
    workbook_records: list[dict[str, Any]],
    direct_by_position: dict[str, list[dict[str, Any]]],
    direct_meta: dict[str, dict[str, str]],
    comparison_summary: dict[str, dict[str, Any]],
    coverage: list[dict[str, Any]],
) -> str:
    counts = Counter(row["position"] for row in workbook_records)
    overall = next(
        row for row in coverage if row["scope"] == "ALL_BOARD" and row["position"] == "ALL"
    )
    lines = [
        "# 2026 Consensus Projection Source Comparison",
        "",
        f"**Snapshot ID:** `{SNAPSHOT_ID}`",
        "",
        "## Selection decision",
        "",
        "The unauthenticated direct FantasyPros pages are verified as 2026 component-projection pages "
        "with August 31, 2026 update timestamps, but each public response exposes only 10 rows behind "
        "a registration fence. That 40-row capture is incomplete and is not promoted.",
        "",
        f"The preserved `{WORKBOOK_VERSION}` workbook is selected as the canonical baseline. Its "
        "package metadata reports `2026-08-08T13:32:00Z`; its Intro sheet attributes all consensus "
        "projections to FantasyPros; its hidden raw tabs contain complete position-applicable components; "
        f"and it covers {overall['matched_projection_rows']}/{overall['draft_command_rows']} "
        f"({overall['coverage_pct']}%) of the current Draft Command QB/RB/WR/TE universe.",
        "",
        "The snapshots are not averaged or blended.",
        "",
        "## Source gate comparison",
        "",
        "| Candidate | Source date | QB/RB/WR/TE rows | Coverage state | Decision |",
        "|---|---:|---:|---|---|",
        (
            "| Direct FantasyPros public pages | "
            + ", ".join(
                f"{position} {direct_meta[position]['displayed_update_timestamp']}"
                for position in ("QB", "RB", "WR", "TE")
            )
            + " | "
            + "/".join(str(len(direct_by_position[position])) for position in ("QB", "RB", "WR", "TE"))
            + " | Incomplete unauthenticated top-10-only capture | Rejected as canonical |"
        ),
        (
            f"| {WORKBOOK_VERSION} | 2026-08-08T13:32:00Z | "
            f"{counts['QB']}/{counts['RB']}/{counts['WR']}/{counts['TE']} | "
            f"{overall['coverage_pct']}% current board; 100% top 100 | Selected canonical |"
        ),
        "",
        "## Same-family sensitivity on the public overlap",
        "",
        "`Difference` is August 31 direct standardized full-PPR points minus August 8 workbook "
        "standardized full-PPR points, calculated only from displayed component fields.",
        "",
        "| Position | Direct rows | Overlap | Mean difference | Median absolute difference | Max absolute difference |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for position in ("QB", "RB", "WR", "TE"):
        summary = comparison_summary[position]
        lines.append(
            f"| {position} | {summary['direct_rows_exposed']} | {summary['overlap_rows']} | "
            f"{summary['mean_direct_minus_workbook_points']} | "
            f"{summary['median_absolute_point_difference']} | "
            f"{summary['max_absolute_point_difference']} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- The chosen snapshot is August 8, not August 31; it must retain that timestamp in Step 14.",
            "- FantasyPros' direct page datetime strings do not declare a timezone; they are preserved verbatim and not assigned one.",
            "- The direct pages cannot establish full-universe August 31 coverage without an account or API key, both excluded by this task.",
            "- Keenan Allen (IND, WR, board order 143) is the sole current-board source gap.",
            "- Source-provided FPTS are preserved but are not the canonical scoring field; standardized full-PPR is recalculated from components.",
            "- Position families absent from a raw tab remain null. They are not silently converted to zero.",
        ]
    )
    return "\n".join(lines)


def addendum_markdown(validation: dict[str, Any]) -> str:
    return f"""# Consensus Projection Source Contract — 2026 Addendum

**Snapshot ID:** `{SNAPSHOT_ID}`

**Status:** Approved frozen 2026 consensus P50 center

**Canonical source:** `{WORKBOOK_VERSION}`

**Canonical source timestamp:** `2026-08-08T13:32:00Z`

**Raw SHA-256:** `{EXPECTED_WORKBOOK_SHA256}`

## 2026 source decision

The August 31, 2026 FantasyPros public position pages were captured without credentials, cookies,
or an authenticated response. All four identify themselves as 2026 component projections and show
August 31 update timestamps, but each public response exposes only 10 player rows behind a registration
fence. The direct capture therefore fails the reproducible full-universe coverage gate and is retained
only as same-family provenance and sensitivity evidence.

The preserved August 8 ElBoberto v0.4 workbook is the canonical 2026 baseline. The workbook attributes
its consensus projections to FantasyPros, contains component projections on hidden position-specific raw
tabs, passes ZIP and hash integrity checks, and covers {validation['coverage']['overall_pct']}% of the
current Draft Command skill-position universe with 100% coverage of its top 100.

No averaging or blending is allowed. The August 8 timestamp must not be relabeled as August 31.

## Canonical scoring and missingness

`standardized_full_ppr_points` is recalculated from source components using 0.04 passing yards, 4 passing
TD, -2 interceptions, 0.10 rushing/receiving yards, 6 rushing/receiving TD, 1 per reception, and -2 fumbles
lost. Source-provided FPTS remain preserved as a separate audit field.

Components not reported by a position raw tab remain null/blank. Explicit source zeroes remain zeroes.
The standardized score uses only the component families explicitly reported for that position.

## Identity and coverage

Identity attachment uses deterministic normalized name + position, prefers exact names, removes common
suffixes for joins, and retains source team metadata for QA. Source team never overwrites the canonical
Draft Command identity. All match methods and confidence values are retained.

The only current-board source gap is Keenan Allen (IND, WR, board order 143). This gap is explicit and
must remain missing unless Step 14 adopts a separately approved source policy.

## Josh Jacobs control

Josh Jacobs' workbook projection is preserved exactly as sourced. No availability, injury, return-date,
stash, replacement-level, or Player Truth adjustment is applied in this package.

## Step 14 governing rule

Use this frozen consensus component package as the universal full-season P50 center. Rank, ADP, ECR,
auction value, opponent-intent, market, injury, and contextual signals are separate layers and may not
replace or mutate this baseline.
"""


def reproduction_markdown() -> str:
    return f"""# Reproduce the 2026 Consensus Projection Freeze

Run from the repository root with Python 3.11+:

```bash
python3 fantasy-draft/research/freeze_consensus_projections_2026.py
```

The command reads only the five frozen raw files under
`fantasy-draft/data/raw/consensus/2026/`, verifies their hashes and source metadata, performs two
independent temporary builds, byte-compares every output, and writes:

`fantasy-draft/data/derived/consensus_2026/{SNAPSHOT_ID}/`

To prove the build without changing the canonical output path:

```bash
tmp_dir=$(mktemp -d)
python3 fantasy-draft/research/freeze_consensus_projections_2026.py --output-root "$tmp_dir/build"
sha256sum "$tmp_dir/build/current_2026_consensus_components_{CAPTURE_TAG}.csv"
```

Expected canonical CSV SHA-256 is recorded in `SHA256SUMS` and
`deterministic_build_proof.json`. Do not recapture the live pages for a deterministic rebuild; a live
recapture is a new source snapshot and requires a new timestamp, hashes, validation, and selection decision.

The original unauthenticated capture commands are documented in the raw-source manifest. They used
plain HTTPS GET requests with a descriptive user agent, no API key, no credentials, and no cookie jar.

For provenance only, the live capture pattern was:

```bash
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/qb.php?scoring=PPR&week=draft' --output fantasypros_2026_qb.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/rb.php?scoring=PPR&week=draft' --output fantasypros_2026_rb.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/wr.php?scoring=PPR&week=draft' --output fantasypros_2026_wr.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' 'https://www.fantasypros.com/nfl/projections/te.php?scoring=PPR&week=draft' --output fantasypros_2026_te.html
curl --fail --location --user-agent 'Mozilla/5.0 (compatible; DraftProjectionFreeze/1.0; +https://github.com/tofo21/Cool-Tools)' '{WORKBOOK_URL}' --output 2026_FantasyFootball_0.4_elboberto.xlsm
```

A live recapture will not reproduce the frozen raw hashes and must never overwrite this snapshot.
"""


def handoff_markdown(validation: dict[str, Any]) -> str:
    canonical_csv = f"current_2026_consensus_components_{CAPTURE_TAG}.csv"
    return f"""# Portable Step 14 Handoff — 2026 Consensus Projection Freeze

## Approved input

- Snapshot ID: `{SNAPSHOT_ID}`
- Canonical file: `{canonical_csv}`
- Source: `{WORKBOOK_VERSION}` using FantasyPros consensus projections
- Source timestamp: `2026-08-08T13:32:00Z`
- Capture timestamp: `{CAPTURE_TIMESTAMP}`
- Validation: `{validation['overall_status']}`

## Exact Step 14 consumption

1. Verify every artifact against `SHA256SUMS`.
2. Read `{canonical_csv}` as UTF-8 CSV.
3. Require `source_state == {WORKBOOK_SOURCE_STATE}` on every row.
4. Join to the Step 14 player universe using `canonical_name + position`; use
   `identity_crosswalk_{CAPTURE_TAG}.csv` to audit Draft Command joins and source-name variants.
5. Use `standardized_full_ppr_points` as the universal full-season P50 consensus center.
6. Preserve every component column as the auditable source basis. Do not use
   `source_provided_fantasy_points` as the PPR center.
7. Treat blank component fields as source-unreported, not zero. Explicit `0.0` remains a real source zero.
8. Keep the sole board gap, Keenan Allen (IND, WR, board order 143), missing unless a new approved source
   addendum is created. Do not infer his projection from rank, ADP, ECR, auction value, or nearby players.
9. Preserve Josh Jacobs' row exactly as the consensus center. Any Step 14 status or availability treatment
   must be a separate, traceable adjustment layer; it may not mutate this CSV.
10. Do not blend the rejected 40-row August 31 direct capture with the August 8 workbook.

## Required preflight assertions

- CSV rows: `{validation['row_counts']['total']}` (`QB={validation['row_counts']['QB']}`,
  `RB={validation['row_counts']['RB']}`, `WR={validation['row_counts']['WR']}`,
  `TE={validation['row_counts']['TE']}`)
- Unique `canonical_name + position`: yes
- Current Draft Command coverage: `{validation['coverage']['overall_pct']}%`
- Current Draft Command top-100 coverage: `{validation['coverage']['top_100_pct']}%`
- Validation report overall status: `PASS`
- Deterministic build proof: `byte_identical == true`

## Non-authorizations

This handoff does not authorize Player Truth adjustments, candidate promotion, model tuning, weight changes,
Draft Command changes, deployment, or a merge to `main`.
"""


def validation_markdown(validation: dict[str, Any]) -> str:
    lines = [
        "# 2026 Consensus Projection Freeze Validation",
        "",
        f"**Snapshot ID:** `{SNAPSHOT_ID}`",
        f"**Overall status:** **{validation['overall_status']}**",
        "",
        "## Gate results",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for gate, result in validation["gates"].items():
        lines.append(f"| `{gate}` | {result} |")
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Rows: {validation['row_counts']['total']}",
            f"- Draft Command coverage: {validation['coverage']['overall_pct']}%",
            f"- Draft Command top-100 coverage: {validation['coverage']['top_100_pct']}%",
            f"- Board gaps: {validation['coverage']['board_gap_count']} (Keenan Allen, IND, WR, board order 143)",
            "",
            "Informational source-team conflicts are retained in the conflict report and do not overwrite source or canonical identity.",
        ]
    )
    return "\n".join(lines)


def build_core(context: BuildContext, output_root: Path) -> dict[str, Any]:
    workbook_path = context.raw_root / WORKBOOK_FILENAME
    direct_paths = {
        position: context.raw_root / DIRECT_FILENAME.format(position=position.lower())
        for position in ("QB", "RB", "WR", "TE")
    }
    for path in [workbook_path, *direct_paths.values(), context.player_universe_path]:
        if not path.is_file():
            raise FileNotFoundError(path)

    workbook_records, workbook_metadata, source_headers = load_workbook_source(
        workbook_path
    )
    if workbook_metadata["modified"] != "2026-08-08T13:32:00Z":
        raise ValueError(f"unexpected workbook modified timestamp: {workbook_metadata}")

    direct_by_position: dict[str, list[dict[str, Any]]] = {}
    direct_meta: dict[str, dict[str, str]] = {}
    for position in ("QB", "RB", "WR", "TE"):
        if sha256_file(direct_paths[position]) != EXPECTED_DIRECT_SHA256[position]:
            raise ValueError(
                f"unexpected direct {position} SHA-256: {direct_paths[position]}"
            )
        records, metadata = parse_direct_html(direct_paths[position], position)
        direct_by_position[position] = records
        direct_meta[position] = metadata

    if sha256_file(context.player_universe_path) != EXPECTED_PLAYER_UNIVERSE_SHA256:
        raise ValueError(
            f"unexpected Draft Command player universe SHA-256: {context.player_universe_path}"
        )
    players = load_player_universe(context.player_universe_path)
    records, crosswalk, unmatched, conflicts = attach_identity(
        workbook_records, players
    )
    coverage = coverage_rows(players, crosswalk)
    comparison_rows, comparison_summary = source_comparison(
        workbook_records, direct_by_position, direct_meta
    )
    validation = validation_payload(
        records,
        workbook_metadata,
        direct_by_position,
        direct_meta,
        players,
        coverage,
        unmatched,
        conflicts,
    )
    if validation["overall_status"] != "PASS":
        failed = [
            gate for gate, state in validation["gates"].items() if state != "PASS"
        ]
        raise ValueError(f"validation failed: {failed}")

    output_root.mkdir(parents=True, exist_ok=True)
    canonical_path = output_root / f"current_2026_consensus_components_{CAPTURE_TAG}.csv"
    write_csv(canonical_path, records, OUTPUT_FIELDS)
    write_csv(
        output_root / f"raw_source_manifest_{CAPTURE_TAG}.csv",
        raw_manifest_rows(
            context,
            workbook_path,
            workbook_records,
            direct_paths,
            direct_by_position,
            direct_meta,
        ),
        [
            "artifact_path",
            "source_family",
            "source_url",
            "source_version",
            "declared_source_timestamp",
            "capture_timestamp",
            "sha256",
            "bytes",
            "rows_exposed",
            "retrieval_mode",
            "source_state",
            "notes",
        ],
    )
    write_csv(
        output_root / f"identity_crosswalk_{CAPTURE_TAG}.csv",
        crosswalk,
        [
            "source_order",
            "source_name",
            "source_team",
            "position",
            "normalized_name",
            "canonical_name",
            "draft_command_id",
            "draft_command_name",
            "draft_command_team",
            "draft_command_board_order",
            "match_method",
            "match_confidence",
            "join_state",
        ],
    )
    write_csv(
        output_root / f"unmatched_players_{CAPTURE_TAG}.csv",
        unmatched,
        [
            "unmatched_scope",
            "draft_command_id",
            "board_order",
            "canonical_name",
            "team",
            "position",
            "source_name",
            "reason",
            "top_board_gap",
        ],
    )
    write_csv(
        output_root / f"coverage_report_{CAPTURE_TAG}.csv",
        coverage,
        [
            "scope",
            "position",
            "draft_command_rows",
            "matched_projection_rows",
            "unmatched_projection_rows",
            "coverage_pct",
            "coverage_gate",
        ],
    )
    write_csv(
        output_root / f"duplicate_conflict_report_{CAPTURE_TAG}.csv",
        conflicts,
        [
            "conflict_type",
            "severity",
            "position",
            "source_name",
            "canonical_name",
            "source_team",
            "draft_command_team",
            "resolution",
        ],
    )
    write_csv(
        output_root / f"source_comparison_detail_{CAPTURE_TAG}.csv",
        comparison_rows,
        [
            "position",
            "canonical_name",
            "direct_source_name",
            "workbook_source_name",
            "direct_team",
            "workbook_team",
            "direct_update_timestamp",
            "workbook_modified_timestamp",
            "direct_standardized_full_ppr_points",
            "workbook_standardized_full_ppr_points",
            "difference_direct_minus_workbook",
            "component_differences_json",
        ],
    )
    write_text(
        output_root / f"source_comparison_report_{CAPTURE_TAG}.md",
        comparison_markdown(
            workbook_records,
            direct_by_position,
            direct_meta,
            comparison_summary,
            coverage,
        ),
    )
    write_json(output_root / f"schema_{CAPTURE_TAG}.json", schema_payload())
    write_json(
        output_root / f"validation_report_{CAPTURE_TAG}.json", validation
    )
    write_text(
        output_root / f"validation_report_{CAPTURE_TAG}.md",
        validation_markdown(validation),
    )
    write_text(
        output_root / "CONSENSUS_PROJECTION_SOURCE_CONTRACT_2026_ADDENDUM.md",
        addendum_markdown(validation),
    )
    write_text(output_root / "REPRODUCTION.md", reproduction_markdown())
    write_text(
        output_root / "STEP14_CONSENSUS_PROJECTION_HANDOFF.md",
        handoff_markdown(validation),
    )
    write_json(
        output_root / f"workbook_audit_{CAPTURE_TAG}.json",
        {
            "archive_valid": workbook_metadata["archive_valid"],
            "attribution": workbook_metadata["attribution"],
            "core_metadata": {
                key: workbook_metadata[key]
                for key in ("creator", "last_modified_by", "created", "modified")
            },
            "raw_sheet_headers": source_headers,
            "row_counts": dict(Counter(row["position"] for row in workbook_records)),
            "sha256": sha256_file(workbook_path),
        },
    )
    return {
        "validation": validation,
        "canonical_path": canonical_path,
        "workbook_path": workbook_path,
        "direct_paths": direct_paths,
    }


def bundle_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def bundle_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in bundle_files(root)
    }


def aggregate_hash(hashes: dict[str, str]) -> str:
    payload = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items()))
    return sha256_bytes(payload.encode("utf-8"))


def finalize_bundle(
    context: BuildContext,
    output_root: Path,
    determinism_proof: dict[str, Any],
) -> None:
    proof_path = output_root / "deterministic_build_proof.json"
    write_json(proof_path, determinism_proof)

    manifest_fields = ["artifact_path", "role", "sha256", "bytes"]
    manifest_path = output_root / f"processed_source_manifest_{CAPTURE_TAG}.csv"
    manifest_rows = []
    for path in bundle_files(output_root):
        if path.name in {manifest_path.name, "SHA256SUMS"}:
            continue
        manifest_rows.append(
            {
                "artifact_path": path.relative_to(output_root).as_posix(),
                "role": "canonical_projection" if path.name.startswith("current_2026") else "supporting_artifact",
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    write_csv(manifest_path, manifest_rows, manifest_fields)

    ledger_entries: list[tuple[str, str]] = []
    for path in bundle_files(output_root):
        if path.name == "SHA256SUMS":
            continue
        ledger_entries.append((path.relative_to(output_root).as_posix(), sha256_file(path)))
    raw_files = [
        context.raw_root / WORKBOOK_FILENAME,
        *[
            context.raw_root / DIRECT_FILENAME.format(position=position.lower())
            for position in ("QB", "RB", "WR", "TE")
        ],
    ]
    for path in raw_files:
        ledger_entries.append(
            (f"../../../raw/consensus/2026/{path.name}", sha256_file(path))
        )
    ledger_entries.append(
        ("../../../players.js", sha256_file(context.player_universe_path))
    )
    write_text(
        output_root / "SHA256SUMS",
        "\n".join(
            f"{digest}  {name}" for name, digest in sorted(ledger_entries)
        ),
    )


def deterministic_build(context: BuildContext, output_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="consensus-freeze-build-a-") as temp_a, tempfile.TemporaryDirectory(
        prefix="consensus-freeze-build-b-"
    ) as temp_b:
        root_a = Path(temp_a) / "bundle"
        root_b = Path(temp_b) / "bundle"
        build_core(context, root_a)
        build_core(context, root_b)
        core_a = bundle_hashes(root_a)
        core_b = bundle_hashes(root_b)
        if core_a != core_b:
            raise ValueError("determinism failure in core outputs")
        proof = {
            "snapshot_id": SNAPSHOT_ID,
            "frozen_input_sha256": {
                WORKBOOK_FILENAME: sha256_file(context.raw_root / WORKBOOK_FILENAME),
                **{
                    DIRECT_FILENAME.format(position=position.lower()): sha256_file(
                        context.raw_root
                        / DIRECT_FILENAME.format(position=position.lower())
                    )
                    for position in ("QB", "RB", "WR", "TE")
                },
                relative_repo_path(context, context.player_universe_path): sha256_file(
                    context.player_universe_path
                ),
            },
            "core_file_count": len(core_a),
            "core_aggregate_sha256": aggregate_hash(core_a),
            "core_file_sha256": core_a,
            "build_a_equals_build_b": True,
            "byte_identical": True,
            "compared_file_count": len(core_a) + 3,
            "finalization_outputs": [
                "deterministic_build_proof.json",
                f"processed_source_manifest_{CAPTURE_TAG}.csv",
                "SHA256SUMS",
            ],
            "comparison_method": "SHA-256 and byte-for-byte equality for every generated file",
        }
        finalize_bundle(context, root_a, proof)
        finalize_bundle(context, root_b, proof)
        final_a = bundle_hashes(root_a)
        final_b = bundle_hashes(root_b)
        if final_a != final_b:
            raise ValueError("determinism failure in finalized outputs")
        for relative_path in final_a:
            if (root_a / relative_path).read_bytes() != (root_b / relative_path).read_bytes():
                raise ValueError(f"byte comparison failed: {relative_path}")

    build_core(context, output_root)
    finalize_bundle(context, output_root, proof)
    actual = bundle_hashes(output_root)

    with tempfile.TemporaryDirectory(prefix="consensus-freeze-proof-") as temp_expected:
        expected_root = Path(temp_expected) / "bundle"
        build_core(context, expected_root)
        finalize_bundle(context, expected_root, proof)
        expected = bundle_hashes(expected_root)
        if actual != expected:
            raise ValueError("actual output differs from deterministic reference build")
        for relative_path in actual:
            if (output_root / relative_path).read_bytes() != (
                expected_root / relative_path
            ).read_bytes():
                raise ValueError(f"actual byte comparison failed: {relative_path}")

    return {
        "output_root": output_root,
        "file_count": len(actual),
        "aggregate_sha256": aggregate_hash(actual),
        "canonical_csv_sha256": sha256_file(
            output_root / f"current_2026_consensus_components_{CAPTURE_TAG}.csv"
        ),
    }


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_repo_root = script_path.parents[2]
    default_raw_root = default_repo_root / "fantasy-draft/data/raw/consensus/2026"
    default_output_root = (
        default_repo_root
        / "fantasy-draft/data/derived/consensus_2026"
        / SNAPSHOT_ID
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=default_repo_root)
    parser.add_argument("--raw-root", type=Path, default=default_raw_root)
    parser.add_argument(
        "--player-universe",
        type=Path,
        default=default_repo_root / "fantasy-draft/data/players.js",
    )
    parser.add_argument("--output-root", type=Path, default=default_output_root)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    context = BuildContext(
        repo_root=args.repo_root.resolve(),
        raw_root=args.raw_root.resolve(),
        player_universe_path=args.player_universe.resolve(),
    )
    result = deterministic_build(context, args.output_root.resolve())
    print(json.dumps({key: str(value) for key, value in result.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
