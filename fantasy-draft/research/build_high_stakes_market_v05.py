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

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
INFILE = OUT / "master_player_season_panel_2020_2025_v0_4.csv"
OUTFILE = OUT / "master_player_season_panel_2020_2025_v0_5.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"

SOURCES = [
    {
        "season": 2021,
        "market_family": "ffpc_redraft",
        "contest": "FFPC/FPC normal season-long",
        "scoring_format": "PPR with 1.5 PPR for TE",
        "te_premium": 0.5,
        "league_type": "managed_redraft",
        "snapshot_date": "2021-09-02",
        "source_state": "preserved_full_table",
        "source_url": "https://www.footballguys.com/article/2021-fpc-adp07",
        "attach_to_panel": True,
        "notes": "Full public Footballguys FFPC/FPC season-long table; high-stakes format differs from standard PPR because TEs receive 1.5 PPR.",
    },
    {
        "season": 2022,
        "market_family": "ffpc_redraft",
        "contest": "FFPC/FPC normal season-long",
        "scoring_format": "PPR with 1.5 PPR for TE",
        "te_premium": 0.5,
        "league_type": "managed_redraft",
        "snapshot_date": "2022-06-25",
        "source_state": "preserved_full_table_early",
        "source_url": "https://www.footballguys.com/article/2022-fpc-adp04",
        "attach_to_panel": True,
        "notes": "Full public Footballguys FFPC/FPC season-long table, but early preseason; date must remain a model feature/caveat.",
    },
    {
        "season": 2023,
        "market_family": "ffpc_redraft",
        "contest": "FFPC normal season-long",
        "scoring_format": "PPR with 1.5 PPR for TE",
        "te_premium": 0.5,
        "league_type": "managed_redraft",
        "snapshot_date": "2023-08-01",
        "source_state": "preserved_full_table",
        "source_url": "https://www.footballguys.com/article/2023-ffpc-adp12",
        "attach_to_panel": True,
        "notes": "Full public Footballguys FFPC season-long table; approximately five weeks before kickoff.",
    },
    {
        "season": 2024,
        "market_family": "nffc",
        "contest": "NFFC recent drafts, generic multi-contest label",
        "scoring_format": "source not normalized to one contest",
        "te_premium": np.nan,
        "league_type": "high_stakes_mixed_or_unspecified",
        "snapshot_date": "2024-05-23",
        "source_state": "preserved_ordinal_early_generic",
        "source_url": "https://www.footballguys.com/article/2024-nffc-average-draft-position-adp-02",
        "attach_to_panel": True,
        "notes": "Public top-50 ordinal NFFC board. Continuous ADP is not exposed. Early and generic across NFFC contests, so never coerce rank into decimal ADP.",
    },
    {
        "season": 2025,
        "market_family": "nffc",
        "contest": "NFFC recent high-stakes drafts, generic multi-contest label",
        "scoring_format": "source not normalized to one contest",
        "te_premium": np.nan,
        "league_type": "high_stakes_mixed_or_unspecified",
        "snapshot_date": "2025-05-30",
        "source_state": "preserved_ordinal_early_generic",
        "source_url": "https://www.footballguys.com/article/2025-nffc-adp-movement-high-stakes-01",
        "attach_to_panel": True,
        "notes": "Public ordinal NFFC movement board. Rank is the source's current ADP order, not a continuous average-pick value. Early and generic across contests.",
    },
]

NFFC_DIRECT_AUDIT = {
    "source_url": "https://nfc.shgn.com/adp/football",
    "endpoint": "https://nfc.shgn.com/adp.data.php",
    "audit_date": "2026-08-30",
    "result": "Current 2026 board available; valid historical 2020-2025 preseason windows returned No ADP Information Available.",
}


def norm_text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [" ".join(str(x) for x in c if str(x) != "nan").strip() for c in out.columns]
    else:
        out.columns = [str(c).strip() for c in out.columns]
    return out


def fetch_table(source: dict) -> pd.DataFrame:
    r = requests.get(source["source_url"], headers={"User-Agent": UA}, timeout=45)
    r.raise_for_status()
    tables = [flatten_columns(t) for t in pd.read_html(io.StringIO(r.text))]
    candidates = []
    for t in tables:
        cols = {norm_text(c): c for c in t.columns}
        has_player = any(k == "player" or k.endswith(" player") for k in cols)
        has_rank = any(k == "rank" or k.startswith("rank ") for k in cols)
        has_adp = any(k == "adp" or k.endswith(" adp") for k in cols)
        if has_player and (has_rank or has_adp):
            candidates.append(t)
    if not candidates:
        raise RuntimeError(f"No player ADP/rank table found for {source['source_url']}")
    # Prefer the largest table, which avoids navigation/summary tables.
    table = max(candidates, key=lambda x: (len(x), len(x.columns)))
    table.to_csv(OUT / f"high_stakes_raw_{source['season']}_{source['market_family']}.csv", index=False)
    return table


