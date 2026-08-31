from __future__ import annotations

import io
import math
import re
import time
import unicodedata
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)
INFILE = OUT / "master_player_season_panel_2020_2025_v0_5.csv"
OUTFILE = OUT / "master_player_season_panel_2020_2025_v0_6.csv"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Safari/537.36"
)

PFR_URL = "https://www.pro-football-reference.com/years/{season}/preseason_odds.htm"

TEAM_NAME_TO_ABBR = {
    "arizona cardinals": "ARI",
    "atlanta falcons": "ATL",
    "baltimore ravens": "BAL",
    "buffalo bills": "BUF",
    "carolina panthers": "CAR",
    "chicago bears": "CHI",
    "cincinnati bengals": "CIN",
    "cleveland browns": "CLE",
    "dallas cowboys": "DAL",
    "denver broncos": "DEN",
    "detroit lions": "DET",
    "green bay packers": "GB",
    "houston texans": "HOU",
    "indianapolis colts": "IND",
    "jacksonville jaguars": "JAX",
    "kansas city chiefs": "KC",
    "las vegas raiders": "LV",
    "los angeles chargers": "LAC",
    "los angeles rams": "LAR",
    "miami dolphins": "MIA",
    "minnesota vikings": "MIN",
    "new england patriots": "NE",
    "new orleans saints": "NO",
    "new york giants": "NYG",
    "new york jets": "NYJ",
    "philadelphia eagles": "PHI",
    "pittsburgh steelers": "PIT",
    "san francisco 49ers": "SF",
    "seattle seahawks": "SEA",
    "tampa bay buccaneers": "TB",
    "tennessee titans": "TEN",
    "washington football team": "WAS",
    "washington commanders": "WAS",
    "washington redskins": "WAS",
}

TEAM_ABBR_ALIASES = {
    "JAC": "JAX",
    "JAX": "JAX",
    "LA": "LAR",
    "LAR": "LAR",
    "WSH": "WAS",
    "WAS": "WAS",
}

PFF_2025_SOURCES = [
    {
        "season": 2025,
        "source_url": "https://www.pff.com/news/bet-nfl-betting-2025-pff-fantasy-projections-passing-props",
        "source_date": "2025-06-13",
        "source_provider": "PFF",
        "book": "FanDuel",
        "sampling_frame": "projection_screened_extremes",
        "source_state": "preserved_projection_screened_table",
        "notes": "Public comparison tables selected for large PFF-projection versus market-line differences; not a representative full player-prop board.",
    },
    {
        "season": 2025,
        "source_url": "https://www.pff.com/news/bet-nfl-betting-2025-pff-fantasy-projections-rushing-props",
        "source_date": "2025-06-17",
        "source_provider": "PFF",
        "book": "DraftKings/Caesars (page-level attribution)",
        "sampling_frame": "projection_screened_extremes",
        "source_state": "preserved_projection_screened_table",
        "notes": "Public comparison tables selected for large PFF-projection versus market-line differences; individual book is not identified for every row.",
    },
    {
        "season": 2025,
        "source_url": "https://www.pff.com/news/bet-nfl-betting-2025-pff-fantasy-projections-receiving-props",
        "source_date": "2025-06-19",
        "source_provider": "PFF",
        "book": "FanDuel/DraftKings/Caesars (page-level attribution)",
        "sampling_frame": "projection_screened_extremes",
        "source_state": "preserved_projection_screened_table",
        "notes": "Public comparison tables selected for large PFF-projection versus market-line differences; individual book is not identified for every row.",
    },
]

PFF_2021_URL = "https://www.pff.com/news/bet-nfl-betting-guide-2021-nfl-season"
FBG_2024_WR_URL = "https://www.footballguys.com/article/2024-season-long-player-props-wide-receivers"
FOURFORFOUR_URL = "https://www.4for4.com/2023/preseason/key-winning-season-long-player-props"


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_team_abbr(value) -> str:
    raw = str(value or "").strip().upper()
    return TEAM_ABBR_ALIASES.get(raw, raw)


