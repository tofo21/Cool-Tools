from __future__ import annotations

import io
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pypdf import PdfReader
from rapidfuzz import fuzz, process

SEASONS = list(range(2020, 2026))
POSITIONS = {"QB", "RB", "WR", "TE"}
OUT_DIR = Path(__file__).resolve().parent / "output"
INFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_1.csv"
OUTFILE = OUT_DIR / "master_player_season_panel_2020_2025_v0_2.csv"

ESPN_RANK_URLS = {
    2020: "https://g.espncdn.com/s/ffldraftkit/20/NFLDK2020_CS_PPR300.pdf",
    2021: "https://g.espncdn.com/s/ffldraftkit/21/NFLDK2021_CS_PPR300.pdf",
    2022: "https://g.espncdn.com/s/ffldraftkit/22/NFLDK2022_CS_PPR300.pdf",
    2023: "https://g.espncdn.com/s/ffldraftkit/23/NFL23_CS_PPR300.pdf?adddata=2023CS_PPR300",
    2024: "https://g.espncdn.com/s/ffldraftkit/24/NFL24_CS_PPR300.pdf?adddata=2024CS_PPR300",
    2025: "https://g.espncdn.com/s/ffldraftkit/25/NFL25_CS_PPR.pdf?adddata=2025CS_PPR",
}
ESPN_RANK_DATES = {
    2020: "2020-09-09", 2021: "2021-09-09", 2022: "2022-09-08",
    2023: "2023-09-01", 2024: "2024-09-05", 2025: "2025-09-02",
}
ESPN_ADP_DATES = {
    2020: "2020-09-09", 2021: "2021-09-07", 2022: "2022-09-07",
    2023: "2023-09-04", 2024: "2024-09-03", 2025: "2025-09-02",
}
SLEEPER_DATES = {
    2020: "2020-08", 2021: "2021-09-08", 2022: "2022-09-07",
    2023: "2023-09-05", 2024: "2024-09-03", 2025: "2025-09-02",
}
FP_PAGE = "https://www.fantasypros.com/nfl/adp/ppr-overall.php?year={season}"
FP_MIRRORS = {
    2020: "https://raw.githubusercontent.com/jughkoop/fantasy-football-adps/main/FantasyPros_2020_Overall_ADP_Rankings.csv",
    2021: "https://raw.githubusercontent.com/jughkoop/fantasy-football-adps/main/FantasyPros_2021_Overall_ADP_Rankings.csv",
    2022: "https://raw.githubusercontent.com/jughkoop/fantasy-football-adps/main/FantasyPros_2022_Overall_ADP_Rankings.csv",
    2023: "https://raw.githubusercontent.com/jughkoop/fantasy-football-adps/main/FantasyPros_2023_Overall_ADP_Rankings.csv",
    2024: "https://raw.githubusercontent.com/jughkoop/fantasy-football-adps/main/FantasyPros_2024_Overall_ADP_Rankings.csv",
    2025: "https://raw.githubusercontent.com/JoshPB21/fantasy-football-2025/main/FantasyPros_2025_Overall_ADP_Rankings.csv",
}
FANTASYDATA_2020 = {
    p: f"https://fantasydata.com/nfl/ppr-adp/{p.lower()}?season=2020" for p in POSITIONS
}

