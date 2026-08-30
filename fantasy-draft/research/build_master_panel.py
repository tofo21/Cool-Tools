from __future__ import annotations

import io
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests
from rapidfuzz import fuzz, process

SEASONS = list(range(2020, 2026))
POSITIONS = {"QB", "RB", "WR", "TE"}
OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

KICKOFF = {
    2020: date(2020, 9, 10),
    2021: date(2021, 9, 9),
    2022: date(2022, 9, 8),
    2023: date(2023, 9, 7),
    2024: date(2024, 9, 5),
    2025: date(2025, 9, 4),
}

ECR_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_fpecr.parquet"
PLAYERIDS_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
FFC_URL = "https://fantasyfootballcalculator.com/api/v1/adp/ppr"
NFLVERSE_SUMMARY_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg_{season}.csv"
NFLVERSE_WEEKLY_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "FantasyDraftIntelligenceResearch/0.1 (+https://github.com/tofo21/Cool-Tools)"
})


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_bytes(url: str, timeout: int = 180) -> bytes:
    last = None
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_id(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "na"}:
        return None
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def first_existing(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for n in names:
        if n in df.columns:
            return n
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def numeric_series(df: pd.DataFrame, names: Iterable[str], default=0.0) -> pd.Series:
    col = first_existing(df, names)
    if col is None:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default).astype(float)