def to_number(value):
    if value is None or pd.isna(value):
        return np.nan
    match = re.search(r"[+-]?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else np.nan


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [" ".join(str(x) for x in col if str(x) != "nan").strip() for col in out.columns]
    else:
        out.columns = [str(col).strip() for col in out.columns]
    return out


def fetch_text(url: str, *, tries: int = 3, pause: float = 1.5) -> tuple[str, str, int]:
    """Fetch a page, trying the source directly and then a text-preserving mirror."""
    candidates = [
        url,
        "https://r.jina.ai/http://" + re.sub(r"^https?://", "", url),
        "https://r.jina.ai/https://" + re.sub(r"^https?://", "", url),
    ]
    errors = []
    for candidate in candidates:
        for attempt in range(tries):
            try:
                response = requests.get(
                    candidate,
                    headers={
                        "User-Agent": UA,
                        "Accept": "text/html,text/plain,application/xhtml+xml,*/*",
                    },
                    timeout=60,
                )
                if response.status_code == 200 and len(response.text) > 500:
                    return response.text, candidate, response.status_code
                errors.append(f"{candidate} status={response.status_code} len={len(response.text)}")
            except Exception as exc:
                errors.append(f"{candidate} {type(exc).__name__}: {exc}")
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"Unable to fetch {url}: {'; '.join(errors)}")


def _read_html_tables(text: str) -> list[pd.DataFrame]:
    variants = [text]
    if "<!--" in text:
        variants.append(text.replace("<!--", "").replace("-->", ""))
    for variant in variants:
        try:
            tables = [flatten_columns(table) for table in pd.read_html(io.StringIO(variant))]
            if tables:
                return tables
        except ValueError:
            continue
    return []


def _team_from_name(name: str) -> str | None:
    clean_name = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", str(name)).replace("**", "")
    return TEAM_NAME_TO_ABBR.get(norm_text(clean_name))


def _find_pfr_table(tables: Iterable[pd.DataFrame]) -> pd.DataFrame | None:
    for table in tables:
        mapped = {norm_text(column): column for column in table.columns}
        team_col = next((mapped[key] for key in mapped if key in {"tm", "team"}), None)
        total_col = next((mapped[key] for key in mapped if "w l o u" in key or "w l over under" in key), None)
        if team_col is not None and total_col is not None and len(table) >= 30:
            return table
    return None