EXPECTED_ESPN_RANK_TOP5 = {
    2020: ["Christian McCaffrey", "Saquon Barkley", "Ezekiel Elliott", "Dalvin Cook", "Alvin Kamara"],
    2021: ["Christian McCaffrey", "Dalvin Cook", "Alvin Kamara", "Saquon Barkley", "Derrick Henry"],
    2022: ["Jonathan Taylor", "Christian McCaffrey", "Cooper Kupp", "Austin Ekeler", "Justin Jefferson"],
    2023: ["Justin Jefferson", "Ja'Marr Chase", "Austin Ekeler", "Christian McCaffrey", "Travis Kelce"],
    2024: ["Christian McCaffrey", "Bijan Robinson", "Breece Hall", "CeeDee Lamb", "Tyreek Hill"],
    2025: ["Ja'Marr Chase", "Bijan Robinson", "Justin Jefferson", "Saquon Barkley", "Jahmyr Gibbs"],
}
EXPECTED_ESPN_ADP_LEADER = {
    2020: "Christian McCaffrey", 2021: "Christian McCaffrey", 2022: "Jonathan Taylor",
    2023: "Justin Jefferson", 2024: "Christian McCaffrey", 2025: "Ja'Marr Chase",
}
EXPECTED_SLEEPER_LEADER = {
    2021: "Christian McCaffrey", 2022: "Jonathan Taylor", 2023: "Justin Jefferson",
    2024: "Christian McCaffrey", 2025: "Ja'Marr Chase",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36"})


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_bytes(url: str, timeout: int = 120) -> bytes:
    last = None
    for _ in range(3):
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
    return re.sub(r"\s+", " ", s).strip()


ALIASES = {
    "gabe davis": "gabriel davis", "kenny gainwell": "kenneth gainwell",
    "chig okonkwo": "chigoziem okonkwo", "hollywood brown": "marquise brown",
    "robbie chosen": "robby anderson", "chosen anderson": "robby anderson",
    "william fuller": "will fuller", "d j chark": "dj chark", "d k metcalf": "dk metcalf",
}


def canon_norm(value) -> str:
    n = norm_text(value)
    return ALIASES.get(n, n)


def parse_espn_pdf(season: int) -> pd.DataFrame:
    reader = PdfReader(io.BytesIO(get_bytes(ESPN_RANK_URLS[season])))
    text = " ".join((page.extract_text() or "") for page in reader.pages)
    flat = re.sub(r"\s+", " ", text)
    rows = []
    if season <= 2024:
        pat = re.compile(r"(?<!\d)(\d{1,3})\.\s+\((?:QB|RB|WR|TE|K|DST)\d+\)\s+(.+?),\s+(?:[A-Z]{2,3}|FA)\s+\$\d+")
        for m in pat.finditer(flat):
            rows.append({"espn_rank": int(m.group(1)), "source_name": m.group(2).strip()})
    else:
        pat = re.compile(r"(?<!\d)(\d{1,3})\.\s+\((\d{1,3})\)\s+(.+?),\s+(?:[A-Z]{2,3}|FA)\s+\$\d+")
        for m in pat.finditer(flat):
            rows.append({"espn_rank": int(m.group(2)), "source_name": m.group(3).strip()})
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError(f"ESPN {season}: PDF parser returned zero rows")
    out["norm_name"] = out["source_name"].map(canon_norm)
    out = out.sort_values("espn_rank").drop_duplicates("norm_name").drop_duplicates("espn_rank")
    return out.reset_index(drop=True)


def read_fp_archive(season: int) -> pd.DataFrame:
    raw = pd.read_csv(io.BytesIO(get_bytes(FP_MIRRORS[season])))
    needed = {"Player", "POS", "ESPN", "Sleeper"}
    missing = needed - set(raw.columns)
    if missing:
        raise RuntimeError(f"FantasyPros mirror {season} missing {sorted(missing)}")
    out = pd.DataFrame()
    out["source_name"] = raw["Player"].astype(str).str.strip()
    out["position"] = raw["POS"].astype(str).str.extract(r"^([A-Z]+)", expand=False)
    out["espn_adp_rank"] = pd.to_numeric(raw["ESPN"], errors="coerce")
    out["sleeper_adp_order"] = pd.to_numeric(raw["Sleeper"], errors="coerce")
    out["norm_name"] = out["source_name"].map(canon_norm)
    out = out[out["position"].isin(POSITIONS)].copy()
    return out.drop_duplicates(["norm_name", "position"]).reset_index(drop=True)


def read_fantasydata_2020() -> pd.DataFrame:
    pieces = []
    for pos, url in sorted(FANTASYDATA_2020.items()):
        html = get_bytes(url).decode("utf-8", errors="ignore")
        tables = pd.read_html(io.StringIO(html))
        chosen = None
        for t in tables:
            cols = [str(c).upper().strip() for c in t.columns]
            if "NAME" in cols and "ADP" in cols:
                t.columns = cols
                chosen = t
                break
        if chosen is None:
            raise RuntimeError(f"FantasyData 2020 {pos}: ADP table not found")
        d = pd.DataFrame({
            "source_name": chosen["NAME"].astype(str).str.strip(),
            "position": pos,
            "sleeper_adp": pd.to_numeric(chosen["ADP"], errors="coerce"),
        })
        d = d[d["sleeper_adp"].notna()].copy()
        pieces.append(d)
    out = pd.concat(pieces, ignore_index=True)
    out["norm_name"] = out["source_name"].map(canon_norm)
    out["sleeper_adp_order"] = out["sleeper_adp"].rank(method="min", ascending=True)
    return out.sort_values("sleeper_adp").drop_duplicates(["norm_name", "position"]).reset_index(drop=True)


def attach(panel: pd.DataFrame, source: pd.DataFrame, season: int, fields: list[str], source_type: str, use_position: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = panel.copy()
    s = source.reset_index(drop=True).copy()
    exact = {}
    for i, row in s.iterrows():
        key = row["norm_name"] + (f"|{row['position']}" if use_position else "")
        if key not in exact:
            exact[key] = i
    used = set()
    logs = []
    for idx in x.index[x["season"].eq(season)]:
        pname = canon_norm(x.at[idx, "player_name"])
        pos = str(x.at[idx, "position"])
        key = pname + (f"|{pos}" if use_position else "")
        si = exact.get(key)
        method, score = None, None
        if si is not None:
            method, score = "exact", 100.0
        else:
            pool = s.loc[~s.index.isin(used)].copy()
            if use_position:
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
            "season": season, "source_type": source_type, "canonical_player_id": x.at[idx, "canonical_player_id"],
            "player_name": x.at[idx, "player_name"], "position": pos, "source_name": s.at[si, "source_name"],
            "match_method": method, "match_score": score,
        })
    return x, pd.DataFrame(logs)


