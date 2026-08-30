from __future__ import annotations

import io
import json
import math
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

SEASONS = list(range(2020, 2026))
POSITIONS = ["qb", "rb", "wr", "te"]
OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Target the final preseason market, not arbitrary mid-summer captures.
TARGET_DATES = {
    2020: "20200906",
    2021: "20210905",
    2022: "20220904",
    2023: "20230903",
    2024: "20240901",
    2025: "20250831",
}

# Historical anchor players. These are deliberately chosen so a current page
# cannot accidentally pass as the requested old season.
SEASON_MARKERS = {
    2020: ["Drew Brees", "Julian Edelman"],
    2021: ["Ben Roethlisberger", "Julio Jones"],
    2022: ["Tom Brady", "Matt Ryan"],
    2023: ["Dalvin Cook", "DeAndre Hopkins"],
    2024: ["Keenan Allen", "Stefon Diggs"],
    2025: ["Cam Ward", "Ashton Jeanty"],
}

ORIGINAL_PATTERNS = [
    "https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft*",
    "http://www.fantasypros.com/nfl/projections/{pos}.php?week=draft*",
    "https://www.fantasypros.com/nfl/projections/{pos}.php*",
]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"
})


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def cdx(pattern: str, season: int) -> list[dict]:
    params = {
        "url": pattern,
        "from": str(season),
        "to": str(season),
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "digest",
    }
    # requests handles repeated filter params when supplied as tuples.
    query = [
        ("url", pattern), ("from", str(season)), ("to", str(season)),
        ("output", "json"), ("fl", "timestamp,original,statuscode,mimetype,digest"),
        ("filter", "statuscode:200"), ("filter", "mimetype:text/html"),
        ("collapse", "digest"),
    ]
    r = SESSION.get("https://web.archive.org/cdx/search/cdx", params=query, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data or len(data) < 2:
        return []
    headers = data[0]
    return [dict(zip(headers, row)) for row in data[1:]]


def distance(ts: str, target: str) -> int:
    a = datetime.strptime(ts[:8], "%Y%m%d")
    b = datetime.strptime(target, "%Y%m%d")
    return abs((a - b).days)


def get_capture(timestamp: str, original: str) -> str:
    # id_ asks Wayback for the archived payload without toolbar rewriting.
    url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    r = SESSION.get(url, timeout=90)
    r.raise_for_status()
    return r.text


def table_profile(html: str) -> tuple[int, bool, list[str]]:
    names: list[str] = []
    projection_table = False
    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception:
        tables = []
    for t in tables:
        cols = []
        for c in t.columns:
            if isinstance(c, tuple):
                cols.append("_".join(str(x) for x in c if not str(x).startswith("Unnamed")).upper())
            else:
                cols.append(str(c).upper())
        if any("PLAYER" in c for c in cols) and any("FPTS" in c for c in cols):
            projection_table = True
            pidx = next((i for i, c in enumerate(cols) if "PLAYER" in c), None)
            if pidx is not None:
                vals = t.iloc[:, pidx].astype(str).tolist()
                names.extend(vals)
    return len(tables), projection_table, names


def probe() -> None:
    rows = []
    selected = []

    for season in SEASONS:
        for pos in POSITIONS:
            captures: dict[tuple[str, str], dict] = {}
            errors = []
            for pat_tmpl in ORIGINAL_PATTERNS:
                pattern = pat_tmpl.format(pos=pos)
                try:
                    for cap in cdx(pattern, season):
                        captures[(cap["timestamp"], cap["original"])] = cap
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"CDX {pattern}: {type(exc).__name__}: {exc}")
                time.sleep(0.25)

            ordered = sorted(
                captures.values(),
                key=lambda x: (distance(x["timestamp"], TARGET_DATES[season]), x["timestamp"]),
            )

            accepted = None
            attempts = 0
            for cap in ordered[:12]:
                attempts += 1
                status = "DOWNLOAD_ERROR"
                table_count = 0
                projection_table = False
                marker_hits = 0
                marker_detail = ""
                err = ""
                try:
                    html = get_capture(cap["timestamp"], cap["original"])
                    table_count, projection_table, names = table_profile(html)
                    corpus = norm_text(" | ".join(names) + " " + html[:500000])
                    hits = [m for m in SEASON_MARKERS[season] if norm_text(m) in corpus]
                    marker_hits = len(hits)
                    marker_detail = ";".join(hits)
                    if projection_table and marker_hits >= 1:
                        status = "ACCEPT"
                    elif projection_table:
                        status = "REJECT_MARKER"
                    else:
                        status = "REJECT_NO_PROJECTION_TABLE"
                except Exception as exc:  # noqa: BLE001
                    err = f"{type(exc).__name__}: {exc}"

                row = {
                    "season": season,
                    "position": pos.upper(),
                    "target_date": TARGET_DATES[season],
                    "capture_timestamp": cap["timestamp"],
                    "capture_date": cap["timestamp"][:8],
                    "days_from_target": distance(cap["timestamp"], TARGET_DATES[season]),
                    "original_url": cap["original"],
                    "digest": cap.get("digest"),
                    "status": status,
                    "html_table_count": table_count,
                    "projection_table_found": projection_table,
                    "marker_hits": marker_hits,
                    "marker_detail": marker_detail,
                    "error": err,
                }
                rows.append(row)
                if status == "ACCEPT":
                    accepted = row
                    break
                time.sleep(0.25)

            selected.append({
                "season": season,
                "position": pos.upper(),
                "target_date": TARGET_DATES[season],
                "captures_discovered": len(ordered),
                "captures_attempted": attempts,
                "selected_timestamp": accepted["capture_timestamp"] if accepted else None,
                "selected_original_url": accepted["original_url"] if accepted else None,
                "selected_days_from_target": accepted["days_from_target"] if accepted else None,
                "validation": "PASS" if accepted else "NO_VERIFIED_CAPTURE",
                "cdx_errors": " | ".join(errors),
            })
            print(season, pos.upper(), selected[-1])

    pd.DataFrame(rows).to_csv(OUT_DIR / "wayback_consensus_capture_attempts_v03.csv", index=False)
    sel = pd.DataFrame(selected)
    sel.to_csv(OUT_DIR / "wayback_consensus_capture_manifest_v03.csv", index=False)

    summary = sel.groupby("season").agg(
        positions_verified=("validation", lambda x: int((x == "PASS").sum())),
        positions_total=("position", "count"),
    ).reset_index()
    summary["season_validation"] = summary.apply(
        lambda r: "PASS" if r["positions_verified"] == r["positions_total"] else "PARTIAL", axis=1
    )
    summary.to_csv(OUT_DIR / "wayback_consensus_season_qa_v03.csv", index=False)
    print("\nWayback consensus season QA")
    print(summary.to_string(index=False))

    # Probe is intentionally non-fatal for missing captures. The manifest tells the
    # next attachment step exactly which seasons/positions are defensibly recoverable.


if __name__ == "__main__":
    probe()
