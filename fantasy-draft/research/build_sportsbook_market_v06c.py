from __future__ import annotations

import numpy as np
import pandas as pd

import build_sportsbook_market_v06b as v06b

base = v06b.base
_original_manual = base.manual_player_prop_observations


def _row(
    player: str,
    market: str,
    line: float,
    projection: float,
    differential: float,
    source_date: str,
    source_url: str,
    book: str,
    raw_label: str,
) -> dict:
    direction = "over" if differential > 0 else "under" if differential < 0 else "push"
    return base._prop_row(
        season=2025,
        player_name=player,
        position=None,
        market_type=market,
        line=line,
        source_date=source_date,
        source_provider="PFF",
        book=book,
        source_url=source_url,
        retrieval_url=source_url,
        source_state="preserved_projection_screened_table_curated",
        sampling_frame="projection_screened_extremes",
        recommendation_side=direction,
        recommendation_odds=np.nan,
        projection=projection,
        projection_line_differential=differential,
        primary_model_eligible=False,
        notes=(
            "Manually transcribed and cross-checked from a public PFF comparison table "
            "selected for large projection-versus-market differences; not a representative full board."
        ),
        raw_market_label=raw_label,
    )


def curated_2025_rows() -> tuple[pd.DataFrame, list[dict]]:
    passing_url = "https://www.pff.com/news/bet-nfl-betting-2025-pff-fantasy-projections-passing-props"
    rushing_url = "https://www.pff.com/news/bet-nfl-betting-2025-pff-fantasy-projections-rushing-props"
    receiving_url = "https://www.pff.com/news/bet-nfl-betting-2025-pff-fantasy-projections-receiving-props"

    rows = []

    passing_yards = [
        ("Brock Purdy", 3900.5, 4236.7, 336.2),
        ("Patrick Mahomes", 4075.5, 4318.7, 243.2),
        ("Matthew Stafford", 4075.5, 4288.6, 213.1),
        ("Justin Herbert", 3875.5, 4076.3, 200.8),
        ("Jordan Love", 3775.5, 3955.4, 179.9),
    ]
    passing_tds = [
        ("Tua Tagovailoa", 27.5, 24.8, -2.7),
        ("Jared Goff", 30.5, 28.0, -2.5),
        ("Lamar Jackson", 27.5, 25.7, -1.8),
        ("Justin Herbert", 26.5, 24.8, -1.7),
        ("Patrick Mahomes", 29.5, 27.9, -1.6),
        ("Russell Wilson", 19.5, 23.5, 4.0),
        ("Drake Maye", 19.5, 22.2, 2.7),
        ("Cam Ward", 17.5, 19.9, 2.4),
        ("Joe Burrow", 32.5, 34.4, 1.9),
        ("Bo Nix", 26.5, 28.4, 1.9),
    ]
    for player, line, projection, diff in passing_yards:
        rows.append(_row(player, "pass_yards", line, projection, diff, "2025-06-13", passing_url, "FanDuel", "Passing Yards Line"))
    for player, line, projection, diff in passing_tds:
        rows.append(_row(player, "pass_tds", line, projection, diff, "2025-06-13", passing_url, "FanDuel", "Passing TDs Line"))

    rb_rushing = [
        ("TreVeyon Henderson", 750.5, 1013.2, 262.7, 6.5, 9.4, 2.9),
        ("Cam Skattebo", 725.5, 914.7, 189.2, 5.5, 7.4, 1.9),
        ("Najee Harris", 700.5, 826.3, 125.8, 6.5, 7.2, 0.7),
        ("Travis Etienne", 675.5, 778.9, 103.4, 4.5, 5.6, 1.1),
        ("Tony Pollard", 950.5, 1037.4, 86.9, 6.5, 7.1, 0.6),
    ]
    for player, yd_line, yd_proj, yd_diff, td_line, td_proj, td_diff in rb_rushing:
        rows.append(_row(player, "rush_yards", yd_line, yd_proj, yd_diff, "2025-06-17", rushing_url, "DraftKings/Caesars (page-level attribution)", "Rushing Yards Line"))
        rows.append(_row(player, "rush_tds", td_line, td_proj, td_diff, "2025-06-17", rushing_url, "DraftKings/Caesars (page-level attribution)", "Rushing TDs Line"))

    qb_rushing = [
        ("Drake Maye", 400.5, 523.8, 123.3),
        ("Jayden Daniels", 750.5, 876.1, 125.6),
        ("Jalen Hurts", 625.5, 729.9, 104.4),
        ("Josh Allen", 550.5, 635.1, 84.6),
        ("Bo Nix", 400.5, 480.8, 80.3),
        ("Kyler Murray", 525.5, 601.0, 75.5),
        ("Brock Purdy", 325.5, 395.6, 70.1),
    ]
    for player, line, projection, diff in qb_rushing:
        rows.append(_row(player, "rush_yards", line, projection, diff, "2025-06-17", rushing_url, "DraftKings/Caesars (page-level attribution)", "QB Rushing Yards Line"))

    additional_rb_yards = [
        ("Quinshon Judkins", 700.5, 831.1, 130.6),
        ("Josh Jacobs", 975.5, 1080.9, 105.4),
        ("Kyren Williams", 1050.5, 1158.9, 108.4),
        ("James Cook", 950.5, 1055.8, 105.3),
        ("Bijan Robinson", 1075.5, 1191.7, 116.2),
    ]
    for player, line, projection, diff in additional_rb_yards:
        rows.append(_row(player, "rush_yards", line, projection, diff, "2025-06-17", rushing_url, "DraftKings/Caesars (page-level attribution)", "Rushing Yards Line"))

    receiving_tds = [
        ("Garrett Wilson", 4.5, 6.8, 2.3),
        ("DeVonta Smith", 5.5, 7.1, 1.6),
        ("Rashid Shaheed", 2.5, 4.0, 1.5),
        ("Josh Downs", 3.5, 4.7, 1.2),
        ("Jameson Williams", 6.5, 7.6, 1.1),
    ]
    receiving_yards = [
        ("Marvin Harrison Jr.", 1025.5, 1118.8, 93.3),
        ("DeMario Douglas", 675.5, 734.0, 58.5),
        ("Davante Adams", 925.5, 964.8, 39.3),
        ("Xavier Worthy", 950.5, 991.1, 40.6),
        ("Kyle Pitts", 625.5, 661.2, 35.7),
        ("Deebo Samuel", 775.5, 683.5, -92.0),
        ("Zay Flowers", 1025.5, 932.8, -92.7),
        ("Calvin Ridley", 1050.5, 1017.8, -32.7),
        ("DJ Moore", 850.5, 829.9, -20.6),
        ("Cedric Tillman", 650.5, 622.3, -28.2),
    ]
    for player, line, projection, diff in receiving_tds:
        rows.append(_row(player, "rec_tds", line, projection, diff, "2025-06-19", receiving_url, "FanDuel/DraftKings/Caesars (page-level attribution)", "Receiving TDs Line"))
    for player, line, projection, diff in receiving_yards:
        rows.append(_row(player, "rec_yards", line, projection, diff, "2025-06-19", receiving_url, "FanDuel/DraftKings/Caesars (page-level attribution)", "Receiving Yards Line"))

    frame = pd.DataFrame(rows).drop_duplicates(subset=["season", "player_name", "market_type", "line", "source_url"])
    manifests = [
        {
            "season": 2025,
            "signal_family": "player_season_prop",
            "source_provider": "PFF",
            "underlying_provider": "FanDuel",
            "source_state": "preserved_projection_screened_table_curated",
            "source_url": passing_url,
            "retrieval_url": passing_url,
            "snapshot_date": "2025-06-13",
            "snapshot_window": "early_preseason_selected",
            "source_rows": 15,
            "primary_model_eligible": False,
            "notes": "Curated from public PFF projection-versus-line tables; not a representative full board.",
        },
        {
            "season": 2025,
            "signal_family": "player_season_prop",
            "source_provider": "PFF",
            "underlying_provider": "DraftKings/Caesars (page-level attribution)",
            "source_state": "preserved_projection_screened_table_curated",
            "source_url": rushing_url,
            "retrieval_url": rushing_url,
            "snapshot_date": "2025-06-17",
            "snapshot_window": "early_preseason_selected",
            "source_rows": 22,
            "primary_model_eligible": False,
            "notes": "Curated from public PFF projection-versus-line tables; not a representative full board.",
        },
        {
            "season": 2025,
            "signal_family": "player_season_prop",
            "source_provider": "PFF",
            "underlying_provider": "FanDuel/DraftKings/Caesars (page-level attribution)",
            "source_state": "preserved_projection_screened_table_curated",
            "source_url": receiving_url,
            "retrieval_url": receiving_url,
            "snapshot_date": "2025-06-19",
            "snapshot_window": "early_preseason_selected",
            "source_rows": 15,
            "primary_model_eligible": False,
            "notes": "Curated from public PFF projection-versus-line tables; not a representative full board.",
        },
    ]
    return frame, manifests


def manual_player_prop_observations() -> tuple[pd.DataFrame, list[dict]]:
    historical, manifests = _original_manual()
    curated, curated_manifests = curated_2025_rows()
    return pd.concat([historical, curated], ignore_index=True), manifests + curated_manifests


# PFF blocks automated scraping of these historical article tables in the CI
# environment. Preserve the verified public rows above instead of treating an
# access-control response as permission to invent or silently drop the source.
base.PFF_2025_SOURCES = []
base.manual_player_prop_observations = manual_player_prop_observations


if __name__ == "__main__":
    base.main()