def load_nflverse_outcomes(season: int) -> pd.DataFrame:
    raw = pd.read_csv(io.BytesIO(get_bytes(NFLVERSE_SUMMARY_URL.format(season=season))), low_memory=False)
    if "season_type" in raw.columns:
        raw = raw[raw["season_type"].astype(str).str.upper().eq("REG")].copy()

    id_col = first_existing(raw, ["player_id", "gsis_id"])
    name_col = first_existing(raw, ["player_display_name", "player_name", "player", "name"])
    pos_col = first_existing(raw, ["position", "pos"])
    team_col = first_existing(raw, ["recent_team", "team", "tm"])
    if not name_col or not pos_col:
        raise RuntimeError(f"nflverse {season}: required name/position columns not found: {list(raw.columns)}")

    out = pd.DataFrame(index=raw.index)
    out["season"] = season
    out["gsis_id"] = raw[id_col].map(clean_id) if id_col else None
    out["outcome_name"] = raw[name_col].astype(str)
    out["position"] = raw[pos_col].astype(str).str.upper().str.strip()
    out["outcome_team"] = raw[team_col].astype(str).replace({"nan": np.nan}) if team_col else np.nan

    stat_aliases = {
        "passing_yards": ["passing_yards", "pass_yards"],
        "passing_tds": ["passing_tds", "passing_td", "pass_tds"],
        "interceptions": ["interceptions", "passing_interceptions", "int"],
        "passing_2pt": ["passing_2pt_conversions", "passing_2pt"],
        "rushing_attempts": ["carries", "rushing_attempts", "rushing_att"],
        "rushing_yards": ["rushing_yards", "rush_yards"],
        "rushing_tds": ["rushing_tds", "rushing_td", "rush_tds"],
        "rushing_2pt": ["rushing_2pt_conversions", "rushing_2pt"],
        "targets": ["targets", "tgt"],
        "receptions": ["receptions", "rec"],
        "receiving_yards": ["receiving_yards", "rec_yards"],
        "receiving_tds": ["receiving_tds", "receiving_td", "rec_tds"],
        "receiving_2pt": ["receiving_2pt_conversions", "receiving_2pt"],
        "special_teams_tds": ["special_teams_tds", "return_tds"],
    }
    for dest, aliases in stat_aliases.items():
        out[dest] = numeric_series(raw, aliases)

    generic_fl = first_existing(raw, ["fumbles_lost"])
    if generic_fl:
        out["fumbles_lost"] = pd.to_numeric(raw[generic_fl], errors="coerce").fillna(0).astype(float)
    else:
        fum_cols = [
            first_existing(raw, ["sack_fumbles_lost"]),
            first_existing(raw, ["rushing_fumbles_lost"]),
            first_existing(raw, ["receiving_fumbles_lost"]),
            first_existing(raw, ["passing_fumbles_lost"]),
        ]
        out["fumbles_lost"] = 0.0
        for col in {c for c in fum_cols if c}:
            out["fumbles_lost"] += pd.to_numeric(raw[col], errors="coerce").fillna(0).astype(float)

    source_ppr = first_existing(raw, ["fantasy_points_ppr"])
    out["source_ppr_points"] = pd.to_numeric(raw[source_ppr], errors="coerce") if source_ppr else np.nan

    games_col = first_existing(raw, ["games", "games_played", "g"])
    if games_col:
        out["games_played"] = pd.to_numeric(raw[games_col], errors="coerce").fillna(0).astype(float)
        out["games_source"] = "nflverse_summary"
    else:
        # Fallback: count player-week rows. This can slightly undercount players who dressed but logged no stats.
        weekly = pd.read_csv(io.BytesIO(get_bytes(NFLVERSE_WEEKLY_URL.format(season=season))), low_memory=False)
        if "season_type" in weekly.columns:
            weekly = weekly[weekly["season_type"].astype(str).str.upper().eq("REG")]
        wid = first_existing(weekly, ["player_id", "gsis_id"])
        wname = first_existing(weekly, ["player_display_name", "player_name", "player", "name"])
        wpos = first_existing(weekly, ["position", "pos"])
        if wid and id_col:
            counts = weekly.groupby(wid, dropna=False).size()
            out["games_played"] = raw[id_col].map(counts).fillna(0).astype(float)
            out["games_source"] = "nflverse_week_rows"
        else:
            weekly["_key"] = weekly[wname].map(norm_text) + "|" + weekly[wpos].astype(str).str.upper()
            counts = weekly.groupby("_key").size()
            key = raw[name_col].map(norm_text) + "|" + raw[pos_col].astype(str).str.upper()
            out["games_played"] = key.map(counts).fillna(0).astype(float)
            out["games_source"] = "nflverse_week_rows_namepos"

    # If the release ever contains multiple summary rows for a player-season, aggregate defensively.
    out = out[out["position"].isin(POSITIONS)].copy()
    out["norm_name"] = out["outcome_name"].map(norm_text)

    # Standardized full PPR: 4pt pass TD, -2 INT, 1 PPR, -2 fumble lost, no yardage bonuses.
    out["ppr_points"] = (
        out["passing_yards"] * 0.04
        + out["passing_tds"] * 4
        - out["interceptions"] * 2
        + out["passing_2pt"] * 2
        + out["rushing_yards"] * 0.10
        + out["rushing_tds"] * 6
        + out["rushing_2pt"] * 2
        + out["receptions"]
        + out["receiving_yards"] * 0.10
        + out["receiving_tds"] * 6
        + out["receiving_2pt"] * 2
        + out["special_teams_tds"] * 6
        - out["fumbles_lost"] * 2
    )
    out["ppr_ppg"] = np.where(out["games_played"] > 0, out["ppr_points"] / out["games_played"], np.nan)
    out["source_ppr_delta"] = out["ppr_points"] - out["source_ppr_points"]

    # Deduplicate if necessary, preferring stable ID then normalized name+position.
    key = out["gsis_id"].fillna("")
    out["_dedupe"] = np.where(key.ne(""), "id:" + key, "np:" + out["norm_name"] + "|" + out["position"])
    if out["_dedupe"].duplicated().any():
        sum_cols = [c for c in stat_aliases] + ["fumbles_lost", "ppr_points", "source_ppr_points"]
        agg = {c: "sum" for c in sum_cols if c in out.columns}
        agg.update({
            "season": "first", "gsis_id": "first", "outcome_name": "first", "position": "first",
            "outcome_team": "last", "games_played": "max", "games_source": "first", "norm_name": "first",
        })
        out = out.groupby("_dedupe", as_index=False).agg(agg)
        out["ppr_ppg"] = np.where(out["games_played"] > 0, out["ppr_points"] / out["games_played"], np.nan)
        out["source_ppr_delta"] = out["ppr_points"] - out["source_ppr_points"]
    out.drop(columns=["_dedupe"], errors="ignore", inplace=True)
    return out


