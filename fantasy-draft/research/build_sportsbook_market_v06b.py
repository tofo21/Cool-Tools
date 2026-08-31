from __future__ import annotations

import numpy as np
import pandas as pd

import build_sportsbook_market_v06 as base

# Curated public source snapshots. Values are embedded rather than fetched during
# the build because several historical odds pages deny automated runner traffic.
# Every row retains its exact source family, date/window, book attribution, and
# available side prices. The sources intentionally differ by season; downstream
# models must carry snapshot timing and source-state metadata.
TEAM_MARKETS: dict[int, dict] = {
    2020: {
        "source_url": "https://www.boydsbets.com/nfl-season-win-totals/",
        "snapshot_date": None,
        "snapshot_window": "2020_preseason_line_retrospectively_archived_2025",
        "source_provider": "Boyd's Bets",
        "underlying_provider": "sportsbook market / book not specified",
        "book": "not specified",
        "source_state": "retrospective_preserved_archive_no_odds",
        "notes": "Archived 2020 win-total table. The later archive preserves the line but not exact book, side prices, or original snapshot date.",
        "rows": {
            "ARI": (7.5, None, None), "ATL": (7.5, None, None), "BAL": (11.5, None, None), "BUF": (9.0, None, None),
            "CAR": (5.5, None, None), "CHI": (8.0, None, None), "CIN": (5.5, None, None), "CLE": (8.5, None, None),
            "DAL": (10.0, None, None), "DEN": (7.5, None, None), "DET": (7.0, None, None), "GB": (8.5, None, None),
            "HOU": (7.5, None, None), "IND": (9.5, None, None), "JAX": (4.5, None, None), "KC": (11.5, None, None),
            "LV": (7.5, None, None), "LAC": (8.0, None, None), "LAR": (8.5, None, None), "MIA": (6.0, None, None),
            "MIN": (9.0, None, None), "NE": (9.0, None, None), "NO": (10.5, None, None), "NYG": (6.5, None, None),
            "NYJ": (6.5, None, None), "PHI": (9.5, None, None), "PIT": (9.5, None, None), "SF": (10.5, None, None),
            "SEA": (9.5, None, None), "TB": (9.5, None, None), "TEN": (8.5, None, None), "WAS": (5.0, None, None),
        },
    },
    2021: {
        "source_url": "https://www.sportsbettingdime.com/news/nfl/latest-2021-nfl-win-totals-for-all-32-teams-and-best-over-under-bets/",
        "snapshot_date": "2021-09-06",
        "snapshot_window": "late_preseason_final_rosters",
        "source_provider": "SportsBettingDime",
        "underlying_provider": "FanDuel Sportsbook",
        "book": "FanDuel",
        "source_state": "preserved_late_preseason_book_table",
        "notes": "Complete all-32 FanDuel win-total table published three days before the 2021 opener; includes over and under prices.",
        "rows": {
            "ARI": (8.5, 105, -125), "ATL": (7.5, -120, 100), "BAL": (11.0, 100, -120), "BUF": (11.0, -120, 100),
            "CAR": (7.5, -105, -115), "CHI": (7.5, 100, -120), "CIN": (6.5, 100, -120), "CLE": (10.5, -105, -115),
            "DAL": (9.5, 115, -135), "DEN": (8.5, -120, 100), "DET": (5.0, 100, -120), "GB": (10.5, -130, 110),
            "HOU": (4.0, -120, 100), "IND": (9.0, -110, -110), "JAX": (6.5, 115, -135), "KC": (12.5, 120, -140),
            "LV": (7.0, -110, -110), "LAC": (9.5, 110, -135), "LAR": (10.5, 120, -140), "MIA": (9.5, 125, -145),
            "MIN": (8.5, -160, 135), "NE": (9.5, 100, -120), "NO": (9.0, 125, -145), "NYG": (7.0, -130, 110),
            "NYJ": (6.0, -115, -105), "PHI": (6.5, -150, 125), "PIT": (8.5, 110, -130), "SF": (10.5, 100, -120),
            "SEA": (10.0, -110, -110), "TB": (11.5, -150, 125), "TEN": (9.0, -150, 125), "WAS": (8.5, -115, -105),
        },
    },
    2022: {
        "source_url": "https://www.sportsbettingdime.com/news/nfl/2022-win-totals-open-bills-projected-win-most-games/",
        "snapshot_date": "2022-03-28",
        "snapshot_window": "early_preseason_opening_market",
        "source_provider": "SportsBettingDime",
        "underlying_provider": "Barstool Sportsbook",
        "book": "Barstool Sportsbook",
        "source_state": "preserved_early_preseason_book_table",
        "notes": "Complete all-32 opening win-total table. It predates the draft and must be treated as an early market snapshot.",
        "rows": {
            "ARI": (9.5, 125, -162), "ATL": (5.5, 101, -130), "BAL": (9.5, -143, 111), "BUF": (11.5, -150, 116),
            "CAR": (6.0, -114, -114), "CHI": (7.0, -104, -125), "CIN": (10.0, 111, -143), "CLE": (8.5, 125, -150),
            "DAL": (10.5, -104, -125), "DEN": (10.0, -114, -114), "DET": (6.0, -104, -125), "GB": (11.0, -114, -114),
            "HOU": (4.5, -114, -114), "IND": (9.5, -125, -104), "JAX": (6.5, -114, -114), "KC": (10.5, -167, 128),
            "LV": (8.5, 111, -143), "LAC": (10.0, -114, -114), "LAR": (10.5, 101, -130), "MIA": (8.5, -125, -104),
            "MIN": (9.0, -114, -114), "NE": (9.0, 116, -150), "NO": (8.0, 111, -143), "NYG": (7.5, 128, -167),
            "NYJ": (5.0, -125, -104), "PHI": (8.5, -134, 104), "PIT": (7.5, -121, -107), "SF": (10.0, -134, 104),
            "SEA": (6.0, -130, 101), "TB": (11.5, -139, 108), "TEN": (9.5, -114, -114), "WAS": (7.5, 104, -134),
        },
    },
    2023: {
        "source_url": "https://www.cbssports.com/nfl/news/2023-nfl-win-totals-for-all-32-teams-five-best-overunder-bets-including-the-jets-soaring-with-aaron-rodgers/",
        "snapshot_date": "2023-03-29",
        "snapshot_window": "early_preseason_opening_market",
        "source_provider": "CBS Sports",
        "underlying_provider": "Caesars Sportsbook",
        "book": "Caesars",
        "source_state": "preserved_early_preseason_book_table",
        "notes": "Complete all-32 Caesars opening win-total table. It predates the draft and must be treated as an early market snapshot.",
        "rows": {
            "ARI": (5.5, 105, -125), "ATL": (7.5, -115, -105), "BAL": (8.5, -140, 120), "BUF": (10.5, -125, 105),
            "CAR": (7.5, -110, -110), "CHI": (7.5, -115, -105), "CIN": (11.5, -110, -110), "CLE": (8.5, -140, 120),
            "DAL": (9.5, -115, -105), "DEN": (8.5, -115, -105), "DET": (9.0, -150, 125), "GB": (7.5, 110, -130),
            "HOU": (5.5, -110, -110), "IND": (6.5, -125, 105), "JAX": (9.5, -140, 120), "KC": (11.5, -110, -110),
            "LV": (7.5, 110, -130), "LAC": (9.5, -115, -105), "LAR": (7.5, -125, 105), "MIA": (9.5, 110, -130),
            "MIN": (8.5, -115, -105), "NE": (7.5, -115, -105), "NO": (9.5, 110, -130), "NYG": (8.5, 110, -130),
            "NYJ": (9.5, -120, 100), "PHI": (10.5, -130, 110), "PIT": (8.5, -105, -115), "SF": (11.5, -105, -115),
            "SEA": (8.5, -125, 105), "TB": (6.5, -115, -105), "TEN": (7.5, -105, -115), "WAS": (7.5, 115, -135),
        },
    },
    2024: {
        "source_url": "https://www.thescore.com/nfl/news/2882262/nfl-stock-watch-tracking-regular-season-win-totals-following-free-agency",
        "snapshot_date": None,
        "snapshot_window": "post_free_agency_opening_market_before_schedule",
        "source_provider": "theScore",
        "underlying_provider": "opening market / book not specified",
        "book": "not specified",
        "source_state": "preserved_post_free_agency_opening_table",
        "notes": "Complete all-32 opening market after free agency and before the schedule release. The source exposes over prices only and does not identify a book or exact publication date in the preserved page.",
        "rows": {
            "ARI": (6.5, -130, None), "ATL": (9.5, -140, None), "BAL": (11.5, 110, None), "BUF": (10.5, -130, None),
            "CAR": (4.5, -135, None), "CHI": (8.5, -125, None), "CIN": (10.5, -125, None), "CLE": (8.5, -120, None),
            "DAL": (10.5, 100, None), "DEN": (5.5, -150, None), "DET": (10.5, -115, None), "GB": (9.5, -140, None),
            "HOU": (9.5, -110, None), "IND": (8.5, 110, None), "JAX": (8.5, -125, None), "KC": (11.5, -120, None),
            "LV": (6.5, -140, None), "LAC": (8.5, -135, None), "LAR": (8.5, -120, None), "MIA": (9.5, -150, None),
            "MIN": (6.5, -140, None), "NE": (4.5, -145, None), "NO": (7.5, -120, None), "NYG": (6.5, 110, None),
            "NYJ": (9.5, 100, None), "PHI": (10.5, 110, None), "PIT": (8.5, -110, None), "SF": (11.5, 115, None),
            "SEA": (7.5, -125, None), "TB": (7.5, -150, None), "TEN": (6.5, 115, None), "WAS": (6.5, -130, None),
        },
    },
    2025: {
        "source_url": "https://www.boydsbets.com/nfl-season-win-totals/",
        "snapshot_date": "2025-08-03",
        "snapshot_window": "late_preseason_multi_book_summary",
        "source_provider": "Boyd's Bets",
        "underlying_provider": "multiple sportsbooks summarized by author",
        "book": "multi-book midpoint-style summary",
        "source_state": "preserved_preseason_multi_book_summary_no_odds",
        "notes": "Complete all-32 table. The author displays the closest-to-even win-total number found across books and omits side prices, so it is not a single-book board.",
        "rows": {
            "ARI": (8.5, None, None), "ATL": (7.5, None, None), "BAL": (11.5, None, None), "BUF": (11.5, None, None),
            "CAR": (6.5, None, None), "CHI": (8.5, None, None), "CIN": (9.5, None, None), "CLE": (5.5, None, None),
            "DAL": (7.5, None, None), "DEN": (9.5, None, None), "DET": (10.5, None, None), "GB": (10.5, None, None),
            "HOU": (9.5, None, None), "IND": (7.5, None, None), "JAX": (7.5, None, None), "KC": (11.5, None, None),
            "LV": (6.5, None, None), "LAC": (9.5, None, None), "LAR": (9.5, None, None), "MIA": (7.5, None, None),
            "MIN": (8.5, None, None), "NE": (8.5, None, None), "NO": (4.5, None, None), "NYG": (5.5, None, None),
            "NYJ": (9.5, None, None), "PHI": (11.5, None, None), "PIT": (8.5, None, None), "SF": (10.5, None, None),
            "SEA": (8.0, None, None), "TB": (9.5, None, None), "TEN": (5.5, None, None), "WAS": (9.5, None, None),
        },
    },
}