def names_by_value(df: pd.DataFrame, field: str, n: int = 5) -> list[str]:
    return df[df[field].notna()].sort_values(field).head(n)["source_name"].astype(str).tolist()


def nlist(xs) -> list[str]:
    return [canon_norm(x) for x in xs]


def build() -> None:
    panel = pd.read_csv(INFILE, low_memory=False)
    original_rows = len(panel)
    for c in [
        "espn_rank_snapshot_date", "espn_adp_snapshot_date", "espn_rank_source_url", "espn_adp_source_url",
        "espn_adp_retrieval_url", "espn_rank_adp_gap", "sleeper_source_url", "sleeper_retrieval_url",
        "sleeper_source_note",
    ]:
        if c not in panel.columns:
            panel[c] = np.nan

    match_logs, coverage, source_rows = [], [], []
    for season in SEASONS:
        print(f"Attaching platform layer {season}")
        ranks = parse_espn_pdf(season)
        fp = read_fp_archive(season)

        rank_top = names_by_value(ranks, "espn_rank", 5)
        if nlist(rank_top) != nlist(EXPECTED_ESPN_RANK_TOP5[season]):
            raise RuntimeError(f"ESPN {season} official rank top-5 failed: {rank_top}")
        espn_adp_leader = names_by_value(fp, "espn_adp_rank", 1)
        if not espn_adp_leader or canon_norm(espn_adp_leader[0]) != canon_norm(EXPECTED_ESPN_ADP_LEADER[season]):
            raise RuntimeError(f"ESPN {season} ADP leader failed: {espn_adp_leader}")
        if season >= 2021:
            sl_leader = names_by_value(fp, "sleeper_adp_order", 1)
            if not sl_leader or canon_norm(sl_leader[0]) != canon_norm(EXPECTED_SLEEPER_LEADER[season]):
                raise RuntimeError(f"Sleeper {season} ADP leader failed: {sl_leader}")

        panel, m1 = attach(panel, ranks, season, ["espn_rank"], "espn_official_ppr_rank", use_position=False)
        panel, m2 = attach(panel, fp, season, ["espn_adp_rank"], "fantasypros_espn_ppr_adp_ordinal", use_position=True)
        match_logs.extend([m1, m2])

        mask = panel["season"].eq(season)
        panel.loc[mask & panel["espn_rank"].notna(), "espn_rank_snapshot_date"] = ESPN_RANK_DATES[season]
        panel.loc[mask & panel["espn_rank"].notna(), "espn_snapshot_date"] = ESPN_RANK_DATES[season]
        panel.loc[mask & panel["espn_rank"].notna(), "espn_rank_source_url"] = ESPN_RANK_URLS[season]
        panel.loc[mask & panel["espn_adp_rank"].notna(), "espn_adp_snapshot_date"] = ESPN_ADP_DATES[season]
        panel.loc[mask & panel["espn_adp_rank"].notna(), "espn_adp_source_url"] = FP_PAGE.format(season=season)
        panel.loc[mask & panel["espn_adp_rank"].notna(), "espn_adp_retrieval_url"] = FP_MIRRORS[season]
        panel.loc[mask, "espn_rank_adp_gap"] = panel.loc[mask, "espn_adp_rank"] - panel.loc[mask, "espn_rank"]

        if season == 2020:
            sl = read_fantasydata_2020()
            panel, m3 = attach(panel, sl, season, ["sleeper_adp", "sleeper_adp_order"], "fantasydata_ppr_sleeper_reconstruction", use_position=True)
            panel.loc[mask & panel["sleeper_adp"].notna(), "sleeper_snapshot_date"] = SLEEPER_DATES[season]
            panel.loc[mask & panel["sleeper_adp"].notna(), "sleeper_source_state"] = "reconstructed"
            panel.loc[mask & panel["sleeper_adp"].notna(), "sleeper_source_url"] = "https://fantasydata.com/nfl/ppr-adp/qb?season=2020"
            panel.loc[mask & panel["sleeper_adp"].notna(), "sleeper_retrieval_url"] = "https://fantasydata.com/nfl/ppr-adp/{position}?season=2020"
            panel.loc[mask & panel["sleeper_adp"].notna(), "sleeper_source_note"] = "Medium-confidence reconstruction: contemporary evidence says Sleeper consumed FantasyData ADP; this is not relabeled as a direct Sleeper feed."
        else:
            panel, m3 = attach(panel, fp, season, ["sleeper_adp_order"], "fantasypros_sleeper_ppr_adp_ordinal", use_position=True)
            panel.loc[mask & panel["sleeper_adp_order"].notna(), "sleeper_snapshot_date"] = SLEEPER_DATES[season]
            panel.loc[mask & panel["sleeper_adp_order"].notna(), "sleeper_source_state"] = "preserved"
            panel.loc[mask & panel["sleeper_adp_order"].notna(), "sleeper_source_url"] = FP_PAGE.format(season=season)
            panel.loc[mask & panel["sleeper_adp_order"].notna(), "sleeper_retrieval_url"] = FP_MIRRORS[season]
            panel.loc[mask & panel["sleeper_adp_order"].notna(), "sleeper_source_note"] = "Late-preseason Sleeper-specific PPR ordinal ADP preserved by FantasyPros. Sleeper default board is ADP-driven, so this is one platform signal, not rank plus ADP as two votes."
        match_logs.append(m3)

        dm = panel.loc[mask & panel["draft_market_present"].fillna(False)].copy()
        coverage.append({
            "season": season, "panel_rows": int(mask.sum()), "draft_market_rows": len(dm),
            "espn_rank_source_rows": int(len(ranks)), "espn_adp_source_rows": int(fp["espn_adp_rank"].notna().sum()),
            "sleeper_source_rows": int((sl["sleeper_adp"].notna().sum() if season == 2020 else fp["sleeper_adp_order"].notna().sum())),
            "draft_market_espn_rank_coverage_pct": round(100 * dm["espn_rank"].notna().mean(), 2),
            "draft_market_espn_adp_coverage_pct": round(100 * dm["espn_adp_rank"].notna().mean(), 2),
            "draft_market_sleeper_coverage_pct": round(100 * (dm["sleeper_adp"].notna() | dm["sleeper_adp_order"].notna()).mean(), 2),
            "espn_official_rank_top5_validation": "PASS", "espn_adp_leader_validation": "PASS",
            "sleeper_leader_validation": "N/A_RECONSTRUCTED" if season == 2020 else "PASS",
        })
        source_rows.extend([
            {"season": season, "layer": "espn_rank", "measurement": "ordinal rank", "source_state": "direct_official", "snapshot_date": ESPN_RANK_DATES[season], "canonical_source_url": ESPN_RANK_URLS[season], "retrieval_url": ESPN_RANK_URLS[season]},
            {"season": season, "layer": "espn_adp_rank", "measurement": "ordinal historical ADP representation", "source_state": "preserved", "snapshot_date": ESPN_ADP_DATES[season], "canonical_source_url": FP_PAGE.format(season=season), "retrieval_url": FP_MIRRORS[season]},
            {"season": season, "layer": "sleeper_adp" if season == 2020 else "sleeper_adp_order", "measurement": "continuous PPR ADP reconstruction" if season == 2020 else "ordinal historical ADP representation", "source_state": "reconstructed" if season == 2020 else "preserved", "snapshot_date": SLEEPER_DATES[season], "canonical_source_url": "https://fantasydata.com/nfl/ppr-adp/qb?season=2020" if season == 2020 else FP_PAGE.format(season=season), "retrieval_url": "https://fantasydata.com/nfl/ppr-adp/{position}?season=2020" if season == 2020 else FP_MIRRORS[season]},
        ])

    if len(panel) != original_rows:
        raise RuntimeError(f"Row count changed: {original_rows} -> {len(panel)}")
    dup = int(panel.duplicated(["season", "canonical_player_id"]).sum())
    if dup:
        raise RuntimeError(f"Canonical duplicates introduced: {dup}")

    # Preserve missingness. Review only draft-market players lacking a platform value.
    review = panel[panel["draft_market_present"].fillna(False) & (
        panel["espn_rank"].isna() | panel["espn_adp_rank"].isna() |
        (panel["sleeper_adp"].isna() & panel["sleeper_adp_order"].isna())
    )][[
        "season", "canonical_player_id", "player_name", "position", "preseason_team", "fp_ecr", "ffc_adp",
        "espn_rank", "espn_adp_rank", "sleeper_adp", "sleeper_adp_order",
    ]].copy()
    review["missing_espn_rank"] = review["espn_rank"].isna()
    review["missing_espn_adp_rank"] = review["espn_adp_rank"].isna()
    review["missing_sleeper"] = review["sleeper_adp"].isna() & review["sleeper_adp_order"].isna()

    panel.to_csv(OUTFILE, index=False)
    pd.DataFrame(coverage).to_csv(OUT_DIR / "platform_layer_coverage_qa.csv", index=False)
    pd.concat([m for m in match_logs if not m.empty], ignore_index=True).to_csv(OUT_DIR / "platform_match_qa.csv", index=False)
    review.to_csv(OUT_DIR / "platform_manual_review.csv", index=False)
    pd.DataFrame(source_rows).to_csv(OUT_DIR / "platform_source_snapshots.csv", index=False)

    field_dictionary = pd.DataFrame([
        ["espn_rank", "Official ESPN PPR draft-kit default ranking", "ordinal", "direct official"],
        ["espn_rank_snapshot_date", "Date of ESPN official ranking artifact", "date string", "direct official"],
        ["espn_adp_rank", "ESPN-specific historical ADP ordinal preserved by FantasyPros", "ordinal", "preserved"],
        ["espn_adp", "Continuous ESPN average pick; intentionally blank for 2020-2025 where archive exposes ordinal only", "continuous", "missing preserved"],
        ["espn_rank_adp_gap", "ESPN ADP ordinal minus ESPN official rank", "picks", "derived"],
        ["sleeper_adp", "Continuous Sleeper ADP where available; populated in 2020 only as FantasyData reconstruction", "continuous", "reconstructed 2020"],
        ["sleeper_adp_order", "Ordinal draft-room order implied by Sleeper ADP", "ordinal", "reconstructed 2020 / preserved 2021-2025"],
        ["sleeper_source_state", "Provenance grade: reconstructed or preserved", "category", "provenance"],
    ], columns=["field", "definition", "measurement_type", "source_state"])
    field_dictionary.to_csv(OUT_DIR / "platform_field_dictionary_v02.csv", index=False)

    manifest = {
        "version": "0.2", "built_at_utc": now_utc(), "input": INFILE.name, "output": OUTFILE.name,
        "rows": len(panel), "duplicate_season_canonical_ids": dup, "platform_manual_review_rows": len(review),
        "locked_rules": [
            "ESPN official rank and ESPN realized ADP remain separate features.",
            "Historical ESPN ADP is stored as ordinal espn_adp_rank; no decimal ADP is invented.",
            "Sleeper default order is ADP-driven and is not double-counted as an independent rank feature.",
            "Sleeper 2020 is explicitly reconstructed from FantasyData PPR ADP and is lower confidence than 2021-2025.",
            "Rank and ADP snapshot dates are stored separately when they differ.",
        ],
    }
    (OUT_DIR / "platform_build_manifest_v02.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(pd.DataFrame(coverage).to_string(index=False))
    print(f"Wrote {OUTFILE} with {len(panel):,} rows; manual review {len(review):,}")


if __name__ == "__main__":
    build()