def _parse_pfr_markdown(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 3:
            continue
        team = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", parts[0]).replace("**", "").strip()
        abbr = _team_from_name(team)
        if not abbr:
            continue
        sb = to_number(parts[1])
        total = to_number(parts[2])
        if pd.isna(total):
            continue
        rows.append({"Tm": team, "Super Bowl Odds": sb, "W/L O-U": total})
    return pd.DataFrame(rows).drop_duplicates(subset=["Tm"], keep="last")


def _extract_updated_date(text: str) -> str | None:
    match = re.search(r"Updated\s+([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})", text)
    if not match:
        return None
    parsed = pd.to_datetime(match.group(1), errors="coerce")
    return parsed.strftime("%Y-%m-%d") if not pd.isna(parsed) else None


def fetch_team_market(season: int) -> tuple[pd.DataFrame, dict]:
    canonical_url = PFR_URL.format(season=season)
    text, retrieval_url, status = fetch_text(canonical_url)
    tables = _read_html_tables(text)
    table = _find_pfr_table(tables)
    if table is None:
        table = _parse_pfr_markdown(text)
    if table is None or table.empty:
        raise RuntimeError(f"No preseason odds table found for {season}: {canonical_url}")

    mapped = {norm_text(column): column for column in table.columns}
    team_col = next((mapped[key] for key in mapped if key in {"tm", "team"}), table.columns[0])
    sb_col = next((mapped[key] for key in mapped if "super bowl" in key), None)
    total_col = next((mapped[key] for key in mapped if "w l o u" in key or "w l over under" in key), None)
    if total_col is None and "W/L O-U" in table.columns:
        total_col = "W/L O-U"
    if total_col is None:
        raise RuntimeError(f"Missing win-total column for {season}: {list(table.columns)}")

    rows = []
    for _, row in table.iterrows():
        source_team = str(row[team_col]).strip()
        team = _team_from_name(source_team)
        total = to_number(row[total_col])
        if not team or pd.isna(total):
            continue
        rows.append(
            {
                "season": season,
                "team": team,
                "source_team": source_team,
                "win_total": total,
                "super_bowl_odds_american": to_number(row[sb_col]) if sb_col else np.nan,
                "over_odds_american": np.nan,
                "under_odds_american": np.nan,
                "snapshot_date": _extract_updated_date(text),
                "snapshot_window": "final_preseason_archive",
                "book": "archive consensus / book not specified",
                "source_provider": "Pro-Football-Reference",
                "underlying_provider": "SportsOddsHistory.com",
                "source_state": "retrospective_preserved_final_preseason_line",
                "source_url": canonical_url,
                "retrieval_url": retrieval_url,
                "retrieval_status": status,
                "notes": "Archived preseason team win total; line is preserved as a team-environment feature, not an offense-only forecast.",
            }
        )
    result = pd.DataFrame(rows).drop_duplicates(subset=["season", "team"], keep="last")
    if len(result) != 32:
        missing = sorted(set(TEAM_NAME_TO_ABBR.values()) - set(result["team"]))
        raise RuntimeError(f"Expected 32 team rows for {season}; got {len(result)}; missing={missing}")
    table.to_csv(OUT / f"sportsbook_team_market_raw_{season}.csv", index=False)
    manifest = {
        "season": season,
        "signal_family": "team_win_total",
        "source_provider": "Pro-Football-Reference",
        "underlying_provider": "SportsOddsHistory.com",
        "source_state": "retrospective_preserved_final_preseason_line",
        "source_url": canonical_url,
        "retrieval_url": retrieval_url,
        "snapshot_date": result["snapshot_date"].iloc[0],
        "snapshot_window": "final_preseason_archive",
        "source_rows": len(result),
        "primary_model_eligible": True,
        "notes": "Complete 32-team preseason win-total archive. Book-level prices are not exposed consistently, so only the line is canonical.",
    }
    time.sleep(1.0)
    return result, manifest


def _market_type_from_label(label: str) -> str | None:
    clean = norm_text(label)
    rules = [
        ("passing yards", "pass_yards"),
        ("passing tds", "pass_tds"),
        ("passing td", "pass_tds"),
        ("interceptions", "pass_interceptions"),
        ("rushing attempts", "rush_attempts"),
        ("qb rushing yards", "rush_yards"),
        ("rushing yards", "rush_yards"),
        ("rushing tds", "rush_tds"),
        ("rushing td", "rush_tds"),
        ("rushing and receiving yards", "rush_rec_yards"),
        ("rush rec yards", "rush_rec_yards"),
        ("receiving yards", "rec_yards"),
        ("receiving tds", "rec_tds"),
        ("receiving td", "rec_tds"),
        ("receptions", "receptions"),
    ]
    for phrase, market_type in rules:
        if phrase in clean:
            return market_type
    return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[-80:]


def _prop_row(
    *,
    season: int,
    player_name: str,
    position: str | None,
    market_type: str,
    line: float,
    source_date: str,
    source_provider: str,
    book: str,
    source_url: str,
    retrieval_url: str | None,
    source_state: str,
    sampling_frame: str,
    recommendation_side: str | None,
    recommendation_odds: float | int | None,
    projection: float | None,
    projection_line_differential: float | None,
    primary_model_eligible: bool,
    notes: str,
    raw_market_label: str,
) -> dict:
    return {
        "season": season,
        "player_name": player_name,
        "position": position or "",
        "market_type": market_type,
        "raw_market_label": raw_market_label,
        "line": float(line),
        "over_odds_american": np.nan,
        "under_odds_american": np.nan,
        "recommendation_side": recommendation_side or "",
        "recommendation_odds_american": to_number(recommendation_odds),
        "projection": to_number(projection),
        "projection_line_differential": to_number(projection_line_differential),
        "book": book,
        "source_date": source_date,
        "source_provider": source_provider,
        "source_url": source_url,
        "retrieval_url": retrieval_url or source_url,
        "source_state": source_state,
        "sampling_frame": sampling_frame,
        "primary_model_eligible": bool(primary_model_eligible),
        "notes": notes,
    }


def extract_pff_2025(source: dict) -> tuple[pd.DataFrame, dict]:
    text, retrieval_url, status = fetch_text(source["source_url"])
    tables = _read_html_tables(text)
    observations = []
    raw_tables = []
    for table_number, table in enumerate(tables):
        mapped = {norm_text(column): column for column in table.columns}
        player_col = next((mapped[key] for key in mapped if key in {"name", "player"}), None)
        if player_col is None:
            continue
        line_columns = [column for column in table.columns if "line" in norm_text(column) and "differential" not in norm_text(column)]
        if not line_columns:
            continue
        raw_tables.append(table.assign(_table_number=table_number))
        for line_column in line_columns:
            market_type = _market_type_from_label(str(line_column))
            if market_type is None:
                continue
            prefix = norm_text(line_column).replace(" line", "").strip()
            projection_column = next(
                (
                    column
                    for column in table.columns
                    if "projection" in norm_text(column)
                    and prefix
                    and prefix in norm_text(column)
                    and "differential" not in norm_text(column)
                ),
                None,
            )
            differential_column = next(
                (
                    column
                    for column in table.columns
                    if "differential" in norm_text(column) and prefix and prefix in norm_text(column)
                ),
                None,
            )
            for _, row in table.iterrows():
                player = str(row[player_col]).strip()
                line = to_number(row[line_column])
                if not player or player.lower() in {"nan", "name", "player"} or pd.isna(line):
                    continue
                projection = to_number(row[projection_column]) if projection_column else np.nan
                differential = to_number(row[differential_column]) if differential_column else np.nan
                direction = None
                if not pd.isna(differential):
                    direction = "over" if differential > 0 else "under" if differential < 0 else "push"
                observations.append(
                    _prop_row(
                        season=source["season"],
                        player_name=player,
                        position=None,
                        market_type=market_type,
                        line=line,
                        source_date=source["source_date"],
                        source_provider=source["source_provider"],
                        book=source["book"],
                        source_url=source["source_url"],
                        retrieval_url=retrieval_url,
                        source_state=source["source_state"],
                        sampling_frame=source["sampling_frame"],
                        recommendation_side=direction,
                        recommendation_odds=np.nan,
                        projection=projection,
                        projection_line_differential=differential,
                        primary_model_eligible=False,
                        notes=source["notes"],
                        raw_market_label=str(line_column),
                    )
                )
    if not observations:
        raise RuntimeError(f"No PFF 2025 player-prop observations found: {source['source_url']}")
    raw = pd.concat(raw_tables, ignore_index=True) if raw_tables else pd.DataFrame()
    raw.to_csv(OUT / f"sportsbook_player_prop_raw_{source['season']}_{_slug(source['source_url'])}.csv", index=False)
    result = pd.DataFrame(observations).drop_duplicates(
        subset=["season", "player_name", "market_type", "line", "source_url"], keep="first"
    )
    manifest = {
        "season": source["season"],
        "signal_family": "player_season_prop",
        "source_provider": source["source_provider"],
        "underlying_provider": source["book"],
        "source_state": source["source_state"],
        "source_url": source["source_url"],
        "retrieval_url": retrieval_url,
        "snapshot_date": source["source_date"],
        "snapshot_window": "early_preseason_selected",
        "source_rows": len(result),
        "primary_model_eligible": False,
        "notes": source["notes"],
        "retrieval_status": status,
    }
    return result, manifest


def manual_player_prop_observations() -> tuple[pd.DataFrame, list[dict]]:
    rows = []
    pff_2021 = [
        ("David Montgomery", "RB", "rush_yards", 1075.5, None, None),
        ("Darnell Mooney", "WR", "rec_yards", 700.5, None, None),
        ("Cole Kmet", "TE", "receptions", 42.5, "over", -115),
        ("Allen Robinson II", "WR", "receptions", 94.5, None, None),
        ("Jared Goff", "QB", "pass_yards", 4150.5, None, None),
        ("Jamaal Williams", "RB", "rush_rec_yards", 725.5, None, None),
        ("Breshad Perriman", "WR", "rec_yards", 750.5, None, None),
        ("T.J. Hockenson", "TE", "rec_yards", 770.5, "over", -115),
        ("D'Andre Swift", "RB", "receptions", 52.5, None, None),
        ("Kirk Cousins", "QB", "pass_yards", 4100.5, None, None),
        ("Dalvin Cook", "RB", "rush_yards", 1350.5, "under", -118),
    ]
    for player, position, market, line, side, odds in pff_2021:
        rows.append(
            _prop_row(
                season=2021,
                player_name=player,
                position=position,
                market_type=market,
                line=line,
                source_date="2021-08-04",
                source_provider="PFF",
                book="DraftKings",
                source_url=PFF_2021_URL,
                retrieval_url=PFF_2021_URL,
                source_state="preserved_regional_public_excerpt",
                sampling_frame="regional_public_excerpt_nfc_north",
                recommendation_side=side,
                recommendation_odds=odds,
                projection=np.nan,
                projection_line_differential=np.nan,
                primary_model_eligible=False,
                notes="Public NFC North excerpt from a league betting guide; not a representative NFL-wide prop board.",
                raw_market_label=market,
            )
        )

    fbg_2024 = [
        ("DK Metcalf", "WR", "rec_yards", 1000.5, "over", -110, "DraftKings"),
        ("Tank Dell", "WR", "rec_yards", 825.5, "over", -105, "DraftKings"),
        ("Curtis Samuel", "WR", "rec_yards", 650.5, "under", -115, "book label unavailable in preserved page"),
        ("DeMario Douglas", "WR", "rec_yards", 600.5, "over", -115, "Caesars"),
        ("Calvin Ridley", "WR", "rec_yards", 875.5, "over", -105, "DraftKings"),
    ]
    for player, position, market, line, side, odds, book in fbg_2024:
        rows.append(
            _prop_row(
                season=2024,
                player_name=player,
                position=position,
                market_type=market,
                line=line,
                source_date="2024-08-07",
                source_provider="Footballguys",
                book=book,
                source_url=FBG_2024_WR_URL,
                retrieval_url=FBG_2024_WR_URL,
                source_state="preserved_editorial_selected",
                sampling_frame="editorial_selected_props",
                recommendation_side=side,
                recommendation_odds=odds,
                projection=np.nan,
                projection_line_differential=np.nan,
                primary_model_eligible=False,
                notes="Five editorially selected wide-receiver season props; not a representative full-board snapshot.",
                raw_market_label="receiving yards",
            )
        )

    manifests = [
        {
            "season": 2021,
            "signal_family": "player_season_prop",
            "source_provider": "PFF",
            "underlying_provider": "DraftKings",
            "source_state": "preserved_regional_public_excerpt",
            "source_url": PFF_2021_URL,
            "retrieval_url": PFF_2021_URL,
            "snapshot_date": "2021-08-04",
            "snapshot_window": "preseason_excerpt",
            "source_rows": len(pff_2021),
            "primary_model_eligible": False,
            "notes": "Public NFC North excerpt only; not a full NFL-wide player-prop board.",
        },
        {
            "season": 2024,
            "signal_family": "player_season_prop",
            "source_provider": "Footballguys",
            "underlying_provider": "multiple/row-level",
            "source_state": "preserved_editorial_selected",
            "source_url": FBG_2024_WR_URL,
            "retrieval_url": FBG_2024_WR_URL,
            "snapshot_date": "2024-08-07",
            "snapshot_window": "preseason_editorial_selection",
            "source_rows": len(fbg_2024),
            "primary_model_eligible": False,
            "notes": "Five selected wide-receiver props with book and recommendation; not representative full-board data.",
        },
    ]
    return pd.DataFrame(rows), manifests


def category_calibration() -> pd.DataFrame:
    annual = [
        (2021, "receiving_yards", 34, 51),
        (2021, "receiving_tds", 19, 26),
        (2021, "receptions", 8, 15),
        (2021, "rush_yards", 15, 23),
        (2021, "rush_tds", 7, 18),
        (2021, "rush_rec_yards", 6, 7),
        (2021, "pass_yards", 6, 21),
        (2021, "qb_rush_yards", 3, 3),
        (2021, "qb_rush_tds", 1, 4),
        (2021, "pass_interceptions", 1, 1),
        (2022, "receiving_yards", 33, 39),
        (2022, "receiving_tds", 21, 37),
        (2022, "receptions", 21, 29),
        (2022, "rush_yards", 15, 18),
        (2022, "rush_tds", 13, 21),
        (2022, "rush_rec_yards", 5, 8),
        (2022, "pass_yards", 9, 22),
        (2022, "qb_rush_yards", 5, 3),
        (2022, "qb_rush_tds", 3, 3),
        (2022, "pass_interceptions", 10, 20),
    ]
    rows = []
    for season, category, overs, unders in annual:
        total = overs + unders
        rows.append(
            {
                "season": season,
                "market_category": category,
                "overs": overs,
                "unders": unders,
                "total": total,
                "under_rate": unders / total,
                "source_url": FOURFORFOUR_URL,
                "source_state": "published_category_aggregate",
                "primary_player_level_model_eligible": False,
                "notes": "Category-level closing-prop result aggregate; useful for calibration design, not player-level feature ingestion.",
            }
        )
    base = pd.DataFrame(rows)
    combined = base.groupby("market_category", as_index=False)[["overs", "unders", "total"]].sum()
    combined["season"] = "2021-2022 combined"
    combined["under_rate"] = combined["unders"] / combined["total"]
    combined["source_url"] = FOURFORFOUR_URL
    combined["source_state"] = "published_category_aggregate"
    combined["primary_player_level_model_eligible"] = False
    combined["notes"] = "Combined category-level closing-prop result aggregate."
    return pd.concat([base, combined[base.columns]], ignore_index=True)


def infer_position(panel: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    obs = observations.copy()
    by_season_name = {}
    for _, row in panel[["season", "player_name", "position"]].dropna().iterrows():
        by_season_name[(int(row["season"]), norm_text(row["player_name"]))] = str(row["position"]).upper()
    missing = obs["position"].astype(str).str.strip().eq("")
    obs.loc[missing, "position"] = [
        by_season_name.get((int(season), norm_text(name)), "")
        for season, name in zip(obs.loc[missing, "season"], obs.loc[missing, "player_name"])
    ]
    return obs


def match_player_observations(panel: pd.DataFrame, observations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    obs = infer_position(panel, observations)
    qa_rows = []
    aliases = {
        "ken walker": "kenneth walker",
        "gabe davis": "gabriel davis",
        "hollywood brown": "marquise brown",
    }
    panel_groups = {
        season: panel[panel["season"].eq(season)]
        for season in sorted(panel["season"].dropna().astype(int).unique())
    }
    matched_ids = []
    matched_names = []
    matched_positions = []
    matched_teams = []
    match_methods = []
    match_scores = []

    for _, row in obs.iterrows():
        season = int(row["season"])
        position = str(row.get("position", "")).upper()
        target_name = aliases.get(norm_text(row["player_name"]), norm_text(row["player_name"]))
        candidates = panel_groups[season]
        if position in {"QB", "RB", "WR", "TE"}:
            candidates = candidates[candidates["position"].astype(str).str.upper().eq(position)]
        exact = candidates[candidates["player_name"].map(norm_text).eq(target_name)]
        target = exact.iloc[0] if len(exact) == 1 else None
        method = "exact" if target is not None else "unmatched"
        score = 100.0 if target is not None else np.nan
        if target is None and not candidates.empty:
            labels = candidates["player_name"].map(norm_text).tolist()
            match = process.extract(target_name, labels, scorer=fuzz.ratio, limit=2)
            if match and match[0][1] >= 94 and (len(match) == 1 or match[0][1] - match[1][1] >= 4):
                target = candidates.iloc[labels.index(match[0][0])]
                method = "fuzzy"
                score = float(match[0][1])
        matched = target is not None
        matched_ids.append(target["canonical_player_id"] if matched else "")
        matched_names.append(target["player_name"] if matched else "")
        matched_positions.append(target["position"] if matched else "")
        matched_teams.append(target["preseason_team"] if matched else "")
        match_methods.append(method)
        match_scores.append(score)
        qa_rows.append(
            {
                "season": season,
                "source_player": row["player_name"],
                "source_position": position,
                "market_type": row["market_type"],
                "source_url": row["source_url"],
                "matched": matched,
                "match_method": method,
                "match_score": score,
                "panel_player": target["player_name"] if matched else "",
                "canonical_player_id": target["canonical_player_id"] if matched else "",
            }
        )

    obs["canonical_player_id"] = matched_ids
    obs["panel_player_name"] = matched_names
    obs["panel_position"] = matched_positions
    obs["panel_preseason_team"] = matched_teams
    obs["match_method"] = match_methods
    obs["match_score"] = match_scores
    return obs, pd.DataFrame(qa_rows)


def attach_team_market(panel: pd.DataFrame, team_market: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    text_fields = [
        "team_win_total_snapshot_date",
        "team_win_total_snapshot_window",
        "team_win_total_source_state",
        "team_win_total_source_url",
        "team_win_total_retrieval_url",
        "team_win_total_source_provider",
        "team_win_total_underlying_provider",
        "team_win_total_book",
    ]
    numeric_fields = ["team_win_total_super_bowl_odds"]
    for field in text_fields:
        if field not in out.columns:
            out[field] = pd.Series([None] * len(out), dtype="object")
    for field in numeric_fields:
        if field not in out.columns:
            out[field] = np.nan

    lookup = team_market.set_index(["season", "team"])
    for idx, row in out.iterrows():
        key = (int(row["season"]), normalize_team_abbr(row["preseason_team"]))
        if key not in lookup.index:
            continue
        source = lookup.loc[key]
        out.at[idx, "team_win_total"] = source["win_total"]
        out.at[idx, "team_win_total_super_bowl_odds"] = source["super_bowl_odds_american"]
        out.at[idx, "team_win_total_snapshot_date"] = source["snapshot_date"]
        out.at[idx, "team_win_total_snapshot_window"] = source["snapshot_window"]
        out.at[idx, "team_win_total_source_state"] = source["source_state"]
        out.at[idx, "team_win_total_source_url"] = source["source_url"]
        out.at[idx, "team_win_total_retrieval_url"] = source["retrieval_url"]
        out.at[idx, "team_win_total_source_provider"] = source["source_provider"]
        out.at[idx, "team_win_total_underlying_provider"] = source["underlying_provider"]
        out.at[idx, "team_win_total_book"] = source["book"]
    return out


def attach_prop_metadata(panel: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    for field in ["sportsbook_player_prop_observation_count", "sportsbook_player_prop_source_count"]:
        if field not in out.columns:
            out[field] = 0
    if "sportsbook_player_prop_sampling_frames" not in out.columns:
        out["sportsbook_player_prop_sampling_frames"] = pd.Series([None] * len(out), dtype="object")
    if "sportsbook_player_prop_primary_model_eligible" not in out.columns:
        out["sportsbook_player_prop_primary_model_eligible"] = False

    matched = observations[observations["canonical_player_id"].astype(str).ne("")].copy()
    if matched.empty:
        return out
    aggregate = matched.groupby(["season", "canonical_player_id"]).agg(
        sportsbook_player_prop_observation_count=("market_type", "size"),
        sportsbook_player_prop_source_count=("source_url", "nunique"),
        sportsbook_player_prop_sampling_frames=(
            "sampling_frame",
            lambda values: " | ".join(sorted(set(str(v) for v in values if str(v)))),
        ),
        sportsbook_player_prop_primary_model_eligible=("primary_model_eligible", "any"),
    )
    for idx, row in out.iterrows():
        key = (int(row["season"]), row["canonical_player_id"])
        if key not in aggregate.index:
            continue
        source = aggregate.loc[key]
        for field in aggregate.columns:
            out.at[idx, field] = source[field]
    return out


def coverage_report(panel: pd.DataFrame, observations: pd.DataFrame, team_market: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for season in range(2020, 2026):
        mask = panel["season"].eq(season)
        draft = mask & panel["draft_market_present"].fillna(False).astype(bool)
        team_rows = team_market[team_market["season"].eq(season)]
        selected = observations[observations["season"].eq(season)]
        matched_selected = selected[selected["canonical_player_id"].astype(str).ne("")]
        eligible = matched_selected[matched_selected["primary_model_eligible"].fillna(False).astype(bool)]
        rows.append(
            {
                "season": season,
                "panel_rows": int(mask.sum()),
                "draft_market_rows": int(draft.sum()),
                "team_source_rows": len(team_rows),
                "panel_team_win_total_coverage_pct": round(100 * panel.loc[mask, "team_win_total"].notna().mean(), 2),
                "draft_market_team_win_total_coverage_pct": round(100 * panel.loc[draft, "team_win_total"].notna().mean(), 2),
                "selected_player_prop_observations": len(selected),
                "selected_player_prop_matched": len(matched_selected),
                "selected_player_prop_unique_players": int(matched_selected["canonical_player_id"].nunique()),
                "primary_model_eligible_player_prop_rows": len(eligible),
                "formal_model_c_player_prop_coverage_pct": 0.0,
                "team_environment_status": "READY" if len(team_rows) == 32 else "FAIL",
                "player_prop_status": "NESTED_EXPLORATORY_ONLY" if len(selected) else "SOURCE_GAP",
            }
        )
    return pd.DataFrame(rows)


def assert_source_discipline(panel: pd.DataFrame, observations: pd.DataFrame, team_market: pd.DataFrame) -> None:
    if len(team_market) != 32 * 6:
        raise AssertionError(f"Expected 192 team-market rows; got {len(team_market)}")
    reserved_vegas_fields = [
        "vegas_pass_yards",
        "vegas_pass_tds",
        "vegas_rush_yards",
        "vegas_rush_tds",
        "vegas_receptions",
        "vegas_rec_yards",
        "vegas_rec_tds",
        "vegas_snapshot_date",
    ]
    contaminated = {field: int(panel[field].notna().sum()) for field in reserved_vegas_fields if panel[field].notna().any()}
    if contaminated:
        raise AssertionError(f"Sampling-biased selected props contaminated primary vegas fields: {contaminated}")
    if panel["team_offense_market_score"].notna().any():
        raise AssertionError("team_offense_market_score must remain null; a generic win total is not offense-specific")
    match_rate = observations["canonical_player_id"].astype(str).ne("").mean() if len(observations) else 1.0
    if match_rate < 0.95:
        raise AssertionError(f"Player-prop match rate below 95%: {match_rate:.3%}")
    if observations["primary_model_eligible"].fillna(False).any():
        raise AssertionError("No selected/excerpt player-prop observation is eligible for the formal Model-C feature")


def main() -> None:
    panel = pd.read_csv(INFILE, low_memory=False)
    manifests = []
    team_frames = []

    print("Building complete 2020-2025 team win-total layer")
    for season in range(2020, 2026):
        frame, manifest = fetch_team_market(season)
        team_frames.append(frame)
        manifests.append(manifest)
        print(f"  {season}: team rows={len(frame)} retrieval={manifest['retrieval_url']}")
    team_market = pd.concat(team_frames, ignore_index=True)
    team_market.to_csv(OUT / "sportsbook_team_market_observations_v06.csv", index=False)

    prop_frames = []
    manual, manual_manifests = manual_player_prop_observations()
    prop_frames.append(manual)
    manifests.extend(manual_manifests)

    print("Building preserved selected player-prop observation archive")
    for source in PFF_2025_SOURCES:
        frame, manifest = extract_pff_2025(source)
        prop_frames.append(frame)
        manifests.append(manifest)
        print(f"  {source['source_date']} {source['source_url'].rsplit('/', 1)[-1]}: rows={len(frame)}")

    prop_observations = pd.concat(prop_frames, ignore_index=True).drop_duplicates(
        subset=["season", "player_name", "market_type", "line", "source_url"], keep="first"
    )
    prop_observations, match_qa = match_player_observations(panel, prop_observations)
    prop_observations.to_csv(OUT / "sportsbook_player_prop_observations_v06.csv", index=False)
    match_qa.to_csv(OUT / "sportsbook_match_qa_v06.csv", index=False)

    calibration = category_calibration()
    calibration.to_csv(OUT / "sportsbook_category_calibration_v06.csv", index=False)
    manifests.append(
        {
            "season": "2021-2022",
            "signal_family": "player_prop_category_calibration",
            "source_provider": "4for4",
            "underlying_provider": "closing season-long player-prop sample",
            "source_state": "published_category_aggregate",
            "source_url": FOURFORFOUR_URL,
            "retrieval_url": FOURFORFOUR_URL,
            "snapshot_date": "2023-06-15",
            "snapshot_window": "published_retrospective_study",
            "source_rows": len(calibration[calibration["season"].isin([2021, 2022])]),
            "primary_model_eligible": False,
            "notes": "604 closing props in aggregate: 235 overs and 369 unders. Category counts are retained for calibration design, not player-level joins.",
        }
    )
    manifests.append(
        {
            "season": "2020-2025 audit",
            "signal_family": "player_season_prop",
            "source_provider": "public-source audit",
            "underlying_provider": "multiple",
            "source_state": "no_comprehensive_public_historical_archive_identified",
            "source_url": "",
            "retrieval_url": "",
            "snapshot_date": "2026-08-30",
            "snapshot_window": "research_audit",
            "source_rows": 0,
            "primary_model_eligible": False,
            "notes": "No comprehensive, consistently sampled, timestamped public NFL season-futures player-prop archive was verified across 2020-2025. Formal Model C remains a nested future study.",
        }
    )

    panel = attach_team_market(panel, team_market)
    panel = attach_prop_metadata(panel, prop_observations)
    assert_source_discipline(panel, prop_observations, team_market)

    coverage = coverage_report(panel, prop_observations, team_market)
    coverage.to_csv(OUT / "sportsbook_coverage_qa_v06.csv", index=False)
    pd.DataFrame(manifests).to_csv(OUT / "sportsbook_source_manifest_v06.csv", index=False)
    panel.to_csv(OUTFILE, index=False)

    print("\nSportsbook coverage QA")
    print(coverage.to_string(index=False))
    print("\nPlayer-prop match QA")
    print(match_qa.groupby(["season", "matched"])["source_player"].count().to_string())
    print(f"\nWrote {OUTFILE} rows={len(panel):,}")
    print("Source discipline: team win totals attached; selected player props archived but primary vegas_* fields remain null.")


if __name__ == "__main__":
    main()
