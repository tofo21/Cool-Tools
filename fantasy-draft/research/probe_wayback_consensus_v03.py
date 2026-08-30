from __future__ import annotations

import io
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

SEASONS = list(range(2020, 2026))
POSITIONS = ["qb", "rb", "wr", "te"]
OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_DATES = {
    2020: "20200906",
    2021: "20210905",
    2022: "20220904",
    2023: "20230903",
    2024: "20240901",
    2025: "20250831",
}
SEASON_MARKERS = {
    2020: ["Drew Brees", "Julian Edelman"],
    2021: ["Ben Roethlisberger", "Julio Jones"],
    2022: ["Tom Brady", "Matt Ryan"],
    2023: ["Dalvin Cook", "DeAndre Hopkins"],
    2024: ["Keenan Allen", "Stefon Diggs"],
    2025: ["Cam Ward", "Ashton Jeanty"],
}
URL_VARIANTS = [
    "https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft",
    "https://www.fantasypros.com/nfl/projections/{pos}.php",
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


def day_distance(ts: str, target: str) -> int:
    a = datetime.strptime(ts[:8], "%Y%m%d")
    b = datetime.strptime(target, "%Y%m%d")
    return abs((a - b).days)


def nearest_capture(original: str, target: str) -> dict | None:
    r = SESSION.get(
        "https://archive.org/wayback/available",
        params={"url": original, "timestamp": target},
        timeout=15,
    )
    r.raise_for_status()
    snap = (r.json().get("archived_snapshots") or {}).get("closest")
    if not snap or not snap.get("available"):
        return None
    return snap


def fetch_capture(timestamp: str, original: str) -> str:
    urls = [
        f"https://web.archive.org/web/{timestamp}id_/{original}",
        f"https://web.archive.org/web/{timestamp}/{original}",
    ]
    last = None
    for url in urls:
        try:
            r = SESSION.get(url, timeout=25)
            r.raise_for_status()
            return r.text
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(str(last))


def profile(html: str) -> tuple[int, bool, list[str]]:
    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception:
        tables = []
    names = []
    found = False
    for t in tables:
        cols = []
        for c in t.columns:
            if isinstance(c, tuple):
                cols.append("_".join(str(x) for x in c if not str(x).startswith("Unnamed")).upper())
            else:
                cols.append(str(c).upper())
        if any("PLAYER" in c for c in cols) and any("FPTS" in c for c in cols):
            found = True
            i = next((i for i, c in enumerate(cols) if "PLAYER" in c), None)
            if i is not None:
                names.extend(t.iloc[:, i].astype(str).tolist())
    return len(tables), found, names


def probe() -> None:
    attempts = []
    selected = []
    for season in SEASONS:
        for pos in POSITIONS:
            accepted = None
            errors = []
            seen = set()
            for tmpl in URL_VARIANTS:
                original = tmpl.format(pos=pos)
                row = {
                    "season": season,
                    "position": pos.upper(),
                    "target_date": TARGET_DATES[season],
                    "query_url": original,
                }
                try:
                    snap = nearest_capture(original, TARGET_DATES[season])
                    if not snap:
                        row.update({"status": "NO_CAPTURE"})
                        attempts.append(row)
                        continue
                    timestamp = str(snap["timestamp"])
                    archived_url = str(snap.get("url") or "")
                    key = (timestamp, archived_url)
                    if key in seen:
                        continue
                    seen.add(key)
                    original_from_snap = re.sub(r"^https?://web\.archive\.org/web/\d+/(?:id_/)?", "", archived_url)
                    if not original_from_snap.startswith("http"):
                        original_from_snap = original
                    html = fetch_capture(timestamp, original_from_snap)
                    table_count, table_found, names = profile(html)
                    corpus = norm_text(" | ".join(names) + " " + html[:500000])
                    hits = [m for m in SEASON_MARKERS[season] if norm_text(m) in corpus]
                    status = "ACCEPT" if table_found and hits else ("REJECT_MARKER" if table_found else "REJECT_NO_TABLE")
                    row.update({
                        "capture_timestamp": timestamp,
                        "capture_date": timestamp[:8],
                        "days_from_target": day_distance(timestamp, TARGET_DATES[season]),
                        "archived_url": archived_url,
                        "original_url": original_from_snap,
                        "html_table_count": table_count,
                        "projection_table_found": table_found,
                        "marker_hits": len(hits),
                        "marker_detail": ";".join(hits),
                        "status": status,
                    })
                    attempts.append(row)
                    if status == "ACCEPT":
                        accepted = row
                        break
                except Exception as exc:  # noqa: BLE001
                    row.update({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
                    attempts.append(row)
                    errors.append(row["error"])

            selected.append({
                "season": season,
                "position": pos.upper(),
                "target_date": TARGET_DATES[season],
                "selected_timestamp": accepted.get("capture_timestamp") if accepted else None,
                "selected_original_url": accepted.get("original_url") if accepted else None,
                "selected_archived_url": accepted.get("archived_url") if accepted else None,
                "selected_days_from_target": accepted.get("days_from_target") if accepted else None,
                "validation": "PASS" if accepted else "NO_VERIFIED_CAPTURE",
                "errors": " | ".join(errors),
            })
            print(season, pos.upper(), selected[-1])

    att = pd.DataFrame(attempts)
    sel = pd.DataFrame(selected)
    att.to_csv(OUT_DIR / "wayback_consensus_capture_attempts_v03.csv", index=False)
    sel.to_csv(OUT_DIR / "wayback_consensus_capture_manifest_v03.csv", index=False)
    summary = sel.groupby("season").agg(
        positions_verified=("validation", lambda x: int((x == "PASS").sum())),
        positions_total=("position", "count"),
    ).reset_index()
    summary["season_validation"] = summary.apply(
        lambda r: "PASS" if r.positions_verified == r.positions_total else "PARTIAL", axis=1
    )
    summary.to_csv(OUT_DIR / "wayback_consensus_season_qa_v03.csv", index=False)
    print("\nWayback consensus season QA")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    probe()
