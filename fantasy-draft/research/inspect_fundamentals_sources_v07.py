from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "FantasyDraftIntelligenceResearch/0.7 (+https://github.com/tofo21/Cool-Tools)"}

SOURCES = {
    "stats_player_2024": "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg_2024.parquet",
    "snap_counts_2024": "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2024.parquet",
    "pfr_rush_season": "https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_season_rush.parquet",
    "pfr_rec_season": "https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_season_rec.parquet",
    "ngs_receiving": "https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/ngs_receiving.parquet",
    "ngs_rushing": "https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/ngs_rushing.parquet",
    "ngs_passing": "https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/ngs_passing.parquet",
    "ffopportunity_2024": "https://github.com/ffverse/ffopportunity/releases/download/latest-data/ep_weekly_2024.parquet",
    "pbp_2024": "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2024.parquet",
}


def fetch(url: str) -> bytes:
    r = requests.get(url, headers=UA, timeout=180)
    r.raise_for_status()
    return r.content


def main() -> None:
    report = {}
    for name, url in SOURCES.items():
        print(f"Inspecting {name}: {url}")
        raw = fetch(url)
        df = pd.read_parquet(io.BytesIO(raw))
        report[name] = {
            "url": url,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {c: str(t) for c, t in df.dtypes.items()},
            "sample": df.head(2).where(pd.notna(df.head(2)), None).to_dict(orient="records"),
        }
        print(f"  rows={len(df):,} cols={len(df.columns)}")
        print("  columns=" + ", ".join(df.columns))
    (OUT / "fundamentals_source_schema_probe_v07.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
