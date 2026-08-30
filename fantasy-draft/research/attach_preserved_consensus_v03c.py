from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

import attach_preserved_consensus_v03 as base

# 2021 bridge: a contemporaneous ElBoberto-derived workbook distributed by
# Roto Street Journal. The accompanying 8/16/2021 article explicitly states
# that the workbook uses aggregate FantasyPros projections and that the data
# in the downloadable tool were updated 8/27/2021.
base.KICKOFF[2021] = date(2021, 9, 9)
base.WORKBOOKS[2021] = {
    "version": "RSJ-2021-08-27",
    "declared_snapshot_date": "2021-08-27",
    "url": "https://www.dropbox.com/s/ejpepisqf9d5296/2021%20Auction%20VBD%20Workbook%20-%20Consensus%20Projections.xlsm?dl=1",
}

# Final pre-kickoff versions for the direct ElBoberto annual workbooks.
base.WORKBOOKS[2023]["declared_snapshot_date"] = "2023-09-05"
base.WORKBOOKS[2024] = {
    "version": "1.05",
    "declared_snapshot_date": "2024-08-29",
    "url": "https://www.dropbox.com/scl/fi/z0d55b8dvvfzf2u50r066/2024_FantasyFootball_1.05_elboberto.xlsm?rlkey=0zgnghh88e1sj9w6syecr63j4&st=y2gnzc7k&dl=1",
}
base.WORKBOOKS[2025] = {
    "version": "1.06",
    "declared_snapshot_date": "2025-09-03",
    "url": "https://www.dropbox.com/scl/fi/45o4zr4vy3batxzu9ngto/2025_FantasyFootball_1.06_elboberto.xlsm?rlkey=2wv8a1l8p7y7hhsbo6wx5ho21&st=pl3r122g&dl=1",
}


def build() -> None:
    panel = pd.read_csv(base.INFILE, low_memory=False)
    fields = [
        "consensus_proj_points",
        "consensus_proj_pass_attempts",
        "consensus_proj_pass_completions",
        "consensus_proj_pass_yards",
        "consensus_proj_pass_tds",
        "consensus_proj_pass_ints",
        "consensus_proj_rush_attempts",
        "consensus_proj_rush_yards",
        "consensus_proj_rush_tds",
        "consensus_proj_receptions",
        "consensus_proj_rec_yards",
        "consensus_proj_rec_tds",
        "consensus_proj_fumbles_lost",
        "consensus_proj_source_points_standard",
        "consensus_proj_source_url",
        "consensus_proj_source_version",
        "consensus_proj_declared_snapshot_date",
        "consensus_proj_workbook_modified_utc",
        "consensus_proj_source_sha256",
        "consensus_proj_source_state",
    ]
    text_fields = {
        "consensus_proj_source_url", "consensus_proj_source_version",
        "consensus_proj_declared_snapshot_date", "consensus_proj_workbook_modified_utc",
        "consensus_proj_source_sha256", "consensus_proj_source_state",
    }
    for field in fields:
        if field not in panel.columns:
            panel[field] = pd.Series([None] * len(panel), dtype="object") if field in text_fields else np.nan

    manifests, sources, matches, coverage = [], [], [], []

    for season in sorted(base.WORKBOOKS):
        print(f"Attaching preserved consensus projections {season}")
        source, manifest = base.source_for_season(season)

        if season == 2021:
            source["consensus_proj_source_state"] = "fantasypros_consensus_via_2021_rotostreet_elboberto_workbook"
            manifest["source_state"] = "fantasypros_consensus_via_2021_rotostreet_elboberto_workbook"
            manifest["distribution_note"] = (
                "Roto Street Journal ElBoberto-derived workbook; contemporaneous article states "
                "aggregate FantasyPros projections updated 2021-08-27"
            )
        else:
            manifest["distribution_note"] = "Direct annual ElBoberto workbook"

        sources.append(source)
        manifests.append(manifest)
        panel, m = base.attach(panel, source, season, fields)
        matches.append(m)

        mask = panel["season"].eq(season)
        draft = mask & panel["draft_market_present"].fillna(False).astype(bool)
        ecr300 = mask & panel["fp_ecr"].notna() & panel["fp_ecr"].le(300)
        coverage.append({
            "season": season,
            "source_rows": len(source),
            "panel_rows": int(mask.sum()),
            "draft_market_rows": int(draft.sum()),
            "draft_market_projection_coverage_pct": round(100 * panel.loc[draft, "consensus_proj_points"].notna().mean(), 2),
            "ecr_top300_rows": int(ecr300.sum()),
            "ecr_top300_projection_coverage_pct": round(100 * panel.loc[ecr300, "consensus_proj_points"].notna().mean(), 2),
            "workbook_pre_kickoff_validation": "PASS",
        })

    # 2020 remains unresolved. Do not contaminate the primary series with the
    # known 2020 Roto Street workbook because that file explicitly blends
    # FantasyPros (75%) with FantasyPoints (25%).
    mask = panel["season"].eq(2020)
    coverage.append({
        "season": 2020,
        "source_rows": 0,
        "panel_rows": int(mask.sum()),
        "draft_market_rows": int((mask & panel["draft_market_present"].fillna(False).astype(bool)).sum()),
        "draft_market_projection_coverage_pct": 0.0,
        "ecr_top300_rows": int((mask & panel["fp_ecr"].notna() & panel["fp_ecr"].le(300)).sum()),
        "ecr_top300_projection_coverage_pct": 0.0,
        "workbook_pre_kickoff_validation": "SOURCE_GAP_NOT_IMPUTED",
    })

    panel.to_csv(base.OUTFILE, index=False)
    pd.concat(sources, ignore_index=True).to_csv(base.OUT_DIR / "consensus_projection_source_snapshot_v03.csv", index=False)
    pd.concat(matches, ignore_index=True).to_csv(base.OUT_DIR / "consensus_projection_match_qa_v03.csv", index=False)
    pd.DataFrame(manifests).to_csv(base.OUT_DIR / "consensus_projection_source_manifest_v03.csv", index=False)
    cov = pd.DataFrame(coverage).sort_values("season")
    cov.to_csv(base.OUT_DIR / "consensus_projection_coverage_qa_v03.csv", index=False)

    missing = panel[
        panel["draft_market_present"].fillna(False).astype(bool) & panel["consensus_proj_points"].isna()
    ][["season", "canonical_player_id", "player_name", "position", "fp_ecr", "ffc_adp", "espn_rank", "sleeper_adp_order"]]
    missing.to_csv(base.OUT_DIR / "consensus_projection_manual_review_v03.csv", index=False)

    print(cov.to_string(index=False))
    print(f"Wrote {base.OUTFILE} with {len(panel):,} rows")
    print(f"Draft-market projection gaps retained={len(missing):,}; 2020 intentionally remains source gap")


if __name__ == "__main__":
    build()