def pick_col(df: pd.DataFrame, *names: str) -> str | None:
    mapped = {norm_text(c): c for c in df.columns}
    for name in names:
        n = norm_text(name)
        if n in mapped:
            return mapped[n]
    return None


def to_number(value):
    if pd.isna(value):
        return np.nan
    s = str(value).strip().replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else np.nan


def standardize(table: pd.DataFrame, source: dict) -> pd.DataFrame:
    player_col = pick_col(table, "Player")
    if player_col is None:
        raise RuntimeError("Missing Player column")
    position_col = pick_col(table, "Pos", "Position")
    team_col = pick_col(table, "Team")
    rank_col = pick_col(table, "Rank")
    prior_col = pick_col(table, "LW", "Last Wk", "Prior")
    adp_col = pick_col(table, "ADP")
    high_col = pick_col(table, "High")
    low_col = pick_col(table, "Low")
    posrank_col = pick_col(table, "PosRnk")

    rows = []
    for _, r in table.iterrows():
        player = str(r[player_col]).strip()
        if not player or player.lower() in {"nan", "player"}:
            continue
        pos = str(r[position_col]).strip().upper() if position_col else ""
        # 2025 NFFC encodes positional rank as WR1/RB1 etc; recover position.
        if not pos and posrank_col:
            m = re.match(r"([A-Za-z]+)", str(r[posrank_col]).strip())
            pos = m.group(1).upper() if m else ""
        if pos not in {"QB", "RB", "WR", "TE"}:
            continue
        rows.append({
            "season": source["season"],
            "market_family": source["market_family"],
            "contest": source["contest"],
            "scoring_format": source["scoring_format"],
            "te_premium": source["te_premium"],
            "league_type": source["league_type"],
            "snapshot_date": source["snapshot_date"],
            "source_state": source["source_state"],
            "source_url": source["source_url"],
            "player_name": player,
            "position": pos,
            "source_team": str(r[team_col]).strip() if team_col else "",
            "adp": to_number(r[adp_col]) if adp_col else np.nan,
            "rank": to_number(r[rank_col]) if rank_col else np.nan,
            "prior_rank": to_number(r[prior_col]) if prior_col else np.nan,
            "min_pick": to_number(r[high_col]) if high_col else np.nan,
            "max_pick": to_number(r[low_col]) if low_col else np.nan,
            "pick_count": np.nan,
            "notes": source["notes"],
        })
    return pd.DataFrame(rows)