def load_ecr_and_crosswalk() -> tuple[dict[int, pd.DataFrame], pd.DataFrame]:
    ecr = pd.read_parquet(io.BytesIO(get_bytes(ECR_URL)))
    ids = pd.read_csv(io.BytesIO(get_bytes(PLAYERIDS_URL)), dtype=str, low_memory=False)

    ecr["scrape_date"] = pd.to_datetime(ecr["scrape_date"], errors="coerce")
    page_col = first_existing(ecr, ["fp_page", "page"])
    type_col = first_existing(ecr, ["ecr_type"])
    fp_id_col = first_existing(ecr, ["id", "fp_id", "fantasypros_id"])
    name_col = first_existing(ecr, ["player", "player_name", "name"])
    pos_col = first_existing(ecr, ["pos", "position"])
    team_col = first_existing(ecr, ["team"])
    if not all([type_col, fp_id_col, name_col, pos_col]):
        raise RuntimeError(f"FantasyPros ECR archive schema changed: {list(ecr.columns)}")

    fp_map_col = first_existing(ids, ["fantasypros_id"])
    gsis_col = first_existing(ids, ["gsis_id"])
    if not fp_map_col or not gsis_col:
        raise RuntimeError(f"DynastyProcess player ID crosswalk schema changed: {list(ids.columns)}")
    idmap = ids[[fp_map_col, gsis_col]].copy()
    idmap.columns = ["fp_id", "gsis_id"]
    idmap["fp_id"] = idmap["fp_id"].map(clean_id)
    idmap["gsis_id"] = idmap["gsis_id"].map(clean_id)
    idmap = idmap.dropna(subset=["fp_id"]).drop_duplicates("fp_id")

    result: dict[int, pd.DataFrame] = {}
    for season in SEASONS:
        x = ecr.copy()
        x = x[x["scrape_date"].dt.year.eq(season)]
        x = x[x[type_col].astype(str).str.lower().eq("ro")]
        x = x[x["scrape_date"].dt.date < KICKOFF[season]]
        if page_col:
            pp = x[page_col].astype(str).str.lower()
            preferred = x[pp.str.contains("ppr-cheatsheets", na=False)]
            if not preferred.empty:
                x = preferred
        if x.empty:
            raise RuntimeError(f"No leak-safe redraft PPR ECR rows found for {season}")
        snapshot = x["scrape_date"].max()
        x = x[x["scrape_date"].eq(snapshot)].copy()
        out = pd.DataFrame({
            "season": season,
            "fp_id": x[fp_id_col].map(clean_id),
            "ecr_name": x[name_col].astype(str),
            "position": x[pos_col].astype(str).str.upper().str.strip(),
            "ecr_team": x[team_col].astype(str).replace({"nan": np.nan}) if team_col else np.nan,
            "fp_ecr": pd.to_numeric(x[first_existing(x, ["ecr"])], errors="coerce"),
            "fp_ecr_sd": pd.to_numeric(x[first_existing(x, ["sd"])], errors="coerce") if first_existing(x, ["sd"]) else np.nan,
            "fp_ecr_best": pd.to_numeric(x[first_existing(x, ["best"])], errors="coerce") if first_existing(x, ["best"]) else np.nan,
            "fp_ecr_worst": pd.to_numeric(x[first_existing(x, ["worst"])], errors="coerce") if first_existing(x, ["worst"]) else np.nan,
            "fp_ecr_snapshot_date": snapshot.date().isoformat(),
        })
        out = out[out["position"].isin(POSITIONS)].copy()
        out["norm_name"] = out["ecr_name"].map(norm_text)
        out = out.merge(idmap, on="fp_id", how="left")
        out = out.sort_values(["fp_ecr", "fp_id"], na_position="last").drop_duplicates(["norm_name", "position"], keep="first")
        result[season] = out.reset_index(drop=True)
    return result, idmap


