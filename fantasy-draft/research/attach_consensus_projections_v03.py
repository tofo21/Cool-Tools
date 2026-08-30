from __future__ import annotations

import io
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from rapidfuzz import fuzz, process

SEASONS = list(range(2020, 2026))
POSITIONS = ["QB", "RB", "WR", "TE"]
OUT_DIR = Path(__file__).resolve().parent / "output"
INFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_2.csv"
OUTFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_3.csv"

URL_TMPL = "https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft&year={season}&scoring=PPR"

# Season-specific players used only to verify that FantasyPros is actually serving
# the requested historical preseason page instead of silently falling back to current data.
SEASON_MARKERS = {
    2020: "Drew Brees",
    2021: "Ben Roethlisberger",
    2022: "Tom Brady",
    2023: "Anthony Richardson",
    2024: "Caleb Williams",
    2025: "Cam Ward",
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"
})


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ALIASES = {
    "gabe davis": "gabriel davis",
    "kenny gainwell": "kenneth gainwell",
    "chig okonkwo": "chigoziem okonkwo",
    "hollywood brown": "marquise brown",
    "robbie chosen": "robby anderson",
    "chosen anderson": "robby anderson",
    "william fuller": "will fuller",
    "d j chark": "dj chark",
    "d k metcalf": "dk metcalf",
}


def canon_norm(value) -> str:
    n = norm_text(value)
    return ALIASES.get(n, n)


def flatten_col(col) -> str:
    if isinstance(col, tuple):
        parts = [str(x).strip() for x in col if str(x).strip() and not str(x).startswith("Unnamed")]
        return "_".join(parts).upper()
    return str(col).strip().upper()


def to_num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.replace("—", "", regex=False), errors="coerce")


def pick_col(df: pd.DataFrame, *tokens: str):
    tokens = tuple(t.upper() for t in tokens)
    for c in df.columns:
        uc = str(c).upper()
        if all(t in uc for t in tokens):
            return c
    return None


def parse_position(season: int, pos: str) -> pd.DataFrame:
    url = URL_TMPL.format(pos=pos.lower(), season=season)
    r = SESSION.get(url, timeout=90)
    r.raise_for_status()
    html = r.text
    tables = pd.read_html(io.StringIO(html))
    candidates = []
    for t in tables:
        t = t.copy()
        t.columns = [flatten_col(c) for c in t.columns]
        if any("PLAYER" in c for c in t.columns) and any("FPTS" in c for c in t.columns):
            candidates.append(t)
    if not candidates:
        raise RuntimeError(f"FantasyPros {season} {pos}: projection table not found at {url}")
    raw = max(candidates, key=len)

    player_col = pick_col(raw, "PLAYER")
    fpts_col = pick_col(raw, "FPTS")
    if player_col is None or fpts_col is None:
        raise RuntimeError(f"FantasyPros {season} {pos}: missing player/FPTS columns: {list(raw.columns)}")

    out = pd.DataFrame()
    out["source_name"] = raw[player_col].astype(str).str.strip()
    # FantasyPros appends team abbreviations in rendered table text.
    out["source_name"] = out["source_name"].str.replace(r"\s+[A-Z]{2,3}$", "", regex=True).str.strip()
    out["position"] = pos
    out["consensus_proj_points"] = to_num(raw[fpts_col])

    mappings = {
        "consensus_proj_pass_yards": [("PASS", "YDS")],
        "consensus_proj_pass_tds": [("PASS", "TD")],
        "consensus_proj_rush_yards": [("RUSH", "YDS")],
        "consensus_proj_rush_tds": [("RUSH", "TD")],
        "consensus_proj_receptions": [("REC", "REC"), ("RECEIVING", "REC")],
        "consensus_proj_rec_yards": [("REC", "YDS"), ("RECEIVING", "YDS")],
        "consensus_proj_rec_tds": [("REC", "TD"), ("RECEIVING", "TD")],
    }
    for target, options in mappings.items():
        col = None
        for toks in options:
            col = pick_col(raw, *toks)
            if col is not None:
                break
        out[target] = to_num(raw[col]) if col is not None else np.nan

    out["norm_name"] = out["source_name"].map(canon_norm)
    out = out[out["source_name"].ne("") & out["consensus_proj_points"].notna()].copy()
    out = out.drop_duplicates(["norm_name", "position"], keep="first")
    out["consensus_proj_source_url"] = url
    out["consensus_proj_source_state"] = "fantasypros_historical_preseason_consensus"
    return out.reset_index(drop=True)