TEAM_NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers", "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}

SOURCE_TEAM_OVERRIDES = {
    (2021, "WAS"): "Washington Football Team",
    (2022, "WAS"): "Washington Football Team",
    (2025, "WAS"): "Wash. Commanders",
}


def curated_team_market(season: int) -> tuple[pd.DataFrame, dict]:
    spec = TEAM_MARKETS[season]
    rows = []
    for team, (line, over_odds, under_odds) in spec["rows"].items():
        rows.append(
            {
                "season": season,
                "team": team,
                "source_team": SOURCE_TEAM_OVERRIDES.get((season, team), TEAM_NAMES[team]),
                "win_total": float(line),
                "super_bowl_odds_american": np.nan,
                "over_odds_american": np.nan if over_odds is None else float(over_odds),
                "under_odds_american": np.nan if under_odds is None else float(under_odds),
                "snapshot_date": spec["snapshot_date"],
                "snapshot_window": spec["snapshot_window"],
                "book": spec["book"],
                "source_provider": spec["source_provider"],
                "underlying_provider": spec["underlying_provider"],
                "source_state": spec["source_state"],
                "source_url": spec["source_url"],
                "retrieval_url": spec["source_url"],
                "retrieval_status": "curated_verified_public_table",
                "notes": spec["notes"],
            }
        )
    frame = pd.DataFrame(rows).sort_values("team").reset_index(drop=True)
    if len(frame) != 32 or frame["team"].nunique() != 32:
        raise AssertionError(f"Curated team market for {season} is not a complete 32-team board")
    frame.to_csv(base.OUT / f"sportsbook_team_market_raw_{season}.csv", index=False)
    manifest = {
        "season": season,
        "signal_family": "team_win_total",
        "source_provider": spec["source_provider"],
        "underlying_provider": spec["underlying_provider"],
        "source_state": spec["source_state"],
        "source_url": spec["source_url"],
        "retrieval_url": spec["source_url"],
        "snapshot_date": spec["snapshot_date"],
        "snapshot_window": spec["snapshot_window"],
        "source_rows": len(frame),
        "primary_model_eligible": True,
        "notes": spec["notes"],
        "retrieval_status": "curated_verified_public_table",
    }
    return frame, manifest


# Patch only the team-market retrieval layer. Player-prop preservation,
# calibration evidence, matching, source-discipline assertions and output logic
# remain in v0.6.
base.fetch_team_market = curated_team_market


if __name__ == "__main__":
    base.main()