def load_ffc(season: int) -> tuple[pd.DataFrame, dict]:
    params = {"teams": 12, "year": season}
    r = SESSION.get(FFC_URL, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") != "Success" or not payload.get("players"):
        raise RuntimeError(f"FFC returned no PPR ADP for {season}: {payload}")
    df = pd.DataFrame(payload["players"])
    meta = payload.get("meta", {})
    out = pd.DataFrame({
        "season": season,
        "ffc_player_id": df[first_existing(df, ["player_id", "id"])].map(clean_id),
        "ffc_name": df[first_existing(df, ["name", "player_name"])].astype(str),
        "position": df[first_existing(df, ["position", "pos"])].astype(str).str.upper().str.strip(),
        "ffc_team": df[first_existing(df, ["team"])].astype(str).replace({"nan": np.nan}) if first_existing(df, ["team"]) else np.nan,
        "ffc_adp": pd.to_numeric(df[first_existing(df, ["adp"])], errors="coerce"),
        "ffc_adp_formatted": df[first_existing(df, ["adp_formatted"])].astype(str) if first_existing(df, ["adp_formatted"]) else np.nan,
        "ffc_stdev": pd.to_numeric(df[first_existing(df, ["stdev"])], errors="coerce") if first_existing(df, ["stdev"]) else np.nan,
        "ffc_high": pd.to_numeric(df[first_existing(df, ["high"])], errors="coerce") if first_existing(df, ["high"]) else np.nan,
        "ffc_low": pd.to_numeric(df[first_existing(df, ["low"])], errors="coerce") if first_existing(df, ["low"]) else np.nan,
        "ffc_times_drafted": pd.to_numeric(df[first_existing(df, ["times_drafted"])], errors="coerce") if first_existing(df, ["times_drafted"]) else np.nan,
        "ffc_teams": 12,
        "ffc_total_drafts": meta.get("total_drafts"),
        "ffc_window_start": meta.get("start_date"),
        "ffc_window_end": meta.get("end_date"),
    })
    out = out[out["position"].isin(POSITIONS)].copy()
    out["norm_name"] = out["ffc_name"].map(norm_text)
    out = out.sort_values(["ffc_adp", "ffc_player_id"], na_position="last").drop_duplicates(["norm_name", "position"], keep="first")
    return out.reset_index(drop=True), meta


def fuzzy_unique(name: str, candidates: list[str], threshold: float = 94.0, min_gap: float = 4.0):
    if not name or not candidates:
        return None, None
    hits = process.extract(name, candidates, scorer=fuzz.ratio, limit=2)
    if not hits:
        return None, None
    best_name, best_score, _ = hits[0]
    second = hits[1][1] if len(hits) > 1 else 0.0
    if best_score >= threshold and best_score - second >= min_gap:
        return best_name, float(best_score)
    return None, float(best_score)


def merge_ffc_into_ecr(ecr: pd.DataFrame, ffc: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    qa: list[dict] = []
    e = ecr.copy()
    e["_key"] = e["norm_name"] + "|" + e["position"]
    f = ffc.copy()
    f["_key"] = f["norm_name"] + "|" + f["position"]
    f_by_key = {k: i for i, k in enumerate(f["_key"]) if k not in set(f.loc[f["_key"].duplicated(False), "_key"])}
    used_ffc: set[int] = set()
    rows = []

    for _, er in e.iterrows():
        rec = er.to_dict()
        key = er["_key"]
        fi = f_by_key.get(key)
        method = None
        score = None
        if fi is not None:
            method, score = "exact_name_position", 100.0
        else:
            pool = f[(f["position"] == er["position"]) & (~f.index.isin(used_ffc))]
            # Prefer same team when both sources publish it.
            if pd.notna(er.get("ecr_team")):
                same_team = pool[pool["ffc_team"].astype(str).eq(str(er.get("ecr_team")))]
                if not same_team.empty:
                    pool = same_team
            cand, fs = fuzzy_unique(er["norm_name"], pool["norm_name"].tolist())
            if cand is not None:
                fi = pool[pool["norm_name"].eq(cand)].index[0]
                method, score = "fuzzy_name_position", fs
        if fi is not None:
            fr = f.loc[fi]
            used_ffc.add(int(fi))
            for c in f.columns:
                if c not in {"season", "position", "norm_name", "_key"}:
                    rec[c] = fr[c]
        rec["ffc_match_method"] = method
        rec["ffc_match_score"] = score
        rows.append(rec)

    # FFC-only market rows.
    for fi, fr in f.loc[~f.index.isin(used_ffc)].iterrows():
        rec = {c: np.nan for c in e.columns}
        rec.update(fr.to_dict())
        rec["ecr_name"] = np.nan
        rec["fp_id"] = np.nan
        rec["gsis_id"] = np.nan
        rec["ffc_match_method"] = "ffc_only"
        rec["ffc_match_score"] = np.nan
        rows.append(rec)
        qa.append({"issue": "ffc_unmatched_to_ecr", "position": fr["position"], "player": fr["ffc_name"], "rank_or_adp": fr["ffc_adp"]})

    out = pd.DataFrame(rows).drop(columns=["_key"], errors="ignore")
    return out, qa


def attach_outcomes(market: pd.DataFrame, outcomes: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    qa: list[dict] = []
    outc = outcomes.copy().reset_index(drop=True)
    outc["_key"] = outc["norm_name"] + "|" + outc["position"]
    used: set[int] = set()
    id_map = {clean_id(v): i for i, v in enumerate(outc["gsis_id"]) if clean_id(v)}
    unique_keys = outc["_key"].value_counts()
    key_map = {k: i for i, k in enumerate(outc["_key"]) if unique_keys.get(k, 0) == 1}
    rows = []

    outcome_payload_cols = [c for c in outc.columns if c not in {"season", "position", "norm_name", "_key"}]
    for _, mr in market.iterrows():
        rec = mr.to_dict()
        oi = None
        method = None
        score = None
        gid = clean_id(mr.get("gsis_id"))
        if gid and gid in id_map:
            oi, method, score = id_map[gid], "fp_to_gsis_crosswalk", 100.0
        if oi is None:
            base_name = mr.get("ecr_name") if pd.notna(mr.get("ecr_name")) else mr.get("ffc_name")
            n = norm_text(base_name)
            key = n + "|" + str(mr.get("position"))
            if key in key_map:
                oi, method, score = key_map[key], "exact_name_position", 100.0
        if oi is None:
            pos_pool = outc[(outc["position"] == mr.get("position")) & (~outc.index.isin(used))]
            team = mr.get("ecr_team") if pd.notna(mr.get("ecr_team")) else mr.get("ffc_team")
            if pd.notna(team):
                same_team = pos_pool[pos_pool["outcome_team"].astype(str).eq(str(team))]
                if not same_team.empty:
                    pos_pool = same_team
            base_name = mr.get("ecr_name") if pd.notna(mr.get("ecr_name")) else mr.get("ffc_name")
            cand, fs = fuzzy_unique(norm_text(base_name), pos_pool["norm_name"].tolist(), threshold=95.0, min_gap=5.0)
            if cand is not None:
                oi = pos_pool[pos_pool["norm_name"].eq(cand)].index[0]
                method, score = "fuzzy_name_position", fs
        if oi is not None:
            used.add(int(oi))
            rr = outc.loc[oi]
            for c in outcome_payload_cols:
                # Preserve market-crosswalk gsis_id when present; otherwise fill from outcomes.
                if c == "gsis_id" and clean_id(rec.get("gsis_id")):
                    continue
                rec[c] = rr[c]
            rec["gsis_id"] = clean_id(rec.get("gsis_id")) or clean_id(rr.get("gsis_id"))
        else:
            # A preseason market player with no regular-season outcome is a real zero, not a missing row.
            for c in outcome_payload_cols:
                rec.setdefault(c, np.nan)
            for c in [
                "passing_yards", "passing_tds", "interceptions", "passing_2pt", "rushing_attempts",
                "rushing_yards", "rushing_tds", "rushing_2pt", "targets", "receptions",
                "receiving_yards", "receiving_tds", "receiving_2pt", "special_teams_tds", "fumbles_lost",
                "ppr_points",
            ]:
                rec[c] = 0.0
            rec["games_played"] = 0.0
            rec["ppr_ppg"] = np.nan
            qa.append({
                "issue": "market_player_no_outcome_match", "position": mr.get("position"),
                "player": mr.get("ecr_name") if pd.notna(mr.get("ecr_name")) else mr.get("ffc_name"),
                "rank_or_adp": mr.get("fp_ecr") if pd.notna(mr.get("fp_ecr")) else mr.get("ffc_adp"),
            })
        rec["outcome_match_method"] = method or "no_outcome_match_zero"
        rec["outcome_match_score"] = score
        rows.append(rec)

    # Outcome-only players retained for completeness, explicitly marked as having no preseason market row.
    for oi, rr in outc.loc[~outc.index.isin(used)].iterrows():
        rec = {c: np.nan for c in market.columns}
        rec.update(rr.drop(labels=["_key"], errors="ignore").to_dict())
        rec["outcome_match_method"] = "outcome_only"
        rec["outcome_match_score"] = np.nan
        rows.append(rec)

    return pd.DataFrame(rows), qa


def finalize_panel(df: pd.DataFrame, season: int) -> pd.DataFrame:
    x = df.copy()
    x["season"] = season
    x["player_name"] = x.get("ecr_name").combine_first(x.get("ffc_name")).combine_first(x.get("outcome_name"))
    x["preseason_team"] = x.get("ecr_team").combine_first(x.get("ffc_team")).combine_first(x.get("outcome_team"))
    x["gsis_id"] = x["gsis_id"].map(clean_id)
    x["fp_id"] = x["fp_id"].map(clean_id)
    x["ffc_player_id"] = x["ffc_player_id"].map(clean_id)
    x["canonical_player_id"] = x["gsis_id"]
    x.loc[x["canonical_player_id"].isna() & x["fp_id"].notna(), "canonical_player_id"] = "FP:" + x.loc[x["canonical_player_id"].isna() & x["fp_id"].notna(), "fp_id"]
    x.loc[x["canonical_player_id"].isna() & x["ffc_player_id"].notna(), "canonical_player_id"] = "FFC:" + x.loc[x["canonical_player_id"].isna() & x["ffc_player_id"].notna(), "ffc_player_id"]
    fallback = x["canonical_player_id"].isna()
    x.loc[fallback, "canonical_player_id"] = (
        "NAME:" + x.loc[fallback, "player_name"].map(norm_text) + "|" + x.loc[fallback, "position"].astype(str)
    )
    x["id_source"] = np.select(
        [x["gsis_id"].notna(), x["fp_id"].notna(), x["ffc_player_id"].notna()],
        ["GSIS", "FantasyPros", "FFC"],
        default="name_position",
    )
    x["draft_market_present"] = x["fp_ecr"].notna() | x["ffc_adp"].notna()
    x["position_finish"] = x.groupby("position")["ppr_points"].rank(method="min", ascending=False, na_option="bottom")
    x["position_finish"] = x["position_finish"].astype("Int64")

    # Reserved model fields. These remain intentionally empty in v0.1.
    reserved = [
        "age", "rookie_flag",
        "consensus_proj_points", "consensus_proj_pass_yards", "consensus_proj_pass_tds",
        "consensus_proj_rush_yards", "consensus_proj_rush_tds", "consensus_proj_receptions",
        "consensus_proj_rec_yards", "consensus_proj_rec_tds",
        "espn_rank", "espn_adp", "espn_adp_rank", "espn_snapshot_date",
        "sleeper_adp", "sleeper_adp_order", "sleeper_snapshot_date", "sleeper_source_state",
        "nffc_adp", "nffc_min_pick", "nffc_max_pick", "nffc_sample",
        "vegas_pass_yards", "vegas_pass_tds", "vegas_rush_yards", "vegas_rush_tds",
        "vegas_receptions", "vegas_rec_yards", "vegas_rec_tds", "vegas_snapshot_date",
        "team_win_total", "team_offense_market_score",
    ]
    for c in reserved:
        if c not in x.columns:
            x[c] = np.nan

    # Consistent ordering for the master file.
    front = [
        "season", "canonical_player_id", "gsis_id", "fp_id", "ffc_player_id", "id_source",
        "player_name", "position", "preseason_team", "draft_market_present",
        "games_played", "games_source", "ppr_points", "ppr_ppg", "position_finish",
        "passing_yards", "passing_tds", "interceptions", "passing_2pt",
        "rushing_attempts", "rushing_yards", "rushing_tds", "rushing_2pt",
        "targets", "receptions", "receiving_yards", "receiving_tds", "receiving_2pt",
        "special_teams_tds", "fumbles_lost", "source_ppr_points", "source_ppr_delta",
        "fp_ecr", "fp_ecr_sd", "fp_ecr_best", "fp_ecr_worst", "fp_ecr_snapshot_date",
        "ffc_adp", "ffc_adp_formatted", "ffc_stdev", "ffc_high", "ffc_low", "ffc_times_drafted",
        "ffc_teams", "ffc_total_drafts", "ffc_window_start", "ffc_window_end",
        "ffc_match_method", "ffc_match_score", "outcome_match_method", "outcome_match_score",
    ]
    ordered = front + [c for c in reserved if c not in front]
    passthrough = [c for c in x.columns if c not in ordered and c not in {"norm_name", "ecr_name", "ffc_name", "outcome_name", "ecr_team", "ffc_team", "outcome_team"}]
    x = x[[c for c in ordered + passthrough if c in x.columns]]
    return x.sort_values(["season", "position", "ppr_points", "player_name"], ascending=[True, True, False, True], na_position="last").reset_index(drop=True)


def build() -> None:
    build_started = now_utc()
    print(f"Build started {build_started}")
    ecr_by_year, _ = load_ecr_and_crosswalk()
    all_panels = []
    qa_rows: list[dict] = []
    source_rows: list[dict] = []

    for season in SEASONS:
        print(f"Building {season}...")
        outcomes = load_nflverse_outcomes(season)
        ffc, ffc_meta = load_ffc(season)
        ecr = ecr_by_year[season]
        market, qa1 = merge_ffc_into_ecr(ecr, ffc)
        merged, qa2 = attach_outcomes(market, outcomes)
        panel = finalize_panel(merged, season)
        all_panels.append(panel)
        for q in qa1 + qa2:
            q["season"] = season
            qa_rows.append(q)

        source_rows.extend([
            {
                "season": season, "source": "nflverse", "rows": int(len(outcomes)), "status": "ready",
                "snapshot_or_window": f"2020-2025 realized regular season; season={season}",
                "url": NFLVERSE_SUMMARY_URL.format(season=season),
            },
            {
                "season": season, "source": "FantasyPros ECR / DynastyProcess", "rows": int(len(ecr)), "status": "ready",
                "snapshot_or_window": str(ecr["fp_ecr_snapshot_date"].iloc[0]) if len(ecr) else None,
                "url": ECR_URL,
            },
            {
                "season": season, "source": "Fantasy Football Calculator PPR ADP", "rows": int(len(ffc)), "status": "ready",
                "snapshot_or_window": f"{ffc_meta.get('start_date')} to {ffc_meta.get('end_date')}",
                "url": f"{FFC_URL}?teams=12&year={season}",
            },
        ])

    master = pd.concat(all_panels, ignore_index=True, sort=False)
    qa = pd.DataFrame(qa_rows)
    sources = pd.DataFrame(source_rows)

    # Coverage QA.
    coverage = []
    for season, g in master.groupby("season"):
        draft_rel = g[g["draft_market_present"]]
        coverage.append({
            "season": int(season),
            "rows_total": int(len(g)),
            "rows_draft_market": int(len(draft_rel)),
            "rows_with_outcome": int((g["outcome_match_method"].notna() & ~g["outcome_match_method"].isin(["no_outcome_match_zero"])).sum()),
            "rows_with_ecr": int(g["fp_ecr"].notna().sum()),
            "rows_with_ffc": int(g["ffc_adp"].notna().sum()),
            "draft_market_with_gsis_id_pct": round(float(draft_rel["gsis_id"].notna().mean() * 100), 2) if len(draft_rel) else np.nan,
            "draft_market_outcome_match_pct": round(float((~draft_rel["outcome_match_method"].eq("no_outcome_match_zero")).mean() * 100), 2) if len(draft_rel) else np.nan,
            "ecr_top300_outcome_match_pct": round(float((~g[g["fp_ecr"].le(300)]["outcome_match_method"].eq("no_outcome_match_zero")).mean() * 100), 2) if len(g[g["fp_ecr"].le(300)]) else np.nan,
            "mean_abs_source_ppr_delta": round(float(g["source_ppr_delta"].abs().dropna().mean()), 4) if g["source_ppr_delta"].notna().any() else np.nan,
        })
    coverage_df = pd.DataFrame(coverage)

    # Duplicate identity checks.
    dupes = master[master.duplicated(["season", "canonical_player_id"], keep=False)].copy()
    if not dupes.empty:
        dupes["issue"] = "duplicate_canonical_player_id"
        qa = pd.concat([qa, dupes[["season", "issue", "player_name", "position", "canonical_player_id"]].rename(columns={"player_name": "player"})], ignore_index=True, sort=False)

    # Top-priority manual review queue only.
    review = master[
        ((master["fp_ecr"].le(300)) | (master["ffc_adp"].le(220)))
        & (master["draft_market_present"])
        & (
            master["outcome_match_method"].isin(["no_outcome_match_zero", "fuzzy_name_position"])
            | master["ffc_match_method"].isin(["ffc_only", "fuzzy_name_position"])
        )
    ].copy()
    review_cols = [
        "season", "player_name", "position", "preseason_team", "fp_ecr", "ffc_adp", "gsis_id",
        "ffc_match_method", "ffc_match_score", "outcome_match_method", "outcome_match_score",
        "games_played", "ppr_points",
    ]
    review = review[review_cols].sort_values(["season", "fp_ecr", "ffc_adp"], na_position="last")

    # Hard integrity checks. We flag rather than silently edit.
    integrity = {
        "duplicate_season_canonical_ids": int(master.duplicated(["season", "canonical_player_id"]).sum()),
        "null_player_names": int(master["player_name"].isna().sum()),
        "invalid_positions": int((~master["position"].isin(POSITIONS)).sum()),
        "negative_games": int((master["games_played"].fillna(0) < 0).sum()),
        "build_started_utc": build_started,
        "build_finished_utc": now_utc(),
    }

    master_path = OUT_DIR / "master_player_season_panel_2020_2025_v0_1.csv"
    master.to_csv(master_path, index=False)
    coverage_df.to_csv(OUT_DIR / "panel_coverage_qa.csv", index=False)
    review.to_csv(OUT_DIR / "panel_manual_review.csv", index=False)
    qa.to_csv(OUT_DIR / "panel_match_qa.csv", index=False)
    sources.to_csv(OUT_DIR / "source_snapshots.csv", index=False)
    (OUT_DIR / "build_integrity.json").write_text(json.dumps(integrity, indent=2))

    dictionary = pd.DataFrame([
        {"field": c, "dtype": str(master[c].dtype), "non_null": int(master[c].notna().sum())}
        for c in master.columns
    ])
    dictionary.to_csv(OUT_DIR / "data_dictionary.csv", index=False)

    manifest = {
        "version": "v0.1",
        "seasons": SEASONS,
        "positions": sorted(POSITIONS),
        "scoring": {
            "passing_yards": 0.04, "passing_td": 4, "interception": -2,
            "rushing_yards": 0.1, "rushing_td": 6,
            "reception": 1, "receiving_yards": 0.1, "receiving_td": 6,
            "two_point_conversion": 2, "special_teams_td": 6, "fumble_lost": -2,
            "bonuses": "none",
        },
        "universe": "union of FantasyPros preseason ECR, FFC preseason PPR ADP, and realized nflverse QB/RB/WR/TE outcomes",
        "future_nullable_layers": ["consensus projections", "ESPN rank/ADP", "Sleeper ADP", "NFFC", "Vegas", "team betting environment"],
        "integrity": integrity,
    }
    (OUT_DIR / "build_manifest.json").write_text(json.dumps(manifest, indent=2))

    print("\nCoverage QA")
    print(coverage_df.to_string(index=False))
    print("\nIntegrity")
    print(json.dumps(integrity, indent=2))
    print(f"\nWrote {len(master):,} player-season rows to {master_path}")


if __name__ == "__main__":
    build()