def attach_family(panel: pd.DataFrame, obs: pd.DataFrame, family: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    fam = obs[obs["market_family"].eq(family)].copy()
    if fam.empty:
        return panel, pd.DataFrame()
    prefix = "ffpc" if family == "ffpc_redraft" else "nffc"
    fields = {
        f"{prefix}_adp": "adp",
        f"{prefix}_rank": "rank",
        f"{prefix}_prior_rank": "prior_rank",
        f"{prefix}_min_pick": "min_pick",
        f"{prefix}_max_pick": "max_pick",
        f"{prefix}_snapshot_date": "snapshot_date",
        f"{prefix}_source_state": "source_state",
        f"{prefix}_source_url": "source_url",
        f"{prefix}_contest": "contest",
        f"{prefix}_scoring_format": "scoring_format",
    }
    for outcol in fields:
        if outcol not in panel.columns:
            panel[outcol] = pd.Series([None] * len(panel), dtype="object") if outcol.endswith(("date", "state", "url", "contest", "format")) else np.nan

    qa_rows = []
    for season in sorted(fam["season"].unique()):
        src = fam[fam["season"].eq(season)].copy()
        pan_idx = panel.index[panel["season"].eq(season)].tolist()
        pan = panel.loc[pan_idx, ["player_name", "position"]].copy()
        pan["_key"] = pan["player_name"].map(norm_text) + "|" + pan["position"].astype(str).str.upper()
        key_to_idx = {k: i for k, i in zip(pan["_key"], pan_idx)}
        candidate_by_pos = {}
        for pos in ["QB", "RB", "WR", "TE"]:
            sub = pan[pan["position"].eq(pos)]
            candidate_by_pos[pos] = list(zip(sub["_key"].tolist(), sub.index.tolist()))

        for _, r in src.iterrows():
            key = norm_text(r["player_name"]) + "|" + r["position"]
            target = key_to_idx.get(key)
            method = "exact"
            score = 100.0
            if target is None:
                candidates = candidate_by_pos.get(r["position"], [])
                if candidates:
                    labels = [x[0] for x in candidates]
                    match = process.extract(norm_text(r["player_name"]) + "|" + r["position"], labels, scorer=fuzz.ratio, limit=2)
                    if match and match[0][1] >= 94 and (len(match) == 1 or match[0][1] - match[1][1] >= 4):
                        target = candidates[labels.index(match[0][0])][1]
                        method = "fuzzy"
                        score = float(match[0][1])
            qa_rows.append({
                "season": season,
                "market_family": family,
                "source_player": r["player_name"],
                "position": r["position"],
                "matched": target is not None,
                "match_method": method if target is not None else "unmatched",
                "match_score": score if target is not None else np.nan,
                "panel_player": panel.at[target, "player_name"] if target is not None else "",
            })
            if target is not None:
                for outcol, srccol in fields.items():
                    panel.at[target, outcol] = r[srccol]
    return panel, pd.DataFrame(qa_rows)


def main() -> None:
    panel = pd.read_csv(INFILE, low_memory=False)
    observations = []
    manifest = []

    for source in SOURCES:
        print(f"Fetching {source['season']} {source['market_family']} from {source['source_url']}")
        table = fetch_table(source)
        obs = standardize(table, source)
        if obs.empty:
            raise RuntimeError(f"No standardized rows for {source['season']} {source['market_family']}")
        observations.append(obs)
        manifest.append({
            **source,
            "source_rows": len(obs),
            "continuous_adp_available": bool(obs["adp"].notna().any()),
            "ordinal_rank_available": bool(obs["rank"].notna().any()),
        })
        print(f"  standardized rows={len(obs)} adp={obs['adp'].notna().sum()} rank={obs['rank'].notna().sum()}")

    all_obs = pd.concat(observations, ignore_index=True)
    all_obs.to_csv(OUT / "high_stakes_market_observations_v05.csv", index=False)

    # Add the direct NFFC endpoint audit to the manifest as a source-level finding.
    manifest.append({
        "season": "2020-2025 audit",
        "market_family": "nffc",
        "contest": "direct NFFC public ADP backend historical query",
        "scoring_format": "football",
        "te_premium": np.nan,
        "league_type": "historical endpoint audit",
        "snapshot_date": NFFC_DIRECT_AUDIT["audit_date"],
        "source_state": "direct_endpoint_no_historical_retention",
        "source_url": NFFC_DIRECT_AUDIT["source_url"],
        "attach_to_panel": False,
        "notes": NFFC_DIRECT_AUDIT["result"],
        "source_rows": 0,
        "continuous_adp_available": False,
        "ordinal_rank_available": False,
    })
    pd.DataFrame(manifest).to_csv(OUT / "high_stakes_source_manifest_v05.csv", index=False)

    qa_all = []
    panel, qa = attach_family(panel, all_obs, "ffpc_redraft")
    if not qa.empty: qa_all.append(qa)
    panel, qa = attach_family(panel, all_obs, "nffc")
    if not qa.empty: qa_all.append(qa)
    qa_df = pd.concat(qa_all, ignore_index=True) if qa_all else pd.DataFrame()
    qa_df.to_csv(OUT / "high_stakes_match_qa_v05.csv", index=False)

    coverage = []
    for season in range(2020, 2026):
        mask = panel["season"].eq(season)
        draft = mask & panel["draft_market_present"].fillna(False).astype(bool)
        row = {"season": season, "draft_market_rows": int(draft.sum())}
        for prefix in ["ffpc", "nffc"]:
            present = panel.loc[draft, f"{prefix}_adp"].notna() | panel.loc[draft, f"{prefix}_rank"].notna()
            row[f"{prefix}_coverage_pct"] = round(100 * present.mean(), 2) if len(present) else 0.0
            row[f"{prefix}_rows"] = int(present.sum())
        coverage.append(row)
    coverage_df = pd.DataFrame(coverage)
    coverage_df.to_csv(OUT / "high_stakes_coverage_qa_v05.csv", index=False)

    panel.to_csv(OUTFILE, index=False)
    print("\nCoverage")
    print(coverage_df.to_string(index=False))
    if not qa_df.empty:
        print("\nMatch QA")
        print(qa_df.groupby(["season", "market_family"])["matched"].agg(["count", "sum", "mean"]).to_string())
    print(f"Wrote {OUTFILE} rows={len(panel):,}")
    print("Source discipline: no unified high_stakes_adp column was created.")


if __name__ == "__main__":
    main()