def attach(panel: pd.DataFrame, source: pd.DataFrame, season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = panel.copy()
    s = source.reset_index(drop=True).copy()
    exact = {f"{r.norm_name}|{r.position}": i for i, r in s.iterrows()}
    used: set[int] = set()
    logs = []
    fields = [
        "consensus_proj_points",
        "consensus_proj_pass_yards",
        "consensus_proj_pass_tds",
        "consensus_proj_rush_yards",
        "consensus_proj_rush_tds",
        "consensus_proj_receptions",
        "consensus_proj_rec_yards",
        "consensus_proj_rec_tds",
        "consensus_proj_source_url",
        "consensus_proj_source_state",
    ]

    for idx in x.index[x["season"].eq(season)]:
        pname = canon_norm(x.at[idx, "player_name"])
        pos = str(x.at[idx, "position"])
        key = f"{pname}|{pos}"
        si = exact.get(key)
        method, score = None, None
        if si is not None:
            method, score = "exact", 100.0
        else:
            pool = s.loc[~s.index.isin(used)]
            pool = pool[pool["position"].eq(pos)]
            hits = process.extract(pname, pool["norm_name"].tolist(), scorer=fuzz.ratio, limit=2)
            if hits:
                second = hits[1][1] if len(hits) > 1 else 0
                if hits[0][1] >= 95 and hits[0][1] - second >= 5:
                    si = pool[pool["norm_name"].eq(hits[0][0])].index[0]
                    method, score = "fuzzy", float(hits[0][1])
        if si is None:
            continue
        used.add(int(si))
        for f in fields:
            x.at[idx, f] = s.at[si, f]
        logs.append({
            "season": season,
            "canonical_player_id": x.at[idx, "canonical_player_id"],
            "player_name": x.at[idx, "player_name"],
            "position": pos,
            "source_name": s.at[si, "source_name"],
            "match_method": method,
            "match_score": score,
        })
    return x, pd.DataFrame(logs)


def build() -> None:
    panel = pd.read_csv(INFILE, low_memory=False)
    for c in ["consensus_proj_source_url", "consensus_proj_source_state"]:
        panel[c] = pd.Series([None] * len(panel), dtype="object")

    all_matches = []
    coverage_rows = []
    raw_source_rows = []

    for season in SEASONS:
        print(f"Consensus projection layer {season}")
        pieces = [parse_position(season, pos) for pos in POSITIONS]
        source = pd.concat(pieces, ignore_index=True)
        raw_source_rows.append(source.assign(season=season))

        marker = canon_norm(SEASON_MARKERS[season])
        if marker not in set(source["norm_name"]):
            raise RuntimeError(
                f"FantasyPros {season}: historical validation marker {SEASON_MARKERS[season]!r} not found; refusing to accept possible current-page fallback"
            )
        if len(source) < 180:
            raise RuntimeError(f"FantasyPros {season}: only {len(source)} projection rows parsed")

        panel, matches = attach(panel, source, season)
        all_matches.append(matches)

        mask = panel["season"].eq(season)
        draft = mask & panel["draft_market_present"].fillna(False).astype(bool)
        ecr300 = mask & panel["fp_ecr"].notna() & panel["fp_ecr"].le(300)
        coverage_rows.append({
            "season": season,
            "source_rows": len(source),
            "panel_rows": int(mask.sum()),
            "draft_market_rows": int(draft.sum()),
            "draft_market_projection_coverage_pct": round(100 * panel.loc[draft, "consensus_proj_points"].notna().mean(), 2) if draft.any() else np.nan,
            "ecr_top300_rows": int(ecr300.sum()),
            "ecr_top300_projection_coverage_pct": round(100 * panel.loc[ecr300, "consensus_proj_points"].notna().mean(), 2) if ecr300.any() else np.nan,
            "historical_marker_validation": "PASS",
        })

    panel.to_csv(OUTFILE, index=False)
    pd.concat(all_matches, ignore_index=True).to_csv(OUT_DIR / "consensus_projection_match_qa_v03.csv", index=False)
    pd.DataFrame(coverage_rows).to_csv(OUT_DIR / "consensus_projection_coverage_qa_v03.csv", index=False)
    pd.concat(raw_source_rows, ignore_index=True).to_csv(OUT_DIR / "consensus_projection_source_snapshot_v03.csv", index=False)

    missing = panel[
        panel["draft_market_present"].fillna(False).astype(bool) & panel["consensus_proj_points"].isna()
    ][["season", "canonical_player_id", "player_name", "position", "fp_ecr", "ffc_adp", "espn_rank", "sleeper_adp_order"]]
    missing.to_csv(OUT_DIR / "consensus_projection_manual_review_v03.csv", index=False)

    cov = pd.DataFrame(coverage_rows)
    print(cov.to_string(index=False))
    print(f"Wrote {OUTFILE} with {len(panel):,} rows; projection gaps in draft-market universe={len(missing):,}")


if __name__ == "__main__":
    build()
